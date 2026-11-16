#!/bin/sh
# Aprovisiona el minimo privilegio del conector en un nodo del laboratorio.
#
#   sh lab/scripts/aprovisionar-minimo-privilegio.sh [nodo] [ip]     (por defecto objetivo-vuln 192.168.1.30)
#
# Lo que deja:
#   - en el auditor (nodo de gestion): un par de claves RSA en /root/.ssh/triaje y la clave del
#     host del nodo en /root/.ssh/known_hosts_triaje, para que el conector verifique el host.
#   - en el nodo: un usuario 'triaje' sin contrasena (solo clave), el envoltorio /usr/local/sbin/mdr-accion
#     GENERADO DESDE EL CATALOGO (python3 -m prototipo.accion.catalogo --envoltorio), que valida cada
#     argumento y ejecuta exactamente los comandos del catalogo cerrado de acciones y nada mas, y un
#     sudoers que solo le permite, sin contrasena, ese envoltorio.
#
# Es idempotente: se puede repetir. Termina con comprobaciones: un comando del catalogo
# (permitido) y varios fuera de el (denegados, incluido un token de mas). Si alguno de estos
# no falla, el aprovisionamiento no vale, y el script lo dice.
#
# RSA y no ed25519, y el sudoers en /etc/sudoers y no en sudoers.d: el objetivo es Metasploitable
# (OpenSSH 4.7 y sudo 1.6.9, de 2007-2008). En un equipo actual se preferiria ed25519 y sudoers.d.
set -e
NODO="${1:-clab-red-cliente-objetivo-vuln}"
IP="${2:-192.168.1.30}"
AUDITOR="${TRIAJE_NODO_GESTION:-clab-red-cliente-auditor}"
USUARIO="${TRIAJE_SSH_USUARIO:-triaje}"
CLAVE="${TRIAJE_SSH_CLAVE:-/root/.ssh/triaje}"
KNOWN="${TRIAJE_SSH_KNOWN_HOSTS:-/root/.ssh/known_hosts_triaje}"
HERE=$(cd "$(dirname "$0")/../.." && pwd)

echo "== 1. Clave del conector en el auditor =="
docker exec $AUDITOR sh -c "mkdir -p /root/.ssh && chmod 700 /root/.ssh
  [ -f $CLAVE ] || ssh-keygen -q -t rsa -b 2048 -N '' -C 'conector-triaje' -f $CLAVE
  touch $KNOWN; grep -v \"^$IP \" $KNOWN > $KNOWN.tmp 2>/dev/null || true; mv $KNOWN.tmp $KNOWN
  ssh-keyscan -t rsa,ed25519 $IP 2>/dev/null >> $KNOWN
  grep -q \"^$IP \" $KNOWN || { echo 'no se pudo leer la clave del host'; exit 1; }"
PUB=$(docker exec $AUDITOR cat "$CLAVE.pub")

echo "== 2. Usuario '$USUARIO' en $NODO, solo con clave =="
docker exec $NODO sh -c "
  if id $USUARIO >/dev/null 2>&1; then :
  elif command -v useradd >/dev/null 2>&1; then useradd -m -s /bin/bash $USUARIO
  else adduser -D -s /bin/sh $USUARIO; fi          # BusyBox (Alpine): adduser -D deja la clave bloqueada
  # Sin contrasena valida ('*'), pero NO con passwd -l: en el shadow del Ubuntu de Metasploitable, -l
  # ademas caduca la cuenta y PAM rechaza el acceso por clave ('account expired'). Medido.
  if command -v usermod >/dev/null 2>&1; then usermod -p '*' $USUARIO; usermod -e '' $USUARIO 2>/dev/null || chage -E -1 $USUARIO 2>/dev/null
  else sed -i "s/^$USUARIO:[!]*:/$USUARIO:*:/" /etc/shadow; fi   # OpenSSH sin PAM rechaza '!' (cuenta bloqueada) aunque la clave valga
  H=\$(getent passwd $USUARIO | cut -d: -f6)
  mkdir -p \$H/.ssh && chmod 700 \$H/.ssh
  echo '$PUB' > \$H/.ssh/authorized_keys && chmod 600 \$H/.ssh/authorized_keys
  chown -R $USUARIO: \$H/.ssh"

