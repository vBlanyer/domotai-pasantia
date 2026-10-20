# domotai-pasantia — Motor de triaje de seguridad asistido por LLM

Prototipo de pasantía en Domotai: un **motor de triaje** que ingiere alertas de seguridad (Wazuh emula el
SIEM del cliente), las clasifica y prioriza, **justifica cada decisión con un modelo de lenguaje**, y ejecuta
respuestas contenidas con validación humana — todo medible contra el método tradicional de referencia (el
nivel de regla de Wazuh). El problema: el analista se ahoga en falsos positivos. La hipótesis: un triaje
asistido por IA, **explicable y con la continuidad del servicio del cliente como restricción**, reduce ese
ruido sin cortar lo que el negocio necesita.

---

## ▶ Pruébalo en pocos pasos

Dos caminos. El **rápido** no necesita Docker ni GPU y demuestra el resultado central en ~1 minuto; es el
recomendado para una primera prueba. El **completo** levanta la demo en vivo.

### 1) Rápido — solo Python (sin Docker, sin GPU, sin npm)

**Requisitos:** Python 3 (probado en 3.14) + PyYAML. Nada más (sin `pip`/`venv`/`pytest`). Desde la raíz del repo:

```bash
# a. Las suites del núcleo deben dar OK (≈20 s en total)
python3 -m unittest discover -s prototipo/tests      # 911 tests
python3 -m unittest discover -s evaluacion/tests      # 59 tests

# b. Reproduce la evaluación frente al baseline de Wazuh (determinista, sin modelo)
python3 -m evaluacion.campana --sin-llm
```

El paso **b** imprime la tabla comparativa (idéntica a [`evaluacion/resultados/tabla.md`](evaluacion/resultados/tabla.md)):
el prototipo logra **recall 1.000 y tasa de FP 0.009** frente a **0.920 / 0.310** del baseline de Wazuh en su
umbral óptimo, sobre la partición de evaluación de **300 alertas**. (Si prefieres no ejecutar nada, esas cifras
ya están comprometidas en [`evaluacion/resultados/`](evaluacion/resultados/README.md).)

### 2) Completo — demo en vivo con Docker

**Requisitos:** Docker + Containerlab. (El visor web ya viene **construido** en `visor/dist` y lo sirve el
daemon, así que **no hace falta Node/npm** para la demo.)

```bash
sh lab/banco/construir-imagen.sh        # construir la imagen de los nodos (una sola vez)
sh lab/lab.sh up banco                   # 14 nodos + Wazuh + monitor de salud
sh lab/banco/banco.sh aprovisionar       # mínimo privilegio del conector — OBLIGATORIO tras cada 'up'

# arrancar el daemon (lee las alertas de Wazuh y decide; --web levanta el visor)
export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
  | python3 -m prototipo.stream - prototipo/perfiles/bancario.yml \
      lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --web
#   → visor en http://127.0.0.1:8787
```

En otra terminal, **lanza ataques** por menú: `sh lab/banco/banco.sh atacar`. Atajo para relanzar el daemon:
`sh reiniciar.sh`. El runbook operativo completo (pantallas, flags y solución de problemas) es
**[`RUNBOOK.md`](RUNBOOK.md)**.

> El LLM (`--con-llm`) y el RAG necesitan GPU/conda (o el sustituto con Claude Code,
> [`lab/scripts/llm_claude.py`](lab/scripts/llm_claude.py)) y **no hacen falta** para validar el resultado
> central: la decisión y la evaluación son 100 % deterministas. Sin él, la justificación es por plantilla,
> instantánea.

---

## Qué hay construido hoy

| Componente | Dónde | Estado |
|------------|-------|--------|
| **Motor de triaje** (ingesta → clasifica → política → perfil de cliente → traza → acción con validación humana) | [`prototipo/`](prototipo/) | Funcional, **911 tests** |
| **Justificador con LLM real + RAG** (LLM local —1B por defecto; Llama-3.1-8B en GPU como objetivo—; recuperación aumentada local con embedder bge-m3 sobre corpus de MITRE/D3FEND/reglas/descartes, dependiente de la clase decidida) | [`prototipo/justificador_llm.py`](prototipo/justificador_llm.py), [`prototipo/rag.py`](prototipo/rag.py) | Funcional (requiere GPU; sustituto [`lab/scripts/llm_claude.py`](lab/scripts/llm_claude.py)) |
| **Daemon en tiempo real** (agrupa en incidentes; valida con el analista; `--sin-llm`/`--con-llm`/`--agente`; healthcheck `/healthz`) | [`prototipo/stream.py`](prototipo/stream.py) | Funcional |
| **Consola web** (8 vistas: panel, métricas e informe exportable, estado de servicios, **Red** —mapa del cliente—, decisiones, aprobaciones, **Contenciones activas** + *kill switch*, trazas) | [`prototipo/tablero.py`](prototipo/tablero.py), [`visor/`](visor/) | Funcional, **148 tests** (React/TS) |
| **Agente de mitigación** (ReAct: contiene en el host, escala al cortafuegos solo si falla; respeta el filtro del perfil) | [`prototipo/agente_mitigacion.py`](prototipo/agente_mitigacion.py) | Funcional, salida restringida por esquema; experimental |
| **Laboratorio** (Containerlab: red de cliente con Wazuh, auditor Nmap, objetivos; lanzador de ataques a medida) | [`lab/`](lab/) | Ejecutable, **137 tests** |
| **Dataset etiquetado** (600 alertas VP/FP/PROPIA/no_soportada; particionado 80/20) | [`lab/dataset/`](lab/dataset/) | Cerrado, **39 tests** |
| **Marco de evaluación** (métricas contra el baseline de Wazuh) | [`evaluacion/`](evaluacion/) | Funcional, **59 tests**; campaña ejecutada |
| **Endurecimiento a producción** (persistencia al reiniciar, supervisión systemd + `/healthz`, retención de traza, *kill switch*, receptor de alertas por red con lista blanca, validador del *ruleset* del cliente) | [`deploy/`](deploy/), [`prototipo/`](prototipo/) | Hecho; ver [guía de integración](documentacion/04-fase4-diseno-de-arquitectura/integracion-en-produccion.md) |

