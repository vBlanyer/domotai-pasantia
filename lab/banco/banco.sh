#!/bin/sh
# Control del laboratorio del banco (spec 2026-09-21-laboratorio-banco-design.md §5).
#
#   sh lab/banco/banco.sh up              despliega, arranca servicios/sshd/reenviadores/monitor y Wazuh
#   sh lab/banco/banco.sh down            lo baja
#   sh lab/banco/banco.sh status          estado de nodos y salud
#   sh lab/banco/banco.sh test            prueba de humo: conectividad y todos los servicios sanos
#   sh lab/banco/banco.sh cascada core-db tumba un servicio, muestra que cae y lo restaura
#   sh lab/banco/banco.sh aprovisionar    minimo privilegio del conector en los nodos del banco
#                                         (hace falta despues de cada 'up': containerlab recrea
#                                         los contenedores y el usuario/sudoers no sobreviven)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
RAIZ=$(cd "$HERE/../.." && pwd)
TOPO="$RAIZ/lab/topologias/banco.clab.yml"
P=clab-banco
red() { (cd "$RAIZ" && python3 -m lab.banco.red "$@"); }

salud() {
  docker exec $P-mdr-siem sh -c "tail -n1 /var/log/banco/salud.jsonl 2>/dev/null" || true
}

case "${1:-up}" in
  up)
    # Cualquier nodo del plano de datos de la red pequena (no solo 'puesto'), salvo el Wazuh
    # compartido: red-cliente-openwrt u otras topologias tambien deben detectarse (minor).
    if docker ps --format '{{.Names}}' | grep '^clab-red-cliente-' | grep -v -- '-wazuh$' | grep -q .; then
      echo "La red pequena (red-cliente) esta levantada: bajala antes (sh lab/lab.sh down)."; exit 1
    fi
    docker image inspect banco-nodo:1 >/dev/null 2>&1 || sh "$HERE/construir-imagen.sh"
    echo "== 1. Desplegando el banco =="
    containerlab deploy -t "$TOPO"
    echo "== 2. Wazuh =="
    sh "$RAIZ/lab/scripts/wazuh-run.sh" up
    W=$(docker inspect clab-red-cliente-wazuh --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
    [ -n "$W" ] || { echo "Wazuh sin IP"; exit 1; }
    echo "== 3. sshd, servicios y reenviadores =="
    for n in web-banking api-movil swift-alliance middleware core-db hsm atm taquilla fw-core fw-edge mdr-siem auditor; do
      docker exec $P-$n sh -c 'pgrep -x sshd >/dev/null || /usr/sbin/sshd -E /var/log/banco/sshd.log; touch /var/log/banco/access.log'
      # I2: sshd y los servicios HTTP escuchan en 0.0.0.0, es decir tambien en eth0 (gestion),
      # que no pasa por ningun cortafuegos del banco. Sin esta regla, alguien con acceso a la
      # red de gestion (p.ej. 'internet', que solo deberia llegar por el plano de datos 10.x a
      # traves de fw-edge/fw-core) podria saltarse los dos cortafuegos entrando por eth0
      # directamente. 'docker exec' y el syslog UDP de salida hacia Wazuh no usan la red de
      # datos y no se ven afectados; el conector sigue entrando por eth1 (10.x) desde mdr-siem.
      docker exec $P-$n sh -c 'iptables -A INPUT -i eth0 -p tcp -j DROP'
      CMD=$(red servicio $n)
      if [ -n "$CMD" ]; then docker exec -d $P-$n sh -c "$CMD"; fi
      docker exec -d $P-$n python3 /opt/banco/reenviador.py --nodo $n --destino "$W:514" \
        --sshd /var/log/banco/sshd.log --web /var/log/banco/access.log
    done
    echo "== 4. Monitor de salud en mdr-siem =="
    docker exec -d $P-mdr-siem sh -c "python3 /opt/banco/monitor.py --intervalo 2 --salida /var/log/banco/salud.jsonl $(red monitor)"
    sleep 5
    echo "== Banco en marcha. Prueba: sh lab/banco/banco.sh test =="
    ;;
  down)
    containerlab destroy -t "$TOPO" 2>/dev/null || true
    sh "$RAIZ/lab/scripts/wazuh-run.sh" down 2>/dev/null || true
    echo "Banco detenido."
    ;;
  status)
    docker ps --filter name=$P --format '  {{.Names}}: {{.Status}}'
    echo "== Salud (ultima muestra) =="; salud
    ;;
  test)
    echo "-- 1. internet -> web-banking (a traves de fw-edge y fw-core)"
    docker exec $P-internet curl -s -m 3 -o /dev/null -w '   HTTP %{http_code}\n' http://10.10.0.10:443/ || echo "   FALLO"
    echo "-- 2. mdr-siem llega a los dos cortafuegos"
    for ip in 10.0.0.1 10.0.0.254; do docker exec $P-mdr-siem ping -c1 -W2 $ip >/dev/null 2>&1 && echo "   $ip OK" || echo "   $ip FALLO"; done
    echo "-- 3. Todos los servicios sanos"
    sleep 3
    salud | python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}').get('estados',{}); m=[k for k,v in d.items() if v!='ok']; print('   OK' if d and not m else f'   CAIDOS: {m or \"sin datos\"}')"
    ;;
  cascada)
    S="${2:?uso: banco.sh cascada <servicio>}"
    echo "Tumbando $S (su servicio HTTP)..."
    docker exec $P-$S sh -c "pkill -f 'servicio.py --nombre $S'" || true
    sleep 6; echo "Salud con $S caido:"; salud
    CMD=$(red servicio $S); docker exec -d $P-$S sh -c "$CMD"
    sleep 6; echo "Salud tras restaurar:"; salud
    ;;
  aprovisionar)
    # I6: minimo privilegio del conector en los nodos sobre los que actua. Hace falta despues
    # de cada 'up' porque containerlab recrea los contenedores (usuario 'triaje' y sudoers no
    # sobreviven). fw-core y fw-edge no estan en lab.banco.red (no tienen servicio HTTP propio
    # que auditar), por eso van con su IP conocida (ver lab/banco/verificaciones.md V1).
    export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
    echo "== Aprovisionando minimo privilegio (conector desde mdr-siem) =="
    FALLOS=""
    for par in $(red nodos) fw-core:10.0.0.1 fw-edge:10.0.0.254; do
      n=${par%%:*}; ip=${par##*:}
      echo "-- $n ($ip) --"
      sh "$RAIZ/lab/scripts/aprovisionar-minimo-privilegio.sh" "$P-$n" "$ip" || FALLOS="$FALLOS $n"
    done
    if [ -n "$FALLOS" ]; then echo "FALLO en:$FALLOS"; exit 1; fi
    echo "== Aprovisionamiento completo =="
    ;;
  *) echo "uso: $0 up|down|status|test|cascada <servicio>|aprovisionar" ;;
esac
