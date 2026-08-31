# Métricas y plan de evaluación

Define **contra qué se mide** el prototipo en la Fase 6, **cómo se calcula** cada métrica y
**cuál es el baseline**. Sin esto fijado antes de implementar, la Fase 5 se construiría sin saber
qué tiene que optimizar.

---

## 1. El baseline: el nivel de regla de Wazuh

El plan de trabajo exige comparar el prototipo contra «el método tradicional de referencia». En
este proyecto ese método **es el nivel de regla de Wazuh**: la clasificación por reglas y firmas,
sin IA, que representa cómo se hace el triaje hoy.

Verificado en el laboratorio: un login fallido da nivel 5, una fuerza bruta correlacionada da
nivel 10. Ese nivel viaja en cada alerta (`rule.level`) y se conserva a lo largo de todo el flujo.

**La comparación es:** para cada alerta del dataset, ¿acierta más el prototipo (clase + prioridad
+ justificación) o el nivel crudo de Wazuh? Ambos se miden contra el mismo ground truth.

---

## 2. El ground truth

Dos fuentes, ya construidas en la Fase 3:

- **Etiqueta de la alerta** (verdadero / falso positivo): de contrastar cada alerta de Wazuh
  contra el [inventario de vulnerabilidades](../../lab/docs/vulnerabilidades-esperadas.md) del nodo al
  que apunta.
- **Prioridad esperada**: derivada de la gravedad documentada del nodo y del tipo de evento.

> **Partición obligatoria.** Si el clasificador requiere fine-tuning (Perfil A), el conjunto de
> alertas se parte en **entrenamiento y evaluación con nodos o campañas disjuntos**. Medir sobre
> las alertas de entrenamiento invalida por completo los resultados.

---

## 3. Métricas

### 3.1 Clasificación (VP/FP)

Sobre la matriz de confusión: VP (verdadero positivo), FP, VN, FN.

| Métrica | Fórmula | Qué dice |
|---------|---------|----------|
| **Precisión** | VP / (VP + FP) | De lo que marcó como amenaza, cuánto lo era |
| **Recall** | VP / (VP + FN) | De las amenazas reales, cuántas detectó |
| **F1** | 2·P·R / (P + R) | Equilibrio entre ambas |
| **Tasa de FP** | FP / (FP + VN) | El ruido que el analista sufre — la métrica del problema que el proyecto ataca |

### 3.2 Priorización

| Métrica | Cómo se calcula |
|---------|-----------------|
| **Acierto de prioridad** | % de alertas cuya prioridad asignada coincide con la esperada (±1 nivel) |
| **Orden de la cola** | correlación (Spearman) entre el orden del prototipo y el orden ideal por gravedad |

### 3.3 Operación

| Métrica | Cómo se calcula | Referencia |
|---------|-----------------|-----------|
| **Tiempo de triaje** | segundos por alerta, de ingesta a decisión | RNF-04: del orden de segundos |
| **Cobertura** | % de alertas clasificadas vs. marcadas «no soportada» (RF-10) | — |
| **Tasa de escalado** | % de alertas que van a validación humana | debe bajar sin perder recall |

### 3.3.bis Continuidad (RF-20)

Dos métricas que solo tienen sentido en este perímetro y que miden si el
[perfil de continuidad](./politica-decision-continuidad.md#42-política-de-continuidad-v3) funciona.
La razón de medirlas: **un triaje con buen F1 que corta el servicio del cliente es peor que el
sistema al que sustituye.**

| Métrica | Cómo se calcula | Referencia |
|---------|-----------------|-----------|
| **Acciones disruptivas indebidas** | nº de respuestas de impacto `alcanza_servicio` que se habrían ejecutado a partir de una alerta que era **falso positivo** | El daño que el prototipo habría causado |
| **Retención correcta** | de esas, % que quedó efectivamente retenido por la validación humana | Mide si la regla del perfil funciona |

Ambas exigen que **cada orden lleve su `impacto` declarado en la traza** (RF-17; ver el
[contrato de la orden](./catalogo-de-acciones.md#estructura-de-una-orden-de-acción)). Sin ese campo
no se pueden calcular.

### 3.4 Calidad de la justificación (RF-05, RNF-02)

No es totalmente automatizable; se combina:

- **Anclaje verificable** (automático): % de justificaciones cuyas afirmaciones referencian
  campos que **existen** en la alerta. Una justificación que cita un campo inexistente es una
  alucinación, y se cuenta como fallo.
- **Utilidad** (revisión manual sobre una muestra): un revisor juzga si la justificación habría
  ahorrado trabajo al analista. Escala simple (útil / parcial / inútil).

---

## 4. Cómo se compara con el baseline

Misma tabla, dos columnas:

| Métrica | Nivel de regla de Wazuh (baseline) | Prototipo (motor de triaje) |
|---------|-----------------------------------|-----------------|
| Precisión | … | … |
| Recall | … | … |
| F1 | … | … |
| Tasa de FP | … | … |
| Tiempo de triaje | (inmediato, pero sin clasificar VP/FP) | … |
| Justificación | (ninguna) | … |

El baseline gana en latencia y coste; la hipótesis del proyecto es que el prototipo gana en
**precisión, tasa de falsos positivos y explicabilidad** — que es donde está el dolor real del
analista. Si no lo hiciera, ese resultado negativo también es un hallazgo válido de la Fase 6.

---

## 5. Umbrales que esto fija para el diseño

La evaluación no solo mide: define constantes que la Fase 5 necesita.

- **Umbral de confianza para escalar a humano** (RF-07): se calibra buscando el punto donde bajar
  el escalado no empieza a perder recall. Es un resultado de la evaluación, no un número elegido a priori.
- **Correspondencia nivel de Wazuh → prioridad del motor de triaje**: qué nivel crudo mapea a qué prioridad
  inicial antes de que el modelo reclasifique.

---

## 6. Condiciones de una campaña válida

- **Perfil fijo**: una campaña usa un solo perfil de modelo (A o B) y no lo cambia a mitad; los
  resultados de ambos perfiles no son comparables entre sí.
- **Feed de Greenbone fijado**: la versión del feed se registra y no cambia dentro de la campaña.
- **Entorno de desarrollo cerrado**: por el presupuesto de memoria medido, las campañas se
  ejecutan sin el resto de herramientas abiertas, o las latencias no son comparables.
- **Traza completa** (RF-09): cada decisión registra entrada, prompt, salida, perfil, modelo,
  versión y veredicto humano. Sin traza, la métrica no es reproducible.

---

## Documentos relacionados

- [Catálogo de acciones](./catalogo-de-acciones.md) · [Selección del modelo](./seleccion-del-modelo.md) · [Flujo](./flujo-triaje-playbook-sandbox.md)
- [Ground truth del laboratorio](../../lab/docs/vulnerabilidades-esperadas.md)
- [Requisitos (RF-14, RF-20, RNF-03)](../02-fase2-estado-del-arte/requisitos.md)
