#!/bin/bash
# Parte del simulacro que corre DENTRO del contenedor amazonlinux:2023 (ver simulacro.sh). Prepara los
# dobles (systemctl y aws anotan lo que se les pide; aws además falla, como sin permiso), un disco de
# bucle si se pide, ejecuta el arranque y, si termina bien, comprueba lo que debe dejar hecho.
# Variables: CON_DISCO=si|no. Imprime «rc=<código>» y una línea por comprobación.
set -u
printf '#!/bin/sh\necho "systemctl $*" >> /tmp/llamadas\nexit 0\n' > /usr/local/bin/systemctl
printf '#!/bin/sh\necho "aws $*" >> /tmp/llamadas\necho "AccessDenied (doble del simulacro)" >&2\nexit 254\n' > /usr/local/bin/aws
chmod +x /usr/local/bin/systemctl /usr/local/bin/aws
: > /tmp/llamadas

dnf install -y -q util-linux findutils >/dev/null 2>&1   # losetup y find (las comprobaciones los usan)
command -v find >/dev/null || { echo "rc=99 (el simulacro no pudo instalar findutils)"; exit 0; }
DISCOS=/dev/no-existe
if [ "$CON_DISCO" = si ]; then
  dd if=/dev/zero of=/disco.img bs=1M count=512 status=none
  # El disco de bucle vive en el núcleo del equipo, no en el contenedor: se suelta SIEMPRE al salir, o
  # cada pasada deja uno enganchado y se agotan. Un contenedor --privileged copia /dev al arrancar, así
  # que el nodo del siguiente loop libre puede no existir aquí: se crea antes de engancharlo.
  DISCOS=$(losetup -f)
  [ -b "$DISCOS" ] || mknod "$DISCOS" b 7 "${DISCOS#/dev/loop}"
  losetup "$DISCOS" /disco.img || { echo "rc=98 (el simulacro no pudo preparar el disco de bucle $DISCOS)"; exit 0; }
  trap 'umount /var/lib/mdr 2>/dev/null; losetup -d "$DISCOS"' EXIT
fi

MDR_DISCOS="$DISCOS" MDR_ESPERA_DISCO=3 MDR_IP=10.90.1.10 bash /arranque.sh > /tmp/arranque.log 2>&1
RC=$?
echo "rc=$RC"
if [ "$RC" -ne 0 ]; then
  echo "--- últimas líneas del arranque ---"
  tail -4 /tmp/arranque.log
  echo "--- llamadas ---"
  cat /tmp/llamadas
  [ -d /opt/mdr ] && echo "instalado: si" || echo "instalado: no"
  exit 0
fi

comprobar() {
  if eval "$2"; then echo "  ok     $1"; else echo "  FALLO  $1"; fi
}
comprobar "el código es de root (nada de triaje en /opt/mdr)" \
  '[ "$(stat -c %U /opt/mdr/prototipo)" = root ] && [ -z "$(find /opt/mdr -user triaje -print -quit)" ]'
comprobar "la consola viene compilada" '[ -f /opt/mdr/visor/dist/index.html ]'
comprobar "el disco de la traza está montado en /var/lib/mdr" 'mountpoint -q /var/lib/mdr'
comprobar "la unidad exige el disco" 'grep -q "RequiresMountsFor=/var/lib/mdr" /etc/systemd/system/mdr-triaje.service.d/traza.conf'
comprobar "la traza se firma (clave HMAC de 64 hex)" 'grep -Eq "^TRIAJE_TRAZA_CLAVE=[0-9a-f]{64}$" /etc/mdr/triaje.env'
comprobar "la consola exige token" 'grep -q "^TRIAJE_CONSOLA_OPERADORES=" /etc/mdr/triaje.env'
comprobar "el token de admin está en /root, 0600" \
  '[ "$(stat -c %a /root/mdr-token-admin)" = 600 ] && grep -q "Token de admin" /root/mdr-token-admin'
comprobar "perfil mínimo escrito y configurado" \
  '[ -s /etc/mdr/perfil.yml ] && grep -q "^TRIAJE_PERFIL=/etc/mdr/perfil.yml$" /etc/mdr/triaje.env'
comprobar "fuente de alertas en el disco de estado" 'grep -q "^TRIAJE_ALERTS=/var/lib/mdr/alerts.json$" /etc/mdr/triaje.env'
comprobar "sin GPU no se activa el modelo" '! grep -q "^TRIAJE_CON_LLM=1" /etc/mdr/triaje.env'
comprobar "el servicio se habilita y arranca" 'grep -q "systemctl enable --now mdr-triaje" /tmp/llamadas'
comprobar "ninguna llamada a AWS sin secretos ni S3" '! grep -q "^aws " /tmp/llamadas'
