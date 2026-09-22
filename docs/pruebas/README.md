# Cómo probar el prototipo

Guía práctica ordenada por **niveles de dependencia**: del **Nivel 0** (solo Python) al **Nivel 3** (lab +
modelo). Para cada comando tienes su **Sinopsis** (sintaxis) y un **Ejemplo** listo para pegar en consola.

**Todos los comandos se ejecutan desde la raíz del repositorio.**

**Convención de sintaxis:** `<obligatorio>` · `[opcional]` · `a | b` (alternativas) · `-` como ruta = leer de *stdin*.

---

## Requisitos por nivel

| Para… | Necesitas |
|-------|-----------|
| Niveles 0–1 (tests, CLI del motor) | **Python 3** (probado en 3.14) + **pyyaml**. Sin `pip`/`venv`/`pytest`. |
| Nivel 2 (RAG, LLM, evaluación con modelo) | Entorno conda `~/miniforge3/envs/triaje-ml` (Python 3.12 + `llama.cpp`) y el modelo `modelos/llama-3.2-1b-q4.gguf` (~808 MB, no versionado). Instalación en [`prototipo/README.md`](../../prototipo/README.md). |
| Nivel 3 (demos en vivo, daemon) | Lo anterior **+ Docker + Containerlab** (el laboratorio). |

Los Niveles 0–1 no necesitan lab ni modelo: el dataset etiquetado y los hallazgos ya están en el repo.

---

## Arranque rápido (copia-pega)

```bash
# 0) Sanidad (segundos, sin dependencias)
python3 -m unittest discover -s prototipo/tests

# 1) El motor decide sobre 600 alertas reales (sin dependencias)
python3 -m prototipo.triaje lab/dataset/etiquetado.jsonl prototipo/perfiles/empresarial.yml \
    lab/campañas/2026-08-31-evaluacion/hallazgos.json salida.jsonl

# 2) Evaluación contra el baseline (sin modelo, rápido)
python3 -m evaluacion.campana --particion evaluacion --sin-llm

# 3) Lab en vivo (necesita Docker + Containerlab + modelo)
sh lab/lab.sh up && python3 lab/scripts/demo-agente-escalado.py --autonomo

# 4) Banco de pruebas del laboratorio del banco (catálogo de casos con veredicto)
python3 -m lab.banco.pruebas              # decision/inyectada/perfil, sin lab, segundos
sh lab/lab.sh up banco && python3 -m lab.banco.pruebas --con-vivo   # además los casos de extremo a extremo

# 5) Tablero web (con el daemon)
python3 -m prototipo.stream <fuente-wazuh> prototipo/perfiles/bancario.yml \
    lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --web   # abre http://127.0.0.1:8787
```

---

## Índice

- [01 · Motor sin dependencias](01-motor.md)
- [02 · RAG y evaluación](02-rag-evaluacion.md)
- [03 · Lab en vivo](03-lab-en-vivo.md)
- [04 · Escenarios de ataque](04-escenarios-de-ataque.md)
- [05 · Topologías del laboratorio](05-topologias.md)
- [06 · Rendimiento y hardware](06-rendimiento-y-hardware.md)
- [07 · Roadmap del pipeline y latencia medida](07-roadmap-pipeline-y-latencia.md)
- [08 · Prueba manual en el laboratorio del banco](08-laboratorio-banco.md) — su apartado 10 remite al **banco de pruebas automático** (`python3 -m lab.banco.pruebas`, catálogo de casos con veredicto OK/FALLO/BLOQUEADO/OMITIDO y guías por caso en [banco/](banco/))
- [09 · Tablero web](09-tablero-web.md) — consola local de observabilidad y aprobación para el daemon (`stream.py --web`), sus cuatro paneles y la verificación manual de extremo a extremo

---

## Qué mirar en cada prueba

- **La traza** es la evidencia auditable: clase, prioridad, confianza, justificación (texto **y**
  estructurada), acción propuesta/final, filtro del perfil, veredicto humano, `version_justificador`,
  y (con RAG) `consulta_rag`/`recuperacion_agentica`/`pasajes_usados`.
- **La decisión NO la toma el modelo**: la política determinista propone y el perfil de cliente filtra
  (permite / degrada / veta). El LLM **justifica** y, en el agente, **elige de un catálogo cerrado** — nunca
  redacta comandos libres.
- **Todo es local** (RNF-01): ninguna alerta sale a servicios externos; el LLM corre por subprocess a un
  binario local.

## Para operarlo, no solo probarlo

La [guía de operación](../../documentacion/07-fase7-documentacion-e-informe-final/guia-de-operacion.md)
cubre arranque, configuración por cliente, mínimo privilegio, verificación de la traza y reversión.

## Más detalle

- [`README.md`](../../README.md) — qué es el proyecto y qué hay construido.
- [`prototipo/README.md`](../../prototipo/README.md) — el motor por dentro (5A–5D, RAG agéntico, agente de mitigación).
- [`documentacion/`](../../documentacion/) — el diseño por fases; el
  [informe de evaluación](../../documentacion/06-fase6-evaluacion-del-prototipo/informe-evaluacion.md) tiene los números.
