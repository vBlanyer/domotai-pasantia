#!/bin/sh
# Arranca el servidor residente de llama.cpp que usa el justificador (generador_servidor).
#
# Por que un servidor y no un subproceso por llamada: el binario llama-simple hace
# completacion cruda, no aplica la plantilla de chat del modelo, no acepta control de
# temperatura y recarga el modelo entero en cada invocacion. El servidor resuelve las
# cuatro cosas y ademas admite json-schema, que es lo que permite restringir la salida
# del agente al catalogo cerrado de acciones.
#
# El modelo queda cargado entre llamadas, asi que la primera tarda y el resto no.
#
# Uso:  sh lab/scripts/llm-server.sh [RUTA_MODELO] [PUERTO]
#       sh lab/scripts/llm-server.sh --parar
#
# Por defecto usa el 8B especializado si existe, y cae al 1B si no.

BIN="${LLAMA_SERVER_BIN:-$HOME/miniforge3/envs/triaje-ml/bin/llama-server}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PID="/tmp/llm-server.pid"
LOG="/tmp/llm-server.log"

if [ "$1" = "--parar" ]; then
    [ -f "$PID" ] && kill "$(cat "$PID")" 2>/dev/null && echo "servidor detenido"
    rm -f "$PID"
    exit 0
fi

M8="$REPO/modelos/foundation-sec-8b-instruct-q4.gguf"
M1="$REPO/modelos/llama-3.2-1b-q4.gguf"
if [ -n "$1" ]; then MODELO="$1"; elif [ -f "$M8" ]; then MODELO="$M8"; else MODELO="$M1"; fi
PUERTO="${2:-8080}"

[ -x "$BIN" ] || { echo "ERROR: no encuentro llama-server en $BIN"; exit 1; }
[ -f "$MODELO" ] || { echo "ERROR: no encuentro el modelo en $MODELO"; exit 1; }

if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "ya hay un servidor vivo (pid $(cat "$PID")) en el puerto $PUERTO"
    exit 0
fi

echo "arrancando  modelo: $(basename "$MODELO")  puerto: $PUERTO"
# -ngl 99 descarga todas las capas a la GPU; sin GPU llama.cpp lo ignora sin fallar.
nohup "$BIN" -m "$MODELO" --port "$PUERTO" --host 127.0.0.1 -ngl 99 >"$LOG" 2>&1 &
echo $! > "$PID"

# Esperar a que responda antes de devolver el control (el 8B tarda unos segundos).
i=0
while [ "$i" -lt 60 ]; do
    if curl -sf "http://127.0.0.1:$PUERTO/health" >/dev/null 2>&1; then
        echo "listo en http://127.0.0.1:$PUERTO   (log: $LOG)"
        echo "para pararlo:  sh lab/scripts/llm-server.sh --parar"
        exit 0
    fi
    i=$((i + 1)); sleep 1
done

echo "ERROR: el servidor no respondio en 60 s. Revisa $LOG"
exit 1
