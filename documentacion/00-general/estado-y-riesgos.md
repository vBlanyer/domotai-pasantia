# Estado del proyecto, incongruencias y riesgos

Documento de trabajo interno. Recoge qué está decidido, qué está bloqueado y qué contradicciones existen hoy entre los documentos del proyecto. **No sustituye al [plan de trabajo](./planDeTrabajoActualizado.md) ni al [roadmap](./roadmap.md)**, que son los documentos que van a coordinación y que no cambian con esta revisión.

Su propósito principal es preparar la reunión con la empresa: las incongruencias 1, 3 y 4 solo pueden resolverlas ellos.

---

## 1. Estado por fase

*Actualizado a 31/08/2026.*

| Fase | Estado | Qué hay hecho / qué falta |
|------|--------|----------------------------|
| 1 — Análisis del módulo propietario | **Completa por modelado** | Ejecutada por modelado al no haber cliente: [modelo de cliente genérico](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md) y [caso de uso acotado](../01-fase1-analisis-del-modulo/caso-de-uso-acotado.md), con las limitaciones y los cinco puntos de variabilidad. Sigue abierto solo lo que depende de la empresa (I-4). |
| 2 — Estado del arte | **Completa** | Estado del arte MDR/XDR **y de los modelos de lenguaje aplicados a seguridad**, con la comparación reglas frente a IA. **34 requisitos** (20 RF + 14 RNF) en un [registro único](../02-fase2-estado-del-arte/requisitos.md). Encuadre de mercado reorientado del segmento PYME al cliente modelado en la Fase 1. |
| 3 — Entorno de pruebas | **Completa** | Red del cliente de 7 nodos, Metasploitable con ground truth, Wazuh generando alertas reales, auditor Nmap normalizado, todo reproducible con `lab/lab.sh` y con [guía de instalación](../../lab/docs/instalacion.md). **Dataset de alertas etiquetado entregado** (`lab/dataset/etiquetado.jsonl`: 410 alertas, 20 VP / 16 FP, particionado). Falta solo: equipo de borde OpenWrt real (vrnetlab bloqueado). |
| 4 — Arquitectura | **Cerrada** | Flujo, protocolos, auditoría, modelo (perfiles A/B), catálogo de acciones con impacto, métricas y baseline, arquitectura consolidada, y la [política de decisión y perfil de cliente](../04-fase4-diseno-de-arquitectura/politica-decision-continuidad.md) (revisión RF-17 a RF-20 y RNF-14 absorbida el 31/08). Único hueco: probar el catálogo sobre OpenWrt real. |
| 5 — Implementación | **No iniciada** | Es el siguiente bloque. Empieza por el módulo de ingesta, que ya tiene entrada real (`alerts.json`) y dataset para entrenar y evaluar. |
| 6 — Evaluación | **No iniciada** | Ya **no** está bloqueada: baseline (nivel de Wazuh), ground truth y métricas están definidos. Depende de tener el prototipo (Fase 5). |
| 7 — Documentación final | **No iniciada** | Buena parte del material ya existe en los documentos de fase; el informe los consolida. |

### Progreso del laboratorio (Fase 3, verificado)

Lo que funciona hoy, medido y reproducible (`sh lab/lab.sh up && sh lab/lab.sh test`):

- **Red del cliente**: punto de entrega → equipo de borde → switch → {puesto, iot, servidor vulnerable}, más auditor en el plano de gestión. Conectividad de extremo a extremo, 2 saltos por el borde. Los identificadores de nodo del `.clab.yml` siguen la terminología actual: `proveedor`, `borde`, `sw-lan`, `puesto`, `iot`, `objetivo-vuln` y `auditor`.
- **Superficie de ataque real**: el `iot` expone telnet sin auth y web; el `objetivo-vuln` es Metasploitable con 19 puertos y CVEs documentados (puerta trasera vsftpd, ingreslock, Samba…).
- **Alertas reales**: Wazuh recibe syslog del objetivo y clasifica — login fallido → nivel 5, fuerza bruta correlacionada → nivel 10, con IP y usuario parseados. Visor en vivo (`lab/scripts/ver-alertas.sh`).
- **Memoria medida**: laboratorio + Wazuh < 0,8 GB, frente a los ~6 GB estimados. El único límite real es el entorno de desarrollo.

**Límite estructural del laboratorio:** el equipo de borde es un contenedor Linux provisional (solo encamina), no OpenWrt, porque el arranque de vrnetlab se cuelga. Deja de ser bloqueante desde que el caso de uso se acota por familia de alerta y no por equipo —el nodo IoT y el servidor vulnerable ya ejercitan la misma superficie—, pero el borde con firmware real sigue siendo el escenario más representativo. Ver [lab/docs/mediciones.md](../../lab/docs/mediciones.md).

