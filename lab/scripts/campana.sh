#!/bin/sh
# Genera una campaña de actividad REAL contra el laboratorio y la congela en disco.
#
#   sh lab/scripts/campana.sh <id-campaña>
#
# Lanza ataques reales (no inyección sintética) que dejan rastro en auth.log y
# llegan a Wazuh por el reenvío. Congela alerts.json fuera del contenedor ANTES
# de cualquier destroy, porque en Containerlab el contenedor es efímero.
set -e
ID="${1:?uso: sh lab/scripts/campana.sh <id-campaña>}"
HERE=$(dirname "$0")
DEST="$HERE/../campañas/$ID"
WZ=clab-red-cliente-wazuh
AUDITOR=clab-red-cliente-auditor
ATACANTE=clab-red-cliente-puesto
AUDITOR_IP=$(docker inspect $AUDITOR --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
mkdir -p "$DEST"

# Marca temporal de inicio, para la ficha
INICIO=$(date -u +%Y-%m-%dT%H:%M:%S+0000)

# El ATAQUE se lanza desde 'puesto' (un nodo de la LAN comprometido), NO desde el
# auditor. Es deliberado: el auditor es nuestro instrumento de medida y su tráfico
# se etiqueta PROPIA; si atacara desde él, todos los ataques reales caerían como
# PROPIA y se descartarían. 'puesto' representa un atacante interno legítimo.
echo "== Preparando el nodo atacante (puesto) =="
docker exec $ATACANTE sh -c 'command -v ssh >/dev/null 2>&1 || apk add --no-cache openssh-client >/dev/null 2>&1' || true

echo "== Fuerza bruta SSH real desde puesto contra objetivo-vuln =="
# El sshd de Metasploitable es de 2007: hay que rebajar los algoritmos del
# cliente o la conexión muere antes de la fase de contraseña y no deja rastro.
docker exec $ATACANTE sh -c '
  for i in $(seq 1 10); do
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
        -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no \
        -o PreferredAuthentications=password \
        root@192.168.1.30 true 2>/dev/null || true
  done'

echo "== Logins fallidos BENIGNOS desde el admin declarado (borde) -> FP =="
# Un administrador legitimo que se equivoca de contrasena produce la MISMA senal
# que un ataque contra un servicio expuesto. Lo que lo separa es el origen. Su IP
# se declara en la ficha (legitimos), y el etiquetado lo marca FP.
ADMIN=clab-red-cliente-borde
docker exec $ADMIN sh -c 'command -v ssh >/dev/null 2>&1 || apk add --no-cache openssh-client >/dev/null 2>&1' || true
docker exec $ADMIN sh -c '
  for i in 1 2 3; do
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
        -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no \
        -o PreferredAuthentications=password \
        admin@192.168.1.30 true 2>/dev/null || true
  done'
ADMIN_IP=192.168.1.1

echo "== Escaneo de puertos (desde el auditor: sera PROPIA) =="
docker exec $AUDITOR nmap -Pn --top-ports 50 192.168.1.30 >/dev/null 2>&1 || true

echo "== esperando a que Wazuh procese =="
sleep 6

echo "== Congelando alerts.json =="
docker exec $WZ sh -c 'cat /var/ossec/logs/alerts/alerts.json' > "$DEST/alerts.json"

echo "== Escribiendo la ficha de campaña =="
cat > "$DEST/campaña.yml" <<YML
id: $ID
fecha: $(date -u +%Y-%m-%d)
ataques:
  - escenario: fuerza bruta SSH
    objetivo: objetivo-vuln
    desde: puesto
  - escenario: logins fallidos benignos (admin legitimo)
    objetivo: objetivo-vuln
    desde: borde
  - escenario: escaneo de puertos
    objetivo: objetivo-vuln
    desde: auditor
auditor:
  ips: ["$AUDITOR_IP"]
  cuando: "$INICIO"
legitimos:
  ips: ["$ADMIN_IP"]
YML

echo "== Auditando la postura (hallazgos.json) =="
sh "$HERE/auditar.sh" "$DEST/hallazgos.json"

N=$(grep -c . "$DEST/alerts.json" 2>/dev/null || echo 0)
echo "== Campaña '$ID' congelada en $DEST ($N alertas) =="
