#!/bin/sh
# Arranca los servidores residentes de llama.cpp: el generador (justificador y agente) y el
# embedder (RAG).
#
# Por que un servidor y no un subproceso por llamada: el binario llama-simple hace
# completacion cruda, no aplica la plantilla de chat del modelo, no acepta control de
# temperatura y recarga el modelo entero en cada invocacion. El servidor resuelve las
# cuatro cosas y ademas admite json-schema, que es lo que permite restringir la salida
# del agente al catalogo cerrado de acciones. Para el embedder la razon es solo el tiempo:
# el subproceso cargaba bge-m3 en cada llamada (unos 2 s por vector); residente, 100 ms.
#
# Los modelos quedan cargados entre llamadas, asi que la primera tarda y el resto no.
#
# Uso:  sh lab/scripts/llm-server.sh [RUTA_MODELO] [PUERTO]      generador (8080)
#       sh lab/scripts/llm-server.sh --embedder [RUTA_MODELO] [PUERTO]   embedder (8082)
#       sh lab/scripts/llm-server.sh --parar          para el generador
#       sh lab/scripts/llm-server.sh --parar-embedder para el embedder
#
# El generador usa por defecto el 8B generalista si existe, y cae al 1B si no. Las dos
# cuantizaciones publicas del Foundation-Sec-8B que selecciono la Fase 4 se comprobaron
# inservibles (plantillas de conversacion que no corresponden a la arquitectura): no se
# arrancan por defecto aunque esten en modelos/.
#
# El embedder arranca con --pooling cls, que es como se entreno bge-m3 y lo mismo que usa el
# subproceso (LLAMA_EMBED_POOLING): con la misma agrupacion y un texto por peticion, servidor y
# subproceso dan el mismo vector y el indice vale para los dos.

BIN="${LLAMA_SERVER_BIN:-$HOME/miniforge3/envs/triaje-ml/bin/llama-server}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

MODO=generador
case "$1" in
    --parar)
        [ -f /tmp/llm-server.pid ] && kill "$(cat /tmp/llm-server.pid)" 2>/dev/null && echo "generador detenido"
        rm -f /tmp/llm-server.pid; exit 0 ;;
    --parar-embedder)
        [ -f /tmp/embed-server.pid ] && kill "$(cat /tmp/embed-server.pid)" 2>/dev/null && echo "embedder detenido"
        rm -f /tmp/embed-server.pid; exit 0 ;;
    --embedder)
        MODO=embedder; shift ;;
esac

if [ "$MODO" = "embedder" ]; then
    PID="/tmp/embed-server.pid"; LOG="/tmp/embed-server.log"
    MODELO="${1:-$REPO/modelos/bge-m3-q8.gguf}"
    PUERTO="${2:-8082}"
    EXTRA="--embedding --pooling ${LLAMA_EMBED_POOLING:-cls}"
else
    PID="/tmp/llm-server.pid"; LOG="/tmp/llm-server.log"
    M8="$REPO/modelos/llama-3.1-8b-instruct-q4.gguf"
    M1="$REPO/modelos/llama-3.2-1b-q4.gguf"
    if [ -n "$1" ]; then MODELO="$1"; elif [ -f "$M8" ]; then MODELO="$M8"; else MODELO="$M1"; fi
    PUERTO="${2:-8080}"
    EXTRA=""
fi

[ -x "$BIN" ] || { echo "ERROR: no encuentro llama-server en $BIN"; exit 1; }
[ -f "$MODELO" ] || { echo "ERROR: no encuentro el modelo en $MODELO"; exit 1; }

# Se comprueba el puerto, no solo el pid: un pid viejo no dice si el puerto esta servido, y
# arrancar un segundo servidor sobre un puerto ocupado muere en silencio en el log.
if curl -sf "http://127.0.0.1:$PUERTO/health" >/dev/null 2>&1; then
    echo "ya hay un servidor respondiendo en el puerto $PUERTO; no se arranca otro"
    exit 0
fi
if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "ya hay un $MODO vivo (pid $(cat "$PID")) en el puerto $PUERTO"
    exit 0
fi

echo "arrancando $MODO  modelo: $(basename "$MODELO")  puerto: $PUERTO"
# -ngl 99 descarga todas las capas a la GPU; sin GPU llama.cpp lo ignora sin fallar.
# shellcheck disable=SC2086
nohup "$BIN" -m "$MODELO" --port "$PUERTO" --host 127.0.0.1 -ngl 99 $EXTRA >"$LOG" 2>&1 &
echo $! > "$PID"

# Esperar a que responda antes de devolver el control (el 8B tarda unos segundos).
i=0
while [ "$i" -lt 60 ]; do
    if curl -sf "http://127.0.0.1:$PUERTO/health" >/dev/null 2>&1; then
        echo "listo en http://127.0.0.1:$PUERTO   (log: $LOG)"
        if [ "$MODO" = "embedder" ]; then
            echo "para pararlo:  sh lab/scripts/llm-server.sh --parar-embedder"
        else
            echo "para pararlo:  sh lab/scripts/llm-server.sh --parar"
            echo "el RAG va mucho mas rapido con el embedder residente:  sh lab/scripts/llm-server.sh --embedder"
        fi
        exit 0
    fi
    i=$((i + 1)); sleep 1
done

echo "ERROR: el $MODO no respondio en 60 s. Revisa $LOG"
exit 1