---

## 2. Decisiones cerradas

| # | Decisión | Documento |
|---|----------|-----------|
| D1 | El plan de trabajo y el roadmap **no se modifican**; la información nueva va al detalle de fases | — |
| D2 | El sandbox es **la red del cliente desde el ODF hacia dentro** (borde, red interna, servidores, puestos); los objetivos prioritarios son los **servicios de gestión expuestos**. *Sustituye al encuadre FTTx/CPE de agosto 2026.* | [sandbox](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) · [Fase 1](../01-fase1-analisis-del-modulo/) |
| D3 | Plataforma de laboratorio: **Containerlab**. Descartados Packet Tracer (simula, no virtualiza) y CML (tope de nodos) | [sandbox §2](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) |
| D4 | Canal motor de triaje → sandbox: **SSH**, acotado a un **catálogo cerrado de acciones**. TR-069/TR-369 como evolución | [protocolos](../04-fase4-diseno-de-arquitectura/protocolos-comunicacion-sandbox.md) |
| D5 | Auditoría limitada a **escaneo de red**: Nmap inventaría, Greenbone dictamina. Sin análisis de firmware | [auditoría](../04-fase4-diseno-de-arquitectura/auditoria-de-vulnerabilidades-del-sandbox.md) |
| D6 | Modelo en **dos perfiles**: A híbrido (equipo actual), B con Foundation-Sec-8B (si hay hardware) | [modelo](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) |
| D10 | El **módulo de ingesta ocupa el papel del playbook** en el laboratorio; no se crea una caja aparte | [flujo §3](../04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md) |
| D8 | **Wazuh dentro del sandbox** como fuente de alertas y **su nivel de regla como baseline** | [sandbox §5.1](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) |
| D9 | El Perfil A incorpora un **modelo de 3B en línea** para la justificación breve de la validación humana | [modelo §3](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) |
| D7 | Dos abstracciones sostienen el diseño: el **conector** (acciones abstractas) y la **interfaz de análisis** (`clasificar`/`justificar`) | [protocolos](../04-fase4-diseno-de-arquitectura/protocolos-comunicacion-sandbox.md), [modelo §5](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) |
| D11 | La interacción humana del prototipo es **por terminal (TUI/CLI)**; **sin UI gráfica**. Una UI gráfica queda como **trabajo futuro** tras culminar el prototipo | [flujo §7](../04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md) |

---

## 3. Incongruencias

Clasificadas por severidad. **Bloqueante** = impide avanzar. **Estructural** = el plan asume algo que no se cumple. **De diseño** = dos documentos nuestros se contradicen. **Menor** = riesgo de confusión.

---

### I-1 · No existe la fuente de alertas — ~~BLOQUEANTE~~ **RESUELTA**

El flujo previsto es `logs → playbook → motor de triaje`. El sistema de logs y el playbook son de la empresa, y **no hay empresa ni sistema definidos**.

Agravante detectado al revisar: el [diseño del sandbox](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) **no contempla ningún componente que genere alertas**. Produce telemetría de red y vulnerabilidades, pero nada que el motor de triaje pueda triar. **El motor de triaje no tiene entrada.**

**Choca con:** el criterio de cierre de la Fase 3 — *«el entorno procesa alertas de prueba de punta a punta»*.

**Resolución (agosto 2026):** se despliega **Wazuh dentro del sandbox** como fuente de alertas de laboratorio — agentes en los nodos Linux y reenvío de syslog desde el equipo de borde OpenWrt. El proyecto deja de depender de la empresa para avanzar. Si su sistema llega, se integra como segunda fuente por el mismo módulo de ingesta. Ver [sandbox §5.1](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md).

---

### I-2 · Dos *ground truths* distintos tratados como uno — ~~BLOQUEANTE~~ **RESUELTA**

El diseño del sandbox afirma que «la topología es el dataset». Eso es cierto para **vulnerabilidades**: se sabe qué CVE hay en cada nodo. Pero el plan exige ground truth de **alertas**: verdadero positivo frente a falso positivo.

**No son lo mismo y no hay puente documentado entre ambos.** Es un error de redacción de la Fase 3 que debe corregirse explícitamente, no matizarse.

**Resolución (agosto 2026):** la sección 6 del diseño del sandbox se reescribió para separar ambos explícitamente y documentar el puente: cada alerta de Wazuh se contrasta contra el inventario de vulnerabilidades del nodo al que apunta, y de ahí sale la etiqueta de verdadero o falso positivo.

