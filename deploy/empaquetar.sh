#!/bin/sh
# Genera el paquete que se entrega al cliente (proveedor; desde la raíz del repositorio):
#
#   sh deploy/empaquetar.sh [versión] [--sin-construir]
#
# Construye la consola web (npm), y deja en dist/mdr-<versión>.tar.gz un directorio mdr-<versión>/ con
# el programa sin tests ni perfiles del laboratorio, la herramienta mdr, las plantillas de deploy/,
# la consola construida, instalar.sh y VERSION. El cliente: tar -xzf … && cd mdr-… && sudo ./instalar.sh
set -eu
RAIZ=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$RAIZ"
VERSION="${1:-$(git describe --tags --always 2>/dev/null | sed 's/^v//')}"
case "$VERSION" in --*|"") VERSION=$(git describe --tags --always 2>/dev/null | sed 's/^v//') ;; esac
if [ "${1:-}" != "--sin-construir" ] && [ "${2:-}" != "--sin-construir" ]; then
  (cd visor && npm ci --silent && npm run build --silent)
fi
[ -f visor/dist/index.html ] || { echo "empaquetar: falta visor/dist (construye la consola)" >&2; exit 1; }

NOMBRE="mdr-$VERSION"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
D="$TMP/$NOMBRE"
mkdir -p "$D/visor"
cp -a prototipo bin "$D/"
cp -a visor/dist "$D/visor/"
mkdir -p "$D/deploy"
for f in deploy/*; do
  case "$f" in deploy/empaquetar.sh) ;; *) cp -a "$f" "$D/deploy/" ;; esac
done
cp deploy/instalar.sh "$D/instalar.sh"
echo "$VERSION" > "$D/VERSION"
rm -rf "$D/prototipo/tests" "$D/prototipo/perfiles"
find "$D" -name __pycache__ -type d -prune -exec rm -rf {} +
mkdir -p dist
tar -czf "dist/$NOMBRE.tar.gz" -C "$TMP" "$NOMBRE"
echo "dist/$NOMBRE.tar.gz ($(du -h "dist/$NOMBRE.tar.gz" | cut -f1))"
