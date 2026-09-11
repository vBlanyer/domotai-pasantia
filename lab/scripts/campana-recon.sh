#!/bin/sh
# Campaña REAL de la familia 'reconocimiento' contra el laboratorio, congelada en disco.
#
#   sh lab/scripts/campana-recon.sh <id-campaña>
#
# Misma estructura que campana.sh (atacante = puesto, admin legitimo = borde, auditor =
# PROPIA), pero con escaneos de puertos en vez de fuerza bruta. Dos diferencias deliberadas:
#
# - Los escaneos se hacen con nc, no con nmap. Un escaneo SYN no completa el handshake y
#   sshd nunca lo ve; por eso la campaña anterior, que escaneaba como root (SYN por
#   defecto), no dejo ni una alerta de reconocimiento. Y se midio que tampoco basta con
#   nmap -sT: cierra con RST y el sshd de Metasploitable (OpenSSH de 2007) solo registra el
#   cierre limpio con FIN que hace nc. Lo que sshd registra es "Did not receive
#   identification string" (regla 5706, nivel 6) y, ante un cliente que habla otro
#   protocolo, "Bad protocol version identification" (regla 5701, nivel 8). Ambas llevan
#   el grupo 'recon' y el adaptador las mapea a la familia reconocimiento.
# - Se congela SOLO la ventana temporal de la campaña, no alerts.json entero: el manager
#   lleva horas acumulando demos, pruebas de humo e inyecciones que no son de esta campaña.
#
# El atacante escanea en rafaga corta a proposito: si hay un daemon del prototipo en
# marcha, bloqueara al puesto en cuanto llegue la primera alerta, y los escaneos
# posteriores dejarian de registrarse.
set -e
ID="${1:?uso: sh lab/scripts/campana-recon.sh <id-campaña>}"
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

echo "== Reconocimiento real desde puesto contra objetivo-vuln (VP) =="
# Seis barridos de puertos (cada uno toca el 22 una vez -> 5706) y tres sondeos de protocolo
# contra el 22 hablando HTTP (-> 5701). En rafaga: ver la cabecera.
docker exec $ATACANTE sh -c "
  for i in 1 2 3 4 5 6; do
    for p in 21 22 23 25 80 111 139 445 512 1524 3306 5432 8180; do
      nc -z -w1 $OBJ_IP \$p >/dev/null 2>&1 || true
    done
  done
  for i in 1 2 3; do
    printf 'GET / HTTP/1.0\r\n\r\n' | nc -w2 $OBJ_IP 22 >/dev/null 2>&1 || true
  done"

echo "== Sondeos BENIGNOS desde el admin declarado (borde) -> FP =="
# El administrador comprueba que ssh responde: misma senal que un escaneo, origen declarado.
docker exec $ADMIN sh -c "
  for i in 1 2 3 4; do
    nc -z -w2 $OBJ_IP 22 >/dev/null 2>&1 || true; sleep 1
  done"

echo "== Barrido desde el auditor (sera PROPIA) =="
docker exec $AUDITOR sh -c "
  for i in 1 2; do
    for p in 21 22 23 25 80 139 445 3306; do
      nc -z -w1 $OBJ_IP \$p >/dev/null 2>&1 || true
    done
  done"

echo "== esperando al reenvio syslog (un datagrama por linea, ~1 s cada uno) =="
sleep 75

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
familia: reconocimiento
ataques:
  - escenario: barridos de puertos y sondeos de protocolo contra ssh (nc)
    objetivo: objetivo-vuln
    desde: puesto
  - escenario: comprobaciones de servicio benignas (admin legitimo, nc -z)
    objetivo: objetivo-vuln
    desde: borde
  - escenario: barrido de puertos (nc)
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
