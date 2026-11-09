#!/bin/sh
# Genera los PDF de los manuales en dos pasadas: la primera averigua en qué página cae cada sección
# (por los marcadores del PDF) y la segunda imprime con esos números en el índice.
#   CHROME=/ruta/a/chrome sh generar-pdf/generar.sh [usuario|produccion]   (sin argumento, los dos)
#   (desde documentacion/07-fase7-documentacion-e-informe-final)
set -e
D=$(cd "$(dirname "$0")" && pwd)

generar() {   # generar <nombre> <título> <línea de portada>
  TMP=$(mktemp -d)
  python3 "$D/convertir.py" "$D/../$1.md" "$TMP/manual.html" --titulo "$2" --sub "$3"
  node "$D/imprimir.mjs" "$TMP/manual.html" "$TMP/pasada1.pdf"
  python3 "$D/paginas.py" "$TMP/pasada1.pdf" "$TMP/paginas.json"
  python3 "$D/convertir.py" "$D/../$1.md" "$TMP/manual.html" "$TMP/paginas.json" --titulo "$2" --sub "$3"
  node "$D/imprimir.mjs" "$TMP/manual.html" "$D/../$1.pdf"
  rm -rf "$TMP"
}

case "${1:-todos}" in
  usuario|todos) generar manual-de-usuario "Manual de usuario" "Consola de detección y respuesta" ;;
esac
case "${1:-todos}" in
  produccion|todos) generar manual-de-produccion "Manual de producción" "Instalación, uso y mantenimiento" ;;
esac
