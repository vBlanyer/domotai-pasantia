# domotai-pasantia — Motor de triaje de seguridad asistido por LLM

Prototipo de pasantía en Domotai: un **motor de triaje** que ingiere alertas de seguridad (Wazuh),
las clasifica y prioriza, **justifica cada decisión con un modelo de lenguaje**, y ejecuta respuestas
contenidas con validación humana — todo medible contra el método tradicional de referencia.

El problema que ataca: el analista de seguridad se ahoga en falsos positivos. La hipótesis: un triaje
asistido por IA, **explicable y con la continuidad del servicio del cliente como restricción**, reduce
ese ruido sin cortar lo que el negocio necesita.

## Qué hay construido hoy

| Componente | Dónde | Estado |
|------------|-------|--------|
| **Motor de triaje** (ingesta → clasifica → política → perfil de cliente → traza → acción con validación humana) | [`prototipo/`](prototipo/) | Funcional, 225 tests |
| **Justificador con LLM real + RAG** (Llama-3.1-8B en servidor residente; recuperación aumentada local con embedder bge-m3 sobre corpus curado de MITRE/D3FEND/reglas Wazuh/descartes, dependiente de la clase decidida) | [`prototipo/justificador_llm.py`](prototipo/justificador_llm.py), [`prototipo/rag.py`](prototipo/rag.py) | Funcional, verificado en vivo |
| **Daemon en tiempo real** (agrupa en incidentes, valida con el analista; modos `--sin-llm` / `--con-llm` / `--agente`) | [`prototipo/stream.py`](prototipo/stream.py) | Funcional |
| **Agente de mitigación** (ReAct: escala host → cortafuegos, aprueba por paso) | [`prototipo/agente_mitigacion.py`](prototipo/agente_mitigacion.py) | Funcional con salida restringida por esquema y escalada determinista de respaldo; exige hardware rápido |
| **Laboratorio** (Containerlab: red de cliente con Wazuh, auditor Nmap/Greenbone, objetivo vulnerable) | [`lab/`](lab/) | Ejecutable |
| **Dataset etiquetado** (466 alertas reales de tres familias, VP/FP/PROPIA/no_soportada, particionado 80/20) | [`lab/dataset/`](lab/dataset/) | Cerrado |
| **Marco de evaluación** (métricas contra el baseline de Wazuh) | [`evaluacion/`](evaluacion/) | Funcional, 30 tests; campaña ejecutada |

**La idea intelectualmente central:** la decisión clasificación→acción **no la toma el modelo**. La toma
una **política determinista** que *propone* una acción y un **perfil de cliente configurable** que la
*filtra* (permite / degrada / veta). Ejemplo probado: la misma acción de bloquear el puerto 443 se
permite en un perfil residencial pero se degrada en uno bancario, porque ese puerto presta el servicio.
El LLM justifica; no manda.

## Cómo se corre

Todo es **Python 3 con biblioteca estándar** (más pyyaml). Sin `pip`, sin `venv`, sin `pytest`. Desde la
raíz del repositorio:

```bash
# Batería de tests del motor
python3 -m unittest discover -s prototipo/tests

# Triaje sobre el dataset (baseline determinista, sin modelo)
python3 -m prototipo.triaje lab/dataset/etiquetado.jsonl \
    prototipo/perfiles/empresarial.yml \
    lab/campañas/2026-08-31-evaluacion/hallazgos.json salida.jsonl
```

El justificador con LLM vive en un entorno conda aparte (`~/miniforge3`, sin sudo) y se invoca por
subprocess; su instalación está documentada en [`prototipo/README.md`](prototipo/README.md). El
laboratorio se levanta con [`lab/lab.sh`](lab/lab.sh) (requiere Docker + Containerlab).

## Cómo está organizado el repositorio

- **[`documentacion/`](documentacion/)** — el diseño completo, organizado en 7 fases. **Empieza por
  [su índice](documentacion/README.md):** cada fase resume qué decidió, qué produjo y en qué estado está.
  Los dos documentos que van a coordinación (plan de trabajo y roadmap) están en
  [`documentacion/00-general/`](documentacion/00-general/).
- **[`prototipo/`](prototipo/)** — el motor de triaje (el código de la Fase 5).
- **[`lab/`](lab/)** — el laboratorio ejecutable y el dataset (la Fase 3).
- **[`evaluacion/`](evaluacion/)** — el marco de medición (la Fase 6).
- **[`docs/superpowers/`](docs/superpowers/)** — las especificaciones y planes de implementación de cada
  subproyecto de código.

## Estado del proyecto

Fases 1–6 completas; la 7 (informe final) **en curso** — borrador completo en LaTeX y compilado en
[`documentacion/report/`](documentacion/report/), y la
**[guía de operación](documentacion/07-fase7-documentacion-e-informe-final/guia-de-operacion.md)** para
desplegarlo y operarlo. El detalle vivo del estado,
las decisiones cerradas y los riesgos está en
[`documentacion/00-general/estado-y-riesgos.md`](documentacion/00-general/estado-y-riesgos.md).

**Resultado medido (Fase 6, ampliado el 11/09/2026 a tres familias de ataque):** frente al nivel de
regla de Wazuh, el prototipo reduce la tasa de falsos positivos **a 0.000** (vs 0.296 del baseline
sobre 233 alertas) **sin perder ninguna amenaza** (recall 1.0, frente a 0.741 del baseline, que deja
pasar las conexiones en claro de nivel 3) y sin acciones disruptivas indebidas.
Detalle en [`evaluacion/resultados/README.md`](evaluacion/resultados/README.md) y en el
[informe de evaluación](documentacion/06-fase6-evaluacion-del-prototipo/informe-evaluacion.md).

Limitación conocida y documentada: el clasificador con fine-tuning (encoder) sigue bloqueado por
muestras insuficientes (el dataset tiene 3 familias de ataque, dos con pocas muestras); el baseline
determinista lo cubre mientras tanto, y el justificador LLM sí es real.