---

### I-3 · No hay baseline, luego la Fase 6 no es ejecutable — ~~BLOQUEANTE~~ **RESUELTA**

La evaluación compara el prototipo contra «el método tradicional de referencia», que en la práctica es la clasificación o severidad que asigna hoy el sistema existente. Sin ese sistema **no hay contra qué medir**, y la Fase 6 completa queda sin sustento.

**Resolución (agosto 2026):** el **nivel de regla de Wazuh** se adopta como método tradicional de referencia. Es literalmente el enfoque basado en reglas y firmas que el plan quiere como comparación, y viene incluido con la fuente de alertas. Si más adelante hay acceso al sistema de la empresa, su severidad se añade como segundo baseline.

---

### I-4 · La identidad del módulo propietario depende de la empresa — ESTRUCTURAL

~~La Fase 1 está vacía~~ **Ya no.** La Fase 1 se ejecutó **por modelado** (cliente genérico y caso de uso acotado), del mismo modo que I-1 se resolvió supliendo la fuente de alertas con Wazuh. Sus salidas —perímetro, clases, criticidad, política de continuidad— existen y las fases 3, 4 y 5 ya las consumen.

Lo único que **sigue abierto**, y solo lo puede resolver la empresa: **¿son la misma cosa «el módulo propietario» del plan y «el sistema existente que emite logs»?** No cambia el avance del prototipo —el diseño está aislado tras el módulo de ingesta—, pero sí afinaría el análisis si el sistema real llega.

**Quién puede resolverlo:** la empresa.

---

### I-5 · El estado del arte no apunta a donde va el proyecto — ESTRUCTURAL

[mdr-xdr.md](../02-fase2-estado-del-arte/mdr-xdr.md) y [limitacionesDeXDR.md](../02-fase2-estado-del-arte/limitacionesDeXDR.md) analizan plataformas XDR/MDR empresariales, operación de SOC y fatiga de alertas, con foco en PYMEs. El proyecto derivó a **seguridad de la red de un cliente**, desde el punto de entrega hacia dentro, que es otro mercado y otra superficie.

Los requisitos funcionales y no funcionales de la Fase 2 se derivaron del primer contexto. **No están necesariamente mal: están sin verificar** contra el segundo.

**Quién puede resolverlo:** nosotros, con una revisión acotada de los RF/RNF.

---

### I-6 · El Perfil A contradice el diseño del flujo — ~~DE DISEÑO~~ **RESUELTA**

Dos choques directos entre [selección del modelo](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) y el [flujo de operación](../04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md):

- **Validación humana sin justificación.** El flujo establece: motor de triaje decide → justificación → validación humana → ejecución. Pero el Perfil A genera la justificación **en lote y fuera de línea**, así que el validador humano decidiría sin tener delante el razonamiento que debía darle criterio.
- **«Punta a punta» imposible.** El criterio de cierre de la Fase 3 lo exige; el Perfil A prohíbe tener sandbox y modelo vivos a la vez.

**Resolución (agosto 2026):** se añade al Perfil A un **tercer componente de 3B cuantizado** (Phi-4-mini o Llama 3.2 3B, ~2 GB) que redacta una justificación breve en 15–20 s, disponible para la validación humana. El 8B en lote queda para la justificación extensa de auditoría y evaluación. El camino interactivo —alerta, clasificación, justificación breve, validación, acción— **sí es demostrable en vivo** en el equipo actual, así que el criterio de cierre de la Fase 3 se sostiene sin reescribirse.

---

### I-7 · Tensión de alcance gestionada, no resuelta — DE DISEÑO

El sandbox se encuadró como «entorno controlado de validación» para no tocar el alcance aprobado. Funciona sobre el papel, pero **el motor de triaje sigue decidiendo y ejecutando acciones**, que es respuesta automatizada — declarada trabajo futuro en el plan. Una lectura atenta desde coordinación podría objetarlo.

**Quién puede resolverlo:** coordinación, si se decide plantearlo abiertamente.

---

### I-8 · Material de referencia con premisa superada — MENOR

[symons.md](../archivo/symons.md) y [herramientas-auxiliares.md](../archivo/herramientas-auxiliares.md) llevan una nota de condicionalidad, pero su contenido interno —el stack Atomic Red Team → Sysmon → Sigma— sigue contradiciendo el diseño actual. Está señalado, no reescrito.

---

### I-9 · Dos planes de trabajo conviviendo — MENOR

