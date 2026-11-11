#!/bin/sh
# Control del laboratorio «oficina»: la red que el asistente de red descubre
# (documentacion/05-fase5-implementacion-del-prototipo/plan-asistente-de-red.md).
#
#   sh lab/oficina/oficina.sh up       despliega la red, arranca sshd, servicios simulados, reenviadores y Wazuh
#   sh lab/oficina/oficina.sh down     lo baja
#   sh lab/oficina/oficina.sh status   qué nodos están vivos
#   sh lab/oficina/oficina.sh test     comprueba desde el nodo mdr que llega a cada equipo, y que internet
#                                      solo entra por fw-borde
#   sh lab/oficina/oficina.sh atacar   fuerza bruta SSH desde internet contra srv-web01 (10 intentos)
#
# A propósito NO se prepara el acceso del conector en ningún equipo: se da con el paquete de alta de la
# vista Conectividad, como en un cliente.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
RAIZ=$(cd "$HERE/../.." && pwd)
TOPO="$RAIZ/lab/topologias/oficina.clab.yml"
P=clab-oficina
red() { (cd "$RAIZ" && python3 -m lab.oficina.red "$@"); }

case "${1:-up}" in
  up)
    if docker ps --format '{{.Names}}' | grep -q '^clab-banco-'; then
      echo "El banco está levantado: bájalo antes (sh lab/lab.sh down banco)."; exit 1
    fi
    if docker ps --format '{{.Names}}' | grep '^clab-red-cliente-' | grep -v -- '-wazuh$' | grep -q .; then
      echo "La red pequeña (red-cliente) está levantada: bájala antes (sh lab/lab.sh down)."; exit 1
    fi
    docker image inspect banco-nodo:1 >/dev/null 2>&1 || sh "$RAIZ/lab/banco/construir-imagen.sh"
    echo "== 1. Desplegando la oficina =="
    containerlab deploy -t "$TOPO"
    echo "== 2. Wazuh =="
    sh "$RAIZ/lab/scripts/wazuh-run.sh" up
    W=$(docker inspect clab-red-cliente-wazuh --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
    [ -n "$W" ] || { echo "Wazuh sin IP"; exit 1; }
    echo "== 3. sshd, servicios simulados y reenviadores =="
    for n in $(red nodos); do
      case "$n" in internet|mdr) continue ;; esac
      docker exec $P-$n sh -c 'mkdir -p /var/log/banco && touch /var/log/banco/sshd.log /var/log/banco/access.log'
      # Como en el banco (I2): sshd y los servicios escuchan también en eth0 (gestión), que no pasa por
      # ningún cortafuegos de la oficina. Solo se entra por el plano de datos.
      docker exec $P-$n sh -c 'iptables -C INPUT -i eth0 -p tcp -j DROP 2>/dev/null || iptables -A INPUT -i eth0 -p tcp -j DROP'
      docker cp "$RAIZ/lab/banco/servicio.py" $P-$n:/opt/banco/servicio.py 2>/dev/null || true
      docker cp "$RAIZ/lab/banco/reenviador.py" $P-$n:/opt/banco/reenviador.py 2>/dev/null || true
    done
    for n in $(red ssh); do
      # La imagen trae las claves del host generadas al construirse: todos los equipos tendrían la misma
      # huella. Cada equipo genera las suyas antes de arrancar sshd.
      docker exec $P-$n sh -c 'pkill -x sshd 2>/dev/null; rm -f /etc/ssh/ssh_host_*; ssh-keygen -A >/dev/null; /usr/sbin/sshd -E /var/log/banco/sshd.log'
      docker exec -d $P-$n python3 /opt/banco/reenviador.py --nodo $n --destino "$W:514" \
        --sshd /var/log/banco/sshd.log --web /var/log/banco/access.log
    done
    for n in $(red nodos); do
      CMD=$(red servicio $n)
      if [ -n "$CMD" ]; then docker exec -d $P-$n sh -c "$CMD"; fi
    done
    sleep 3
    echo "== Oficina en marcha. Prueba: sh lab/oficina/oficina.sh test =="
    ;;
  down)
    containerlab destroy -t "$TOPO" --cleanup 2>/dev/null || true
    sh "$RAIZ/lab/scripts/wazuh-run.sh" down 2>/dev/null || true
    ;;
  status)
    docker ps --format '{{.Names}}\t{{.Status}}' | grep "^$P-" || echo "La oficina no está levantada."
    ;;
  test)
    fallos=0
    for par in $(red ips); do
      n=${par%%:*}; ip=${par#*:}
      if docker exec $P-mdr ping -c1 -W2 "$ip" >/dev/null 2>&1; then echo "  ok   mdr → $n ($ip)"
      else echo "  FALLO mdr → $n ($ip)"; fallos=$((fallos+1)); fi
    done
    if docker exec $P-internet nc -z -w 3 172.16.10.10 22 >/dev/null 2>&1; then echo "  ok   internet → srv-web01:22 por fw-borde"
    else echo "  FALLO internet → srv-web01:22"; fallos=$((fallos+1)); fi
    if docker exec $P-internet sh -c 'ip route | grep -q "^default"'; then echo "  FALLO internet tiene ruta por defecto"; fallos=$((fallos+1))
    else echo "  ok   internet sin salida real"; fi
    [ "$fallos" -eq 0 ] && echo "== Todo en verde ==" || { echo "== $fallos fallo(s) =="; exit 1; }
    ;;
  atacar)
    echo "Fuerza bruta SSH desde internet (198.51.100.10) contra srv-web01 (172.16.10.10): 10 intentos"
    for i in 1 2 3 4 5 6 7 8 9 10; do
      docker exec $P-internet sh -c "sshpass -p 'mal$i' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o PreferredAuthentications=password -o PubkeyAuthentication=no -o ConnectTimeout=3 root@172.16.10.10 true" \
        >/dev/null 2>&1 || true
    done
    echo "Hecho. Mira la Consola del MDR."
    ;;
  *)
    sed -n '2,12p' "$0"; exit 2
    ;;
esac
