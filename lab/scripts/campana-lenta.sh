#!/bin/sh
# Campaña REAL de ATAQUE LENTO (experimento A): una fuerza bruta repartida en minutos, desde la IP
# declarada del administrador, para probar el punto ciego que el spike encontró.
#
#   sh lab/scripts/campana-lenta.sh <id-campaña>
#
# Por que existe: el unico rasgo que voltea un origen legitimo a amenaza es la rafaga de 60 s
# (6a regla, umbral 9). Un atacante que entra desde la maquina del admin PERO DESPACIO ---un intento
# cada ~18 s--- nunca junta 9 en 60 s, asi que el motor lo clasifica como actividad legitima: amenaza
# PERDIDA (falso negativo). El rasgo nuevo `n_origen_600s` (fallos del mismo origen en 10 min) SI lo
# ve. Esta campana genera esos casos con verdad declarada por el experimento para medir si el arbol
# descubre una regla de ventana larga estable (candidata a 7a regla determinista).
#
#   L1  fuerza bruta LENTA root@ desde el BORDE (IP del admin, declarada legitima)  -> reglas dicen FP; verdad VP
#
# Espaciado 18 s x 12 intentos ~= 200 s: n_origen_60s se queda en 3-4 (< umbral 9) y n_origen_600s ~= 12.
# La ventana de reenvio es generosa (90 s) porque el sello de Wazuh es de LLEGADA (un datagrama/seg).
# Correr DOS veces, una por particion (ver lab/dataset/particion.yml): -entrenamiento y -evaluacion.
set -e
ID="${1:?uso: sh lab/scripts/campana-lenta.sh <id-campaña>}"
HERE=$(dirname "$0")
DEST="$HERE/../campañas/$ID"
WZ=clab-red-cliente-wazuh
AUDITOR=clab-red-cliente-auditor
BORDE=clab-red-cliente-borde
OBJETIVO=clab-red-cliente-objetivo-vuln
OBJ_IP=192.168.1.30
BORDE_IP=192.168.1.1
AUDITOR_IP=$(docker inspect $AUDITOR --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
mkdir -p "$DEST"
ahora() { docker exec $WZ date -u +%Y-%m-%dT%H:%M:%S; }
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no -o PreferredAuthentications=password"
intento() {  # $1 contenedor, $2 usuario, $3 contrasena
  docker exec "$1" sh -c "sshpass -p '$3' $SSH $2@$OBJ_IP true >/dev/null 2>&1 || true"
}

INICIO=$(ahora)
echo "== Dejando el objetivo sin bloqueos previos del borde =="
docker exec $OBJETIVO sh -c "iptables -D INPUT -s $BORDE_IP -j DROP 2>/dev/null" || true
docker exec $BORDE sh -c 'command -v sshpass >/dev/null 2>&1 || apk add --no-cache openssh-client sshpass >/dev/null 2>&1' || true

echo "== L1 (borde, root@, fuerza bruta LENTA: 1 intento cada 18 s x 12) =="
T1=$(ahora)
i=1
while [ "$i" -le 12 ]; do
  intento $BORDE root "lento_$i"
  echo "   intento $i/12 a las $(ahora)"
  [ "$i" -lt 12 ] && sleep 18
  i=$((i + 1))
done
echo "   esperando al reenvio..."; sleep 90
T1F=$(ahora)

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
familia: acceso_credenciales
proposito: ataque lento (fuerza bruta repartida en minutos, evade la rafaga de 60 s) desde la IP declarada del admin; experimento A, verdad declarada
ataques:
  - escenario: L1 fuerza bruta LENTA root@ desde la IP declarada del administrador (equipo comprometido)
    objetivo: objetivo-vuln
    desde: borde
auditor:
  ips: ["$AUDITOR_IP"]
  cuando: "$INICIO+0000"
legitimos:
  ips: ["$BORDE_IP"]
verdad:
  - { origen: "$BORDE_IP", desde: "$T1", hasta: "$T1F", etiqueta: VP, motivo: "L1: fuerza bruta lenta desde la IP del admin (suplantacion o equipo comprometido); evade la rafaga de 60 s pero no la ventana de 600 s" }
YML

echo "== Auditando la postura (hallazgos.json) =="
sh "$HERE/auditar.sh" "$DEST/hallazgos.json"

echo "== Dejando el objetivo neutro =="
docker exec $OBJETIVO sh -c "iptables -D INPUT -s $BORDE_IP -j DROP 2>/dev/null" || true
N=$(grep -c . "$DEST/alerts.json" 2>/dev/null || echo 0)
echo "== Campaña '$ID' congelada en $DEST ($N alertas) =="
