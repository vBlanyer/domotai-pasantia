#!/bin/sh
# Rota la clave del conector (usuario 'triaje') en todos los nodos gestionados. Todo o nada.
#
#   sh lab/scripts/rotar-clave-conector.sh nodo1:ip1 [nodo2:ip2 ...]
#   p. ej. sh lab/scripts/rotar-clave-conector.sh clab-red-cliente-objetivo-vuln:192.168.1.30 clab-red-cliente-borde:192.168.1.1
#
# Como:
#   1. genera una clave NUEVA en el auditor (RSA, por el OpenSSH de 2007 del objetivo);
#   2. la ANADE a authorized_keys de 'triaje' en cada nodo (la vieja sigue valiendo);
#   3. verifica con la nueva, en cada nodo, un comando del catalogo por sudo;
#   4. solo si TODOS verifican: deja en cada nodo unicamente la nueva, y en el auditor la nueva
#      pasa a ser /root/.ssh/triaje (la vieja se guarda como triaje.retirada.<fecha>, ya inutil
#      en los nodos, por si hay que reconstruir que paso);
#   5. si alguno falla: retira la nueva de donde se anadio y se detiene; la vieja no se toca.
#   6. anota la rotacion en Wazuh (evento syslog 'triaje-rotacion', regla local 100101), para que
#      el cambio de credencial conste en el mismo sitio que las decisiones.
#
# El conector no se reinicia: lee la clave por su ruta en cada llamada.
set -e
AUDITOR=clab-red-cliente-auditor
USUARIO="${TRIAJE_SSH_USUARIO:-triaje}"
CLAVE="${TRIAJE_SSH_CLAVE:-/root/.ssh/triaje}"
KNOWN="${TRIAJE_SSH_KNOWN_HOSTS:-/root/.ssh/known_hosts_triaje}"
NUEVA="$CLAVE.nueva"
FECHA=$(date -u +%Y%m%dT%H%M%SZ)
[ $# -ge 1 ] || { echo "uso: $0 nodo:ip [nodo:ip ...]"; exit 2; }

ssh_con() {  # $1 clave, $2 ip, $3 comando remoto
  docker exec $AUDITOR sh -c "ssh -n -i $1 -o IdentitiesOnly=yes -o BatchMode=yes -o PasswordAuthentication=no \
    -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN -o ConnectTimeout=5 \
    -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa $USUARIO@$2 '$3'" >/dev/null 2>&1
}
ipt_de() {   # ruta de iptables en el nodo (Metasploitable: /sbin; Alpine: /usr/sbin)
  docker exec "$1" sh -c 'command -v iptables'
}

echo "== 1. Clave nueva en el auditor =="
docker exec $AUDITOR sh -c "[ -f $CLAVE ] || { echo 'no hay clave que rotar: aprovisiona primero'; exit 1; }
  rm -f $NUEVA $NUEVA.pub; ssh-keygen -q -t rsa -b 2048 -N '' -C 'conector-triaje-$FECHA' -f $NUEVA"
PUB_NUEVA=$(docker exec $AUDITOR cat "$NUEVA.pub")
PUB_VIEJA=$(docker exec $AUDITOR cat "$CLAVE.pub")

echo "== 2. Anadiendo la nueva en cada nodo (la vieja sigue valiendo) =="
ANADIDOS=""
for par in "$@"; do
  NODO=${par%%:*}; IP=${par#*:}
  docker exec "$NODO" sh -c "H=\$(getent passwd $USUARIO | cut -d: -f6); grep -qF '$PUB_NUEVA' \$H/.ssh/authorized_keys || echo '$PUB_NUEVA' >> \$H/.ssh/authorized_keys"
  ANADIDOS="$ANADIDOS $par"
  echo "   $NODO: anadida"
done

echo "== 3. Verificando la nueva en cada nodo con un comando del catalogo =="
FALLO=""
for par in "$@"; do
  NODO=${par%%:*}; IP=${par#*:}
  if ssh_con "$NUEVA" "$IP" "sudo -S $(ipt_de "$NODO") -L -n"; then
    echo "   $NODO ($IP): OK con la clave nueva"
  else
    echo "   $NODO ($IP): FALLO con la clave nueva"; FALLO="si"
  fi
done

if [ -n "$FALLO" ]; then
  echo "== ABORTADA: se retira la nueva de los nodos; la clave vieja no se ha tocado =="
  for par in $ANADIDOS; do
    NODO=${par%%:*}
    docker exec "$NODO" sh -c "H=\$(getent passwd $USUARIO | cut -d: -f6); grep -vF '$PUB_NUEVA' \$H/.ssh/authorized_keys > \$H/.ssh/ak.tmp; mv \$H/.ssh/ak.tmp \$H/.ssh/authorized_keys; chmod 600 \$H/.ssh/authorized_keys; chown $USUARIO: \$H/.ssh/authorized_keys"
  done
  docker exec $AUDITOR sh -c "rm -f $NUEVA $NUEVA.pub"
  exit 1
fi

echo "== 4. Retirando la vieja de cada nodo y promoviendo la nueva en el auditor =="
for par in "$@"; do
  NODO=${par%%:*}
  docker exec "$NODO" sh -c "H=\$(getent passwd $USUARIO | cut -d: -f6); echo '$PUB_NUEVA' > \$H/.ssh/authorized_keys; chmod 600 \$H/.ssh/authorized_keys; chown $USUARIO: \$H/.ssh/authorized_keys"
  echo "   $NODO: solo la nueva"
done
docker exec $AUDITOR sh -c "mv $CLAVE $CLAVE.retirada.$FECHA; mv $CLAVE.pub $CLAVE.retirada.$FECHA.pub; mv $NUEVA $CLAVE; mv $NUEVA.pub $CLAVE.pub; chmod 600 $CLAVE"

echo "== 5. Comprobacion final: la vieja ya no entra, la nueva si =="
for par in "$@"; do
  NODO=${par%%:*}; IP=${par#*:}
  if ssh_con "$CLAVE.retirada.$FECHA" "$IP" "true"; then echo "   ERROR: la clave retirada sigue entrando en $NODO"; exit 1; fi
  ssh_con "$CLAVE" "$IP" "sudo -S $(ipt_de "$NODO") -L -n" || { echo "   ERROR: la nueva no entra en $NODO tras promoverla"; exit 1; }
  echo "   $NODO: vieja denegada, nueva OK"
done

echo "== 6. Anotando la rotacion en Wazuh =="
WZ_IP=$(docker inspect clab-red-cliente-wazuh --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null || true)
if [ -n "$WZ_IP" ]; then
  HUELLA=$(docker exec $AUDITOR sh -c "ssh-keygen -lf $CLAVE.pub | awk '{print \$2}'")
  python3 - "$WZ_IP" "$HUELLA" "$*" <<'PY'
import socket, sys, time
ip, huella, nodos = sys.argv[1], sys.argv[2], sys.argv[3]
msg = f"<38>{time.strftime('%b %d %H:%M:%S')} triaje triaje-rotacion: usuario=triaje huella={huella} nodos={nodos.replace(' ', ',')}"
socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(msg.encode(), (ip, 514))
PY
  echo "   huella nueva: $HUELLA"
fi
echo "== rotacion completada =="
