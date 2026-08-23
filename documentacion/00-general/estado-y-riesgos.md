# Estado del proyecto, incongruencias y riesgos

Documento de trabajo interno. Recoge qué está decidido, qué está bloqueado y qué contradicciones existen hoy entre los documentos del proyecto. **No sustituye al [plan de trabajo](./planDeTrabajoActualizado.md) ni al [roadmap](./roadmap.md)**, que son los documentos que van a coordinación y que no cambian con esta revisión.

Su propósito principal es preparar la reunión con la empresa: las incongruencias 1, 3 y 4 solo pueden resolverlas ellos.

---

## 1. Estado por fase

| Fase | Estado | Comentario |
|------|--------|------------|
| 1 — Análisis del módulo propietario | **Vacía / bloqueada** | No hay módulo ni cliente definido. Es la raíz de la que dependen las fases 3, 4 y 6 |
| 2 — Estado del arte | **Completa** | Único bloque sustancial terminado. Ver incongruencia #5 |
| 3 — Entorno de pruebas | **Diseñada, no ejecutada** | Sandbox especificado; nada desplegado. Falta la fuente de alertas |
| 4 — Arquitectura | **Parcial** | Flujo, protocolos, auditoría y modelo escritos. Faltan diagrama consolidado, umbrales, métricas y baseline |
| 5 — Implementación | **No iniciada** | — |
| 6 — Evaluación | **No iniciada** | Bloqueada por ausencia de baseline (#3) |
| 7 — Documentación final | **No iniciada** | — |

---

## 2. Decisiones cerradas

| # | Decisión | Documento |
|---|----------|-----------|
| D1 | El plan de trabajo y el roadmap **no se modifican**; la información nueva va al detalle de fases | — |
| D2 | El sandbox es la cadena de acceso **FTTx**; el objetivo principal es el **CPE/HGU** | [sandbox](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) |
| D3 | Plataforma de laboratorio: **Containerlab**. Descartados Packet Tracer (simula, no virtualiza) y CML (tope de nodos) | [sandbox §2](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) |
| D4 | Canal EDR → sandbox: **SSH**, acotado a un **catálogo cerrado de acciones**. TR-069/TR-369 como evolución | [protocolos](../04-fase4-diseno-de-arquitectura/protocolos-comunicacion-sandbox.md) |
| D5 | Auditoría limitada a **escaneo de red**: Nmap inventaría, Greenbone dictamina. Sin análisis de firmware | [auditoría](../04-fase4-diseno-de-arquitectura/auditoria-de-vulnerabilidades-del-sandbox.md) |
| D6 | Modelo en **dos perfiles**: A híbrido (equipo actual), B con Foundation-Sec-8B (si hay hardware) | [modelo](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) |
| D7 | Dos abstracciones sostienen el diseño: el **conector** (acciones abstractas) y la **interfaz de análisis** (`clasificar`/`justificar`) | [protocolos](../04-fase4-diseno-de-arquitectura/protocolos-comunicacion-sandbox.md), [modelo §5](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) |

---

## 3. Incongruencias

Clasificadas por severidad. **Bloqueante** = impide avanzar. **Estructural** = el plan asume algo que no se cumple. **De diseño** = dos documentos nuestros se contradicen. **Menor** = riesgo de confusión.

---

### I-1 · No existe la fuente de alertas — BLOQUEANTE

El flujo previsto es `logs → playbook → EDR`. El sistema de logs y el playbook son de la empresa, y **no hay empresa ni sistema definidos**.

Agravante detectado al revisar: el [diseño del sandbox](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) **no contempla ningún componente que genere alertas**. Produce telemetría de red y vulnerabilidades, pero nada que el EDR pueda triar. **El EDR no tiene entrada.**

**Choca con:** el criterio de cierre de la Fase 3 — *«el entorno procesa alertas de prueba de punta a punta»*.

**Quién puede resolverlo:** la empresa (si cede el sistema), o nosotros (ver §4).

---

### I-2 · Dos *ground truths* distintos tratados como uno — BLOQUEANTE

El diseño del sandbox afirma que «la topología es el dataset». Eso es cierto para **vulnerabilidades**: se sabe qué CVE hay en cada nodo. Pero el plan exige ground truth de **alertas**: verdadero positivo frente a falso positivo.

**No son lo mismo y no hay puente documentado entre ambos.** Es un error de redacción de la Fase 3 que debe corregirse explícitamente, no matizarse.

**Quién puede resolverlo:** nosotros, una vez resuelta I-1.

---

### I-3 · No hay baseline, luego la Fase 6 no es ejecutable — BLOQUEANTE

La evaluación compara el prototipo contra «el método tradicional de referencia», que en la práctica es la clasificación o severidad que asigna hoy el sistema existente. Sin ese sistema **no hay contra qué medir**, y la Fase 6 completa queda sin sustento.

**Quién puede resolverlo:** la empresa, o nosotros adoptando un motor de reglas propio como baseline (ver §4).

---

### I-4 · La Fase 1 está vacía y es la raíz de las demás — ESTRUCTURAL

«Analizar el módulo propietario» no ha empezado porque no hay módulo ni cliente. Las fases 3, 4 y 6 consumen sus salidas.

Sin resolver además: **¿son la misma cosa «el módulo propietario» del plan y «el sistema existente que emite logs» que describió la empresa?** Nadie lo ha preguntado, y cambia el análisis.

**Quién puede resolverlo:** la empresa.

---

### I-5 · El estado del arte no apunta a donde va el proyecto — ESTRUCTURAL

[mdr-xdr.md](../02-fase2-estado-del-arte/mdr-xdr.md) y [limitacionesDeXDR.md](../02-fase2-estado-del-arte/limitacionesDeXDR.md) analizan plataformas XDR/MDR empresariales, operación de SOC y fatiga de alertas, con foco en PYMEs. El proyecto derivó a **seguridad de CPE en la red de acceso de un operador**, que es otro mercado y otra superficie.

Los requisitos funcionales y no funcionales de la Fase 2 se derivaron del primer contexto. **No están necesariamente mal: están sin verificar** contra el segundo.

**Quién puede resolverlo:** nosotros, con una revisión acotada de los RF/RNF.

---

### I-6 · El Perfil A contradice el diseño del flujo — DE DISEÑO

Dos choques directos entre [selección del modelo](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) y el [flujo de operación](../04-fase4-diseno-de-arquitectura/flujo-edr-playbook-sandbox.md):

- **Validación humana sin justificación.** El flujo establece: EDR decide → justificación → validación humana → ejecución. Pero el Perfil A genera la justificación **en lote y fuera de línea**, así que el validador humano decidiría sin tener delante el razonamiento que debía darle criterio.
- **«Punta a punta» imposible.** El criterio de cierre de la Fase 3 lo exige; el Perfil A prohíbe tener sandbox y modelo vivos a la vez.

**Quién puede resolverlo:** nosotros. Requiere decidir qué cede: el flujo, el criterio de cierre o el perfil.

---

### I-7 · Tensión de alcance gestionada, no resuelta — DE DISEÑO

El sandbox se encuadró como «entorno controlado de validación» para no tocar el alcance aprobado. Funciona sobre el papel, pero **el EDR sigue decidiendo y ejecutando acciones**, que es respuesta automatizada — declarada trabajo futuro en el plan. Una lectura atenta desde coordinación podría objetarlo.

**Quién puede resolverlo:** coordinación, si se decide plantearlo abiertamente.

---

### I-8 · Material de referencia con premisa superada — MENOR

[symons.md](../04-fase4-diseno-de-arquitectura/symons.md) y [herramientas-auxiliares.md](../04-fase4-diseno-de-arquitectura/herramientas-auxiliares.md) llevan una nota de condicionalidad, pero su contenido interno —el stack Atomic Red Team → Sysmon → Sigma— sigue contradiciendo el diseño FTTx. Está señalado, no reescrito.

---

### I-9 · Dos planes de trabajo conviviendo — MENOR

[planDeTrabajo.md](./planDeTrabajo.md) (6 objetivos, objetivo 4 con la frase cortada) sigue junto a [planDeTrabajoActualizado.md](./planDeTrabajoActualizado.md) (7 objetivos). Riesgo de que alguien lea el equivocado.

---

## 4. Propuesta: Wazuh como generador de alertas del sandbox

Una sola decisión resuelve **I-1, I-2 e I-3** a la vez: desplegar **Wazuh dentro del sandbox**, con agentes en los nodos OpenWrt y Linux, un manager que correlaciona, y sus alertas como entrada del EDR.

| Incongruencia | Cómo la resuelve |
|---------------|------------------|
| **I-1** — sin fuente de alertas | El EDR pasa a tener entrada real, generada en el propio laboratorio |
| **I-2** — ground truth equivocado | Las alertas de Wazuh sobre nodos con vulnerabilidades conocidas **sí** se pueden etiquetar como VP/FP |
| **I-3** — sin baseline | El **nivel de regla de Wazuh es exactamente «el método tradicional basado en reglas y firmas»** contra el que el plan quiere comparar. El baseline sale gratis |

Encaja con lo ya escrito: el roadmap tiene la casilla «Evaluar si herramientas como Wazuh se usarán como base de ingestión», sin marcar, y [edr-xdr-mdr-telemetria.md](../04-fase4-diseno-de-arquitectura/edr-xdr-mdr-telemetria.md) ya lo encuadra como infraestructura y no como solución del prototipo. Solo falta **decidirlo y meterlo en la topología**, donde hoy no aparece.

**Coste:** RAM en un equipo que ya va justo. Habrá que comprobar si Wazuh y Greenbone pueden convivir o si también se separan en el tiempo, como el modelo. Ver el presupuesto de memoria en [selección del modelo §2](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md).

---

## 5. Preguntas para la empresa

Consolidadas. Las tres primeras desbloquean fases enteras.

1. **¿Son la misma cosa «el módulo propietario» y «el sistema existente que emite logs»?** (I-4)
2. **¿Cuál es el formato exacto de salida de ese sistema?** Bloquea la especificación del módulo de ingesta.
3. **¿Qué severidad o clasificación asigna hoy?** Es el baseline de la Fase 6 (I-3).
4. **¿Tendremos acceso real a ese sistema y al playbook, o construimos un sustituto en el laboratorio?** (I-1)
5. **¿El playbook espera respuesta del EDR, o es asíncrono?** Determina el presupuesto de latencia y si la validación humana en línea es viable.
6. **¿Existe ya un catálogo de acciones que el playbook sepa ejecutar?**
7. **¿Hay alguna máquina de laboratorio disponible?** Con 32 GB o una GPU dedicada, el Perfil B pasa a ser viable y el prototipo pierde un componente entero.

---

## 6. Estado de resolución

| # | Incongruencia | Severidad | Responsable | Estado |
|---|---------------|-----------|-------------|--------|
| I-1 | Sin fuente de alertas | Bloqueante | Empresa / nosotros | Abierta |
| I-2 | Dos ground truths | Bloqueante | Nosotros | Abierta |
| I-3 | Sin baseline | Bloqueante | Empresa / nosotros | Abierta |
| I-4 | Fase 1 vacía | Estructural | Empresa | Abierta |
| I-5 | Estado del arte desalineado | Estructural | Nosotros | Abierta |
| I-6 | Perfil A vs flujo | De diseño | Nosotros | Abierta |
| I-7 | Tensión de alcance | De diseño | Coordinación | Gestionada |
| I-8 | Material con premisa superada | Menor | Nosotros | Señalada |
| I-9 | Dos planes conviviendo | Menor | Nosotros | Abierta |
