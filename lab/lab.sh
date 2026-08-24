#!/bin/sh
# Control maestro del laboratorio FTTx completo.
#
#   sh lab/lab.sh up      despliega la red + arranca Wazuh + activa el reenvio
#   sh lab/lab.sh down    lo baja todo
#   sh lab/lab.sh status  muestra que esta vivo
#   sh lab/lab.sh test    ejecuta la prueba de humo de extremo a extremo
set -e
HERE=$(dirname "$0")
TOPO="$HERE/fttx-lab.clab.yml"

case "${1:-up}" in
  up)
    echo "== 1. Desplegando la red FTTx =="
    containerlab deploy -t "$TOPO"
    echo "== 2. Arrancando Wazuh manager =="
    sh "$HERE/wazuh-run.sh" up
    echo "   esperando a que Wazuh este listo..."
    until docker exec clab-fttx-lab-wazuh sh -c '/var/ossec/bin/wazuh-control status 2>/dev/null | grep -q "wazuh-analysisd is running"' 2>/dev/null; do sleep 4; done
    echo "== 3. Activando el reenvio de syslog =="
    sh "$HERE/reenvio-syslog.sh"
    echo "== Laboratorio en marcha. Prueba con: sh lab/lab.sh test =="
    ;;
  down)
    sh "$HERE/wazuh-run.sh" down 2>/dev/null || true
    containerlab destroy -t "$TOPO" 2>/dev/null || true
    echo "Laboratorio detenido."
    ;;
  status)
    echo "== Nodos de la red =="
    docker ps --filter name=clab-fttx-lab --format '  {{.Names}}: {{.Status}}'
    echo "== Wazuh =="
    docker ps --filter name=clab-fttx-lab-wazuh --format '  {{.Names}}: {{.Status}}' | grep . || echo "  Wazuh no esta corriendo"
    echo "== Memoria =="
    free -m | awk '/Mem:/{printf "  disponible=%d MiB\n",$7}'
    ;;
  test)
    echo "== Prueba de humo de extremo a extremo =="
    W=$(docker inspect clab-fttx-lab-wazuh --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)
    echo "-- 1. Conectividad LAN (abonado -> objetivo)"
    docker exec clab-fttx-lab-abonado ping -c1 -W2 192.168.1.30 >/dev/null 2>&1 && echo "   OK" || echo "   FALLO"
    echo "-- 2. El auditor ve los servicios del objetivo"
    # Metasploitable tarda en levantar sus servicios; esperar al FTP antes de escanear
    n=0; until docker exec clab-fttx-lab-auditor sh -c "nc -w2 -z 192.168.1.30 21" 2>/dev/null || [ $n -ge 15 ]; do sleep 2; n=$((n+1)); done
    docker exec clab-fttx-lab-auditor nmap -Pn --top-ports 20 192.168.1.30 2>/dev/null | grep -c "open" | xargs -I{} echo "   {} puertos abiertos detectados"
    echo "-- 3. Un ataque genera alerta en Wazuh"
    IP="10.20.30.$(( $$ % 200 + 1 ))"
    # Fuerza bruta por inyeccion directa al manager (rafaga apretada -> se
    # correlaciona en nivel 10). Es la via fiable; el reenvio desde auth.log
    # entrega bien los eventos sueltos (nivel 5) pero su latencia por datagrama
    # dispersa las rafagas fuera de la ventana de correlacion.
    for i in $(seq 1 10); do
      docker exec clab-fttx-lab-objetivo-vuln sh -c "echo '<38>'$(date '+%b %d %H:%M:%S')' objetivo-vuln sshd[70'$i']: Failed password for root from $IP port 500'$i' ssh2' | nc -u -w1 $W 514" 2>/dev/null
    done
    sleep 6
    N=$(docker exec clab-fttx-lab-wazuh sh -c "grep -ac '$IP' /var/ossec/logs/alerts/alerts.json 2>/dev/null" 2>/dev/null || echo 0)
    echo "   $N alertas generadas desde $IP"
    docker exec clab-fttx-lab-wazuh sh -c "grep -a '$IP' /var/ossec/logs/alerts/alerts.json 2>/dev/null" 2>/dev/null | python3 -c "
import sys,json
lv=set()
for l in sys.stdin:
    try: lv.add(json.loads(l).get('rule',{}).get('level'))
    except: pass
if 10 in lv or 12 in lv: print('   Fuerza bruta correlacionada (nivel 10): OK')
elif lv: print('   Niveles vistos:', sorted(lv))
else: print('   sin alertas -- revisa el reenvio: sh lab/reenvio-syslog.sh')
"
    ;;
  *) echo "uso: $0 up|down|status|test" ;;
esac
