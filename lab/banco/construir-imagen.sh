#!/bin/sh
# Construye la imagen banco-nodo:1 (una vez; despues el laboratorio se despliega sin descargar nada).
set -e
cd "$(dirname "$0")"
docker build -t banco-nodo:1 .
docker run --rm banco-nodo:1 sh -c 'python3 -c "import sys; print(sys.version.split()[0])" && ls /opt/banco'
