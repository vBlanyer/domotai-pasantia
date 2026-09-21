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

- [informe-evaluacion.md](informe-evaluacion.md) — el informe con la tabla comparativa prototipo vs
  baseline, la curva del barrido, el análisis de errores y los umbrales calibrados devueltos a la Fase 5.

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

**Hecha.** El marco de medición vive en [`evaluacion/`](../../evaluacion/) y la campaña corre con
`python3 -m evaluacion.campana --particion evaluacion`. Resultado principal: sobre la partición de
evaluación el prototipo **elimina los falsos positivos** (tasa 0.000 vs 0.282 del nivel de regla de Wazuh en la campaña original de una familia; con la configuración de orígenes legítimos que distingue admin de atacante, RF-03) **sin perder ninguna amenaza** (recall 1.0) y sin acciones disruptivas indebidas. **Ampliada el 11/09/2026 a tres familias** (233 alertas): FP 0.000 vs **0.296** y recall 1.000 vs **0.741** — el baseline deja pasar amenazas reales de baja severidad que el prototipo sí reconoce (ver [resultados vigentes](../../evaluacion/resultados/README.md)). Sus
límites —cubre 4 de las 6 categorías (las 2 finas exigen etiquetas de las que el dataset no dispone, no una pieza pendiente), la legitimidad se apoya en la IP (suplantable), y el 1B justifica mal sin RAG (el 8B con RAG sí: 18/18 ancladas, 0 contradicciones)—
están medidos y documentados. Los números de la campaña original y su análisis están en el
[informe](informe-evaluacion.md).

**Criterio de cierre** (roadmap): cumplido — existen resultados cuantitativos (tabla comparativa,
curva del baseline) y cualitativos (lectura de las justificaciones) que demuestran el valor y las
limitaciones del enfoque. Queda pendiente para un dataset mayor: la calibración del umbral de escalado
(RF-07) y la granularidad fina de 6 clases (que exige etiquetas finas; el clasificador determinista
nutrido por el árbol de decisión ya cubre VP/FP/no_soportada).
