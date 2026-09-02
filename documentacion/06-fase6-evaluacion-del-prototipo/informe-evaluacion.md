# Informe de evaluación del prototipo (Fase 6)

**Fecha:** 2026-09-02 · **Perfil:** empresarial · **Partición:** evaluación (205 alertas; 18 soportadas)
**Baseline:** nivel de regla de Wazuh · **Justificador:** Llama-3.2-1B (q4), temp 0
**Reproducir:** `python3 -m evaluacion.campana --particion evaluacion`
(marco de medición en [`evaluacion/`](../../evaluacion/); definición de métricas en la
[Fase 4](../04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md); diseño en la
[spec de la Fase 6](../../docs/superpowers/specs/2026-09-02-fase6-evaluacion-design.md)).

---

## 1. Resultado principal

La pregunta de la fase —**¿aporta algo el triaje asistido sobre el nivel de regla de Wazuh?**— tiene una
respuesta cuantitativa clara sobre la partición de evaluación:

| Métrica | Prototipo | Baseline (Wazuh @óptimo, nivel ≥ 5) |
|---------|-----------|-------------------------------------|
| Precisión | **0.556** | 0.154 |
| Recall | 1.000 | 1.000 |
| F1 | **0.714** | 0.267 |
| Tasa de FP | **0.041** | 0.282 |

- Matriz prototipo: VP=10, FP=8, VN=187, FN=0
- Matriz baseline: VP=10, FP=55, VN=140, FN=0

**Ambos detectan todas las amenazas (recall 1.0), pero el prototipo reduce drásticamente el ruido.** El
baseline, en su umbral óptimo, deja pasar **55 falsos positivos**; el prototipo, **8**. La diferencia son
los **187 eventos de ruido de plataforma** que el motor clasifica correctamente como `no_soportada`/sin
acción (VN=187) y que el nivel de regla no sabe suprimir. La **tasa de FP baja de 0.282 a 0.041** —casi
7×— que es exactamente el dolor del analista que el proyecto ataca.

**Este es un resultado positivo y medido a favor del enfoque.**

---

## 2. La limitación del prototipo, medida

La precisión del prototipo se queda en **0.556**, no en 1.0, y la razón es concreta y honesta: **las 18
alertas soportadas de la partición son todas el mismo activo y servicio** (`objetivo-vuln/ssh`, familia
`acceso_credenciales`). De ellas, 10 son ataques reales (VP) y 8 son actividad del **administrador
legítimo** (FP). El clasificador baseline decide por familia + postura del activo, y como el servicio SSH
está expuesto en ese nodo, **clasifica las 18 como amenaza** — no distingue al admin del atacante, porque
esa señal (la legitimidad del origen) no está en la regla que usa. De ahí los 8 FP.

Es el límite esperado del clasificador determinista, y es justo lo que motiva el clasificador con
fine-tuning (bloqueado por datos, ver §5). El baseline de Wazuh sufre lo mismo y peor: no solo confunde
admin y atacante, sino que además inunda con ruido de plataforma.

---

## 3. La curva del baseline (por qué su óptimo es débil)

El nivel de Wazuh se evaluó como clasificador barriendo el umbral. F1 por umbral:

| nivel ≥ | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---------|---|---|---|---|---|---|---|----|----|----|
| F1 | 0.093 | 0.267 | **0.267** | 0.035 | 0.035 | 0.167 | 0.167 | 0.167 | n/d | n/d |

El mejor F1 del baseline es **0.267** (umbrales 4-5; se reporta el 5 por el desempate a mayor umbral). La
curva no es monótona: subir el umbral no mejora limpiamente, porque los VP y buena parte del ruido
conviven en los mismos niveles. **En ningún punto el baseline se acerca al prototipo** (F1 0.714).

---

## 4. Las demás métricas

### Priorización
n=18, **acierto de prioridad ±1 = 0.556**; **Spearman = n/d**. La correlación de cola no se puede calcular
porque todas las soportadas son un solo nodo → no hay variedad de prioridad esperada que ordenar. Es la
consecuencia directa del dataset de una familia; se reporta como **indicativo, no como resultado**.

### Operación
- **Tiempo de clasificar+decidir: ~0.01 ms/alerta** (baseline determinista). Cumple RNF-04 con enorme
  margen.
- **Tiempo de justificar con el LLM 1B: ~36 s/alerta** (10 m 46 s para 18). Es más que los ~14 s de una
  llamada aislada (Fase 5C) porque cada justificación **recarga el modelo de 808 MB** en un subprocess
  nuevo. En un despliegue real el modelo se mantendría cargado; aquí se mide honestamente el coste de la
  frontera de subprocess.
