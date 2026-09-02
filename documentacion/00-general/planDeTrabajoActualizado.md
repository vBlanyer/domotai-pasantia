# Resumen

Las organizaciones se enfrentan a un volumen creciente de eventos y alertas de seguridad que supera la capacidad de análisis manual de los equipos de operaciones internas, por lo cual muchas veces se debe buscar una forma de automatización y respuesta que pueda ayudar en estos procesos.

Para ello se plantea el uso de servicios de detección y respuesta gestionada (MDR), y su evolución extendida (XDR). Tecnologías que buscan centralizar la detección, correlación y respuesta ante incidentes a través de múltiples fuentes de información como son: la red, los endpoints y las identificaciones de usuarios.

Las soluciones tradicionales están basadas en reglas y firmas, lo cual genera altos volúmenes de falsos positivos, que al final dependen de analistas especializados para su interpretación, lo que limita su adopción en el mercado general, especialmente en pequeñas y medianas empresas.

Este proyecto se centra en el desarrollo de módulos para la detección y el triaje inteligente de eventos de seguridad usando como base una tecnología propietaria de análisis de alertas, con el objetivo de ampliar sus casos de uso.

El sistema buscará clasificar y priorizar alertas, justificar decisiones mediante razonamiento explicable para apoyar al analista y reducir la fatiga por falsos positivos. Se priorizará un caso de uso acotado y la incorporación de validación humana en las decisiones críticas, dejando como trabajo futuro la respuesta automatizada y la integración multicapa en producción.

# Objetivo general

Desarrollar un prototipo para la detección y el triaje de eventos de seguridad en entornos
empresariales, basado en modelos de lenguaje (LLMs) con un **módulo de generación aumentada por
recuperación (RAG)** ejecutado sobre un modelo desplegado de forma local, de forma que permita
clasificar y priorizar alertas con razonamiento explicable, reduciendo los falsos positivos y apoyando
la labor de los analistas de seguridad.

# Objetivos específicos

1. **Analizar y aprender a usar el módulo propietario:** Analizar la solución actual de la empresa para recepción y análisis de datos, identificando las limitaciones que se tengan y necesidades no cubiertas actualmente por el mismo, y definiendo el caso de uso acotado sobre el que se construirá el prototipo.

2. **Revisar el estado del arte:** Analizar las soluciones de MDR/XDR existentes y las aplicaciones de modelos de lenguaje en el ámbito de ciberseguridad, identificando sus ventajas, limitaciones y las necesidades no cubiertas por las herramientas actuales del mercado, para derivar de ello los requisitos funcionales y no funcionales del prototipo.

3. **Configurar un entorno de pruebas:** Instalar y poner en funcionamiento el módulo propietario con casos de prueba, garantizando la privacidad de los datos al evitar su envío a servicios externos, y preparar un conjunto de alertas de prueba **etiquetado** (verdaderos y falsos positivos) que sirva como referencia de evaluación.

4. **Diseñar la arquitectura del sistema:** Definir el flujo de acciones, las reglas de decisión y umbrales, las formas de interacción con el módulo propietario y las herramientas auxiliares, el formato del razonamiento explicable y los puntos de validación humana. Como parte de este diseño se definen también las **métricas de evaluación y el método tradicional de referencia** contra el que se comparará el prototipo.

5. **Implementar el prototipo:** Construir el caso de uso acotado definido en el objetivo 1, integrando la ingesta y normalización de alertas, la clasificación y priorización asistida por modelos de lenguaje, la generación de justificación explicable y el flujo de validación humana en las decisiones críticas, con registro de trazas para auditoría.

6. **Evaluar el prototipo:** Medir el desempeño del sistema frente a escenarios de prueba y al método tradicional de referencia, empleando las métricas y el baseline definidos en el objetivo 4, y analizar errores sistemáticos y limitaciones del enfoque.

7. **Elaborar la documentación técnica:** Generar la documentación e informe técnico que incluya la arquitectura, las decisiones de diseño, los resultados, las limitaciones y las líneas de trabajo futuro.

# Alcance

Queda **dentro** del alcance del proyecto: un prototipo funcional sobre un caso de uso acotado, desplegado en el entorno de pruebas, con clasificación, priorización, **razonamiento explicable apoyado en un módulo RAG local** y validación humana.

Queda **fuera** del alcance y se documenta como trabajo futuro:

- Respuesta automatizada ante incidentes (playbooks de remediación).
- Integración multicapa en producción (correlación de red, endpoints e identidad).
- Aprendizaje continuo a partir de la retroalimentación del analista.
- Despliegue y escalabilidad en entornos de clientes PYME.

# Trazabilidad objetivos → fases

Cada objetivo se corresponde con una fase del [roadmap](./roadmap.md):

| Objetivo | Fase del roadmap |
|----------|------------------|
| 1. Analizar el módulo propietario | Fase 1 — Análisis del módulo propietario |
| 2. Revisar el estado del arte | Fase 2 — Revisión del estado del arte |
| 3. Configurar el entorno de pruebas | Fase 3 — Configuración del entorno de pruebas |
| 4. Diseñar la arquitectura | Fase 4 — Diseño de la arquitectura del sistema |
| 5. Implementar el prototipo | Fase 5 — Implementación del prototipo |
| 6. Evaluar el prototipo | Fase 6 — Evaluación del prototipo |
| 7. Elaborar la documentación técnica | Fase 7 — Documentación técnica e informe final |

# Cambios respecto a la versión anterior

Este documento actualiza a [planDeTrabajo.md](../archivo/planDeTrabajo.md) con las correcciones detectadas al contrastarlo con el roadmap:

1. **Nuevo objetivo 5 (implementación).** La versión anterior pasaba de *diseñar la arquitectura* a *evaluar el prototipo* sin ningún objetivo que mandara construirlo, dejando la Fase 5 del roadmap sin respaldo.
2. **Objetivo 4 completado.** La redacción anterior quedaba cortada en «formas de interacción con herramientas»; ahora enumera reglas, umbrales, interfaces, formato del razonamiento explicable y puntos de validación humana.
3. **Métricas y baseline movidos al diseño (objetivo 4).** El objetivo de evaluación asumía métricas «ya definidas» que nadie definía antes de la Fase 6; definirlas durante el diseño permite implementar sabiendo contra qué se medirá.
4. **Etiquetado del dataset obligatorio (objetivo 3).** El roadmap lo dejaba como «si aplica», pero sin ground truth no se pueden calcular precisión, recall ni F1 en la evaluación.
5. **Objetivos 1 y 2 con salida explícita.** Se añade la definición del caso de uso acotado al objetivo 1 y la derivación de requisitos al objetivo 2, que eran entregables del roadmap sin reflejo en el plan.
6. **Secciones de alcance y trazabilidad.** Se explicita qué queda fuera del proyecto y se fija la correspondencia uno a uno entre objetivos y fases.