[planDeTrabajo.md](../archivo/planDeTrabajo.md) (6 objetivos, objetivo 4 con la frase cortada) sigue junto a [planDeTrabajoActualizado.md](./planDeTrabajoActualizado.md) (7 objetivos). Riesgo de que alguien lea el equivocado.

---

## 4. Propuesta: Wazuh como generador de alertas del sandbox

Una sola decisión resuelve **I-1, I-2 e I-3** a la vez: desplegar **Wazuh dentro del sandbox**, con agentes en los nodos OpenWrt y Linux, un manager que correlaciona, y sus alertas como entrada del motor de triaje.

| Incongruencia | Cómo la resuelve |
|---------------|------------------|
| **I-1** — sin fuente de alertas | El motor de triaje pasa a tener entrada real, generada en el propio laboratorio |
| **I-2** — ground truth equivocado | Las alertas de Wazuh sobre nodos con vulnerabilidades conocidas **sí** se pueden etiquetar como VP/FP |
| **I-3** — sin baseline | El **nivel de regla de Wazuh es exactamente «el método tradicional basado en reglas y firmas»** contra el que el plan quiere comparar. El baseline sale gratis |

Encaja con lo ya escrito: el roadmap tiene la casilla «Evaluar si herramientas como Wazuh se usarán como base de ingestión», sin marcar, y [edr-xdr-mdr-telemetria.md](../04-fase4-diseno-de-arquitectura/edr-xdr-mdr-telemetria.md) ya lo encuadra como infraestructura y no como solución del prototipo. Solo falta **decidirlo y meterlo en la topología**, donde hoy no aparece.

**Coste:** RAM en un equipo que ya va justo. Habrá que comprobar si Wazuh y Greenbone pueden convivir o si también se separan en el tiempo, como el modelo. Ver el presupuesto de memoria en [selección del modelo §2](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md).

---

## 5. Preguntas para la empresa

Consolidadas. **Ninguna bloquea ya el avance** tras adoptar Wazuh como fuente de alertas y baseline, pero todas mejoran el resultado y deben plantearse en la reunión.

1. **¿Son la misma cosa «el módulo propietario» y «el sistema existente que emite logs»?** (I-4)
2. **¿Cuál es el formato exacto de salida de ese sistema?** Bloquea la especificación del módulo de ingesta.
3. **¿Qué severidad o clasificación asigna hoy?** Es el baseline de la Fase 6 (I-3).
4. **¿Tendremos acceso real a ese sistema y al playbook, o construimos un sustituto en el laboratorio?** (I-1)
5. **¿El playbook espera respuesta del motor de triaje, o es asíncrono?** Determina el presupuesto de latencia y si la validación humana en línea es viable.
6. **¿Existe ya un catálogo de acciones que el playbook sepa ejecutar?**
7. **¿Hay alguna máquina de laboratorio disponible?** Con 32 GB o una GPU dedicada, el Perfil B pasa a ser viable y el prototipo pierde un componente entero.

---

## 6. Estado de resolución

| # | Incongruencia | Severidad | Responsable | Estado |
|---|---------------|-----------|-------------|--------|
| I-1 | Sin fuente de alertas | Bloqueante | Nosotros | **Resuelta** — Wazuh en el sandbox |
| I-2 | Dos ground truths | Bloqueante | Nosotros | **Resuelta** — sandbox §6 reescrita |
| I-11 | Playbook sin sustituto en el laboratorio | Estructural | Nosotros | **Resuelta** — lo ocupa la ingesta (D10) |
| I-3 | Sin baseline | Bloqueante | Nosotros | **Resuelta** — nivel de regla de Wazuh |
| I-4 | Identidad del módulo propietario | Estructural | Empresa | **Parcial** — Fase 1 hecha por modelado; solo queda la pregunta de identidad, que depende de la empresa |
| I-5 | Estado del arte desalineado | Estructural | Nosotros | **Resuelta** — revisión de requisitos contra el contexto del cliente |
| I-6 | Perfil A vs flujo | De diseño | Nosotros | **Resuelta** — modelo de 3B en línea |
| I-7 | Tensión de alcance | De diseño | Coordinación | Gestionada |
| I-8 | Material con premisa superada | Menor | Nosotros | **Resuelta** — movido a documentacion/archivo/ |
| I-9 | Dos planes conviviendo | Menor | Nosotros | **Resuelta** — plan viejo movido a documentacion/archivo/ |
| I-10 | El componente central se llamaba «EDR» siendo el motor de triaje de un XDR | De diseño | Nosotros | **Resuelta** — renombrado a «motor de triaje» |
