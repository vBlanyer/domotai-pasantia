#!/bin/sh
# Aprovisiona el minimo privilegio del conector en un nodo del laboratorio.
#
#   sh lab/scripts/aprovisionar-minimo-privilegio.sh [nodo] [ip]     (por defecto objetivo-vuln 192.168.1.30)
#
# Lo que deja:
#   - en el auditor (nodo de gestion): un par de claves RSA en /root/.ssh/triaje y la clave del
#     host del nodo en /root/.ssh/known_hosts_triaje, para que el conector verifique el host.
#   - en el nodo: un usuario 'triaje' sin contrasena (solo clave), y un bloque en /etc/sudoers
#     GENERADO DESDE EL CATALOGO (python3 -m prototipo.catalogo --sudoers) que le permite, sin
#     contrasena, exactamente los comandos del catalogo cerrado de acciones y nada mas. Las rutas
#     de los binarios se resuelven en el propio nodo, porque sudoers las exige absolutas.
#
# Es idempotente: se puede repetir. Termina con dos comprobaciones: un comando del catalogo
# (permitido) y uno fuera de el (denegado). Si la segunda no falla, el aprovisionamiento no
# vale, y el script lo dice.
#
# RSA y no ed25519, y el sudoers en /etc/sudoers y no en sudoers.d: el objetivo es Metasploitable
# (OpenSSH 4.7 y sudo 1.6.9, de 2007-2008). En un equipo actual se preferiria ed25519 y sudoers.d.
set -e
NODO="${1:-clab-red-cliente-objetivo-vuln}"
IP="${2:-192.168.1.30}"
AUDITOR=clab-red-cliente-auditor
USUARIO="${TRIAJE_SSH_USUARIO:-triaje}"
CLAVE="${TRIAJE_SSH_CLAVE:-/root/.ssh/triaje}"
KNOWN="${TRIAJE_SSH_KNOWN_HOSTS:-/root/.ssh/known_hosts_triaje}"
HERE=$(cd "$(dirname "$0")/../.." && pwd)

echo "== 1. Clave del conector en el auditor =="
docker exec $AUDITOR sh -c "mkdir -p /root/.ssh && chmod 700 /root/.ssh
  [ -f $CLAVE ] || ssh-keygen -q -t rsa -b 2048 -N '' -C 'conector-triaje' -f $CLAVE
  ssh-keyscan -t rsa $IP 2>/dev/null > $KNOWN
  [ -s $KNOWN ] || { echo 'no se pudo leer la clave del host'; exit 1; }"
PUB=$(docker exec $AUDITOR cat "$CLAVE.pub")

echo "== 2. Usuario '$USUARIO' en $NODO, solo con clave =="
docker exec $NODO sh -c "
  id $USUARIO >/dev/null 2>&1 || useradd -m -s /bin/bash $USUARIO
  # Sin contrasena valida ('*'), pero NO con passwd -l: en el shadow de este Ubuntu, -l ademas
  # caduca la cuenta y PAM rechaza el acceso por clave ('account expired'). Medido.
  usermod -p '*' $USUARIO
  usermod -e '' $USUARIO 2>/dev/null || chage -E -1 $USUARIO
  H=\$(getent passwd $USUARIO | cut -d: -f6)
  mkdir -p \$H/.ssh && chmod 700 \$H/.ssh
  echo '$PUB' > \$H/.ssh/authorized_keys && chmod 600 \$H/.ssh/authorized_keys
  chown -R $USUARIO: \$H/.ssh"

echo "== 3. Sudoers generado desde el catalogo =="
RUTAS=$(docker exec $NODO sh -c 'for b in iptables ss tc service passwd tcpdump ps ip reboot ping timeout restaurar; do
  p=$(command -v $b 2>/dev/null || true); printf "%s=%s," "$b" "$p"; done')
SUDOERS=$(cd "$HERE" && python3 -m prototipo.catalogo --sudoers "$USUARIO" --rutas "$RUTAS")
docker exec -i $NODO sh -c "
  sed -i '/^# >>> conector-triaje/,/^# <<< conector-triaje/d' /etc/sudoers
  { echo '# >>> conector-triaje (generado; ver lab/scripts/aprovisionar-minimo-privilegio.sh)'; cat; echo '# <<< conector-triaje'; } >> /etc/sudoers
  visudo -c -f /etc/sudoers >/dev/null" <<EOF
$SUDOERS
EOF
echo "   $(echo "$SUDOERS" | grep -c "^$USUARIO ") comandos permitidos"

echo "== 4. Comprobaciones =="
SSH="ssh -n -i $CLAVE -o IdentitiesOnly=yes -o BatchMode=yes -o PasswordAuthentication=no -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN -o ConnectTimeout=5 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa"
if docker exec $AUDITOR sh -c "$SSH $USUARIO@$IP 'sudo -S /sbin/iptables -L -n'" >/dev/null 2>&1; then
  echo "   permitido (del catalogo):  iptables -L -n   OK"
else
  echo "   ERROR: el comando del catalogo no se pudo ejecutar"; exit 1
fi
if docker exec $AUDITOR sh -c "$SSH $USUARIO@$IP 'sudo -S cat /etc/shadow'" >/dev/null 2>&1; then
  echo "   ERROR: un comando FUERA del catalogo se ejecuto: el sudoers no restringe"; exit 1
else
  echo "   denegado (fuera del catalogo): cat /etc/shadow   OK"
fi
if docker exec $AUDITOR sh -c "$SSH $USUARIO@$IP 'sudo -S /sbin/iptables -F'" >/dev/null 2>&1; then
  echo "   ERROR: 'iptables -F' (mismo binario, otros argumentos) se ejecuto"; exit 1
else
  echo "   denegado (mismo binario, argumentos fuera del catalogo): iptables -F   OK"
fi
echo "== listo: el conector usara la clave (conector.ejecutor_por_defecto) =="