- **Cobertura (RF-10): 0.088** — solo el 8.8 % de las alertas son clasificables; el resto es ruido de
  plataforma marcado `no_soportada`. Es un dato del dataset, no un fallo: refleja que la mayor parte del
  tráfico de un Wazuh recién montado es telemetría interna.
- **Tasa de escalado a humano: 0.0** — el baseline determinista casi nunca pide validación humana sobre
  este dataset.

### Continuidad (RF-20)
- **Acciones disruptivas indebidas: 0.** El motor no propuso ninguna acción que alcanzara el servicio del
  cliente a partir de un falso positivo (las acciones sobre las soportadas fueron de impacto localizado,
  p. ej. BLOQUEAR_IP). **Retención correcta: n/d** (no hubo ninguna que retener).
- Lectura: sobre este dataset el prototipo **no habría cortado el servicio por error**. Es un resultado
  favorable de continuidad, con la salvedad de que el escenario disruptivo (una acción que alcanza el
  servicio) no llegó a ejercitarse aquí.

---

## 5. Calidad de la justificación: anclada, pero poco útil

**Anclaje (RNF-02, automático): 18/18 justificaciones del 1B ancladas, 0 degradadas a plantilla → tasa
1.0.** El modelo cita campos que existen en la alerta (regla, técnica MITRE, activo), así que la
verificación de anclaje pasa siempre.

**Utilidad (revisión manual): baja.** Y aquí está el hallazgo más matizado de la fase: **anclado no es lo
mismo que útil.** Las justificaciones del 1B, aunque ancladas, son **semánticamente incorrectas**. Ejemplo
literal generado:

> «La regla 5760 es un protocolo de seguridad para la autenticación de usuarios en redes. El MITRE
> T1110.001 es un conjunto de técnicas de seguridad para la autenticación de usuarios…»

La regla 5760 **no es un protocolo**: es la regla de Wazuh que detecta un fallo de autenticación SSH.
T1110.001 **no es una técnica de seguridad**: es *Password Guessing*, una técnica de **ataque**. El modelo
1B toma los campos correctos y los **describe al revés**. Además, de las 18 justificaciones solo hay **4
textos distintos** (temp 0 sobre un único nodo produce casi la misma salida), así que aportan poca
diferenciación.

**Conclusión honesta:** el mecanismo funciona (ancla, es reproducible, degrada bien), pero un modelo de
1B no tiene la capacidad para justificar de forma fiable eventos de seguridad. La métrica de anclaje al
100 % **no debe leerse como "justificación de calidad"**: mide que no inventa campos, no que acierte el
significado. Un modelo mayor (el 3B/8B en lote del diseño) es lo que cerraría esta brecha —el anclaje y la
interfaz ya están listos para sustituirlo.

> *Nota de método:* la lectura de utilidad de arriba es la valoración del autor del informe sobre la
> muestra; conviene que un segundo revisor la confirme antes de fijarla en el informe final de la Fase 7.

---

## 5.bis Justificación con RAG (Fase 5D): el contraste medido

El fallo de §5 —el 1B ancla pero describe las reglas y técnicas al revés— es exactamente lo que ataca el
**módulo RAG local** de la Fase 5D. Se recupera de un corpus curado (fichas reales de las técnicas MITRE,
las reglas de Wazuh y las vulnerabilidades del laboratorio) la descripción correcta, y se inyecta en el
prompt. Contraste medido sobre las mismas 18 alertas soportadas
(`--con-rag` vs sin RAG, ambos con el 1B, temp 0):

| | Sin RAG | Con RAG |
|---|---------|---------|
| Anclaje (automático) | 18/18 (100 %) | 18/18 (100 %) |
| **Corrección semántica** (lectura manual) | **incorrecta** | **corregida** |

**El antes/después literal, misma alerta:**

- **Alerta VP:**
  - *Sin RAG:* «La regla 5760 **es un protocolo de seguridad** para la autenticación de usuarios en
    redes. El MITRE T1110.001 **es un conjunto de técnicas de seguridad**…» — falso.
  - *Con RAG:* «La regla 5760 de Wazuh **indica un ataque de fuerza bruta SSH** en curso desde una IP.» —
    correcto, apoyado en el pasaje recuperado (fichas de las reglas 5712/5763/5710).
- **Alerta FP:**
  - *Sin RAG:* «La regla 5710 **define el protocolo SSH como un protocolo seguro**… objetivo-vuln es un
    servicio de seguridad…» — disparate.
  - *Con RAG:* «La regla 5710 de Wazuh indica que se probó un **nombre de usuario que no existe** por SSH.
    Esto es un indicio de **ataque de fuerza bruta SSH**. La regla 5710 es nivel 5…» — correcto.

