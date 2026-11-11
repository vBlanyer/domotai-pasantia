#!/bin/sh
# Campaña REAL de la ampliación del conjunto de datos (R1), con la verdad declarada por el experimento.
# Diseño fijado antes de medir: documentacion/06-fase6-evaluacion-del-prototipo/ampliacion-dataset-2026-11.md
#
#   sh lab/scripts/campana-ampliacion.sh <id-campaña>
#
# Cada escenario sale de su PROPIA IP (alias en el nodo), así la verdad se asigna por origen:
#   A1 proveedor 10.0.1.50  -> objetivo-vuln SSH   fuerza bruta root@ (10)          VP
#   A2 proveedor 10.0.1.51  -> iot telnet          3 conexiones                     VP
#   B1 puesto 192.168.1.42  -> iot telnet          3 conexiones (equipo interno)    VP
#   B2 puesto 192.168.1.43  -> iot telnet          1 conexión (técnico legítimo)    FP
#   C1 puesto 192.168.1.44  -> objetivo-vuln FTP   fuerza bruta msfadmin@ (8)       VP
#   C2 puesto 192.168.1.45  -> objetivo-vuln FTP   1 error y acceso correcto        FP
#   D1 proveedor 10.0.1.52  -> objetivo-vuln SSH   2 errores y acceso correcto      FP
set -e
ID="${1:?uso: sh lab/scripts/campana-ampliacion.sh <id-campaña>}"
HERE=$(cd "$(dirname "$0")" && pwd)
RAIZ=$(cd "$HERE/../.." && pwd)
DEST="$RAIZ/lab/campañas/$ID"
P=clab-red-cliente
WZ=$P-wazuh; PROV=$P-proveedor; PUESTO=$P-puesto; OBJ=$P-objetivo-vuln; IOT=$P-iot
OBJ_IP=192.168.1.30; IOT_IP=192.168.1.20
W=$(docker inspect $WZ --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
[ -n "$W" ] || { echo "Wazuh no está corriendo (sh lab/lab.sh up)"; exit 1; }
AUDITOR_IP=$(docker inspect $P-auditor --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
mkdir -p "$DEST"
ahora() { docker exec $WZ date -u +%Y-%m-%dT%H:%M:%S; }
SSH="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no -o PreferredAuthentications=password"

echo "== Preparando los nodos (idempotente) =="
docker exec $PROV sh -c 'command -v sshpass >/dev/null || apk add --no-cache openssh-client sshpass >/dev/null 2>&1; for h in 50 51 52; do ip addr add 10.0.1.$h/24 dev eth1 2>/dev/null; done; true'
docker exec $PUESTO sh -c 'command -v curl >/dev/null || apk add --no-cache curl >/dev/null 2>&1; for h in 42 43 44 45; do ip addr add 192.168.1.$h/24 dev eth1 2>/dev/null; done; true'
# iot: el telnetd de BusyBox no deja registro; se sustituye por el señuelo del banco y su reenviador.
docker exec $IOT sh -c 'command -v python3 >/dev/null || apk add --no-cache python3 >/dev/null 2>&1; mkdir -p /opt/banco /var/log/banco; touch /var/log/banco/telnet.log; pkill telnetd; pkill -f "[t]elnet_expuesto.py"; pkill -f "[r]eenviador.py"; true'
docker cp "$RAIZ/lab/banco/telnet_expuesto.py" $IOT:/opt/banco/telnet_expuesto.py
docker cp "$RAIZ/lab/banco/reenviador.py" $IOT:/opt/banco/reenviador.py
docker exec -d $IOT python3 /opt/banco/telnet_expuesto.py 23 /var/log/banco/telnet.log
docker exec -d $IOT python3 /opt/banco/reenviador.py --nodo iot --destino "$W:514" --telnet /var/log/banco/telnet.log
# objetivo-vuln: además de auth.log y daemon.log, el registro propio de vsftpd con cabecera syslog
# (auth.log pliega los fallos repetidos en «last message repeated» y no registra el acceso correcto).
# pkill en su propia orden: dentro de un `sh -c` que contiene el nombre del guion, se mataría a sí mismo.
docker exec $OBJ pkill -f reenvio-vsftpd.sh 2>/dev/null || true
docker exec $OBJ sh -c "cat > /usr/local/bin/reenvio-vsftpd.sh <<SCRIPT
#!/bin/sh
tail -n0 -f /var/log/vsftpd.log | while IFS= read -r l; do
  printf '<30>%s objetivo-vuln vsftpd[1]: %s\\\\n' \"\\\$(date '+%b %e %H:%M:%S')\" \"\\\$l\" | nc -u -w1 $W 514
done
SCRIPT
chmod +x /usr/local/bin/reenvio-vsftpd.sh; true"
docker exec -d $OBJ sh /usr/local/bin/reenvio-vsftpd.sh   # con sh: sin él, un fallo del shebang lo mata en silencio
for ip in 10.0.1.50 10.0.1.52 192.168.1.44 192.168.1.45; do docker exec $OBJ sh -c "iptables -D INPUT -s $ip -j DROP 2>/dev/null" || true; done
sleep 3

INICIO=$(ahora)
echo "== A1: fuerza bruta SSH externa (10.0.1.50) contra objetivo-vuln =="
docker exec $PROV sh -c "for i in 1 2 3 4 5 6 7 8 9 10; do sshpass -p mal_\$i $SSH -b 10.0.1.50 root@$OBJ_IP true >/dev/null 2>&1; done; true"
echo "== A2: telnet externo (10.0.1.51) contra iot =="
docker exec $PROV sh -c "for i in 1 2 3; do printf 'x\r\n' | nc -s 10.0.1.51 -w3 $IOT_IP 23 >/dev/null 2>&1; sleep 1; done; true"
echo "== B1: telnet interno (192.168.1.42) contra iot =="
docker exec $PUESTO sh -c "for i in 1 2 3; do printf 'x\r\n' | nc -s 192.168.1.42 -w3 $IOT_IP 23 >/dev/null 2>&1; sleep 1; done; true"
echo "== B2: técnico de mantenimiento (192.168.1.43), una conexión a iot =="
docker exec $PUESTO sh -c "printf 'x\r\n' | nc -s 192.168.1.43 -w3 $IOT_IP 23 >/dev/null 2>&1; true"
echo "== C1: fuerza bruta FTP (192.168.1.44) contra objetivo-vuln =="
docker exec $PUESTO sh -c "for i in 1 2 3 4 5 6 7 8; do curl -s --interface 192.168.1.44 -m 5 ftp://msfadmin:mal_\$i@$OBJ_IP/ >/dev/null 2>&1; done; true"
echo "== C2: usuario legítimo de FTP (192.168.1.45): un error y acceso correcto =="
docker exec $PUESTO sh -c "curl -s --interface 192.168.1.45 -m 5 ftp://msfadmin:msfadmni@$OBJ_IP/ >/dev/null 2>&1; sleep 2; curl -s --interface 192.168.1.45 -m 5 ftp://msfadmin:msfadmin@$OBJ_IP/ >/dev/null 2>&1; true"
echo "== D1: técnico del proveedor (10.0.1.52): dos errores y acceso correcto por SSH =="
docker exec $PROV sh -c "sshpass -p msfadmni $SSH -b 10.0.1.52 msfadmin@$OBJ_IP true >/dev/null 2>&1; sleep 2; sshpass -p msfadmn $SSH -b 10.0.1.52 msfadmin@$OBJ_IP true >/dev/null 2>&1; sleep 2; sshpass -p msfadmin $SSH -b 10.0.1.52 msfadmin@$OBJ_IP true >/dev/null 2>&1; true"
FIN=$(ahora)
echo "   esperando al reenvío..."; sleep 60
CIERRE=$(ahora)

echo "== Congelando la ventana de alerts.json desde $INICIO =="
docker exec $WZ sh -c 'cat /var/ossec/logs/alerts/alerts.json' | python3 -c "
import sys, json
desde = sys.argv[1]; n = 0
for l in sys.stdin:
    l = l.strip()
    if not l: continue
    try: d = json.loads(l)
    except json.JSONDecodeError: continue
    if d.get('timestamp', '') >= desde:
        print(l); n += 1
print(n, 'alertas en la ventana', file=sys.stderr)
" "$INICIO" > "$DEST/alerts.json"

echo "== Escribiendo la ficha de campaña (con la verdad declarada) =="
cat > "$DEST/campaña.yml" <<YML
id: $ID
fecha: $(date -u +%Y-%m-%d)
familia: varias
proposito: ampliación R1 (otro equipo, otro servicio, atacante externo, legítimos no declarados); verdad declarada por el experimento
diseno: documentacion/06-fase6-evaluacion-del-prototipo/ampliacion-dataset-2026-11.md
ataques:
  - { escenario: "A1 fuerza bruta SSH root@ desde un atacante externo", objetivo: objetivo-vuln, desde: proveedor }
  - { escenario: "A2 conexiones telnet al iot desde un atacante externo", objetivo: iot, desde: proveedor }
  - { escenario: "B1 conexiones telnet al iot desde un equipo interno", objetivo: iot, desde: puesto }
  - { escenario: "B2 un técnico de mantenimiento entra por telnet al iot desde un origen no declarado", objetivo: iot, desde: puesto }
  - { escenario: "C1 fuerza bruta FTP msfadmin@", objetivo: objetivo-vuln, desde: puesto }
  - { escenario: "C2 usuario legítimo de FTP que se equivoca una vez y entra", objetivo: objetivo-vuln, desde: puesto }
  - { escenario: "D1 técnico del proveedor que se equivoca dos veces y entra por SSH", objetivo: objetivo-vuln, desde: proveedor }
auditor:
  ips: ["$AUDITOR_IP"]
  cuando: "$CIERRE+0000"
legitimos:
  ips: ["192.168.1.1"]
verdad:
  - { origen: "10.0.1.50",    desde: "$INICIO", hasta: "$CIERRE", etiqueta: VP, motivo: "A1: fuerza bruta SSH de un atacante externo" }
  - { origen: "10.0.1.51",    desde: "$INICIO", hasta: "$CIERRE", etiqueta: VP, motivo: "A2: telnet al iot desde un atacante externo" }
  - { origen: "192.168.1.42", desde: "$INICIO", hasta: "$CIERRE", etiqueta: VP, motivo: "B1: telnet al iot desde un equipo interno" }
  - { origen: "192.168.1.43", desde: "$INICIO", hasta: "$CIERRE", etiqueta: FP, motivo: "B2: técnico de mantenimiento legítimo, origen no declarado" }
  - { origen: "192.168.1.44", desde: "$INICIO", hasta: "$CIERRE", etiqueta: VP, motivo: "C1: fuerza bruta FTP" }
  - { origen: "192.168.1.45", desde: "$INICIO", hasta: "$CIERRE", etiqueta: FP, motivo: "C2: usuario legítimo de FTP que se equivoca una vez" }
  - { origen: "10.0.1.52",    desde: "$INICIO", hasta: "$CIERRE", etiqueta: FP, motivo: "D1: técnico del proveedor que se equivoca dos veces" }
YML

echo "== Auditando la postura (hallazgos.json) =="
sh "$HERE/auditar.sh" "$DEST/hallazgos.json"
echo "== Campaña $ID lista en $DEST =="
