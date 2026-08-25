> ⚠️ **Documento archivado — superado.** Esta es la versión antigua del plan (6 objetivos, uno incompleto).
> El plan vigente es [planDeTrabajoActualizado.md](../00-general/planDeTrabajoActualizado.md). Se conserva solo por trazabilidad.

# Resumen

Las organizaciones se enfrentan a un volumen creciente de eventos y alertas de seguridad que supera la capacidad de análisis manual de los equipos de operaciones internas, por lo cual muchas veces se debe buscar una forma de automatización y respuesta que pueda ayudar en estos procesos.

Para ello se plantea el uso de servicios de detección y respuesta gestionada (MDR), y su evolución extendida (XDR). Tecnologías que buscan centralizar la detección, correlación y respuesta ante incidentes a través de múltiples fuentes de información como son: La red, los endpoints y las identificaciones de usuarios.

Las soluciones tradicionales están basadas en reglas y firmas, lo cual genera altos volúmenes de falsos positivos, que al final dependen de analistas especializados para su interpretación, lo que limita su adopción en el mercado general, especialmente en pequeñas y medianas empresas.

Este proyecto se centra en el desarrollo de módulos para la detección y el triaje inteligente de eventos de seguridad usando como base una tecnología propietaria de análisis de alertas, con el objetivo de ampliar sus casos de uso.

El sistema buscará clasificar y priorizar alertas, justificar decisiones mediante razonamiento explicable para apoyar al analista y reducir la fatiga por falsos positivos. Se priorizará un caso de uso acotado y la incorporación de validación humana en las decisiones críticas, dejando como trabajo futuro la respuesta automatizada y la integración multicapa en producción. 

# Objetivos generales

1. Analizar y aprender a usar el módulo propietario: Analizar la solución actual de la empresa para recepción y análisis de datos, identificando las limitaciones que se tengan y necesidades no cubiertas actualmente por el mismo.

2. Revisar el estado del arte: Analizar las soluciones de MDR/XDR existentes y las aplicaciones de modelos de lenguaje en el ámbito de ciberseguridad, identificando sus ventajas, limitaciones y las necesidades no cubiertas por las herramientas actuales del mercado.

3. Configurar un entorno de pruebas: Instalar y poner en funcionamiento el módulo propietario con casos de prueba, garantizando la privacidad de los datos al evitar su envío a servicios externos.

4. Diseñar la arquitectura del sistema: Definir el flujo de acciones, reglas a seguir, formas de interacción con herramientas 

5. Evaluar el prototipo: Medir el desempeño del sistema frente a escenarios de prueba y a un método tradicional de referencia, empleando las métricas definidas. 

6. Elaborar la documentación técnica: Generar la documentación e informe técnico que incluya la arquitectura, las decisiones de diseño, los resultados, las limitaciones y las líneas de trabajo futuro.