**Veredicto:** RAG **corrige la corrección semántica** que era el fallo central del justificador. La
mejora es cualitativa y clara en las 18; es la evidencia que cierra la incongruencia I-12 (el módulo RAG
del objetivo general).

**Matices honestos (medidos):**
- El **anclaje no cambia** (100 % en ambos): mide que no inventa campos, no la corrección — de ahí que
  §5 siguiera necesitando lectura manual.
- Siguen saliendo **solo 4 textos distintos de 18** (un solo nodo + temp 0); RAG mejora la *calidad*, no
  la *diversidad*.
- La **recuperación del 1B es imprecisa en el ID exacto**: para una alerta de la regla 5760/5710 recuperó
  el grupo de reglas de fuerza bruta SSH (5712/5763/5710), no el ID exacto. Aun así entrega el dominio
  correcto, y por eso la justificación mejora. Un modelo de embeddings dedicado afinaría la recuperación
  (trabajo futuro; la interfaz del embedder es inyectable).
- Con RAG el 1B tiende a **parafrasear los pasajes** recuperados (lista las reglas) más que a razonar
  sobre la alerta concreta — mejor que inventar, pero lejos de un analista. Un modelo mayor lo cerraría.

Reproducir: `python3 -m evaluacion.campana --particion evaluacion --con-rag`.

---

## 6. Anexo: la partición completa confirma que no hubo fuga

Corrida sobre las 410 alertas (36 soportadas), sin LLM
(`--particion todas --salida-dir evaluacion/resultados/anexo-completo`):

| Métrica | Prototipo | Baseline |
|---------|-----------|----------|
| Precisión | 0.556 | 0.154 |
| Recall | 1.000 | 1.000 |
| F1 | 0.714 | 0.267 |
| Tasa de FP | 0.041 | 0.282 |

Matriz prototipo: VP=20, FP=16, VN=374, FN=0. **Las tasas son idénticas a las de la partición de
evaluación**, lo que era esperable: el clasificador es determinista y **no se entrenó**, así que no hay
diferencia entre entrenar y evaluar. La partición se respetó igualmente por rigor.

---

## 7. Umbrales calibrados que se devuelven a la Fase 5

La evaluación debía devolver dos constantes a la implementación (doc de métricas §5). Con la salvedad de
que **n=18 los hace provisionales**:

- **Mapeo nivel de Wazuh → decisión:** el barrido sitúa el mejor punto del baseline en **nivel ≥ 5**, pero
  con F1 0.267; no hay un umbral de Wazuh que sustituya al clasificador. La lección para la Fase 5 es que
  el nivel de regla **no basta como prioridad**, justificando la reclasificación del motor.
- **Umbral de confianza para escalado (RF-07):** **no calibrable con estos datos.** La tasa de escalado
  fue 0.0 (el baseline casi nunca escala), así que no hay puntos para buscar el equilibrio escalado/recall.
  Queda pendiente de un dataset con más variedad.

---

## 8. Limitaciones y análisis de errores

- **n pequeño y de una sola familia.** 18 alertas soportadas, todas `objetivo-vuln/ssh`. Los porcentajes
  se sostienen sobre pocos casos; se reportan siempre con la matriz cruda. La priorización es casi no
  medible. Es la limitación central y estructural de toda la evaluación.
- **Los 8 FP del prototipo son admin vs atacante.** El clasificador no usa la legitimidad del origen; con
  esa señal (o el clasificador entrenado) la precisión subiría. Es el error sistemático dominante.
- **El clasificador con fine-tuning (encoder) sigue bloqueado por datos** — no hay encoder que medir, así
  que el desajuste "encoder preentrenado sobre prosa vs eventos estructurados" queda documentado, no
  cuantificado.
- **El 1B justifica de forma poco fiable** (§5): anclado pero semánticamente flojo.
- **El auditor no es infalible:** la ausencia de hallazgo no prueba que un activo sea seguro; la postura se
  tomó de los hallazgos reales de la campaña, con esa salvedad.

---

## 9. Veredicto de la fase

**El enfoque aporta valor medible donde importa:** reduce la tasa de falsos positivos casi 7× frente al
método por reglas, sin perder ninguna amenaza (recall 1.0), y sin cortar el servicio por error (0 acciones
disruptivas indebidas). Su límite —no separar admin de atacante, y un justificador 1B poco fiable— está
medido y tiene camino conocido (clasificador entrenado, modelo mayor). El resultado es un **sí con
matices**, cuantificado y honesto, que es exactamente lo que la Fase 6 debía entregar a la
[Fase 7](../07-fase7-documentacion-e-informe-final/).
