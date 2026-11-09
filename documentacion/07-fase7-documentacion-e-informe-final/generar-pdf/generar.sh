#!/bin/sh
# Genera manual-de-usuario.pdf en dos pasadas: la primera averigua en qué página cae cada sección (por
# los marcadores del PDF) y la segunda imprime con esos números en el índice.
#   CHROME=/ruta/a/chrome sh generar-pdf/generar.sh      (desde documentacion/07-fase7-documentacion-e-informe-final)
set -e
D=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d)
python3 "$D/convertir.py" "$D/../manual-de-usuario.md" "$TMP/manual.html"
node "$D/imprimir.mjs" "$TMP/manual.html" "$TMP/pasada1.pdf"
python3 "$D/paginas.py" "$TMP/pasada1.pdf" "$TMP/paginas.json"
python3 "$D/convertir.py" "$D/../manual-de-usuario.md" "$TMP/manual.html" "$TMP/paginas.json"
node "$D/imprimir.mjs" "$TMP/manual.html" "$D/../manual-de-usuario.pdf"
rm -rf "$TMP"
