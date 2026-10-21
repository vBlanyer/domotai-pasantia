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
  # La variante viva (README) cuelga portatil-wazuh de la red de compose: si sigue ahí,
  # `compose down` falla con «active endpoints» y no limpia nada. Se quita primero.
  docker rm -f portatil-wazuh >/dev/null 2>&1 || true
  docker compose -f "$CF" down
  exit 0
fi

echo "== 1. Nodos (Docker plano) =="
# --build: con image:+build:, un tag viejo se reusa en silencio y la demo correría binarios
# antiguos (la lección documentada del banco); reconstruir con caché cuesta segundos.
docker compose -f "$CF" up -d --build
# Se sondea el PUERTO, no el proceso: sshd reescribe su título («sshd: /usr/sbin/sshd …») y el
# pgrep -x de busybox no lo casa. Con tope: si en 60 s no escucha, algo va mal y se dice.
i=0
until docker exec portatil-objetivo nc -z 127.0.0.1 22 2>/dev/null; do
  i=$((i + 1)); [ $i -gt 60 ] && { echo "ERROR: sshd no escucha en el objetivo"; exit 1; }
  sleep 1
done
IP_OBJ=$(docker inspect -f '{{(index .NetworkSettings.Networks "portatil_default").IPAddress}}' portatil-objetivo)
IP_GES=$(docker inspect -f '{{(index .NetworkSettings.Networks "portatil_default").IPAddress}}' portatil-gestion)
for ip in "$IP_OBJ" "$IP_GES"; do
  # Una IP vacía o pegada (nodo en varias redes) envenenaría el perfil y el keyscan.
  echo "$ip" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' \
    || { echo "ERROR: IP ilegible de docker inspect: '$ip'"; exit 1; }
done
echo "   objetivo=$IP_OBJ · gestion=$IP_GES"

echo "== 2. Mínimo privilegio del conector (el script oficial, con sus comprobaciones) =="
# Sin pipe a tail: POSIX sh no tiene pipefail y un fallo del aprovisionador quedaría
# enmascarado — la demo seguiría SIN la garantía de mínimo privilegio.
SALIDA_APROV=$(TRIAJE_NODO_GESTION=portatil-gestion \
  sh "$HERE/lab/scripts/aprovisionar-minimo-privilegio.sh" portatil-objetivo "$IP_OBJ" 2>&1) \
  || { echo "$SALIDA_APROV" | tail -15; echo "ERROR: el aprovisionamiento falló"; exit 1; }
echo "$SALIDA_APROV" | tail -4

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

# El origen de la alerta de muestra (el «atacante»); -wF: literal y de palabra completa,
# que 192.168.1.10 sin escapar casaría también 192.168.1.100.
ATACANTE=192.168.1.10
echo "== 5. La contención, vista desde DENTRO del objetivo =="
if docker exec portatil-objetivo iptables -L INPUT -n | grep -wF -- "$ATACANTE"; then
  echo "== 6. Reversión (cierra el ciclo) =="
  TRIAJE_NODO_GESTION=portatil-gestion TRIAJE_SSH_MODO=clave \
    python3 -m prototipo.revertir "$GEN/traza.jsonl" d0 --motivo "demo portátil: fin de la prueba"
  if docker exec portatil-objetivo iptables -L INPUT -n | grep -qwF -- "$ATACANTE"; then
    echo "   ERROR: la regla sigue puesta"; exit 1
  fi
  echo "   objetivo limpio: la regla se quitó y quedó trazado"
else
  echo "   (sin regla: la decisión se rechazó o quedó retenida)"
fi

echo
echo "Traza encadenada: $GEN/traza.jsonl · los contenedores siguen arriba"
echo "Apagar: sh lab/portatil/demo.sh down"
