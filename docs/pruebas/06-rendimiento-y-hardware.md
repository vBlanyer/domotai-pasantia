# 06 · Rendimiento y hardware (planificar dónde probar el MDR)

Guía para saber **qué latencia esperar** al probar el daemon MDR según el modo y el hardware, y qué cambia
al pasar a una máquina con GPU. Útil para decidir dónde correr las pruebas cómodas.

## Los dos modos y su coste

| Modo | Justificación | Latencia (hardware actual) | Cuándo |
|---|---|---|---|
| **`--sin-llm`** (default) | plantilla determinista (más vaga) | **instantánea** | lazo humano ágil, iterar rápido |
| **`--con-llm`** | 1B local + RAG agéntico (enriquecida) | **~30–60 s / incidente** | inspeccionar el anclaje y los pasajes RAG |

La **decisión y el bloqueo son deterministas e instantáneos en cualquier modo/hardware** (RF-15); el LLM/RAG
solo **explica** (y, en el agente, decide la estrategia de escalada). El coste del LLM afecta a la
*explicación*, no a la respuesta de seguridad.

## De dónde viene la espera con `--con-llm`

Tres retardos se suman entre el ataque y el prompt:
1. **Wazuh** (~pocos s): recibe los syslog, correlaciona la ráfaga y la escribe en `alerts.json`.
2. **Ventana de agrupación** (`--ventana-agrupacion N`): el daemon espera N s antes de emitir el incidente.
3. **El 1B** (el grande): `--con-llm` hace **2 generaciones** por incidente (consulta agéntica + justificación)
   de ~64 tokens cada una, **antes** de abrir el prompt.

## Baseline medido (hardware actual)

- Portátil, **CPU sin GPU**, `llama-3.2-1b-q4` → **~3.7 t/s**.
- `--con-llm`: 64 tok / 3.7 ≈ 17 s por generación × 2 + embeddings → **~30–60 s por incidente**.

## Estimación en Ryzen 7 9800X3D + RTX 5070

El 1B q4 pesa ~0.8 GB → cabe entero en los 12 GB del 5070; la inferencia es *memory-bandwidth-bound*.
**Son estimaciones** (dependen de versión de llama.cpp, quant, contexto y del diseño de invocación); para
números reales, `llama-bench` en la máquina objetivo.

| Configuración | t/s (1B q4, aprox.) | ~por generación (64 tok) | ~por incidente (2 gen + emb.) |
|---|---|---|---|
| Portátil CPU (**actual, medido**) | ~3.7 | ~17 s | **~30–60 s** |
| **9800X3D — solo CPU** (Zen5, 3D V-cache, DDR5 ~90 GB/s) | ~40–70 | ~1–1.6 s | **~3–6 s** |
| **RTX 5070 — GPU** (GDDR7 ~600–700 GB/s) | ~200–400 | ~0.2–0.3 s | **~1–3 s\*** |

**\*** En GPU el cuello **deja de ser la generación** y pasa al **arranque del subproceso + carga del modelo
por llamada** (el diseño actual lanza `llama-simple`/`llama-embedding` por invocación, ~0.5–1 s c/u). Con un
**servidor residente** (`llama-server`, modelo ya en VRAM) → **sub-segundo por incidente**.

## Recomendación para la máquina objetivo (para testear el MDR cómodo)

1. **Deja `--con-llm` siempre activo.** A ~1–6 s por incidente ya no penaliza la interacción, así pruebas
   siempre con la justificación enriquecida.
2. **Pasa a un modelo residente** para exprimir la GPU: `llama-server` (modelo cargado una vez en VRAM) +
   cliente HTTP en `justificador_llm`/`rag`, en lugar de un subproceso por llamada. Es un cambio **acotado**
   que **no toca el motor de decisión**. Elimina el mayor coste en hardware rápido (la recarga del modelo).
3. **Sube a un modelo 7–8B** (cabe en 12 GB a q4, ~5 GB, ~50–100 t/s en el 5070). Resuelve la limitación de
   calidad del 1B (el "5760 es una regla de firewall" que alucinó) — la justificación pasa a ser bastante
   más rica y correcta. Es el *perfil B* que ya contemplaba el proyecto (Foundation-Sec-8B). Tendrías
   **velocidad y calidad a la vez**.

## Mientras tanto (hardware actual), para pruebas ágiles

```bash
# lazo humano rápido (plantilla, instantáneo) + ventana corta
… | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml \
      lab/campañas/hallazgos-sin-perfilar.json --ventana-agrupacion 5
# y cuando quieras ver el RAG, añade --con-llm y asume la espera del 1B
```
