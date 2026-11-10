# Evaluar un modelo de justificación en la máquina con GPU

Qué mide esta corrida y qué no:

- **No cambia VP, FP ni FN.** La clase (amenaza o no) la decide el motor determinista, así que la
  matriz sale igual con cualquier modelo: 87 VP · 2 FP · 211 VN · 0 FN, recall 1.000, FP 0.009,
  escalado 0.297. Eso ya lo fija `evaluacion/tests/test_canonicos.py`, sin modelo.
- **Mide el anclaje de la justificación (RNF-02).** El modelo justifica cada una de las 106 alertas
  soportadas de la partición de evaluación. La campaña cuenta cuántas justificaciones pasan la
  verificación de anclaje y cuántas se degradan a la plantilla, en total y por clase.
- **Referencia.** Llama-3.1-8B con RAG ancló 106/106 (`evaluacion/resultados/8b-con-rag/tabla.md`).

## 1. Preparar

```bash
git clone https://github.com/vBlanyer/domotai-pasantia.git   # o git pull si ya está
cd domotai-pasantia
```

Hace falta `llama-server` compilado con soporte de GPU. `lab/scripts/llm-server.sh` lo busca en
`~/miniforge3/envs/triaje-ml/bin/llama-server`; si está en otro sitio, exporta
`LLAMA_SERVER_BIN=/ruta/a/llama-server`. El script ya pasa `-ngl 99`, así que todas las capas van a la GPU.

Modelos: van en `modelos/`, que no está en git. Descárgalos con `aria2c`, que abre varias
conexiones y es mucho más rápido que el navegador (`sudo apt install -y aria2`).

```bash
cd modelos

# Embedder del RAG (obligatorio con --con-rag)
aria2c -x16 -s16 -c -o bge-m3-q8.gguf \
  "https://huggingface.co/gpustack/bge-m3-GGUF/resolve/main/bge-m3-Q8_0.gguf"

# Llama-3.1-8B Q4_K_M: el que se evaluó en el informe
aria2c -x16 -s16 -c -o llama-3.1-8b-instruct-q4.gguf \
  "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
echo "7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c  llama-3.1-8b-instruct-q4.gguf" | sha256sum -c -

# Qwen2.5-3B (el que se probó en el portátil el 30/09)
aria2c -x16 -s16 -c -o qwen2.5-3b-instruct-q4_0.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_0.gguf"

# Foundation-Sec-1.1-8B-Instruct (Cisco, especializado en seguridad) + su plantilla de chat
aria2c -x16 -s16 -c \
  "https://huggingface.co/fdtn-ai/Foundation-Sec-1.1-8B-Instruct-Q4_K_M-GGUF/resolve/main/foundation-sec-1.1-8b-instruct-q4_k_m.gguf"
curl -L -o foundation-sec-1.1-chat_template.jinja \
  "https://huggingface.co/fdtn-ai/Foundation-Sec-1.1-8B-Instruct/raw/main/chat_template.jinja"
cd ..
```

El embedder tiene que ser el mismo con el que se construyó el índice (`prototipo/corpus/indice.json`).
El del portátil mide 634 553 760 bytes, igual que el de este enlace (`ls -l modelos/bge-m3-q8.gguf`).
Si no coincide, cópialo del portátil en vez de descargarlo: con otro embedder la recuperación no sirve.

## 2. Arrancar los servidores

```bash
sh lab/scripts/llm-server.sh --embedder            # embedder en :8082
sh lab/scripts/llm-server.sh --parar               # por si había otro generador
sh lab/scripts/llm-server.sh modelos/<modelo>.gguf # generador en :8080
curl -s localhost:8080/props | python3 -c "import json,sys; print(json.load(sys.stdin)['model_path'])"
```

**Foundation-Sec necesita su plantilla.** El GGUF oficial no la incluye y sin ella responde mal o
vacío (fue lo que lo descartó en la Fase 4). `llm-server.sh` no la pasa, así que arráncalo a mano:

```bash
sh lab/scripts/llm-server.sh --parar
"${LLAMA_SERVER_BIN:-$HOME/miniforge3/envs/triaje-ml/bin/llama-server}" \
  -m modelos/foundation-sec-1.1-8b-instruct-q4_k_m.gguf --port 8080 --host 127.0.0.1 -ngl 99 -c 8192 \
  --jinja --chat-template-file modelos/foundation-sec-1.1-chat_template.jinja > /tmp/llm-server.log 2>&1 &
```

Antes de lanzar la campaña, prueba que responde algo con sentido:

```bash
curl -s localhost:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"system","content":"Explica en una frase que es un ataque de fuerza bruta SSH."}],"max_tokens":60}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
```

## 3. Lanzar la campaña (una por modelo)

**Usa siempre una carpeta de salida propia.** La campaña sobrescribe `tabla.md` y el JSON de la
carpeta de salida; con la de por defecto se pisarían los resultados vigentes del informe.

```bash
python3 -m evaluacion.campana --particion evaluacion --con-rag \
  --salida-dir evaluacion/resultados/<modelo>-con-rag
```

- `<modelo>`: por ejemplo `8b`, `qwen3b` o `foundation-sec-1.1`.
- Sin `--con-rag` mide el justificador sin recuperación. Es la otra mitad del contraste del informe:
  `evaluacion/resultados/8b-sin-rag/`.
- Tiempo: en el portátil sin GPU, ~80 s por justificación (unas 2.5 h). Con GPU deberían ser pocos
  minutos por corrida (el 8B dio ~110 tokens/s).

## 4. Leer el resultado

En `evaluacion/resultados/<modelo>-con-rag/tabla.md`, la línea **«Anclaje LLM (RNF-02)»**:

```
{'llm_total': 106, 'anclados': 106, 'degradados': 0, 'pct_anclaje': 1.0, 'versiones': [...], 'por_clase': {...}}
```

- `anclados / llm_total`: justificaciones del modelo que pasaron el anclaje.
- `degradados`: las que cayeron a la plantilla.
- `por_clase`: el desglose entre amenazas (`vp_intento_acceso`) y falsos positivos
  (`fp_actividad_legitima`).
- La matriz, el recall y el FP de la misma tabla deben salir **idénticos** a los del informe. Si
  no, algo va mal en el entorno, no en el modelo.

Guarda también el tiempo total de cada corrida: la latencia por alerta es el otro dato que decide
qué modelo llevar a la demo.

## 5. Traer los resultados

```bash
git checkout -b eval/modelos-gpu
git add evaluacion/resultados/*-con-rag
git commit -m "eval: anclaje con RAG de <modelos> en GPU"
git push -u origin eval/modelos-gpu
```
