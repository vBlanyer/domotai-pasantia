# Fase 4 — Diseño de la arquitectura del sistema

## Diseño del prototipo

- [Flujo de operación: logs → playbook → EDR → sandbox → auditoría](flujo-edr-playbook-sandbox.md) — componentes, contratos, catálogo de acciones y validación humana.
- [Protocolos de comunicación con el sandbox](protocolos-comunicacion-sandbox.md) — comparativa por tramo FTTx y decisión de diseño.
- [Auditoría de vulnerabilidades del sandbox](auditoria-de-vulnerabilidades-del-sandbox.md) — alcance, herramientas, salida normalizada y encaje en el flujo.
- [Selección del modelo de análisis](seleccion-del-modelo.md) — criterios, perfiles de despliegue A/B según hardware, e interfaz de análisis.
- [Catálogo cerrado de acciones](catalogo-de-acciones.md) — qué puede ordenar el EDR, con precondición, reversibilidad y validación humana.
- [Métricas y plan de evaluación](metricas-y-evaluacion.md) — baseline, ground truth, fórmulas y condiciones de campaña.
- [Arquitectura consolidada](arquitectura-consolidada.md) — vista única: componentes, planos, flujo y los tres puntos de aislamiento.

## Material de referencia

- [EDR, XDR, MDR y telemetría](edr-xdr-mdr-telemetria.md)
- [Herramientas auxiliares para pruebas de XDR](herramientas-auxiliares.md) — *premisa parcialmente superada; ver la nota del documento.*
- [Sysmon](symons.md) — *condicional a que entre un endpoint Windows en la topología.*

## Estado

**Fase 4 cerrada.** El diseño de la arquitectura está completo; ver [arquitectura consolidada](arquitectura-consolidada.md).
El único hueco conocido es que el CPE es provisional hasta desbloquear OpenWrt en vrnetlab.
Los umbrales concretos de escalado se calibran en la evaluación (Fase 6), según el [plan de métricas](metricas-y-evaluacion.md).