**La idea intelectualmente central:** la decisión clasificación→acción **no la toma el modelo**. La toma una
**política determinista** que *propone* una acción y un **perfil de cliente configurable** que la *filtra*
(permite / degrada / veta). Ejemplo probado: bloquear el puerto 443 se permite en un perfil residencial pero
se degrada en uno bancario, porque ese puerto presta el servicio. El LLM justifica; no manda.

**Y la idea del alcance honesto:** qué hace el motor con cada alerta lo decide un **registro de familias
extensible** ([`prototipo/familias.yml`](prototipo/familias.yml), hoy **10 familias** alineadas a MITRE ATT&CK),
con tres niveles de respuesta — **actuar** (contener con el catálogo cerrado), **triar y encaminar** (clasificar
y derivar con contexto MITRE, sin contener) y **no soportada** (a juicio humano, severidad intacta). Añadir una
familia es una línea; la cobertura real por cliente es *lo que su SIEM detecta ∩ lo que el registro cubre*
(medible con `python3 -m prototipo.validar_reglas`). Así el sistema **dice la verdad** en el borde de su
competencia en vez de inventar una respuesta.

## Cómo está organizado el repositorio

El mapa completo, carpeta a carpeta, está en **[`STRUCTURE.md`](STRUCTURE.md)**. En resumen:

- **[`prototipo/`](prototipo/)** — el motor de triaje, el daemon y la API (Fase 5). *Producto.*
- **[`visor/`](visor/)** — la consola web (React/TS) que sirve el daemon. *Producto.*
- **[`deploy/`](deploy/)** — artefactos de despliegue (systemd, wrapper, `/healthz`, retención). *Producto.*
- **[`evaluacion/`](evaluacion/resultados/README.md)** — el marco de medición y los resultados (Fase 6).
- **[`lab/`](lab/)** — el laboratorio ejecutable, el banco y el dataset (Fase 3).
- **[`documentacion/`](documentacion/README.md)** — el diseño completo en 7 fases; empieza por su índice. La
  **integración en producción**, la **hoja de ruta de cierre** y los **requisitos del cliente/gobernanza** están
  en [`documentacion/04-fase4-diseno-de-arquitectura/`](documentacion/04-fase4-diseno-de-arquitectura/).
- **[`docs/pruebas/`](docs/pruebas/)** — guías de prueba y evidencia por escenario.
- **[`RUNBOOK.md`](RUNBOOK.md)** — cómo operar el sistema completo paso a paso.
- **Manual del analista** — uso diario de la consola web:
  [`documentacion/07-fase7-documentacion-e-informe-final/manual-del-analista.md`](documentacion/07-fase7-documentacion-e-informe-final/manual-del-analista.md).
- **[`CHANGELOG.md`](CHANGELOG.md)** — qué cambió en cada versión (v1.0, v1.1 y posteriores).
- **[`archivo/`](archivo/)** — archivo del **proceso de desarrollo** (planes/specs); no es diseño vigente.
  El **material de referencia superado** del propio diseño vive aparte, en
  [`documentacion/material-superado/`](documentacion/material-superado/).

## Estado y resultado medido

Fases 1–6 completas; la 7 (informe final) con borrador completo compilado en
[`documentacion/report/`](documentacion/report/). El estado vivo, las decisiones cerradas y los riesgos están en
[`documentacion/00-general/estado-y-riesgos.md`](documentacion/00-general/estado-y-riesgos.md).

**Resultado (Fase 6, partición de 300 alertas, perfil empresarial):** frente al nivel de regla de Wazuh en su
umbral óptimo (nivel ≥ 5), el prototipo reduce la tasa de falsos positivos de **0.310 a 0.009** (87 VP, 2 FP,
211 VN, 0 FN) **sin perder ninguna amenaza** (recall **1.000** vs **0.920** del baseline, que deja pasar 7). Con
la **conciencia de impacto** —medida sobre la red real del laboratorio, donde el atacante es interno— escala al
analista el **29,7 % (89/300)** y reduce a **cero** las contenciones automáticas indebidas (la automatización
queda para los orígenes externos). Fuente: [`evaluacion/resultados/`](evaluacion/resultados/README.md).

Decisión de diseño: el clasificador **no** es un codificador con ajuste fino, sino un **árbol de decisión**
([`arbol.py`](prototipo/arbol.py)) que valida y descubre reglas para el baseline determinista auditable — la
escala honesta para un dataset de unos cientos de filas. El justificador LLM sí es real.
