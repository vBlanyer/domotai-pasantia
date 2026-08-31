# Revisión de los requisitos frente al contexto del cliente modelado

Los requisitos funcionales y no funcionales de [limitacionesDeXDR.md](./limitacionesDeXDR.md) se
derivaron del análisis de **XDR/MDR empresarial y operación de SOC**. El proyecto derivó después
a un caso concreto: **triaje de alertas de seguridad sobre la red de un cliente**, desde el punto
de entrega del proveedor hacia dentro —equipo de borde, electrónica de red y servidores—, con los
servicios de gestión expuestos como perímetro. Este documento comprueba, requisito a requisito,
cuáles siguen aplicando, cuáles cambian de matiz y cuáles faltaban.

Resuelve la incongruencia **I-5** de [estado-y-riesgos.md](../00-general/estado-y-riesgos.md).

> **Este documento es el registro de la revisión, no la lista de requisitos.** Sus conclusiones —los
> matices y los dos requisitos nuevos que detectó— están ya incorporadas al
> [registro único de requisitos](./requisitos.md), que es donde hay que mirar. Se conserva por
> trazabilidad: deja constancia de que la verificación se hizo requisito a requisito.

Marcas: **✔ vigente** · **~ vigente con matiz** · **+ nuevo** · **✘ descartado**.

---

## Requisitos funcionales

| ID | Estado | Nota para el contexto del cliente |
|----|--------|----------------------------|
| RF-01 Ingesta y normalización | ✔ | La fuente concreta es Wazuh (`alerts.json`), que instancia el sistema de logs del cliente modelado; el módulo real entra después como segunda fuente. Verificado en el laboratorio. |
| RF-02 Enriquecimiento con contexto | ~ | El contexto más valioso aquí es la **postura del nodo del auditor** (¿el equipo afectado es vulnerable a lo que la alerta sugiere?), más que el histórico de un SOC. |
| RF-03 Clasificar VP/FP | ✔ | El caso de uso acotado de la [Fase 1](../01-fase1-analisis-del-modulo/) —acceso no autorizado a servicios de gestión expuestos— da las categorías. |
| RF-04 Prioridad/score | ✔ | Sin cambios. |
| RF-05 Justificación estructurada | ✔ | MITRE ATT&CK sigue aplicando: la fuerza bruta SSH que probamos es T1110. |
| RF-06 Nivel de confianza | ✔ | Sin cambios; es el disparador del escalado. |
| RF-07 Reglas y umbrales de escalado | ✔ | Los umbrales se calibran en la evaluación (Paso 8). |
| RF-08 Validación humana | ✔ | Encaja con el catálogo de acciones: alto impacto → humano. |
| RF-09 Traza auditable | ✔ | Reforzado: la traza es también la base de la evaluación. |
| RF-10 Marcar «no soportada» fuera de alcance | ✔ | **Ahora sí es implementable:** el caso de uso acotado está definido en la Fase 1 y fija el perímetro. |
| RF-11 Agrupar/deduplicar | ~ | Wazuh **ya correlaciona** (fuerza bruta → una alerta nivel 10). Parte de RF-11 la cubre la fuente; el motor de triaje agrupa por incidente por encima de eso. |
| RF-12 Guardar feedback | ✔ | Sin cambios. |
| RF-13 Interfaz con el módulo propietario | ~ | En el laboratorio no hay módulo propietario; el motor de triaje expone sus resultados y el consumidor real llega después. |
| RF-14 Calcular métricas | ✔ | Detallado en el Paso 8. |
| **RF-15** Actuar sobre el sandbox por catálogo cerrado | **+** | **Nuevo.** El flujo real incluye que el motor de triaje ordene acciones sobre el sandbox; no había requisito que lo recogiera. Ver [catálogo de acciones](../04-fase4-diseno-de-arquitectura/catalogo-de-acciones.md). |
| **RF-16** Identificar el nodo origen sin agente | **+** | **Nuevo.** El equipo de borde reenvía syslog como `agent.id 000`; el motor de triaje debe deducir el activo de los campos del evento, no del id de agente. Detectado al desplegar Wazuh. |

## Requisitos no funcionales

| ID | Estado | Nota para el contexto del cliente |
|----|--------|----------------------------|
| RNF-01 Privacidad / local | ✔ | Refuerza la elección de modelo local (Perfil A/B). Sin cambios. |
| RNF-02 Explicabilidad verificable | ✔ | Métrica de anclaje definida en el Paso 8. |
| RNF-03 Reproducibilidad | ✔ | Extendido: la campaña fija perfil, modelo y feed. |
| RNF-04 Latencia (segundos) | ~ | Aplica al camino interactivo; la justificación extensa del Perfil A es en lote y no compite en latencia. |
| RNF-05 Coste operativo bajo | ✔ | **Confirmado con datos:** laboratorio + Wazuh < 0,8 GB. Encaja con hardware modesto. |
| RNF-06 Interoperabilidad / agnóstico | ✔ | El esquema normalizado de ingesta lo garantiza. |
| RNF-07 Degradación controlada | ✔ | Ante alerta incompleta, baja confianza y escala; nunca inventa. |
| RNF-08 Seguridad del propio módulo | ~ | **Más crítico aquí:** el `full_log` viene de un equipo potencialmente comprometido. La resistencia a inyección de prompt desde campos del atacante no es teórica. |
| RNF-09 Disponibilidad / no descartar | ✔ | Si el modelo falla, la alerta va a cola manual. |
| RNF-10 Mantenibilidad / config externa | ✔ | Prompts, reglas y umbrales versionados. |
| RNF-11 Usabilidad (<1 min/alerta) | ✔ | Sin cambios. |
| RNF-12 Cumplimiento / retención | ~ | El dato de laboratorio es sintético (Metasploitable), lo que simplifica el cumplimiento en esta fase. |
| RNF-13 Escalabilidad acotada / batch | ✔ | Encaja con la separación en vivo / en lote del Perfil A. |

---

## Resumen

- **Vigentes sin cambio:** la mayoría. El análisis de Fase 2 resultó ser sólido pese al giro de contexto.
- **Con matiz (~):** RF-02, RF-11, RF-13, RNF-04, RNF-08, RNF-12 — cambia el énfasis, no la exigencia.
- **Nuevos (+):** **RF-15** (actuar por catálogo) y **RF-16** (identificar nodo sin agente), ambos
  surgidos del flujo real y del despliegue de Wazuh.
- **Descartados:** ninguno. Ningún requisito dejó de aplicar por el cambio de contexto.

Los dos requisitos nuevos ya tienen reflejo en el diseño (catálogo de acciones y módulo de
ingesta), así que esta revisión no abrió trabajo pendiente: solo cerró la trazabilidad.

**Revisión posterior (25/08/2026).** El modelado del cliente genérico en la
[Fase 1](../01-fase1-analisis-del-modulo/) produjo restricciones operativas —continuidad del
servicio, reversibilidad obligatoria y preservación del plano de gestión— que ningún requisito
recogía. De ahí salieron **RF-17 a RF-20** y **RNF-14**, incorporados directamente al
[registro único](./requisitos.md). Con ellos, RF-15 y RF-16 dejan de vivir solo en este documento.

---

## Documentos relacionados

- [Requisitos originales](./limitacionesDeXDR.md) · [Catálogo de acciones](../04-fase4-diseno-de-arquitectura/catalogo-de-acciones.md) · [Flujo](../04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md)
