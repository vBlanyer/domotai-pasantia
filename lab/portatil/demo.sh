#!/bin/sh
# Demo portátil: el ciclo completo del MDR —alerta real -> decisión -> validación humana ->
# contención SSH con mínimo privilegio -> verificación -> reversión— en Docker PLANO, sin
# Containerlab. Empaqueta lo que validó el spike de portabilidad del 21/10.
#
#   sh lab/portatil/demo.sh          corre el ciclo completo (deja los contenedores arriba)
#   sh lab/portatil/demo.sh down     apaga y limpia los contenedores de la demo
#
# Requisitos: Docker con el plugin compose y Python 3 + PyYAML (los del repo). La imagen de los
# nodos se construye sola la primera vez. No toca el laboratorio Containerlab si está levantado.
set -e
HERE=$(cd "$(dirname "$0")/../.." && pwd)
CF="$HERE/lab/portatil/docker-compose.yml"
GEN="$HERE/run/portatil"
cd "$HERE"

if [ "${1:-}" = "down" ]; then
  docker compose -f "$CF" down
  exit 0
fi

echo "== 1. Nodos (Docker plano) =="
docker compose -f "$CF" up -d 2>&1 | tail -2
# Se sondea el PUERTO, no el proceso: sshd reescribe su título («sshd: /usr/sbin/sshd …») y el
# pgrep -x de busybox no lo casa. Con tope: si en 60 s no escucha, algo va mal y se dice.
i=0
until docker exec portatil-objetivo nc -z 127.0.0.1 22 2>/dev/null; do
  i=$((i + 1)); [ $i -gt 60 ] && { echo "ERROR: sshd no escucha en el objetivo"; exit 1; }
  sleep 1
done
IP_OBJ=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' portatil-objetivo)
IP_GES=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' portatil-gestion)
echo "   objetivo=$IP_OBJ · gestion=$IP_GES"

echo "== 2. Mínimo privilegio del conector (el script oficial, con sus comprobaciones) =="
TRIAJE_NODO_GESTION=portatil-gestion \
  sh "$HERE/lab/scripts/aprovisionar-minimo-privilegio.sh" portatil-objetivo "$IP_OBJ" | tail -4

echo "== 3. Perfil (el empresarial, con el activo apuntando al contenedor) y alerta normalizada =="
mkdir -p "$GEN"
sed "s/192\\.168\\.1\\.30/$IP_OBJ/g; s/^ip_gestion: .*/ip_gestion: $IP_GES/" \
  "$HERE/prototipo/perfiles/empresarial.yml" > "$GEN/perfil.yml"
# El lazo por lotes consume alertas NORMALIZADAS (el daemon en vivo normaliza solo).
python3 -m prototipo.ingesta "$HERE/lab/portatil/alerta-muestra.jsonl" "$GEN/alertas.jsonl" wazuh portatil

echo "== 4. El lazo con el conector REAL (origen interno -> la aprobación es tuya: 1 aprueba) =="
TRIAJE_NODO_GESTION=portatil-gestion TRIAJE_SSH_MODO=clave \
  python3 -m prototipo.lazo "$GEN/alertas.jsonl" "$GEN/perfil.yml" \
  "$HERE/lab/portatil/hallazgos.json" "$GEN/traza.jsonl"

echo "== 5. La contención, vista desde DENTRO del objetivo =="
if docker exec portatil-objetivo iptables -L INPUT -n | grep 192.168.1.10; then
  echo "== 6. Reversión (cierra el ciclo) =="
  TRIAJE_NODO_GESTION=portatil-gestion TRIAJE_SSH_MODO=clave \
    python3 -m prototipo.revertir "$GEN/traza.jsonl" d0 --motivo "demo portátil: fin de la prueba"
  if docker exec portatil-objetivo iptables -L INPUT -n | grep -q 192.168.1.10; then
    echo "   ERROR: la regla sigue puesta"; exit 1
  fi
  echo "   objetivo limpio: la regla se quitó y quedó trazado"
else
  echo "   (sin regla: la decisión se rechazó o quedó retenida)"
fi

echo
echo "Traza encadenada: $GEN/traza.jsonl · los contenedores siguen arriba"
echo "Apagar: sh lab/portatil/demo.sh down"
