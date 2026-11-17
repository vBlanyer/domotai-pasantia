#!/bin/bash
# El laboratorio del banco + el MDR como servicio (unidad mdr-laboratorio, variante «laboratorio» del
# despliegue en AWS). En CADA arranque rehace el laboratorio desde cero, porque la red de Containerlab y
# Wazuh no sobreviven a un reinicio de la máquina, comprueba que está sano y que Wazuh genera alertas, y
# arranca el daemon leyendo las alertas de Wazuh. Si algo falla, sale con error y systemd lo reintenta.
#
# Es el equivalente desatendido de reiniciar.sh (que sigue siendo el de la terminal): las mismas
# variables, pero la traza en un fichero FIJO del disco persistente, así que la cadena firmada continúa
# entre encendidos (el daemon sigue la numeración de la traza que retoma). La clave de la traza y los
# analistas llegan por el entorno (EnvironmentFile=/etc/mdr/triaje.env).
set -euo pipefail
RAIZ=$(cd "$(dirname "$0")/../.." && pwd)
cd "$RAIZ"
WAZUH=clab-red-cliente-wazuh

echo "== Rehaciendo el laboratorio =="
sh lab/banco/banco.sh down
sh lab/lab.sh up banco
sh lab/banco/banco.sh aprovisionar
sh lab/banco/banco.sh test
sh lab/banco/banco.sh comprobar-alertas
SALIDA="${TRIAJE_SALIDA:-/var/lib/mdr/trazas-laboratorio.jsonl}"
# Lo que la traza daba por contenido ya no existe (equipos recreados): se anota como revertido, o el MDR
# suprimiría los ataques repetidos y la consola listaría contenciones fantasma.
python3 -m lab.banco.rehecho "$SALIDA"

export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
export TRIAJE_SALUD_CONTENEDOR=clab-banco-mdr-siem:/var/log/banco/salud.jsonl
export TRIAJE_GEOIP="${TRIAJE_GEOIP:-lab/geo_demo/geoip-muestra.csv}"
export TRIAJE_ASN="${TRIAJE_ASN:-lab/geo_demo/asn-muestra.csv}"

echo "== MDR en marcha (traza: $SALIDA; consola en http://127.0.0.1:8787) =="
docker exec "$WAZUH" sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
  | python3 -m prototipo.servicio.stream - prototipo/perfiles/bancario.yml \
      lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --salida "$SALIDA" --web