echo "== 3. Envoltorio mdr-accion y sudoers que solo lo permite =="
# El envoltorio (python3 -m prototipo.accion.catalogo --envoltorio) valida cada argumento contra el
# catalogo y ejecuta exactamente esa orden; el sudoers solo permite el envoltorio. Antes eran reglas
# de sudoers con comodines, y un `*` de sudoers admite espacios: `iptables -A INPUT -s * -j DROP`
# dejaba pasar `--modprobe=<programa>` (root). #13 de la revision del 15/11.
ENVOLTORIO=/usr/local/sbin/mdr-accion
(cd "$HERE" && python3 -m prototipo.accion.catalogo --envoltorio) | docker exec -i $NODO sh -c "
  mkdir -p /usr/local/sbin && cat > $ENVOLTORIO.tmp && sh -n $ENVOLTORIO.tmp &&
  chown root:root $ENVOLTORIO.tmp && chmod 755 $ENVOLTORIO.tmp && mv $ENVOLTORIO.tmp $ENVOLTORIO"
SUDOERS="$USUARIO ALL=(root) NOPASSWD: $ENVOLTORIO"
# sudoers.d si el sudo del nodo lo admite (Alpine); si no (sudo 1.6.9 de Metasploitable), un bloque
# entre marcas en /etc/sudoers. En ambos casos visudo -c valida antes de dar por bueno.
docker exec -i $NODO sh -c "
  if [ -d /etc/sudoers.d ] && grep -q '^#includedir /etc/sudoers.d\|^@includedir /etc/sudoers.d' /etc/sudoers 2>/dev/null; then
    cat > /etc/sudoers.d/conector-triaje && chmod 440 /etc/sudoers.d/conector-triaje
    visudo -c -f /etc/sudoers.d/conector-triaje >/dev/null
  else
    sed -i '/^# >>> conector-triaje/,/^# <<< conector-triaje/d' /etc/sudoers
    { echo '# >>> conector-triaje (generado; ver lab/scripts/aprovisionar-minimo-privilegio.sh)'; cat; echo '# <<< conector-triaje'; } >> /etc/sudoers
    visudo -c -f /etc/sudoers >/dev/null
  fi" <<EOF
$SUDOERS
EOF
echo "   sudo solo permite $ENVOLTORIO ($(docker exec $NODO $ENVOLTORIO --reglas | wc -l) plantillas del catalogo)"

echo "== 4. Comprobaciones =="
SSH="ssh -n -i $CLAVE -o IdentitiesOnly=yes -o BatchMode=yes -o PasswordAuthentication=no -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN -o ConnectTimeout=5 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa"
if docker exec $AUDITOR sh -c "$SSH $USUARIO@$IP 'sudo -S $ENVOLTORIO iptables -L -n'" >/dev/null 2>&1; then
  echo "   permitido (del catalogo):  iptables -L -n   OK"
else
  echo "   ERROR: el comando del catalogo no se pudo ejecutar"; exit 1
fi
if docker exec $AUDITOR sh -c "$SSH $USUARIO@$IP 'sudo -S true'" >/dev/null 2>&1; then
  echo "   ERROR: un comando FUERA del envoltorio se ejecuto: el sudoers no restringe"; exit 1
else
  echo "   denegado (fuera del envoltorio): true   OK"
fi
if docker exec $AUDITOR sh -c "$SSH $USUARIO@$IP 'sudo -S $ENVOLTORIO iptables -F'" >/dev/null 2>&1; then
  echo "   ERROR: 'iptables -F' (mismo binario, otros argumentos) se ejecuto"; exit 1
else
  echo "   denegado (mismo binario, argumentos fuera del catalogo): iptables -F   OK"
fi
if docker exec $AUDITOR sh -c "$SSH $USUARIO@$IP 'sudo -S $ENVOLTORIO iptables -A INPUT -s 1.2.3.4 --modprobe=/tmp/x -j DROP'" >/dev/null 2>&1; then
  echo "   ERROR: un token de mas (--modprobe) se ejecuto: el envoltorio no restringe"; exit 1
else
  echo "   denegado (token de mas): iptables -A INPUT -s 1.2.3.4 --modprobe=/tmp/x -j DROP   OK"
fi
echo "== listo: el conector usara la clave (conector.ejecutor_por_defecto) =="
