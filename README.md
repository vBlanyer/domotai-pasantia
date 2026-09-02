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
| **Motor de triaje** (ingesta → clasifica → política → perfil de cliente → traza → acción con validación humana) | [`prototipo/`](prototipo/) | Funcional, 63 tests |
| **Justificador con LLM real** (Llama-3.2-1B, anclaje verificable, degradación a plantilla) | [`prototipo/justificador_llm.py`](prototipo/justificador_llm.py) | Funcional, verificado en vivo |
| **Laboratorio** (Containerlab: red de cliente con Wazuh, auditor Nmap/Greenbone, objetivo vulnerable) | [`lab/`](lab/) | Ejecutable |
| **Dataset etiquetado** (410 alertas reales, VP/FP/no_soportada, particionado 80/20) | [`lab/dataset/`](lab/dataset/) | Cerrado |
| **Marco de evaluación** (métricas contra el baseline de Wazuh) | [`evaluacion/`](evaluacion/) | Funcional, 21 tests; campaña ejecutada |

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

Fases 1–6 completas; la 7 (informe final) pendiente. El detalle vivo del estado,
las decisiones cerradas y los riesgos está en
[`documentacion/00-general/estado-y-riesgos.md`](documentacion/00-general/estado-y-riesgos.md).

**Resultado medido (Fase 6):** frente al nivel de regla de Wazuh, el prototipo reduce la tasa de
falsos positivos casi **7×** (0.041 vs 0.282) **sin perder ninguna amenaza** (recall 1.0) y sin
acciones disruptivas indebidas. Detalle en el
[informe de evaluación](documentacion/06-fase6-evaluacion-del-prototipo/informe-evaluacion.md).

Limitación conocida y documentada: el clasificador con fine-tuning (encoder) sigue bloqueado por un
dataset de una sola familia de ataque; el baseline determinista lo cubre mientras tanto, y el
justificador LLM sí es real.
