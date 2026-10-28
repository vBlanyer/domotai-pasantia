#!/bin/sh
# Demo de GEOLOCALIZACIÓN observable, SIN contenedores. Inyecta una campaña SINTÉTICA de ataques con
# IPs de origen PÚBLICAS de varios países por el PIPELINE REAL (normalizador -> motor -> traza -> visor),
# para que la vista «Ubicaciones» del tablero se encienda con marcadores por país y cada decisión
# muestre país + ASN + (si TRIAJE_RDNS=1) DNS inverso.
#
#   sh lab/geo_demo/geo-demo.sh                        arranca el daemon web y va inyectando ataques
#   sh lab/geo_demo/geo-demo.sh --pausa 0.3 --por-pais 2   más denso / más rápido
#   PUERTO=9000 sh lab/geo_demo/geo-demo.sh            otro puerto
#   TRIAJE_RDNS=1 sh lab/geo_demo/geo-demo.sh          además resuelve el DNS inverso (egreso, opt-in)
#   Ctrl-C para parar.
#
# Requisitos: solo Python 3 + PyYAML (los del repo). NO toca el laboratorio ni el corpus de evaluación
# (la traza va aparte, run/trazas-geo-demo.jsonl). Escenario claramente sintético («[DEMO SINTÉTICA]»
# en el evento crudo): simula el caso de producción (IPs públicas) que el lab real —con IPs de
# documentación/internas— no puede mostrar porque, por diseño honesto, no geolocalizan.
set -e
HERE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$HERE"
PERFIL="$HERE/prototipo/perfiles/bancario.yml"
HALLAZGOS="$HERE/lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json"
SALIDA="$HERE/run/trazas-geo-demo.jsonl"
PUERTO="${PUERTO:-8787}"
mkdir -p "$HERE/run"
: > "$SALIDA"   # arranca de cero: la demo no arrastra trazas de corridas anteriores

echo "== Demo de geolocalización (escenario sintético) =="
echo "  Abre  http://127.0.0.1:$PUERTO  ->  vista «Ubicaciones» (mapa por país) y «Decisiones»."
echo "  Cada ataque llega de una IP pública de un país distinto; el mapa se irá poblando."
echo "  Ctrl-C para parar.   (TRIAJE_RDNS=1 para además resolver el DNS inverso.)"
echo

# El generador emite alertas Wazuh CRUDAS; el daemon las normaliza, triaja y sirve el visor en vivo.
# --continuo mantiene abierta la tubería, así el daemon sigue arriba para navegar el tablero.
python3 -m lab.geo_demo.generador --continuo "$@" \
  | python3 -m prototipo.servicio.stream - "$PERFIL" "$HALLAZGOS" --web "$PUERTO" --salida "$SALIDA"
