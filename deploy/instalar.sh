#!/bin/sh
# Instala o actualiza el MDR en este equipo, o lo desinstala.
#
#   sudo ./instalar.sh                         instala, o actualiza si ya estaba (la versión anterior
#                                              queda en /opt/mdr.anterior)
#   sudo ./instalar.sh --desinstalar           quita el programa; conserva /etc/mdr y /var/lib/mdr
#   sudo ./instalar.sh --desinstalar --purgar  además borra la configuración (/etc/mdr)
#
# Nunca toca la configuración ni el estado existentes. La traza (/var/lib/mdr) no se borra nunca:
# es evidencia, y su destino lo decide el cliente.
set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -d "$DIR/prototipo" ]; then ORIGEN=$DIR; else ORIGEN=$(dirname "$DIR"); fi   # paquete o repositorio
R="${MDR_INSTALAR_RAIZ:-}"            # solo para probar el script en un directorio, sin tocar el sistema
OPT="$R/opt/mdr"
ETC="$R/etc/mdr"
VAR="$R/var/lib/mdr"
UNIDAD="$R/etc/systemd/system/mdr-triaje.service"
ENLACE="$R/usr/bin/mdr"

die() { echo "instalar: $*" >&2; exit 1; }
paso() { echo "  · $*"; }
[ -n "$R" ] || [ "$(id -u)" -eq 0 ] || die "ejecútalo con sudo"

desinstalar() {
  echo "Desinstalar el MDR."
  echo "Parar el servicio NO quita las contenciones puestas en los equipos: revísalas antes en la consola"
  printf "(Contenciones activas → «Revertir todas»). ¿Continuar? Escribe «si»: "
  read -r r
  [ "$r" = "si" ] || die "cancelado"
  systemctl disable --now mdr-triaje >/dev/null 2>&1 || true
  rm -f "$UNIDAD"
  systemctl daemon-reload >/dev/null 2>&1 || true
  if [ "$(readlink "$ENLACE" 2>/dev/null)" = "/opt/mdr/bin/mdr" ]; then rm -f "$ENLACE"; fi
  rm -rf "$OPT" "$OPT.anterior"
  paso "programa quitado"
  if [ "${1:-}" = "--purgar" ]; then rm -rf "$ETC"; paso "configuración borrada ($ETC)"; fi
  echo "Se conserva $VAR (la traza y el estado): archívala o bórrala según la política del cliente."
  echo "En cada equipo, su administrador quita el acceso: rm /etc/sudoers.d/mdr-triaje && userdel -r triaje"
}

case "${1:-}" in
  --desinstalar) desinstalar "${2:-}"; exit 0 ;;
  "") ;;
  *) die "uso: sudo ./instalar.sh [--desinstalar [--purgar]]" ;;
esac

VERSION=$(cat "$ORIGEN/VERSION" 2>/dev/null || echo "sin versión")
echo "MDR $VERSION · instalación"

# 1 · dependencias: se dicen todas de una vez, con la orden para instalarlas
if command -v apt-get >/dev/null 2>&1; then GESTOR="apt-get install"; YAML=python3-yaml; SSH=openssh-client
elif command -v dnf >/dev/null 2>&1; then GESTOR="dnf install"; YAML=python3-pyyaml; SSH=openssh-clients
else GESTOR=""; YAML="PyYAML para python3"; SSH="cliente OpenSSH"; fi
falta=""
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
  python3 -c 'import yaml' 2>/dev/null || falta="$falta $YAML"
else
  falta="$falta python3"
fi
{ command -v ssh && command -v ssh-keygen; } >/dev/null 2>&1 || falta="$falta $SSH"
command -v curl >/dev/null 2>&1 || falta="$falta curl"
command -v systemctl >/dev/null 2>&1 || die "este equipo no usa systemd"
if [ -n "$falta" ]; then
  echo "Faltan dependencias:$falta (Python debe ser 3.9 o superior)" >&2
  if [ -n "$GESTOR" ]; then echo "Instálalas con: sudo $GESTOR$falta nmap" >&2; fi
  exit 1
fi
command -v nmap >/dev/null 2>&1 || paso "aviso: sin nmap no habrá escaneo de postura (mdr escanear); instálalo cuando puedas"
paso "dependencias correctas"

# 2 · el usuario del servicio, sin shell ni contraseña
if ! id triaje >/dev/null 2>&1; then
  NOLOGIN=$(command -v nologin 2>/dev/null || echo /usr/sbin/nologin)
  useradd --system --home-dir /var/lib/mdr --no-create-home --shell "$NOLOGIN" triaje
  paso "usuario triaje creado"
fi

# 3 · el programa, de root y solo lectura para el servicio; la versión anterior se guarda
ACTUALIZA=no
[ -d "$OPT" ] && ACTUALIZA=si
rm -rf "$OPT.nuevo"
mkdir -p "$OPT.nuevo"
for d in prototipo bin deploy visor VERSION; do
  if [ -e "$ORIGEN/$d" ]; then cp -a "$ORIGEN/$d" "$OPT.nuevo/"; fi
done
[ -d "$OPT.nuevo/visor/dist" ] || die "el paquete no trae la consola construida (visor/dist)"
chown -R root:root "$OPT.nuevo"
chmod -R u+rwX,go+rX,go-w "$OPT.nuevo"
if [ "$ACTUALIZA" = si ]; then rm -rf "$OPT.anterior"; mv "$OPT" "$OPT.anterior"; fi
mv "$OPT.nuevo" "$OPT"
paso "programa en $OPT"

# 4 · configuración y estado: se crean si no existen; nunca se pisan
mkdir -p "$ETC" && chmod 0750 "$ETC" && chown root:triaje "$ETC"
if [ ! -f "$ETC/triaje.env" ]; then
  cp "$OPT/deploy/triaje.env.ejemplo" "$ETC/triaje.env"
  chmod 0600 "$ETC/triaje.env"
  paso "configuración inicial en $ETC/triaje.env"
fi
mkdir -p "$VAR" && chmod 0700 "$VAR" && chown triaje:triaje "$VAR"
if [ ! -f "$VAR/postura.json" ]; then
  echo '{"nodos": {}}' > "$VAR/postura.json"
  chown triaje:triaje "$VAR/postura.json"
fi

# 5 · el servicio y la orden mdr
mkdir -p "$(dirname "$UNIDAD")"
cp "$OPT/deploy/mdr-triaje.service" "$UNIDAD" && chmod 0644 "$UNIDAD"
systemctl daemon-reload
mkdir -p "$(dirname "$ENLACE")"
if [ -e "$ENLACE" ] && [ "$(readlink "$ENLACE")" != "/opt/mdr/bin/mdr" ]; then
  paso "aviso: ya existe otro $ENLACE; usa /opt/mdr/bin/mdr"
else
  ln -sfn /opt/mdr/bin/mdr "$ENLACE"
fi

echo
if [ "$ACTUALIZA" = si ]; then
  if systemctl is-active --quiet mdr-triaje; then systemctl restart mdr-triaje; fi
  echo "Actualizado a $VERSION. La versión anterior queda en /opt/mdr.anterior."
  echo "Comprueba con: sudo mdr estado"
else
  echo "Instalado. Siguiente paso: sudo mdr configurar"
fi
