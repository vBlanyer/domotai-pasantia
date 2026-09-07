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

**Primer borrador del informe final, en `documentacion/report/`** (formato LaTeX según la norma
del Decanato de Estudios Profesionales de la USB): carátula, resumen, lista de símbolos y de
abreviaturas, introducción, descripción de la empresa, marco teórico, metodología, resultados y
discusión, conclusiones y recomendaciones, y referencias. Compila con
`latexmk -pdf ip1_main.tex` desde ese directorio (no verificado en este entorno por no disponer de
una distribución LaTeX instalada).

Pendiente antes de la entrega: confirmar el nombre y el cargo del tutor académico y del tutor
industrial (marcados como «por confirmar» en `ip1_main.tex` e `ip3_empresa.tex`), insertar el Acta
de Evaluación de Pasantía cuando exista, y verificar la compilación completa con una distribución
LaTeX real.

---

## Entradas y salidas

**Consume:** todas las fases anteriores. En particular los resultados y el análisis de errores de
la [Fase 6](../06-fase6-evaluacion-del-prototipo/), y el registro de decisiones y contradicciones
de [estado-y-riesgos.md](../00-general/estado-y-riesgos.md), que documenta el porqué de buena parte
del camino.

**Entrega a:** nadie dentro del proyecto. Es la salida.

---

## Estado

**En curso.** Primer borrador completo del informe redactado el 07/09/2026, consolidando el
material de las fases 1 a 6. Falta la revisión humana del contenido, los datos pendientes de
confirmar con la empresa y coordinación (tutores), y la compilación verificada.

**Criterio de cierre** (roadmap): la documentación está completa, revisada y lista para entrega o
presentación.
