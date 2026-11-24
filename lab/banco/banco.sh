#!/bin/sh
# Control del laboratorio del banco (spec 2026-09-21-laboratorio-banco-design.md §5).
#
#   sh lab/banco/banco.sh up              despliega, arranca servicios/sshd/reenviadores/monitor y Wazuh
#   sh lab/banco/banco.sh down            lo baja
#   sh lab/banco/banco.sh status          estado de nodos y salud
#   sh lab/banco/banco.sh test            prueba de humo: conectividad y todos los servicios sanos (error si falla)
#   sh lab/banco/banco.sh comprobar-alertas  Wazuh de punta a punta: una alerta 100200 de prueba (error si no llega)
#   sh lab/banco/banco.sh cascada core-db tumba un servicio, muestra que cae y lo restaura
#   sh lab/banco/banco.sh restaurar       quita los bloqueos de ataque y reinicia los servicios
#                                         caidos (deja el banco sano tras una demo, sin down/up)
#   sh lab/banco/banco.sh atacar          menu de ataques (tecla 't'=tanda, 'c'=soak continuo)
#   sh lab/banco/banco.sh atacar auto     lanza TODA la bateria una vez, sin interaccion
#   sh lab/banco/banco.sh atacar continuo ataques variados SIN FIN para probar el MDR en continuo
#                                         (Ctrl+C para parar; --gap/--restaurar-cada/--semilla/--vueltas)
#   sh lab/banco/banco.sh vigilar         panel en vivo: servicios en verde/rojo y ultimos cambios
#   sh lab/banco/banco.sh comprobar-red   ¿conservan los nodos sus IPs 10.x y sshd? (tras reiniciar el equipo, no)
#   sh lab/banco/banco.sh claves-propias  una clave SSH de host propia en cada nodo (una sola vez por
#                                         contenedor); despues, 'aprovisionar' para fijar las huellas nuevas
#   sh lab/banco/banco.sh desaprovisionar deshace 'aprovisionar' (equipos sin usuario triaje ni sudoers, y
#                                         sin clave del conector): para darlos de alta a mano en Conectividad
#   sh lab/banco/banco.sh mdr-nuevo       el MDR como en un cliente NUEVO: perfil minimo y traza propia en
#                                         run/banco-nuevo/; la red se describe con el asistente de red
#   sh lab/banco/banco.sh aprovisionar    minimo privilegio del conector en los nodos del banco
#                                         (hace falta despues de cada 'up': containerlab recrea
#                                         los contenedores y el usuario/sudoers no sobreviven)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
RAIZ=$(cd "$HERE/../.." && pwd)
TOPO="$RAIZ/lab/topologias/banco.clab.yml"
P=clab-banco
red() { (cd "$RAIZ" && python3 -m lab.banco.red "$@"); }

# Nodos con sshd (el conector, el auditor y el equipo por dar de alta entran por SSH).
NODOS_SSH="web-banking api-movil swift-alliance middleware core-db hsm atm taquilla fw-core fw-edge mdr-siem auditor pagos-qr internet"

# Una clave SSH de host PROPIA por nodo: la imagen trae una sola para todos, y con ella fijar la huella de un
# equipo no lo distinguía de otro (ni el asistente de red sabía qué IPs son de la misma máquina). Una sola
# vez por contenedor (marca /etc/ssh/.claves_propias): un 'up' sobre contenedores que siguen no las cambia.
claves_propias() {
  for n in $NODOS_SSH; do
    # Tras matar el sshd viejo hay que ESPERAR a que suelte el puerto 22: si no, el nuevo muere al arrancar
    # y el nodo se queda sin sshd (pasó en vivo el 23/11).
    docker exec $P-$n sh -c 'if [ ! -f /etc/ssh/.claves_propias ]; then rm -f /etc/ssh/ssh_host_*; ssh-keygen -A >/dev/null && touch /etc/ssh/.claves_propias; pkill -f "^sshd: /usr/sbin/sshd" 2>/dev/null; i=0; while pgrep -f "^sshd: /usr/sbin/sshd" >/dev/null && [ $i -lt 50 ]; do sleep 0.1; i=$((i+1)); done; fi; pgrep -f "^sshd: /usr/sbin/sshd" >/dev/null || /usr/sbin/sshd -E /var/log/banco/sshd.log' 2>/dev/null || true
  done
}

