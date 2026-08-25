# Camino paso a paso

Plan de ejecución ordenado, derivado del [roadmap](./roadmap.md) y de las decisiones recogidas en [estado y riesgos](./estado-y-riesgos.md). El roadmap dice **qué** hay que hacer por fase; este documento dice **en qué orden** y **cuándo se puede dar por hecho** cada cosa.

No sustituye al roadmap ni al plan de trabajo.

---

## Bloque 0 — La compuerta: medir antes de construir

### Paso 1 · Verificar el presupuesto de memoria

**Todo el diseño descansa en estimaciones que nadie ha comprobado.** Si no caben en el equipo, cambia el plan, no la realidad. Este paso va primero y condiciona el resto.

Desplegar por incrementos y **medir el consumo real en cada escalón**:

| Escalón | Qué se añade | Estimado |
|---------|--------------|----------|
| 1 | Containerlab mínimo: borde + CPE OpenWrt + un endpoint | ~1,5–2 GB |
| 2 | + Wazuh manager **sin indexer ni dashboard** | +1–2 GB |
| 3 | + modelo de 3B cuantizado | +2–2,3 GB |
| 4 | + Greenbone | +4–8 GB |
| 5 | + modelo de 8B cuantizado | +5 GB |

**Hecho cuando:** existe una tabla con el consumo medido de cada escalón y se sabe qué combinaciones caben en 16 GB.

**Decisión que produce:** hasta qué escalón se puede llegar simultáneamente. Si el escalón 4 no cabe junto al 2, Greenbone se separa en el tiempo o se sustituye por Nmap con scripts NSE.

> **Riesgo principal del proyecto.** Si ni siquiera el escalón 3 cabe con holgura, hay que replantear el Perfil A y volver a pedir hardware. Merece la pena saberlo la primera semana y no en la Fase 5.

---

## Bloque 1 — Entorno de pruebas (Fase 3)

### Paso 2 · Topología mínima versionada

Tres nodos: borde, CPE OpenWrt y un endpoint Linux. Nada más todavía.

**Hecho cuando:** `containerlab deploy` levanta la topología desde un `.clab.yml` **commiteado**, hay conectividad de extremo a extremo, y `containerlab destroy && deploy` devuelve el laboratorio a un estado idéntico.

**Ojo:** la imagen de OpenWrt del `kind: openwrt` **se construye localmente** con vrnetlab; no se descarga lista. Es un paso previo que suele llevar más de lo esperado.

### Paso 3 · Wazuh generando alertas

Manager sin indexer ni dashboard. Reenvío de syslog desde el CPE, agente Wazuh en el endpoint Linux.

**Hecho cuando:** una acción deliberada sobre el CPE (por ejemplo, un intento de acceso fallido) **aparece como alerta en `alerts.json`**, con su nivel de regla.

**Ojo:** los dispositivos sin agente registran bajo el manager (ID 000). Hay que comprobar desde el principio que se puede **atribuir cada alerta a su nodo** mediante los campos del evento; si no, el etiquetado del Paso 6 se complica.

### Paso 4 · Nodos vulnerables e inventario documentado

Añadir a la topología los objetivos con CVEs conocidos, y **documentar por nodo qué se espera encontrar**.

**Hecho cuando:** el repositorio contiene el `.clab.yml` y, junto a él, el inventario de vulnerabilidades esperadas por nodo.

### Paso 5 · Auditor de vulnerabilidades

Greenbone si el Paso 1 dijo que cabe; Nmap con scripts NSE si no.

**Hecho cuando:** una campaña completa produce hallazgos normalizados, con la **versión del feed fijada y registrada**.

### Paso 6 · Dataset de alertas etiquetado

Generar actividad sobre el sandbox, recolectar las alertas de Wazuh, y **etiquetar cada una** contrastándola contra el inventario del Paso 4: verdadero positivo si la exposición existe, falso positivo si no.

**Hecho cuando:** existe un conjunto de alertas etiquetado, con el nivel de regla de Wazuh conservado en cada una, y **particionado en entrenamiento y evaluación con nodos o campañas disjuntos**.

> **El error que invalida la Fase 6:** entrenar el clasificador y medirlo sobre las mismas alertas. La partición no es opcional.

**Cierra la Fase 3.**

---

## Bloque 2 — Completar la arquitectura (Fase 4)

Puede solaparse con el Bloque 1: no depende de que el entorno esté desplegado.

### Paso 7 · Catálogo cerrado de acciones
> **HECHO** (24/08/2026).

Enumerar cada acción que el motor de triaje puede ordenar, con precondiciones, efecto esperado, reversibilidad y cómo verificar que se aplicó.

**Hecho cuando:** el catálogo está cerrado y cada acción tiene su comando concreto sobre OpenWrt o Linux.

