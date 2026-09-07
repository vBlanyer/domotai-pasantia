# Requisitos del prototipo

**Registro único.** Todo requisito funcional y no funcional del proyecto vive aquí. Si un requisito
no está en estas tablas, no existe.

Constituye el entregable *«Lista de requisitos funcionales y no funcionales derivados del análisis»*
de la Fase 2 del [roadmap](../00-general/roadmap.md). Cada requisito se traza a lo que lo motiva: una
limitación del mercado ([limitaciones de XDR](./limitacionesDeXDR.md)), un criterio del análisis de
modelos de lenguaje ([LLM en seguridad](./llm-en-seguridad.md)), una restricción del cliente modelado
([Fase 1](../01-fase1-analisis-del-modulo/)) o una exigencia del plan.

**Estado:** ✔ vigente · ~ vigente con matiz · **+** añadido después del análisis original.

---

## Requisitos funcionales

| ID | Requisito | Deriva de | Estado y nota |
|----|-----------|-----------|---------------|
| RF-01 | Ingerir alertas de la fuente del cliente y normalizarlas a un esquema común, tolerando campos ausentes | XDR §4 · [V1](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad) | ✔ Módulo de producto `prototipo/ingesta.py`: adaptador por fuente (RNF-06), tolerante sin inferir (RNF-07). En el laboratorio la fuente es Wazuh (`alerts.json`) |
| RF-02 | Enriquecer cada alerta con el contexto disponible antes de clasificar | XDR §2 · LLM §4 | ~ `analisis.enriquecer` añade **postura del activo** (`prototipo/postura.py`, módulo de producto) + criticidad del perfil, ambas antes de clasificar; sin postura → baja la confianza (RNF-07). Fuera de alcance: histórico de SOC |
| RF-03 | Clasificar cada alerta según las categorías del caso de uso acotado | XDR §1 · LLM §1 | ~ El baseline determinista produce **4 de 6** categorías (incl. `fp_actividad_legitima` vía orígenes legítimos, RF-03); faltan `vp_acceso_consumado` y `vp_exposicion_gestion` (exigen el encoder bloqueado por datos) |
| RF-04 | Asignar una prioridad que permita ordenar la cola de triaje | XDR §1, §2 | ~ La prioridad combina la clase con la **criticidad del activo** ([V4](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad)). *Límite conocido:* `_priorizar` colapsa los 4 niveles de criticidad en 2 (crítica=alta, media=baja) y satura en 4 — granularidad pendiente de afinar |
| RF-05 | Generar por cada decisión una justificación estructurada: evidencia citada, hipótesis, técnica MITRE ATT&CK y acción sugerida | XDR §9 · LLM §1 | ✔ |
| RF-06 | Emitir un nivel de confianza explícito junto a cada clasificación | XDR §9, §7 · LLM §4 | ✔ Es el disparador del escalado |
| RF-07 | Aplicar reglas y umbrales configurables que determinen cuándo se escala a validación humana | Fase 4 | ~ Uno de los criterios es ahora el **impacto sobre el servicio** (RF-17) |
| RF-08 | Ofrecer flujo de validación humana —aprobar, rechazar, reclasificar— para decisiones críticas o de baja confianza | XDR §7 · LLM §3 | ✔ |
| RF-09 | Registrar traza auditable de cada ejecución: entrada, prompt, salida, decisión, veredicto del analista, marcas de tiempo y versión de prompt y modelo | XDR §9 · Fase 5 | ✔ La traza es también la base de la evaluación |
| RF-10 | Marcar como **«no soportada»** toda alerta fuera del caso de uso acotado, en lugar de emitir una clasificación no fundamentada | XDR §3 | ✔ Implementable desde que el perímetro existe; la alerta conserva su severidad de origen |
| RF-11 | Agrupar y deduplicar alertas relacionadas con un mismo incidente | XDR §1, §2 | ~ La fuente **ya correlaciona** en parte; el motor agrupa por incidente por encima de eso |
| RF-12 | Almacenar el feedback del analista en formato reutilizable, sin reentrenamiento | Trabajo futuro | ✔ |
| RF-13 | Exponer los resultados al sistema del cliente mediante una interfaz definida, sin sustituir sus funciones | XDR §5 | ~ En el laboratorio no hay consumidor real; el motor expone sus resultados y el consumidor llega después |
| RF-14 | Calcular las métricas de evaluación sobre el dataset etiquetado, **comparando siempre contra el baseline de reglas** | Fase 6 · LLM §5 | ✔ |
| RF-15 | Ordenar acciones sobre los activos **únicamente a través de un catálogo cerrado** de acciones enumeradas | Flujo real · Fase 4 | **+** Ningún requisito recogía que el motor actúa |
| RF-16 | Identificar el activo origen de la alerta a partir de los campos del evento cuando el equipo no tiene agente | Despliegue Wazuh | **+** Los equipos sin agente registran bajo el manager; el id de agente no sirve |
| RF-17 | **Determinar y declarar el impacto sobre el servicio** de cada acción antes de proponerla: ninguno, localizado o alcanza a un servicio del cliente | Fase 1 · [C1](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#52-operativas-del-cliente--lo-que-el-prototipo-debe-respetar) | **+** Es la entrada de la política de continuidad y de RF-07 |
| RF-18 | **No proponer ninguna acción cuyo procedimiento de reversión no esté definido y sea verificable** | Fase 1 · [C3](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#52-operativas-del-cliente--lo-que-el-prototipo-debe-respetar) | **+** Sin manos en el equipo, un error irreversible exige presencia física |
| RF-19 | **Rechazar toda acción que dejaría el activo fuera del alcance del plano de gestión** | Fase 1 · [C6](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#52-operativas-del-cliente--lo-que-el-prototipo-debe-respetar) | **+** Precondición, no criterio de escalado: impediría la siguiente respuesta y la verificación |
| RF-20 | Calcular las **métricas de continuidad**: acciones disruptivas indebidas y retención correcta | Fase 1 · caso de uso §10 | **+** Sin ellas el informe no puede demostrar que se respetó la continuidad |

## Requisitos no funcionales

| ID | Requisito | Deriva de | Estado y nota |
|----|-----------|-----------|---------------|
| RNF-01 | **Privacidad:** el análisis ocurre en local o en entorno aislado; ninguna alerta sale a servicios externos | XDR §8 · LLM §3 · Objetivo 3 | ✔ Es además el hueco que los asistentes en la nube no cubren |
| RNF-02 | **Explicabilidad verificable:** toda afirmación de la justificación debe referenciar campos concretos de la alerta o del contexto, nunca conocimiento genérico del modelo | XDR §9 · LLM §4 | ✔ Contrapeso directo a la alucinación con apariencia de fundamento |
| RNF-03 | **Reproducibilidad:** misma alerta y misma versión de prompt y modelo → misma decisión | XDR §9 · LLM §4 | ✔ Sin esto la Fase 6 no es comparable |
| RNF-04 | **Latencia:** tiempo de triaje del orden de segundos en el camino interactivo | XDR §2 | ~ No aplica al camino en lote, que no compite en latencia |
| RNF-05 | **Coste operativo bajo:** ejecutable sobre hardware modesto, sin licencias enterprise ni plataforma adicional | XDR §8 | ✔ Verificado: laboratorio y fuente de alertas por debajo de 1 GB |
| RNF-06 | **Interoperabilidad:** esquema de entrada y salida agnóstico de fabricante | XDR §5 · [V1](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad) | ✔ |
| RNF-07 | **Degradación controlada:** ante telemetría incompleta, bajar la confianza y escalar; nunca inferir lo ausente | XDR §4 · LLM §4 | ✔ Aplica también cuando el auditor no puede dar postura del activo |
| RNF-08 | **Seguridad del propio módulo:** los campos de la alerta se tratan como **datos, nunca como instrucciones**; control de acceso e integridad de los registros | XDR §10 · LLM §4 | ~ **Más crítico aquí:** el contenido del log lo escribe quien ataca |
| RNF-09 | **Disponibilidad:** si el modelo falla, la alerta pasa a cola manual; nunca se descarta en silencio | XDR §7 · LLM §4 | ✔ |
| RNF-10 | **Mantenibilidad:** prompts, reglas y umbrales como configuración externa versionada | XDR §8 | ✔ |
| RNF-11 | **Usabilidad:** salida legible por un analista en menos de un minuto por alerta | XDR §1, §9 | ✔ |
| RNF-12 | **Cumplimiento:** política de retención y anonimización de los datos conforme a la normativa aplicable | XDR §8 | ~ El dato de laboratorio es sintético, lo que simplifica esta fase |
| RNF-13 | **Escalabilidad acotada:** procesamiento por lotes del dataset; la escalabilidad de producción es trabajo futuro | Alcance del plan | ✔ |
| RNF-14 | **Adaptabilidad:** adaptar el sistema a un cliente nuevo consiste en configurar los cinco puntos de variabilidad [**V1–V5**](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad), sin cambios de código | Fase 1 · modelo §6 | **+** Es lo que convierte «se adapta a varios clientes» en comprobable |

---

## Los cinco puntos de variabilidad

Referenciados en la columna «Deriva de». Definidos en el
[modelo de cliente genérico](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad).

| # | Qué varía entre clientes | Requisitos que lo atraviesan |
|---|--------------------------|------------------------------|
| [V1](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad) | Esquema y transporte de la alerta | RF-01, RNF-06 |
| [V2](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad) | Repertorio de respuestas y canal | RF-15 |
| [V3](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad) | Política de continuidad | RF-07, RF-17, RF-18, RF-19 |
| [V4](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad) | Inventario y criticidad de activos | RF-02, RF-04 |
| [V5](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad) | Severidad de referencia | RF-14, RF-20 |

---

## Limitaciones sin requisito asociado

Se enumeran para que nadie espere del prototipo algo que no se ha comprometido a hacer:

- **Respuesta orquestada multi-dominio** (XDR §6 y parte de §7). Es respuesta automatizada,
  declarada trabajo futuro en el plan.
- **Lock-in de fabricante** (XDR §5) y **evasión de agentes** (XDR §10). Aportan restricciones de
  diseño —RNF-06 y RNF-08— no funcionalidad nueva.
- **Correlación multicapa entre equipos** (limitación **L5** del [modelo de cliente
  genérico](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#51-del-sistema-base--lo-que-el-prototipo-viene-a-cubrir)). El
  prototipo mejora el triaje de la alerta que recibe; **no** mejora la correlación que la produjo.
  Está declarado trabajo futuro y conviene que conste aquí para que no se dé por prometido.

---

## Trazabilidad y recuento

| | Original (Fase 2) | Añadidos | Total |
|---|---|---|---|
| Funcionales | 14 | 6 (RF-15 a RF-20) | **20** |
| No funcionales | 13 | 1 (RNF-14) | **14** |

**Ninguno descartado.** Ningún requisito del análisis original dejó de aplicar al cambiar el
contexto del proyecto; seis cambiaron de matiz y siete se añadieron. El recorrido requisito a
requisito que verificó esto está en
[revision-requisitos-contexto.md](./revision-requisitos-contexto.md).

---

## Documentos relacionados

- [Limitaciones de XDR](./limitacionesDeXDR.md) — el análisis del que derivan los requisitos originales.
- [LLM en seguridad](./llm-en-seguridad.md) — los criterios de diseño de la §6 de ese documento.
- [Modelo de cliente genérico](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md) · [Caso de uso acotado](../01-fase1-analisis-del-modulo/caso-de-uso-acotado.md)
- [Métricas y plan de evaluación](../04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md) — cómo se calcula lo que exigen RF-14 y RF-20.
