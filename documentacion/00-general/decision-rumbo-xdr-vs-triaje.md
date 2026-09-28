# Decisión de rumbo: correlación XDR vs. refuerzo del triaje

> **Documento breve para coordinación.** Plantea dos rutas para la próxima etapa del prototipo y pide
> una decisión de rumbo. No modifica el plan de trabajo ni el informe; los resume para decidir.
> Fecha: 2026-09-24.

## 1. Contexto

El prototipo funciona como **módulo de triaje inteligente** sobre alertas de un SIEM (Wazuh emula el del
cliente): normaliza a un modelo de evento común, clasifica (VP / FP / no soportada), **justifica** con
LLM+RAG y MITRE, prioriza, aplica **contención** (bloqueo por IP, escalada host→cortafuegos) y deja una
**traza auditable** (cadena de hashes). Todo esto ya está implementado y evaluado (Fases 5–6).

Dos hechos de diseño encuadran la decisión:

- La **arquitectura ya es telemetría-agnóstica** (Modelo B): `ingesta.normalizar(cruda, adaptador)` produce
  un modelo común; solo existe **un adaptador** (Wazuh). Añadir una fuente = escribir un adaptador.
- Un **incidente** hoy se agrupa por `(origen_ip, activo, servicio, familia)` en una ventana temporal:
  es **una fuente y un dominio**. No hay correlación entre dominios.

La Fase 4 posiciona explícitamente el proyecto en la **capa de análisis y triaje**, y define **XDR** como
**correlación multi-capa de varias fuentes**, señalando que *"el diferencial comercial es la correlación"*.
De ahí la disyuntiva.

## 2. Ruta A — Correlación cross-domain (hacia XDR)

**Qué es.** Que el motor **ligue eventos de dominios distintos** (endpoint, red, identidad, correo, cloud)
en un solo incidente/historia de ataque, correlacionando por actor/activo/tiempo/técnica ATT&CK. Es el
rasgo que *define* a un XDR.

**Qué implica (concreto).**
- **Más fuentes de telemetría:** ≥1 adaptador adicional al modelo común (p. ej. endpoint con Sysmon, red
  con Zeek/Suricata, o la fuente CEF ya analizada). La costura existe; falta el adaptador y su lab.
- **Motor de correlación:** un nivel por encima de la agrupación actual, que una incidentes de fuentes y
  familias distintas del mismo actor/activo en una ventana, con un modelo de incidente multi-fuente.
- **(Opcional) Reconstrucción de campaña:** encadenar incidentes en una narrativa mapeada a fases de
  ATT&CK (recon → acceso → lateral → exfiltración).

**Encaje con el alcance.** Es **expansión de alcance**: mueve el prototipo de "módulo de triaje" hacia
"plataforma XDR". No es cerrar un hueco del alcance actual, sino ampliarlo conscientemente.

**Esfuerzo / riesgo.** **Alto.** Cambia el modelo de incidente (hoy central en todo el pipeline y la
evaluación), exige montar ≥1 fuente nueva en el laboratorio, y abre preguntas de diseño (reglas de
correlación, ventana, deduplicación). Mayor valor demostrativo, mayor riesgo de no cerrar en el tiempo.

**Qué demuestra.** El **diferencial XDR** (correlación) y la tesis Modelo B del propio proyecto llevada a
su conclusión: valor sobre telemetría heterogénea y accesible.

## 3. Ruta B — Reforzar el rol de triaje (dentro del alcance)

**Qué es.** Profundizar lo que el prototipo *ya* hace, ampliando cobertura y robustez sin cambiar su papel.

**Qué implica (concreto).**
- **Ampliar familias/técnicas:** hoy el fuerte es fuerza bruta SSH (`acceso_credenciales`); dentro del
  alcance cabe robustecer y ejercitar con más reglas, dataset y casos las familias **ya registradas** en
  `familias.yml` — que es el *registro de familias* (4: `acceso_credenciales`, `reconocimiento`,
  `servicio_expuesto`, `explotacion_conocida`), **no** el catálogo de acciones (`catalogo.yml`). En cambio,
  llevar el clasificador+justificador a **malware, ataques web, movimiento lateral, exfiltración,
  persistencia** es **trabajo futuro fuera del alcance actual**: esas familias no están en `familias.yml` y
  están declaradas fuera de alcance por diseño en [estado-y-riesgos §7](estado-y-riesgos.md#fuera-de-alcance-por-diseño-no-se-hará-y-por-qué)
  porque exigen **detección primaria** nueva (que es del SIEM, no del MDR), no un hueco «por ejercitar».
- **Respuesta multi-capa (SOAR-lite):** hoy `BLOQUEAR_IP` + escalada host→cortafuegos; sumar acciones del
  catálogo orquestadas por capa (aislar nodo, cerrar servicio/puerto) con su filtro de perfil.
- **Encoder afinado, solo si algún día crece el dataset:** el ajuste fino se **descartó** (el árbol de
  decisión `arbol.py` es la escala honesta con unos cientos de filas); la interfaz `clasificar` queda
  **abierta** para un encoder si el bucle de feedback (RF-12) acumula suficientes datos etiquetados. No es
  un ítem abierto de la Fase 5, que está cerrada.

**Encaje con el alcance.** **Dentro del alcance declarado.** Consolida la capa de triaje explicable.

**Esfuerzo / riesgo.** **Medio, incremental, bajo riesgo.** Cada familia/acción es una adición acotada,
probable de cerrar en el tiempo, y reutiliza el pipeline y la evaluación existentes.

**Qué demuestra.** Un triaje explicable **más completo y con más cobertura** de amenazas — el objetivo
central del trabajo, más sólido.

## 4. Comparativa

| Dimensión | Ruta A — Correlación XDR | Ruta B — Refuerzo del triaje |
|---|---|---|
| Naturaleza | Expansión de alcance (hacia XDR) | Dentro del alcance actual |
| Valor diferencial | Correlación multi-capa (el sello del XDR) | Más cobertura y robustez del triaje |
| Esfuerzo | Alto | Medio (incremental) |
| Riesgo de cierre | Mayor (cambia el modelo de incidente + lab nuevo) | Menor (adiciones acotadas) |
| Reutiliza lo hecho | Parcial (nuevo nivel de correlación) | Alto (mismo pipeline y evaluación) |
| Encaje con Fase 4 | Redefine el posicionamiento | Lo consolida |
| Dependencias externas | ≥1 fuente de telemetría nueva | Dataset etiquetado de las familias nuevas |

## 5. Recomendación y decisión pedida

Ambas son legítimas y no excluyentes en el tiempo. La recomendación técnica depende del objetivo de la
etapa:

- Si la prioridad es **maximizar el diferencial "XDR"** y hay margen de tiempo/riesgo, la **Ruta A** en
  versión **acotada** (una segunda fuente + una correlación ligera por actor/activo) es la que más mueve
  el prototipo hacia XDR sin reescribir todo.
- Si la prioridad es **cerrar con solidez dentro del alcance comprometido**, la **Ruta B** entrega más
  cobertura con menos riesgo y reutiliza la evaluación existente.

**Propuesta:** priorizar **Ruta B** para asegurar un cierre sólido, y dejar la **Ruta A acotada** como
extensión opcional si el calendario lo permite. Se solicita a coordinación confirmar el rumbo (A, B, o
B con A acotada como extensión) para planificar la siguiente etapa.
