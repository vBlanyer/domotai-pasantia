# Fase 7 — Documentación técnica e informe final

**Objetivo (plan de trabajo, objetivo 7):** consolidar la arquitectura, las decisiones de diseño,
los resultados, las limitaciones y las líneas de trabajo futuro en un informe técnico completo.

---

## Resumen

Esta fase **no genera conocimiento nuevo: lo consolida.** Buena parte del informe ya está escrita y
repartida por las carpetas de fase — el estado del arte, el modelo de cliente, el caso de uso, la
arquitectura, las decisiones y sus alternativas descartadas. El trabajo es reunirlo, darle un hilo
único y añadir lo que solo existe al final: los resultados y su lectura.

Hay tres cosas que conviene que el informe no se deje, porque son las que más se pierden al
consolidar y las que un lector externo va a buscar:

**Las alternativas descartadas y por qué.** Containerlab frente a Packet Tracer y CML; SSH frente a
TR-069 y TR-369; el encoder frente a pedirle la clasificación al generativo; Nmap frente a
Greenbone. Cada descarte tiene un motivo documentado, y son la parte del proyecto que demuestra
criterio.

**Las reinterpretaciones documentadas.** La Fase 1 se ejecutó por modelado porque no había cliente;
el módulo de ingesta ocupa el papel del playbook; Wazuh ocupa el del sistema de logs y aporta el
baseline. Ninguna cambió el plan de trabajo, y el informe debe explicar por qué eso es defendible en
lugar de dejarlo implícito.

**Las limitaciones, sin suavizar.** El auditor no es infalible; el modelo tiene corte de
conocimiento; los encoders se preentrenaron sobre prosa y la entrada son eventos estructurados; el
equipo de borde del laboratorio fue provisional; los perfiles A y B no son comparables entre sí; y
las cifras de mercado de la Fase 2 vienen de informes de acceso restringido y necesitan
verificación directa antes de entrar aquí.

El trabajo futuro ya está enumerado en el plan: respuesta automatizada, integración multicapa,
aprendizaje continuo a partir del feedback del analista, y escalabilidad operativa.

---

## Documentos

*Ninguno todavía.* Aquí irán el informe técnico final, la documentación de arquitectura y operación,
y el roadmap de trabajo futuro.

---

## Entradas y salidas

**Consume:** todas las fases anteriores. En particular los resultados y el análisis de errores de
la [Fase 6](../06-fase6-evaluacion-del-prototipo/), y el registro de decisiones y contradicciones
de [estado-y-riesgos.md](../00-general/estado-y-riesgos.md), que documenta el porqué de buena parte
del camino.

**Entrega a:** nadie dentro del proyecto. Es la salida.

---

## Estado

**No iniciada.**

**Criterio de cierre** (roadmap): la documentación está completa, revisada y lista para entrega o
presentación.
