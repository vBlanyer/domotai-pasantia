#!/bin/sh
# Reinicia el daemon MDR (--web) de un solo comando: mata el anterior, libera el puerto 8787 y
# relanza leyendo las alertas de Wazuh, con una traza NUEVA (evita id_decision duplicados).
#
#   sh reiniciar.sh                 # modo plantilla (rápido, ideal para probar la UI)
#   sh reiniciar.sh --con-llm       # EXPERIMENTAL: justificador LLM + RAG (necesita el llama-server;
#                                   #   sin GPU tarda minutos por alerta; sin servidor arranca sin LLM)
#   sh reiniciar.sh --agente        # EXPERIMENTAL: mitigación con el agente ReAct (mismos requisitos)
#   (cualquier flag extra de prototipo.stream se pasa tal cual)
#
# Ctrl+C para detener. Requiere el banco levantado (sh lab/lab.sh up banco) y aprovisionado.
set -e
RAIZ=$(cd "$(dirname "$0")" && pwd)
cd "$RAIZ"

PERFIL="prototipo/perfiles/bancario.yml"
HALLAZGOS="lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json"
WAZUH="clab-red-cliente-wazuh"
mkdir -p run
SALIDA="run/trazas-$(date +%F-%H%M).jsonl"

echo "→ deteniendo el daemon anterior (si hay)…"
pkill -9 -f "python3 -m prototipo.stream" 2>/dev/null || true
pkill -9 -f "tail -n0 -F /var/ossec/logs/alerts/alerts.json" 2>/dev/null || true
sleep 1

if ! docker ps --format '{{.Names}}' | grep -q "^${WAZUH}$"; then
  echo "✗ El contenedor '${WAZUH}' no está corriendo. Levanta el banco: sh lab/lab.sh up banco" >&2
  exit 1
fi

# El `tail` de las alertas corre DENTRO del contenedor de Wazuh: el pkill de arriba (en el host, sin
# permisos sobre procesos root del contenedor) no lo alcanza, y quedaba uno huérfano por reinicio.
docker exec "$WAZUH" pkill -f "tail -n0 -F /var/ossec/logs/alerts/alerts.json" 2>/dev/null || true

export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
echo "→ relanzando daemon --web (traza: ${SALIDA})"
echo "  Abre http://127.0.0.1:8787  ·  Ctrl+C para detener"
docker exec "$WAZUH" sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
  | python3 -m prototipo.stream - "$PERFIL" "$HALLAZGOS" --salida "$SALIDA" --web "$@"
