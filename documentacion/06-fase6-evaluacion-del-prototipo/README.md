# Fase 6 — Evaluación del prototipo

**Objetivo (plan de trabajo, objetivo 6):** medir el desempeño del sistema frente a escenarios de
prueba y al método tradicional de referencia, empleando las métricas y el baseline definidos en la
Fase 4, y analizar errores sistemáticos y limitaciones del enfoque.

---

## Resumen

La pregunta que esta fase responde es una sola: **¿aporta algo el triaje asistido sobre lo que ya
hay?** Y se responde comparando el prototipo contra el **nivel de regla de Wazuh** sobre el mismo
dataset y la misma partición — el método basado en reglas y firmas que hoy está en producción en la
mayoría de organizaciones.

Se miden cuatro grupos de métricas, todas definidas ya en la
[Fase 4](../04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md):

- **Clasificación** — precisión, recall, F1 y **tasa de falsos positivos**, que es la métrica del
  problema que el proyecto ataca.
- **Priorización** — acierto de prioridad y orden de la cola frente al orden ideal por gravedad.
- **Operación** — tiempo de triaje, cobertura frente a las alertas marcadas «no soportada», y tasa
  de escalado a validación humana, que debe bajar sin perder recall.
- **Continuidad** ([RF-20](../02-fase2-estado-del-arte/requisitos.md)) — acciones disruptivas indebidas y retención correcta. Existen porque
  **un triaje con buen F1 que corta el servicio del cliente es peor que el sistema al que
  sustituye**, y sin medirlo el informe no podría demostrar lo contrario.

La calidad de la justificación se mide en dos mitades: el **anclaje verificable** es automático
—qué porcentaje de las afirmaciones referencia campos que existen de verdad en la alerta; citar un
campo inexistente cuenta como fallo— y la utilidad se juzga a mano sobre una muestra.

Dos condiciones hacen válida una campaña. **La partición no es opcional:** medir sobre las alertas
con las que se ajustó el clasificador invalida por completo los resultados. Y **el perfil se fija y
no se cambia a mitad**, porque los resultados de los perfiles A y B no son comparables entre sí; si
se comparan, es un experimento propio con su propia sección.

El análisis de errores cierra la fase, y debe recoger las limitaciones conocidas: el auditor no es
infalible y la ausencia de hallazgo no prueba que un activo sea seguro, el modelo tiene un corte de
conocimiento, y los encoders de seguridad se preentrenaron sobre prosa y no sobre eventos
estructurados — un desajuste que es barato medir comparándolos contra un modelo genérico.

---

## Documentos

*Ninguno todavía.* Aquí irán el informe de evaluación con la tabla comparativa, el análisis de
errores y las recomendaciones.

---

## Entradas y salidas

**Consume:** el prototipo y sus trazas de la [Fase 5](../05-fase5-implementacion-del-prototipo/);
el dataset etiquetado y particionado y el baseline de la [Fase 3](../03-fase3-entorno-de-pruebas/);
las métricas y las condiciones de campaña de la [Fase 4](../04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md);
y el perímetro de la [Fase 1](../01-fase1-analisis-del-modulo/), que delimita sobre qué se mide.

**Entrega a:** la [Fase 7](../07-fase7-documentacion-e-informe-final/) — resultados, análisis de
errores y limitaciones. También devuelve a la Fase 5 los **umbrales calibrados** de escalado, que
la implementación arranca con valores provisionales.

---

## Estado

**No iniciada, y ya no bloqueada.** Durante un tiempo lo estuvo: no había baseline contra el que
comparar ni ground truth de alertas. Ambos están resueltos —el nivel de regla de Wazuh y el
etiquetado contra el inventario de cada nodo—, así que la única dependencia real es tener el
prototipo.

**Criterio de cierre** (roadmap): existen resultados cuantitativos y cualitativos que demuestran el
valor —o las limitaciones— del enfoque propuesto. Un resultado negativo bien medido también es un
hallazgo válido.
