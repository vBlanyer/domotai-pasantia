#!/bin/sh
# Campaña REAL de los casos en que las cinco reglas del clasificador determinista FALLAN, con la
# verdad declarada por el experimento (bloque 'verdad' de la ficha), no por la heuristica.
#
#   sh lab/scripts/campana-reglas-fallan.sh <id-campaña>
#
# Por que existe: en el dataset anterior, las etiquetas las generaban las mismas senales que usa
# el clasificador (origen declarado -> FP, postura -> VP), asi que su 1.000 era una tautologia y
# un modelo entrenado solo podria copiar las reglas. Ademas habia un confundido: el admin fallaba
# con 'admin@' (usuario inexistente, reglas 5710/5712) y el atacante con 'root@' (5760/5763), de
# modo que la regla de Wazuh delataba el origen. Aqui se cruzan los dos ejes:
#
#   E1  fuerza bruta root@   desde el BORDE (IP del admin, declarada legitima)  -> las reglas dicen FP; verdad VP
#   E2  error de contrasena y acceso correcto de msfadmin@ desde el PUESTO      -> las reglas dicen VP; verdad FP
#   E3  un solo error root@  desde el BORDE (el admin se equivoca)              -> reglas FP; verdad FP (5760 que es FP)
#   E4  fuerza bruta admin@  desde el PUESTO (usuario inexistente)              -> reglas VP; verdad VP (5710/5712 que son VP)
#
# Las ventanas son generosas (90 s) porque el sello de tiempo de Wazuh es de LLEGADA y el reenvio
# entrega la rafaga a un datagrama por segundo. Origenes distintos pueden solaparse; el mismo
# origen no: por eso E1/E2 van juntos y E3/E4 despues.
set -e
ID="${1:?uso: sh lab/scripts/campana-reglas-fallan.sh <id-campaña>}"
HERE=$(dirname "$0")
DEST="$HERE/../campañas/$ID"
WZ=clab-red-cliente-wazuh
AUDITOR=clab-red-cliente-auditor
PUESTO=clab-red-cliente-puesto
BORDE=clab-red-cliente-borde
OBJETIVO=clab-red-cliente-objetivo-vuln
OBJ_IP=192.168.1.30
PUESTO_IP=192.168.1.10
BORDE_IP=192.168.1.1
AUDITOR_IP=$(docker inspect $AUDITOR --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
mkdir -p "$DEST"
ahora() { docker exec $WZ date -u +%Y-%m-%dT%H:%M:%S; }
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no -o PreferredAuthentications=password"
intento() {  # $1 contenedor, $2 usuario, $3 contrasena
  docker exec "$1" sh -c "sshpass -p '$3' $SSH $2@$OBJ_IP true >/dev/null 2>&1 || true"
}

INICIO=$(ahora)
echo "== Dejando el objetivo sin bloqueos previos =="
for ip in $PUESTO_IP $BORDE_IP; do docker exec $OBJETIVO sh -c "iptables -D INPUT -s $ip -j DROP 2>/dev/null" || true; done
for c in $PUESTO $BORDE; do docker exec $c sh -c 'command -v sshpass >/dev/null 2>&1 || apk add --no-cache openssh-client sshpass >/dev/null 2>&1' || true; done

echo "== E1 (borde, root@, fuerza bruta) + E2 (puesto, msfadmin@, error y acceso) =="
T1=$(ahora)
for i in 1 2 3 4 5 6 7 8 9 10; do intento $BORDE root "mal_$i"; done &
intento $PUESTO msfadmin "msfadmni"          # el error de tecleo
sleep 3
intento $PUESTO msfadmin "msfadmin"          # y el acceso correcto (5715)
wait
echo "   esperando al reenvio..."; sleep 90
T1F=$(ahora)

echo "== E3 (borde, root@, un solo error) + E4 (puesto, admin@, fuerza bruta) =="
T2=$(ahora)
intento $BORDE root "olvidada"
for i in 1 2 3 4 5 6 7 8 9 10; do intento $PUESTO admin "mal_$i"; done
echo "   esperando al reenvio..."; sleep 90
T2F=$(ahora)

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
proposito: casos en que las reglas del clasificador determinista fallan; verdad declarada por el experimento
ataques:
  - escenario: E1 fuerza bruta root@ desde la IP declarada del administrador
    objetivo: objetivo-vuln
    desde: borde
  - escenario: E2 error de contrasena y acceso correcto de un usuario legitimo desde un origen no declarado
    objetivo: objetivo-vuln
    desde: puesto
  - escenario: E3 un solo error de contrasena del administrador (root@)
    objetivo: objetivo-vuln
    desde: borde
  - escenario: E4 fuerza bruta con usuario inexistente (admin@) desde el atacante
    objetivo: objetivo-vuln
    desde: puesto
auditor:
  ips: ["$AUDITOR_IP"]
  cuando: "$INICIO+0000"
legitimos:
  ips: ["$BORDE_IP"]
verdad:
  - { origen: "$BORDE_IP",  desde: "$T1", hasta: "$T1F", etiqueta: VP, motivo: "E1: fuerza bruta lanzada desde la IP del admin (suplantacion o equipo comprometido)" }
  - { origen: "$PUESTO_IP", desde: "$T1", hasta: "$T1F", etiqueta: FP, motivo: "E2: usuario legitimo que erro la contrasena y entro despues, desde un puesto no declarado" }
  - { origen: "$BORDE_IP",  desde: "$T2", hasta: "$T2F", etiqueta: FP, motivo: "E3: el administrador se equivoca una vez" }
  - { origen: "$PUESTO_IP", desde: "$T2", hasta: "$T2F", etiqueta: VP, motivo: "E4: fuerza bruta con usuario inexistente desde el atacante" }
YML

echo "== Auditando la postura (hallazgos.json) =="
sh "$HERE/auditar.sh" "$DEST/hallazgos.json"

echo "== Dejando el objetivo neutro =="
for ip in $PUESTO_IP $BORDE_IP; do docker exec $OBJETIVO sh -c "iptables -D INPUT -s $ip -j DROP 2>/dev/null" || true; done
N=$(grep -c . "$DEST/alerts.json" 2>/dev/null || echo 0)
echo "== Campaña '$ID' congelada en $DEST ($N alertas) =="
