# El RAG agéntico con distintos modelos generadores

Una ejecución del banco del RAG (`evaluacion/simular_ataques_rag.py --con-sintesis`) por modelo
generador, sobre el mismo banco (`evaluacion/simulaciones/ataques.jsonl`, 16 alertas de cuatro
familias), el mismo corpus (35 fichas, `prototipo/corpus/indice.json`) y el mismo *embedder* local
(`bge-m3`). Solo cambia el modelo que formula la consulta agéntica y redacta la justificación. La
columna «Fija» de cada fichero no usa generador y es la misma en todos.

| Fichero | Generador | Cómo se sirvió | Tiempo en el portátil |
|---|---|---|---|
| `2026-11-16-llama-3.2-1b-q4.md` | Llama 3.2 1B (Q4, local) | `lab/scripts/llm-server.sh modelos/llama-3.2-1b-q4.gguf` | 21 min |
| `2026-11-16-qwen2.5-3b-instruct-q4_0.md` | Qwen2.5 3B Instruct (Q4_0, local) | `lab/scripts/llm-server.sh modelos/qwen2.5-3b-instruct-q4_0.gguf` | 18 min |
| `2026-11-16-foundation-sec-8b-instruct-q4_k_m.md` | Foundation-Sec-8B-Instruct (Q4_K_M de mradermacher, local) | `lab/scripts/llm-server.sh modelos/foundation-sec-8b-instruct-q4_k_m.gguf` y el banco con `--plazo 900` | 67 min |
| `2026-11-16-claude-haiku.md` | Claude Haiku | `lab/scripts/llm_claude.py --modelo haiku` | 7 min |
| `2026-11-16-claude-sonnet.md` | Claude Sonnet | `lab/scripts/llm_claude.py --modelo sonnet` | 6 min |

Los ficheros `*-ronda1.md` son la primera pasada con Claude, anterior a que el banco separara las
justificaciones del modelo de las de la plantilla (commit `fdf73c5`); se conservan porque muestran la
variación entre dos ejecuciones sin temperatura fija.

**Qué mide la síntesis.** Un texto del modelo que no pasa la comprobación de anclaje se sustituye por
la plantilla (anclada por construcción), así que la «tasa de anclaje» es 1,00 siempre. Lo que mide al
modelo es cuántas justificaciones escribió él (y ancladas) y, sobre esas, cuántas citan el número de
la regla de Wazuh de la alerta (`termino_esperado`).

**Límites.** Los modelos de Claude se sirven con `claude -p` a través del sustituto de
`llm-server`: no se puede fijar la temperatura a 0 (no es reproducible, RNF-03), los enunciados
salen del equipo (solo datos sintéticos del banco) y no son el modelo que se despliega. Sirven
para comparar modelos entre sí, no para fijar una cifra del producto.

## Añadir un modelo

1. Servir el modelo en `127.0.0.1:8080` con la API de `llama-server` (`llama-server` con otro
   `.gguf`, o `python3 lab/scripts/llm_claude.py --modelo <m>`), y el *embedder* como siempre.
2. `python3 -m evaluacion.simular_ataques_rag --con-sintesis --salida-dir <carpeta temporal>`
3. Copiar el informe aquí como `AAAA-MM-DD-<modelo>.md`, añadir su fila a esta tabla y a la
   tabla `tab:modelos` del informe (`documentacion/report/ip6_resultados.tex`).
