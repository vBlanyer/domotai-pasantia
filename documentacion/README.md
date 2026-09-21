# Documentación del proyecto

Organizada siguiendo las fases del [plan de trabajo](00-general/planDeTrabajoActualizado.md) y del
[roadmap](00-general/roadmap.md). **Cada carpeta de fase tiene un `README.md`** que resume qué
decidió y qué produjo esa fase, indexa sus documentos, y declara qué consume, qué entrega y en qué
estado está. Empieza por ahí.

## Documentos base

- [00-general/](00-general/) — plan de trabajo y roadmap, los dos documentos que van a coordinación.
  - [estado-y-riesgos.md](00-general/estado-y-riesgos.md) — estado por fase, decisiones cerradas e incongruencias abiertas.
  - [camino-paso-a-paso.md](00-general/camino-paso-a-paso.md) — plan de ejecución ordenado, con criterio de cierre por paso.
- [archivo/](archivo/) — material superado, conservado por trazabilidad. No es diseño vigente.

## Las siete fases

| Fase | Qué contiene | Estado |
|------|--------------|--------|
| [1 — Análisis del módulo](01-fase1-analisis-del-modulo/) | Modelo de cliente genérico y caso de uso acotado | Completa por sustitución |
| [2 — Estado del arte](02-fase2-estado-del-arte/) | MDR/XDR, modelos de lenguaje en seguridad y el registro único de requisitos | Completa |
| [3 — Entorno de pruebas](03-fase3-entorno-de-pruebas/) | Diseño del laboratorio (ejecutable en [`lab/`](../lab/)) y el dataset etiquetado y particionado | Completa (410 alertas etiquetadas) |
| [4 — Arquitectura](04-fase4-diseno-de-arquitectura/) | Flujo, protocolos, catálogo de acciones, auditoría, modelo y métricas | Cerrada |
| [5 — Implementación](05-fase5-implementacion-del-prototipo/) | El prototipo [`prototipo/`](../prototipo/): decisión (5A), lazo en vivo (5B), justificador LLM real (5C), **RAG local (5D)** y **taxonomía de familias extensible (registro MITRE + tres niveles de respuesta: actuar / triar_y_enrutar / no_soportada)** | Completa (clasificador por árbol de decisión; registro de familias y perfil bancario) |
| [6 — Evaluación](06-fase6-evaluacion-del-prototipo/) | Medición contra el baseline de Wazuh, [informe](06-fase6-evaluacion-del-prototipo/informe-evaluacion.md) y análisis de errores | Completa (prototipo: tasa de FP 0.000 vs 0.296 del baseline; recall 1.0 vs 0.741 — tres familias) |
| [7 — Informe final](07-fase7-documentacion-e-informe-final/) | Consolidación de todo lo anterior | Borrador entregado ([`report/`](report/)) |

La correspondencia con los objetivos del plan es uno a uno: la fase *N* implementa el objetivo *N*.

## Convención

Los `README.md` de fase **resumen y enlazan; no redefinen**. Ninguna tabla normativa —requisitos,
catálogo de acciones, clases de clasificación, métricas, puntos de variabilidad— se copia en ellos:
vive en su documento y el README la cita. Es para evitar el problema que este repositorio ya ha
tenido dos veces: dos copias de la misma lista que se desincronizan sin que nadie se entere.
