# Fase 4 — Diseño de la arquitectura del sistema

## Diseño del prototipo

- [Flujo de operación: logs → playbook → EDR → sandbox → auditoría](flujo-edr-playbook-sandbox.md) — componentes, contratos, catálogo de acciones y validación humana.
- [Protocolos de comunicación con el sandbox](protocolos-comunicacion-sandbox.md) — comparativa por tramo FTTx y decisión de diseño.
- [Auditoría de vulnerabilidades del sandbox](auditoria-de-vulnerabilidades-del-sandbox.md) — alcance, herramientas, salida normalizada y encaje en el flujo.
- [Selección del modelo de análisis](seleccion-del-modelo.md) — criterios, perfiles de despliegue A/B según hardware, e interfaz de análisis.

## Material de referencia

- [EDR, XDR, MDR y telemetría](edr-xdr-mdr-telemetria.md)
- [Herramientas auxiliares para pruebas de XDR](herramientas-auxiliares.md) — *premisa parcialmente superada; ver la nota del documento.*
- [Sysmon](symons.md) — *condicional a que entre un endpoint Windows en la topología.*

## Pendiente

- Diagrama de arquitectura consolidado.
- Reglas de decisión, umbrales de escalado y umbral de confianza para la validación humana.
- Métricas de evaluación y definición del baseline.