# Las IP que añade el lanzador para rotar el origen de un ataque (`ip addr add` en la misma /24 que la del
# nodo) quedan marcadas «secondary» por el kernel: se quitan todas. Las de Containerlab son primarias.
quitar_alias() {
  for c in $(docker ps --format '{{.Names}}' | grep "^$P-"); do
    docker exec $c sh -c 'ip -4 -o addr show | awk "/ secondary / {print \$4, \$2}" | while read a d; do ip addr del "$a" dev "$d"; done' 2>/dev/null || true
  done
}

# ¿Conserva el banco su red? Tras reiniciar el equipo los contenedores vuelven SIN sus IPs 10.x (las pone el
# despliegue) ni sshd: el MDR no podría escanear ni contener, y nada lo decía (24/11). Se mira en mdr-siem.
red_viva() {
  docker exec $P-mdr-siem sh -c 'ip -4 -o addr show' 2>/dev/null | grep -q ' 10\.100\.0\.10/' \
    && docker exec $P-mdr-siem sh -c 'pgrep -f "^sshd: /usr/sbin/sshd"' >/dev/null 2>&1
}
aviso_red() {
  echo "✗ El banco perdió su red (¿se reinició el equipo?): los nodos no tienen sus IPs 10.x o sshd está parado." >&2
  echo "  Recréalo:  sh lab/banco/banco.sh down && sh lab/lab.sh up banco   (después, aprovisionar o el alta en Conectividad)" >&2
}

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
    # pagos-qr: equipo nuevo por dar de alta desde la consola (sshd si; ni servicio ni aprovisionamiento)
    claves_propias
    for n in web-banking api-movil swift-alliance middleware core-db hsm atm taquilla fw-core fw-edge mdr-siem auditor pagos-qr; do
      docker exec $P-$n sh -c 'pgrep -f "^sshd: /usr/sbin/sshd" >/dev/null || /usr/sbin/sshd -E /var/log/banco/sshd.log; touch /var/log/banco/access.log /var/log/banco/auth.log'
      # I2: sshd y los servicios HTTP escuchan en 0.0.0.0, es decir tambien en eth0 (gestion),
      # que no pasa por ningun cortafuegos del banco. Sin esta regla, alguien con acceso a la
      # red de gestion (p.ej. 'internet', que solo deberia llegar por el plano de datos 10.x a
      # traves de fw-edge/fw-core) podria saltarse los dos cortafuegos entrando por eth0
      # directamente. 'docker exec' y el syslog UDP de salida hacia Wazuh no usan la red de
      # datos y no se ven afectados; el conector sigue entrando por eth1 (10.x) desde mdr-siem.
      docker exec $P-$n sh -c 'iptables -A INPUT -i eth0 -p tcp -j DROP'
      CMD=$(red servicio $n)
      if [ -n "$CMD" ]; then docker exec -d $P-$n sh -c "$CMD"; fi
      # La imagen banco-nodo:1 puede traer una reenviador.py anterior (sin --auth/--telnet): se copia
      # la actual a CADA nodo antes de arrancarla, o un flag nuevo mataría el reenviador al arrancar
      # (argparse: "unrecognized arguments"). Mismo criterio que el señuelo telnet de atm.
      docker cp "$HERE/reenviador.py" $P-$n:/opt/banco/reenviador.py 2>/dev/null || true
      docker exec -d $P-$n python3 /opt/banco/reenviador.py --nodo $n --destino "$W:514" \
        --sshd /var/log/banco/sshd.log --web /var/log/banco/access.log --auth /var/log/banco/auth.log
    done
    # Señuelo telnet EXPUESTO en atm (familia servicio_expuesto): "connect from <ip> (<ip>)" -> Wazuh
    # (regla de fábrica 5602, grupo telnetd) vía un reenviador --telnet. El auditor lo marca expuesto
    # (hallazgos). Se copian por si la imagen es anterior a estos ficheros.
    docker cp "$HERE/telnet_expuesto.py" $P-atm:/opt/banco/telnet_expuesto.py 2>/dev/null || true
    docker cp "$HERE/reenviador.py" $P-atm:/opt/banco/reenviador.py 2>/dev/null || true
    docker exec $P-atm sh -c 'touch /var/log/banco/telnet.log'
    docker exec -d $P-atm python3 /opt/banco/telnet_expuesto.py 23 /var/log/banco/telnet.log
    docker exec -d $P-atm python3 /opt/banco/reenviador.py --nodo atm --destino "$W:514" --telnet /var/log/banco/telnet.log
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
    red_viva || aviso_red
    echo "== Salud (ultima muestra) =="; salud
    ;;
  test)
    # Termina con error si falla alguna comprobación: el arranque desatendido (servicio-mdr.sh) se para.
    FALLOS=0
    echo "-- 1. internet -> web-banking (a traves de fw-edge y fw-core)"
    docker exec $P-internet curl -s -m 3 -o /dev/null -w '   HTTP %{http_code}\n' http://10.10.0.10:443/ || { echo "   FALLO"; FALLOS=$((FALLOS+1)); }
    echo "-- 2. mdr-siem llega a los dos cortafuegos"
    for ip in 10.0.0.1 10.0.0.254; do
      if docker exec $P-mdr-siem ping -c1 -W2 $ip >/dev/null 2>&1; then echo "   $ip OK"; else echo "   $ip FALLO"; FALLOS=$((FALLOS+1)); fi
    done
    echo "-- 3. Todos los servicios sanos"
    sleep 3
    salud | python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}').get('estados',{}); m=[k for k,v in d.items() if v!='ok']; print('   OK' if d and not m else f'   CAIDOS: {m or \"sin datos\"}'); sys.exit(0 if d and not m else 1)" || FALLOS=$((FALLOS+1))
    if [ "$FALLOS" -gt 0 ]; then echo "banco.sh test: $FALLOS comprobación(es) fallida(s)" >&2; exit 1; fi
    ;;
  comprobar-alertas)
    # Wazuh de punta a punta: una conexión sin banner SSH desde el auditor a web-banking (sshd la registra,
    # el reenviador la manda a Wazuh) tiene que acabar en alerts.json como regla 100200. Inofensivo: el
    # auditor es un activo de gestión del perfil, y el MDR, si está en marcha, lo trata como legítimo.
    W=clab-red-cliente-wazuh
    MAX=${ALERTAS_ESPERA_MAX:-120}
    # un Wazuh recién levantado puede no haber escrito aún ninguna alerta: entonces son 0 líneas
    ANTES=$(docker exec $W sh -c 'wc -l < /var/ossec/logs/alerts/alerts.json 2>/dev/null || echo 0')
    ANTES=$((ANTES + 0))
    echo "-- conexion de prueba: auditor -> web-banking:22 (sin banner SSH)"
    docker exec $P-auditor sh -c "printf 'comprobar-alertas\r\n' | nc -w3 10.10.0.10 22 >/dev/null 2>&1; true"
    T=0
    until docker exec $W sh -c "tail -n +$((ANTES + 1)) /var/ossec/logs/alerts/alerts.json" | grep -q '"id":"100200"'; do
      if [ "$T" -ge "$MAX" ]; then
        echo "comprobar-alertas: Wazuh no generó la alerta 100200 en $MAX s (revisa el reenviador de web-banking y Wazuh)" >&2
        exit 1
      fi
      sleep 2; T=$((T + 2))
    done
    echo "OK: Wazuh generó la alerta 100200"
    ;;
  cascada)
    S="${2:?uso: banco.sh cascada <servicio>}"
    echo "Tumbando $S (su servicio HTTP)..."
    docker exec $P-$S sh -c "pkill -f 'servicio.py --nombre $S'" || true
    sleep 6; echo "Salud con $S caido:"; salud
    CMD=$(red servicio $S); docker exec -d $P-$S sh -c "$CMD"
    sleep 6; echo "Salud tras restaurar:"; salud
    ;;
  desaprovisionar)
    # Lo contrario de 'aprovisionar' (lab/scripts/aprovisionar-minimo-privilegio.sh): el banco como un cliente
    # al que aún no se ha dado de alta. El acceso se vuelve a dar desde Conectividad (paquete de alta).
    echo "== Desaprovisionando: sin usuario triaje, sudoers ni envoltorio en los equipos =="
    for par in $(red nodos) fw-core:10.0.0.1 fw-edge:10.0.0.254 pagos-qr:10.70.0.10; do
      n=${par%%:*}
      [ "$n" = mdr-siem ] && continue
      docker exec $P-$n sh -c 'deluser triaje 2>/dev/null; rm -rf /home/triaje; rm -f /etc/sudoers.d/conector-triaje /usr/local/sbin/mdr-accion; sed -i "/^# >>> conector-triaje/,/^# <<< conector-triaje/d" /etc/sudoers 2>/dev/null; true' || true
      echo "   $n"
    done
    echo "== Sin clave del conector ni huellas fijadas en el nodo de gestión (mdr-siem) =="
    docker exec $P-mdr-siem sh -c 'rm -f /root/.ssh/triaje /root/.ssh/triaje.pub /root/.ssh/known_hosts_triaje' || true
    echo "Hecho. Para volver al banco aprovisionado: sh lab/banco/banco.sh aprovisionar"
    ;;
  mdr-nuevo)
    # Como un cliente nuevo (mismo recorrido que 'oficina.sh mdr'): el servicio arranca con el perfil mínimo y
    # la red se describe con el asistente de red. Lo que exporta el asistente se copia a run/banco-nuevo/
    # (perfil.yml, postura.json, politica.yml) y se vuelve a ejecutar. Retoma la traza más reciente de ahí.
    cd "$RAIZ"
    D=run/banco-nuevo
    mkdir -p $D
    [ -f $D/perfil.yml ] || python3 -m prototipo.herramientas.perfil_minimo --gestion 10.100.0.10 \
      --rango 10.10.0.0/24 --rango 10.20.0.0/24 --rango 10.30.0.0/24 --rango 10.40.0.0/24 \
      --rango 10.50.0.0/24 --rango 10.60.0.0/24 --rango 10.200.0.0/24 --rango 10.210.0.0/24 --salida $D/perfil.yml
    [ -f $D/postura.json ] || echo '{"nodos": {}}' > $D/postura.json
    W=clab-red-cliente-wazuh
    docker ps --format '{{.Names}}' | grep -q "^$W$" || { echo "Wazuh no está en marcha: sh lab/lab.sh up banco"; exit 1; }
    red_viva || { aviso_red; exit 1; }
    pkill -9 -f "python3 -m prototipo(\.servicio)?\.stream" 2>/dev/null || true
    docker exec "$W" pkill -f "tail -n0 -F /var/ossec/logs/alerts/alerts.json" 2>/dev/null || true
    sleep 1
    export TRIAJE_NODO_GESTION=clab-banco-mdr-siem            # el escaneo y el conector salen de mdr-siem
    export TRIAJE_SSH_PLAZO_CONEXION=15
    export TRIAJE_SALUD_CONTENEDOR=clab-banco-mdr-siem:/var/log/banco/salud.jsonl
    export TRIAJE_ASISTENTE_ABIERTO=1 TRIAJE_CONECTIVIDAD_ABIERTA=1 TRIAJE_POLITICA_ABIERTA=1   # laboratorio
    if [ -f $D/politica.yml ]; then export TRIAJE_POLITICA=$D/politica.yml; fi
    SALIDA=$(ls -t $D/trazas-*.jsonl 2>/dev/null | head -n 1)
    [ -n "$SALIDA" ] || SALIDA="$D/trazas-$(date +%F-%H%M).jsonl"
    echo "→ MDR del banco como cliente nuevo: perfil $D/perfil.yml · traza $SALIDA"
    echo "  Consola: http://127.0.0.1:8787  ·  Ctrl+C para detener"
    docker exec "$W" sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
      | python3 -m prototipo.servicio.stream - $D/perfil.yml $D/postura.json --salida "$SALIDA" --web
    ;;
  comprobar-red)
    if red_viva; then echo "red del banco: ok (IPs 10.x y sshd en su sitio)"; else aviso_red; exit 1; fi
    ;;
  claves-propias)
    echo "== Clave SSH de host propia en cada nodo (solo en los que aún tienen la de la imagen) =="
    claves_propias
    echo "Hecho. Las huellas han cambiado: fija las nuevas con  sh lab/banco/banco.sh aprovisionar"
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
  restaurar)
    # Deja el banco sano tras una demo, sin un down/up completo: quita las reglas DROP por IP de
    # origen (los bloqueos que aplico el MDR al contener, incluidas las IP rotativas de los ataques)
    # y reinicia los servicios. Conserva el bloqueo de gestion eth0. Util cuando aprobar un ataque
    # interno (p.ej. K1) tumbo la cascada.
    echo "== Restaurando: quito bloqueos de ataque y reinicio los servicios =="
    for n in web-banking api-movil swift-alliance middleware core-db hsm atm fw-core fw-edge; do
      docker exec $P-$n sh -c '
        iptables -S 2>/dev/null | grep -E "^-A (INPUT|FORWARD) -s .* -j DROP" | sed "s/^-A/-D/" | \
          while read -r regla; do iptables $regla 2>/dev/null || true; done' 2>/dev/null || true
    done
    for n in $(red servicios); do
      docker exec $P-$n sh -c "pkill -f 'servicio.py --nombre $n'" 2>/dev/null || true
      CMD=$(red servicio $n); docker exec -d $P-$n sh -c "$CMD"
    done
    echo "== Quito las IP de origen que añadieron los ataques rotados =="
    quitar_alias
    echo "== Servicios reiniciados; esperando al monitor... =="
    sleep 8
    echo "== Salud =="
    salud | python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}').get('estados',{}); m=[k for k,v in d.items() if v!='ok']; print('   TODOS OK' if d and not m else f'   CAIDOS: {m or \"sin datos\"}')"
    ;;
  vigilar)
    cd "$RAIZ" && exec python3 -m lab.banco.panel
    ;;
  atacar)
    # pasa el resto a demo:
    #   atacar                      menú interactivo (incluye la tecla 'c' = tanda continua / soak)
    #   atacar auto [reps] [gap]    tanda automática: toda la batería una vez (o 'reps' veces)
    #   atacar continuo [opciones]  SOAK: ataques variados SIN FIN hasta Ctrl+C (alias: soak)
    #                               opciones: --gap S --restaurar-cada N --semilla S --vueltas N
    #   detalle de comandos         TODAS las modalidades (menu, auto, continuo) muestran por defecto
    #                               el nodo y el comando exacto de cada ataque (no caja negra);
    #                               --sin-detalle / -q lo silencia en las tandas (tecla 'v' en el menu)
    shift
    cd "$RAIZ" && exec python3 -m lab.banco.demo "$@"
    ;;
  *) echo "uso: $0 up|down|status|test|cascada <servicio>|restaurar|aprovisionar|vigilar|atacar [auto|continuo]" ;;
esac