### Paso 8 · Métricas y forma de cálculo
> **HECHO** (24/08/2026).

Precisión, recall, F1, tasa de falsos positivos y tiempo de triaje, definidos sobre el dataset del Paso 6 y sobre el baseline de Wazuh.

**Hecho cuando:** cada métrica tiene su fórmula y se sabe de qué campo del dataset sale.

### Paso 9 · Revisar los requisitos contra el contexto FTTx
> **HECHO** (24/08/2026).

Los RF/RNF de la Fase 2 se derivaron de XDR empresarial y SOC. Revisar cuáles siguen aplicando a triaje de alertas sobre CPE de red de acceso, cuáles sobran y cuáles faltan. Resuelve la incongruencia **I-5**.

**Hecho cuando:** cada requisito está marcado como vigente, descartado o nuevo, con una línea de justificación.

### Paso 10 · Diagrama de arquitectura consolidado
> **HECHO** (24/08/2026).

Un único diagrama que reúna sandbox, Wazuh, motor de triaje, conector, auditor y validación humana.

**Cierra la Fase 4.**

---

## Bloque 3 — Prototipo (Fase 5)

### Paso 11 · Ingesta y normalización
Leer `alerts.json`, normalizar al esquema de entrada del motor de triaje, **conservando el nivel de regla** como baseline.

### Paso 12 · Interfaz de análisis y clasificador
Implementar `clasificar` y `justificar` como interfaz, y detrás el encoder con fine-tuning sobre la partición de entrenamiento del Paso 6.

**Hecho cuando:** dada una alerta, devuelve clase, prioridad y **confianza numérica**.

### Paso 13 · Justificador en línea
Modelo de 3B cuantizado detrás de `justificar`.

**Hecho cuando:** produce una justificación breve que **referencia campos concretos de la alerta** (RNF-02) en un tiempo tolerable para una persona.

### Paso 14 · Conector SSH
Traduce acciones abstractas del catálogo a comandos, con autenticación por clave, privilegio mínimo y registro de orden, comando, código de salida y salida.

**Hecho cuando:** el motor de triaje ordena una acción del catálogo y el nodo del sandbox la ejecuta, con la traza completa registrada.

### Paso 15 · Validación humana y trazas
Retener las órdenes que requieren aprobación, mostrar la justificación del Paso 13, registrar la decisión del analista.

**Hecho cuando:** el **lazo completo funciona en vivo**: alerta de Wazuh → clasificación → justificación → validación humana → acción sobre el CPE → verificación.

**Cierra la Fase 5.**

---

## Bloque 4 — Evaluación (Fase 6)

### Paso 16 · Justificaciones extensas en lote
Con el sandbox apagado, ejecutar el modelo de 8B sobre el dataset guardado.

### Paso 17 · Medir prototipo contra baseline
Ambos sobre **el mismo dataset y la misma partición de evaluación**. Registrar perfil, modelo, versión y cuantización en cada ejecución.

**Hecho cuando:** hay una tabla comparativa de métricas entre el prototipo y el nivel de regla de Wazuh.

### Paso 18 · Análisis de errores
Casos de éxito, errores sistemáticos, y las limitaciones conocidas: el auditor no es infalible, el corte de conocimiento del modelo, el desajuste de dominio del encoder.

**Cierra la Fase 6.**

---

## Bloque 5 — Cierre (Fase 7)

### Paso 19 · Informe final
Arquitectura, decisiones y alternativas descartadas, resultados, limitaciones y trabajo futuro. Buena parte ya está escrita en los documentos de fase: el informe los consolida.

---

## En paralelo, sin bloquear nada

| Tarea | Por qué | Incongruencia |
|-------|---------|---------------|
| Reunión con la empresa: las siete preguntas de [estado y riesgos §5](./estado-y-riesgos.md) | Ya no bloquean, pero mejoran el resultado. La 7 (hardware) puede cambiar el Perfil | I-4 |
| Retirar o archivar `planDeTrabajo.md` | Convive con la versión actualizada y alguien puede leer el equivocado | I-9 |
| Reescribir o podar `herramientas-auxiliares.md` y `symons.md` | Llevan nota de condicionalidad, pero su contenido sigue contradiciendo el diseño FTTx | I-8 |
| Plantear a coordinación el encuadre del sandbox | El motor de triaje ejecuta acciones; está encuadrado como validación, pero conviene que lo sepan | I-7 |

---

## Por dónde empezar

**El Paso 1.** No es burocracia: es la única forma de saber si el diseño de los últimos días se sostiene en el equipo que hay. Cuesta poco y puede ahorrar semanas.

Después, los pasos 2 y 3 en ese orden. Con el Paso 3 terminado el proyecto tiene, por primera vez, **una alerta real generada por el propio laboratorio** — que es lo que faltaba para que el motor de triaje tuviera algo que triar.
