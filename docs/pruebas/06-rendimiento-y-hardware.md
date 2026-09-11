# 06 · Rendimiento y hardware (planificar dónde probar el MDR)

Guía para saber **qué latencia esperar** al probar el daemon MDR según el modo y el hardware, y qué cambia
al pasar a una máquina con GPU. Útil para decidir dónde correr las pruebas cómodas.

## Los dos modos y su coste

| Modo | Justificación | Latencia (hardware actual) | Cuándo |
|---|---|---|---|
| **`--sin-llm`** (default) | plantilla determinista (más vaga) | **instantánea** | lazo humano ágil, iterar rápido |
| **`--con-llm`** | 1B local + RAG agéntico (enriquecida) | **~30–60 s / incidente** | inspeccionar el anclaje y los pasajes RAG |
| **`--agente`** | 1B para el ReAct (decide + escala) | **impráctico en CPU** (medido: >4 min/incidente, no terminó en 260 s) | mitigación multi-nodo (host → firewall) — **requiere hardware rápido** |

La **decisión y el bloqueo son deterministas e instantáneos en cualquier modo/hardware** (RF-15); el LLM/RAG
solo **explica** (y, en el agente, decide la estrategia de escalada). El coste del LLM afecta a la
*explicación*, no a la respuesta de seguridad.

## De dónde viene la espera con `--con-llm`

Tres retardos se suman entre el ataque y el prompt:
1. **Wazuh** (~pocos s): recibe los syslog, correlaciona la ráfaga y la escribe en `alerts.json`.
2. **Ventana de agrupación** (`--ventana-agrupacion N`): el daemon espera N s antes de emitir el incidente.
3. **El 1B** (el grande): `--con-llm` hace **2 generaciones** por incidente (consulta agéntica + justificación)
   de ~64 tokens cada una, **antes** de abrir el prompt.

## Hallazgo medido: crecer el corpus con el 1B lo empeora

Se intentó **crecer el corpus** 29 → 39 fichas (+8 técnicas ATT&CK hermanas + 2 D3FEND) y se re-midió con el
banco (§2.4). Resultado de la recuperación **fija**:

| | 29 fichas | 39 fichas |
|---|---|---|
| Hit@1 | 0.25 | 0.00 |
| MRR | **0.41** | **0.19** |

**Crecer el corpus DILUYÓ la recuperación** (MRR a la mitad): el embedder 1B **no discrimina técnicas
semánticamente cercanas** (p. ej. `T1110.001` Password Guessing vs `T1110.002` Password Cracking), así que
más fichas = más confusión. Se hizo **rollback** a las 29 fichas. **Conclusión:** con el 1B, el corpus no se
puede crecer útilmente; **crecerlo exige un modelo de embeddings dedicado** (`bge`/`e5`, o el 7–8B en GPU) —
otra razón para el hardware objetivo. La calibración (banco §2.4) es la que permite detectar esto antes de fijar nada.

### Seguimiento (10/09/2026): con bge-m3, crecer el corpus deja de romper la recuperación

Se repitió el experimento con el embedder dedicado (`bge-m3`, agrupación CLS), ampliando el corpus vigente
de 32 fichas con 8 técnicas hermanas del perímetro (`T1110.002`, `T1078.001`, `T1078.003`, `T1021.001`,
`T1021.002`, `T1595.003`, `T1211`, `T1212`), extraídas del bundle oficial con `prototipo/extraer_attack.py`
y medidas en memoria sin tocar el corpus versionado:

| Recuperación fija | 32 fichas | 40 fichas |
|---|---|---|
| Hit@1 | 0.50 | 0.42 |
| Hit@3 | 0.83 | 0.83 |
| Hit@5 | 1.00 | 1.00 |
| MRR | **0.70** | **0.66** |

Con el 1B la misma ampliación partía el MRR por la mitad y vaciaba el Hit@1; con bge-m3 el coste es de
0.04 de MRR, una sola alerta pierde el primer puesto frente a su técnica hermana, y la ficha correcta sigue
entre las tres primeras en el 83 % y entre las cinco primeras siempre. **Crecer el corpus pasa de inviable a
viable**, que es lo que la recomendación original decía que ocurriría. No se incorporó la ampliación al
corpus versionado porque el banco no tiene casos que la necesiten: se añadirán fichas cuando haya alertas
del perímetro que las requieran, no antes.

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
3. **`--agente` prácticamente exige GPU/CPU rápido.** El ReAct hace **varias** llamadas al 1B por
   incidente (hasta `max_pasos`); en el CPU actual eso supera los ~4 min y no es usable en vivo (medido). La
   lógica de escalada está verificada por test determinista; en el hardware objetivo cae a segundos. Úsalo
   con `demo-agente-escalado.py` (guionizado, instantáneo) mientras tanto, y en el daemon (`--agente`) cuando
   tengas la máquina rápida.
4. **Sube a un modelo 7–8B** (cabe en 12 GB a q4, ~5 GB, ~50–100 t/s en el 5070). Resuelve la limitación de
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
