#!/bin/sh
# Campaña REAL de la familia 'servicio_expuesto' (telnet en claro) contra el laboratorio.
#
#   sh lab/scripts/campana-telnet.sh <id-campaña>
#
# Misma estructura que campana-recon.sh: atacante = puesto, admin legitimo = borde, auditor = PROPIA.
# Lo que se observa es el in.telnetd de Metasploitable, que pasa por tcpd y escribe en daemon.log
#   "in.telnetd[pid]: connect from 192.168.1.10 (192.168.1.10)"   -> regla 5602 de Wazuh (nivel 3)
#   "telnetd[pid]: ttloop: peer died: EOF"                         -> 5603 (nivel 5, si sigue a 5602)
# y seis o mas conexiones del mismo origen en dos minutos -> 5631 (nivel 10, posible escaneo).
# Dos cosas que hubo que resolver para que esto llegara: el reenvio solo llevaba auth.log (ahora
# tambien daemon.log), y el decodificador de fabrica no sacaba el srcip del formato de tcpd
# (lab/wazuh/local_decoder_telnetd.xml).
set -e
ID="${1:?uso: sh lab/scripts/campana-telnet.sh <id-campaña>}"
HERE=$(dirname "$0")
DEST="$HERE/../campañas/$ID"
WZ=clab-red-cliente-wazuh
AUDITOR=clab-red-cliente-auditor
ATACANTE=clab-red-cliente-puesto
ADMIN=clab-red-cliente-borde
OBJETIVO=clab-red-cliente-objetivo-vuln
OBJ_IP=192.168.1.30
ATAC_IP=192.168.1.10
ADMIN_IP=192.168.1.1
AUDITOR_IP=$(docker inspect $AUDITOR --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
mkdir -p "$DEST"

INICIO=$(docker exec $WZ date -u +%Y-%m-%dT%H:%M:%S)

echo "== Dejando el objetivo sin bloqueos previos =="
for ip in $ATAC_IP $ADMIN_IP; do
  docker exec $OBJETIVO sh -c "iptables -D INPUT -s $ip -j DROP 2>/dev/null" || true
done

# Una conexion telnet que negocia y cierra: tcpd registra 'connect from', y al cerrar, 'peer died'.
conexion() {  # $1 contenedor
  docker exec "$1" sh -c "(printf '\\r\\n'; sleep 1) | nc -w2 $OBJ_IP 23 >/dev/null 2>&1 || true"
}

echo "== Conexiones telnet desde puesto contra objetivo-vuln (VP): ocho, en dos minutos =="
for i in 1 2 3 4 5 6 7 8; do conexion $ATACANTE; sleep 2; done

echo "== Comprobaciones BENIGNAS del admin declarado (borde): tres -> FP =="
for i in 1 2 3; do conexion $ADMIN; sleep 2; done

echo "== Comprobacion desde el auditor: dos -> PROPIA =="
for i in 1 2; do conexion $AUDITOR; sleep 2; done

echo "== esperando al reenvio syslog =="
sleep 60

echo "== Congelando la ventana de alerts.json desde $INICIO =="
docker exec $WZ sh -c 'cat /var/ossec/logs/alerts/alerts.json' | python3 -c "
import sys, json
desde = sys.argv[1]
n = 0
for l in sys.stdin:
    l = l.strip()
    if not l:
        continue
    try:
        d = json.loads(l)
    except json.JSONDecodeError:
        continue
    if d.get('timestamp', '') >= desde:
        print(l); n += 1
print(n, 'alertas en la ventana', file=sys.stderr)
" "$INICIO" > "$DEST/alerts.json"

echo "== Escribiendo la ficha de campaña =="
cat > "$DEST/campaña.yml" <<YML
id: $ID
fecha: $(date -u +%Y-%m-%d)
familia: servicio_expuesto
ataques:
  - escenario: conexiones repetidas al telnet en claro (nc)
    objetivo: objetivo-vuln
    desde: puesto
  - escenario: comprobaciones benignas del servicio (admin legitimo, nc)
    objetivo: objetivo-vuln
    desde: borde
  - escenario: comprobacion del servicio (nc)
    objetivo: objetivo-vuln
    desde: auditor
auditor:
  ips: ["$AUDITOR_IP"]
  cuando: "$INICIO+0000"
legitimos:
  ips: ["$ADMIN_IP"]
YML

echo "== Auditando la postura (hallazgos.json) =="
sh "$HERE/auditar.sh" "$DEST/hallazgos.json"

echo "== Dejando el objetivo neutro =="
for ip in $ATAC_IP $ADMIN_IP; do
  docker exec $OBJETIVO sh -c "iptables -D INPUT -s $ip -j DROP 2>/dev/null" || true
done

N=$(grep -c . "$DEST/alerts.json" 2>/dev/null || echo 0)
echo "== Campaña '$ID' congelada en $DEST ($N alertas) =="
