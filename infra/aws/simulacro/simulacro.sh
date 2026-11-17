#!/bin/sh
# Simulacro del arranque del MDR en AWS, sin cuenta ni coste. Renderiza la plantilla de arranque con
# OpenTofu (templatefile, como en un apply) y la ejecuta en un contenedor amazonlinux:2023 (la misma
# distribución que la AMI) con el paquete del release servido como fichero, un disco de bucle y dobles
# de systemctl y aws. Cuatro casos:
#   1. normal: instala, firma la traza, consola con token, disco montado, servicio habilitado;
#   2. sin disco de la traza: el arranque se para;
#   3. paquete con otra huella: se para y no instala nada;
#   4. secreto de la traza indicado pero ilegible: se para (no genera una clave nueva).
#
# Uso: sh infra/aws/simulacro/simulacro.sh [dist/mdr-<versión>.tar.gz]
# Necesita docker (contenedor --privileged para el disco de bucle), tofu y red para dnf.
set -eu
RAIZ=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
PAQ=$(realpath "${1:-$RAIZ/dist/mdr-1.9.1.tar.gz}")
[ -f "$PAQ" ] || { echo "falta el paquete $PAQ (genéralo con sh deploy/empaquetar.sh)"; exit 2; }
SHA=$(sha256sum "$PAQ" | cut -d' ' -f1)
NOMBRE=$(basename "$PAQ")
TRABAJO=$(mktemp -d)
trap 'rm -rf -- "$TRABAJO"' EXIT

cd "$RAIZ/infra/aws"
tofu init -backend=false -input=false >/dev/null

render() { # render SALIDA HUELLA SECRETO_TRAZA
  printf 'templatefile("templates/mdr_user_data.sh.tftpl", {region="eu-west-1", paquete_url="file:///paquete/%s", paquete_sha256="%s", perfil_url="", rangos="--rango 10.90.0.0/16", secreto_traza_arn="%s", secreto_operadores_arn="", llm_url="", llm_embed_url="", volumen="vol0simulacro"})\n' \
    "$NOMBRE" "$2" "$3" | tofu console | sed '1d;$d' > "$1"
}

correr() { # correr ARRANQUE CON_DISCO
  docker run --rm --privileged -e CON_DISCO="$2" \
    -v "$(dirname "$PAQ")":/paquete:ro -v "$1":/arranque.sh:ro -v "$RAIZ/infra/aws/simulacro/dentro.sh":/dentro.sh:ro \
    amazonlinux:2023 bash /dentro.sh
}

FALLOS=0
espera() { # espera NOMBRE SALIDA CONDICION
  if printf '%s\n' "$2" | grep -Eq "$3"; then echo "== $1: como se esperaba"; else echo "== $1: NO como se esperaba"; FALLOS=1; fi
  printf '%s\n' "$2" | sed 's/^/   /'
}

render "$TRABAJO/normal.sh" "$SHA" ""
render "$TRABAJO/huella.sh" "0000000000000000000000000000000000000000000000000000000000000000" ""
render "$TRABAJO/secreto.sh" "$SHA" "arn:aws:secretsmanager:eu-west-1:000000000000:secret:no-existe"

S=$(correr "$TRABAJO/normal.sh" si)
if printf '%s\n' "$S" | grep -q FALLO; then echo "== 1. normal: FALLA alguna comprobación"; FALLOS=1; printf '%s\n' "$S" | sed 's/^/   /'
else espera "1. normal" "$S" "^rc=0$"; fi
espera "2. sin disco de la traza" "$(correr "$TRABAJO/normal.sh" no)" "el disco de la traza no apareció"
espera "3. paquete con otra huella" "$(correr "$TRABAJO/huella.sh" si)" "instalado: no"
espera "4. secreto de la traza ilegible" "$(correr "$TRABAJO/secreto.sh" si)" "aws secretsmanager get-secret-value"
[ "$FALLOS" -eq 0 ] && echo "SIMULACRO: todo como se esperaba" || { echo "SIMULACRO: hay fallos"; exit 1; }
