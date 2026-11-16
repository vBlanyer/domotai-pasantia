# El RAG agéntico con distintos modelos generadores

Una ejecución del banco del RAG (`evaluacion/simular_ataques_rag.py --con-sintesis`) por modelo
generador, sobre el mismo banco (`evaluacion/simulaciones/ataques.jsonl`, 16 alertas de cuatro
familias), el mismo corpus (35 fichas, `prototipo/corpus/indice.json`) y el mismo *embedder* local
(`bge-m3`). Solo cambia el modelo que formula la consulta agéntica y redacta la justificación. La
columna «Fija» de cada fichero no usa generador y es la misma en todos.

| Fichero | Generador | Cómo se sirvió |
|---|---|---|
| `2026-11-16-claude-haiku.md` | Claude Haiku | `lab/scripts/llm_claude.py --modelo haiku` |
| `2026-11-16-claude-sonnet.md` | Claude Sonnet | `lab/scripts/llm_claude.py --modelo sonnet` |

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
