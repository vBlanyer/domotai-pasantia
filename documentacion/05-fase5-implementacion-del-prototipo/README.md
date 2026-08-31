# Fase 5 — Implementación del prototipo

**Objetivo (plan de trabajo, objetivo 5):** construir el caso de uso acotado definido en la Fase 1,
integrando ingesta y normalización, clasificación y priorización asistidas por modelos de lenguaje,
generación de justificación explicable y flujo de validación humana en las decisiones críticas, con
registro de trazas para auditoría.

---

## Resumen

Es la fase que convierte el diseño en código. Nada de lo que aquí se construye inventa criterio
propio: el perímetro lo fija la [Fase 1](../01-fase1-analisis-del-modulo/), los requisitos la
[Fase 2](../02-fase2-estado-del-arte/requisitos.md), la arquitectura la
[Fase 4](../04-fase4-diseno-de-arquitectura/) y la entrada real la
[Fase 3](../03-fase3-entorno-de-pruebas/).

El trabajo se ordena en cinco piezas, que son los **pasos 11 a 15** del
[camino paso a paso](../00-general/camino-paso-a-paso.md), agrupadas en tres subproyectos: **5A**
(núcleo de decisión, offline, hecho), **5B** (lazo en vivo: conector + validación humana,
pendiente) y **5C** (ML real detrás de la interfaz, pendiente).

| Pieza | Qué hace | Se da por hecha cuando | Estado |
|-------|----------|------------------------|--------|
| **Ingesta y normalización** | Lee las alertas de la fuente y las lleva al esquema común, conservando la severidad de origen como baseline | Una alerta real de `alerts.json` sale normalizada, con su activo resuelto aunque el equipo no tenga agente ([RF-16](../02-fase2-estado-del-arte/requisitos.md)) | **Hecho** — `lab/dataset/esquema.py` |
| **Núcleo de decisión (5A)** | Análisis (baseline) → política → perfil → traza: el lazo completo hasta antes de ejecutar | Corre sobre el dataset etiquetado de la Fase 3 y produce trazas con clase, acción y resultado de filtro auditables | **Hecho** — [`prototipo/`](../../prototipo/README.md) |
| **Interfaz de análisis y clasificador real (5C)** | `clasificar` detrás de un encoder ajustado sobre la partición de entrenamiento | Dada una alerta, devuelve clase, prioridad y **confianza numérica** desde el modelo, no desde una regla fija | Pendiente |
| **Justificador en línea (5C)** | `justificar` detrás del modelo pequeño del Perfil A | Produce una justificación breve que **referencia campos concretos** de la alerta ([RNF-02](../02-fase2-estado-del-arte/requisitos.md)), en un tiempo tolerable para una persona | Pendiente |
| **Conector (5B)** | Traduce acciones abstractas del catálogo a comandos, con clave dedicada y privilegio mínimo | El motor ordena una acción y el nodo la ejecuta, con orden, comando, código de salida y salida registrados | Pendiente |
| **Validación humana y trazas en vivo (5B)** | Retiene lo que exige aprobación, muestra la justificación **por terminal (TUI/CLI, sin UI gráfica — [flujo §7](../04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md))**, registra la decisión | El lazo completo funciona en vivo: alerta → clasificación → justificación → validación → acción → verificación | Pendiente |

> **Sobre el clasificador de 5A.** El núcleo de decisión ya construido corre con un
> **baseline determinista** (regla fija sobre postura de exposición, sin ML) detrás de la interfaz
> `clasificar`/`justificar`. Es un placeholder deliberado, no el resultado final: el clasificador y
> el justificador reales de **5C** se enchufan detrás de esa misma interfaz, sin tocar política,
> perfil ni traza. Ver [`prototipo/README.md`](../../prototipo/README.md#2-el-clasificador-es-un-baseline-no-un-modelo).

Dos restricciones de diseño condicionan cómo se implementa. La primera: **el dataset en disco es la
frontera** entre el camino en vivo y el camino en lote, porque el presupuesto de memoria no permite
tenerlo todo levantado a la vez. La segunda: **los campos de la alerta son datos, nunca
instrucciones** ([RNF-08](../02-fase2-estado-del-arte/requisitos.md)) — el contenido del log lo escribe quien ataca, y llega hasta el prompt del
justificador.

Y una condición previa que no es de esta fase pero la bloquea: el clasificador necesita el
**dataset etiquetado y particionado** que la [Fase 3](../03-fase3-entorno-de-pruebas/) todavía debe
producir.

---

## Documentos

- [`docs/superpowers/specs/2026-08-31-fase5a-nucleo-decision-design.md`](../../docs/superpowers/specs/2026-08-31-fase5a-nucleo-decision-design.md) — diseño del subproyecto 5A.

Se irán añadiendo aquí conforme la fase avance: prompts versionados (5C), contrato del conector
(5B).

El código del prototipo vive fuera de esta carpeta, junto al laboratorio, en
[`prototipo/`](../../prototipo/README.md) — no en `documentacion/`.

---

## Entradas y salidas

**Consume:** el caso de uso y las clases de la [Fase 1](../01-fase1-analisis-del-modulo/); los
requisitos de la [Fase 2](../02-fase2-estado-del-arte/requisitos.md); las alertas reales y el
dataset etiquetado de la [Fase 3](../03-fase3-entorno-de-pruebas/); el flujo, el catálogo, los
perfiles de modelo y las métricas de la [Fase 4](../04-fase4-diseno-de-arquitectura/).

**Entrega a:** la [Fase 6](../06-fase6-evaluacion-del-prototipo/) — el prototipo ejecutable y las
trazas sobre las que se calculan las métricas.

---

## Estado

**En curso.** El subproyecto **5A** (núcleo de decisión) está hecho: corre sobre el dataset
etiquetado real de la Fase 3 y produce trazas auditables — ver [`prototipo/README.md`](../../prototipo/README.md).
Quedan **5B** (conector SSH + validación humana TUI + verificación por reescaneo) y **5C**
(clasificador y justificador reales, ML, detrás de la misma interfaz que hoy usa el baseline
determinista de 5A).

**Criterio de cierre** (roadmap): el prototipo procesa el dataset de prueba completo y produce
clasificaciones priorizadas con justificación explicable.

Antes de arrancar conviene resolver dos cosas: el **dataset etiquetado** de la Fase 3, sin el cual
el clasificador no se puede ajustar, y la **revisión pendiente de la Fase 4** —[RF-17 a RF-20 y
RNF-14](../02-fase2-estado-del-arte/requisitos.md), más la regla que traduce clasificación en acción—, porque afecta directamente al conector y
a la validación humana.

>**Decisión de stack pendiente.** El prototipo es Python (atado por el ecosistema ML del
>clasificador y el justificador). Queda abierto evaluar **Go para el conector SSH** —binario
>estático, buena librería SSH, robustez para un componente que ejecuta y traza acciones— cuando se
>aborde el Paso 14; se decide por sus méritos entonces, no antes.

> **Sobre el alcance.** Las acciones que el motor ejecuta sobre el entorno de pruebas son un
> mecanismo de **validación en entorno controlado**, no respuesta automatizada en producción, que
> el plan declara trabajo futuro. La finalidad es medir la calidad de la decisión, no remediar
> incidentes reales.
