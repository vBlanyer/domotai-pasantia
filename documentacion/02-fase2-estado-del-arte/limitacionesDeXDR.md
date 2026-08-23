# Limitaciones de XDR: implementación y uso actual

Este documento recopila las limitaciones más reportadas en la implementación y operación de plataformas **Extended Detection and Response (XDR)** según el estado del arte del mercado, evaluaciones independientes (MITRE ATT&CK 2025) y análisis sectoriales recientes. Complementa el documento [mdr-xdr.md](./mdr-xdr.md) y sirve como base para la Fase 2 del proyecto, cuyos requisitos funcionales y no funcionales se derivan al final de este documento.

---

## Panorama general

XDR integra telemetría de endpoints, red, identidad, correo y nube para correlacionar eventos y priorizar alertas. Las plataformas líderes obtienen puntuaciones altas en evaluaciones como MITRE ATT&CK Enterprise 2025, pero persisten limitaciones operativas y arquitectónicas que afectan su adopción, especialmente en PYMEs y organizaciones con stacks multi-vendor.

**Lo que XDR resuelve bien:**
- Visibilidad unificada multi-capa
- Correlación cross-layer de eventos
- Reducción parcial del ruido de alertas
- Acciones tácticas rápidas (aislar host, bloquear IP, deshabilitar cuenta)

**Lo que sigue sin resolver de forma satisfactoria:**
- Triaje final y priorización sin intervención humana
- Investigación profunda de incidentes
- Respuesta orquestada multi-dominio
- Reducción de la necesidad de analistas
- Adopción viable en PYMEs sin servicios MDR asociados
- Explicabilidad clara de las decisiones de detección

---

## 1. Fatiga por alertas y falsos positivos

Sigue siendo la queja principal de los analistas, incluso con XDR desplegado.

- Las soluciones basadas en reglas y firmas siguen generando alertas benignas.
- La correlación multi-capa **reduce** el ruido, pero **no lo elimina**.
- En evaluaciones MITRE 2025 se mide explícitamente el **volumen de alertas** que un analista debe triar; los líderes compiten por minimizarlo, lo que confirma que el problema persiste.
- Estudios del sector (p. ej. Omdia) reportan que cerca del **46% de las alertas** siguen siendo ruido operativo.

**Implicación:** el triaje manual sigue siendo cuello de botella, aunque la organización disponga de XDR.

---

## 2. Brecha entre detección e investigación (investigation gap)

Una de las limitaciones arquitectónicas más citadas en 2025–2026.

| Qué hace bien el XDR | Qué no resuelve |
|----------------------|-----------------|
| Correlacionar señales de endpoint, red, identidad, cloud | Determinar el alcance real del incidente |
| Priorizar alertas | Reconstruir la cadena de ataque completa |
| Acciones tácticas (aislar host, bloquear IP) | Decidir la respuesta coordinada multi-capa |

- La investigación manual puede tomar **~70 minutos por alerta**; ataques como phishing pueden completarse en **menos de 60 minutos**.
- XDR **automatiza la detección y acciones puntuales**, pero la investigación que define *qué* hacer sigue siendo humana.
- El XDR cambia *qué* hace el analista (menos consolas, alertas correlacionadas), pero **no reduce cuántos analistas se necesitan**.
- Encuestas del sector reportan **más del 70% de burnout** en analistas de SOC, impulsado principalmente por la carga de investigación — capa que XDR no aborda de forma directa.

---

## 3. Techo de correlación (correlation ceiling)

La correlación XDR suele basarse en lógica predefinida alineada con técnicas MITRE ATT&CK.

**Limitaciones:**
- Técnicas novedosas o **Living-off-the-Land (LOTL)** que imitan actividad legítima.
- Campañas multi-etapa que no encajan en reglas conocidas.
- Dificultad para distinguir actividad de negocio legítima de amenaza real (destacado en MITRE Evaluations 2025).

Estas no son fallos de implementación aislados, sino **límites del paradigma XDR** cuando la sofisticación del atacante supera los patrones predefinidos.

---

## 4. Dependencia de telemetría y arquitectura de datos

Un XDR solo es tan bueno como los datos que recibe.

- **Gaps de cobertura** producen puntos ciegos (OT, SaaS de terceros, shadow IT, entornos cloud parcialmente instrumentados).
- **Retención y búsqueda** a escala resultan costosas y técnicamente complejas para reconstrucción forense.
- En despliegues MDR/XDR gestionados, la calidad del servicio depende de la telemetría que aporta el cliente; logs deficientes limitan el valor de la plataforma.

---

## 5. Lock-in de vendor vs. interoperabilidad

| Tipo | Fortaleza | Limitación |
|------|-----------|------------|
| **XDR nativo** (CrowdStrike, Microsoft, Palo Alto) | Correlación profunda dentro del ecosistema | Menor valor fuera del stack del vendor |
| **Open XDR** (Elastic, Stellar Cyber, Arctic Wolf Aurora) | Integra múltiples fuentes | Calidad de correlación cross-vendor inferior al nativo |

La selección suele ser una **decisión de ecosistema**, no solo técnica.

### Limitaciones por plataforma líder

| Plataforma | Limitaciones reportadas |
|------------|-------------------------|
| **CrowdStrike Falcon XDR** | Coste elevado para organizaciones pequeñas; mayor valor cuando se adopta el ecosistema Falcon completo |
| **Microsoft Defender XDR** | Menor flexibilidad en entornos multi-vendor; dependencia del stack Microsoft |
| **Palo Alto Cortex XDR** | Menor ventaja como XDR standalone sin el resto del ecosistema; reglas de detección menos tunables que CrowdStrike |
| **SentinelOne Singularity XDR** | Ecosistema de terceros menos maduro; menor presencia en servicios gestionados propios |

---

## 6. Respuesta fragmentada y dependencia de SOAR

XDR ofrece **acciones tácticas aisladas**, no flujos de respuesta orquestados de extremo a extremo:

- Aislar endpoint, bloquear IP, deshabilitar cuenta de usuario.
- Incidentes que cruzan phishing → robo de credenciales → movimiento lateral → exfiltración requieren **secuencias coordinadas** guiadas por hallazgos de investigación.

Para orquestación completa, muchas organizaciones deben añadir una plataforma **SOAR** aparte (p. ej. CrowdStrike Falcon Fusion, Cortex XSOAR), lo que incrementa coste, complejidad operativa y superficie de mantenimiento.

---

## 7. Respuesta automatizada acotada

- El avance real se concentra sobre todo en **endpoint** (respuesta autónoma en plataformas como SentinelOne o CrowdStrike).
- La **remediación multi-capa coordinada** sigue requiriendo intervención humana en la mayoría de los despliegues.
- Fuera de horario (noches, fines de semana, festivos), la respuesta automática tiende a limitarse a acciones tácticas sin el contexto investigativo completo.
- La promesa de un "SOC autónomo" aún no reemplaza la validación humana en decisiones críticas.

---

## 8. Coste y complejidad de implementación

Reportado de forma recurrente en PYMEs y mid-market:

- Licencias enterprise (CrowdStrike, Palo Alto) resultan costosas para organizaciones pequeñas.
- La combinación **SIEM + SOAR + XDR** puede ser más compleja que el problema que pretende resolver.
- Desafíos habituales de implementación:
  - Integración multi-fuente
  - Brechas de skills en el equipo interno
  - Privacidad de datos y cumplimiento normativo (DORA, NIS2, etc.)
  - Tiempo de despliegue y tuning de reglas antes de obtener valor operativo real

---

## 9. Explicabilidad limitada

Muchas plataformas priorizan **detección sobre justificación clara**:

- El analista debe reconstruir *por qué* una alerta es relevante y *qué* acción tomar.
- Las detecciones de alta fidelidad mejoran (p. ej. resultados MITRE 2025 de Sophos, CrowdStrike), pero la **justificación del triaje** sigue siendo en gran medida manual.
- Esta limitación es central para el enfoque del proyecto: apoyar al analista con razonamiento explicable.

---

## 10. Evasión y desactivación de agentes

Tendencia creciente en evaluaciones y reportes de amenazas 2025:

- Técnicas **LOTL** y **BYOVD** (Bring-Your-Own-Vulnerable-Driver).
- Métodos para **deshabilitar o evadir agentes XDR**.
- Ataques **cloud-native** (incorporados por primera vez en el alcance de MITRE 2025) que desafían la cobertura tradicional centrada en Windows y endpoint.

---

## Flujo operativo: dónde se concentran las limitaciones

```
Telemetría multi-fuente
        ↓
Correlación XDR
        ↓
Alertas priorizadas
        ↓
   [Triaje manual]          ← cuello de botella
        ↓
 [Investigación humana]     ← carga principal / burnout
        ↓
 [Decisión de respuesta]
        ↓
Acciones tácticas / SOAR
```

XDR optimiza las etapas superiores del flujo. Las etapas marcadas siguen dependiendo del analista en la mayoría de los despliegues actuales.

---

## Implicaciones para este proyecto

| Limitación del mercado | Oportunidad del prototipo |
|------------------------|---------------------------|
| Falsos positivos y fatiga de alertas | Clasificación y priorización inteligente de eventos |
| Explicabilidad limitada | Razonamiento explicable generado por LLM |
| Coste y complejidad en PYMEs | Enfoque acotado, validación humana, sin dependencia de servicios cloud externos |
| Complemento a XDR/MDR existentes | Módulo de triaje sobre la plataforma propietaria, no competencia directa con ella |

El mercado valida la demanda (crecimiento sostenido del segmento XDR/MXDR), pero las soluciones líderes siguen dependiendo de analistas para el triaje e investigación final. Un módulo que **clasifique, priorice y explique** alertas — con validación humana en decisiones críticas — aborda un vacío real documentado en la industria.

---

## Requisitos derivados del análisis

Esta sección constituye el entregable *«Lista de requisitos funcionales y no funcionales derivados del análisis»* de la Fase 2 del [roadmap](../00-general/roadmap.md). Cada requisito se traza a la limitación de mercado que lo motiva o a la fase del proyecto que lo exige.

### Requisitos funcionales

| ID | Requisito | Deriva de |
|----|-----------|-----------|
| RF-01 | Ingerir alertas del módulo propietario y normalizarlas a un esquema común, tolerando campos ausentes | §4 Dependencia de telemetría |
| RF-02 | Enriquecer cada alerta con contexto disponible (activo, usuario, histórico de alertas similares, IoC) antes de clasificar | §2 Brecha detección–investigación |
| RF-03 | Clasificar cada alerta como verdadero/falso positivo (o categoría del caso de uso acotado) | §1 Fatiga por alertas |
| RF-04 | Asignar una prioridad/score que permita ordenar la cola de triaje | §1, §2 |
| RF-05 | Generar por cada decisión una justificación estructurada: evidencia citada de la alerta, hipótesis, técnica MITRE ATT&CK asociada y acción sugerida | §9 Explicabilidad limitada |
| RF-06 | Emitir un nivel de confianza explícito junto a cada clasificación | §9, §7 |
| RF-07 | Aplicar reglas de decisión y umbrales configurables que determinen cuándo se escala a validación humana | Fase 4 del roadmap |
| RF-08 | Ofrecer flujo de validación humana (aprobar / rechazar / reclasificar) para alertas críticas o de baja confianza | §7 Respuesta automatizada acotada |
| RF-09 | Registrar traza auditable de cada ejecución: entrada, prompt, salida del modelo, decisión, veredicto del analista, timestamps y versión de prompt/modelo | §9, Fase 5 |
| RF-10 | Marcar explícitamente como «no soportada» toda alerta fuera del caso de uso acotado, en lugar de emitir una clasificación no fundamentada | §3 Techo de correlación |
| RF-11 | Agrupar/deduplicar alertas relacionadas con un mismo incidente | §1, §2 |
| RF-12 | Almacenar el feedback del analista en formato reutilizable (sin reentrenamiento — trabajo futuro) | Trabajo futuro |
| RF-13 | Exponer los resultados al módulo propietario mediante una interfaz definida, sin sustituir sus funciones | §5 Lock-in / complemento a XDR |
| RF-14 | Calcular métricas de evaluación (precisión, recall, F1, tasa de falsos positivos, tiempo de triaje) sobre el dataset etiquetado | Fase 6 |

### Requisitos no funcionales

| ID | Requisito | Deriva de |
|----|-----------|-----------|
| RNF-01 | **Privacidad:** procesamiento del LLM en local o entorno aislado; ninguna alerta sale a servicios externos | §8 Cumplimiento (DORA, NIS2), Objetivo 3 |
| RNF-02 | **Explicabilidad verificable:** toda afirmación de la justificación debe referenciar campos concretos de la alerta o del contexto, no conocimiento genérico del modelo | §9 |
| RNF-03 | **Reproducibilidad:** misma alerta + misma versión de prompt/modelo → misma decisión (temperatura baja, prompts versionados) | §9, comparabilidad de la evaluación |
| RNF-04 | **Latencia:** tiempo de triaje por alerta del orden de segundos, frente a los ~70 minutos de investigación manual citados | §2 |
| RNF-05 | **Coste operativo bajo:** ejecutable sobre hardware modesto, sin licencias enterprise ni plataforma SOAR adicional | §8 Coste y complejidad |
| RNF-06 | **Interoperabilidad:** esquema de entrada/salida agnóstico de vendor, sin dependencia de un ecosistema XDR concreto | §5 Lock-in |
| RNF-07 | **Degradación controlada:** ante telemetría incompleta debe reducir la confianza y escalar a humano, nunca inferir datos ausentes | §4 |
| RNF-08 | **Seguridad del propio módulo:** resistencia a inyección de prompt desde campos controlables por el atacante, control de acceso e integridad de los logs | §10 Evasión y desactivación de agentes |
| RNF-09 | **Disponibilidad:** si el LLM falla o no responde, la alerta pasa a cola de revisión manual; nunca se descarta silenciosamente | §7 |
| RNF-10 | **Mantenibilidad:** prompts, reglas y umbrales como configuración externa versionada, modificables sin tocar código | §8 Tuning de reglas |
| RNF-11 | **Usabilidad:** salida legible por un analista en menos de un minuto por alerta | §1, §9 |
| RNF-12 | **Cumplimiento:** política de retención y anonimización de los datos de prueba conforme a la normativa aplicable | §8 |
| RNF-13 | **Escalabilidad acotada:** procesamiento por lotes del dataset de prueba; la escalabilidad de producción queda como trabajo futuro | Alcance del plan de trabajo |

### Limitaciones sin requisito asociado

Cuatro limitaciones del análisis no generan requisitos funcionales porque quedan fuera del alcance declarado en el [plan de trabajo](../00-general/planDeTrabajoActualizado.md):

- **§6 Respuesta fragmentada y dependencia de SOAR** y parte de **§7**: corresponden a respuesta automatizada, documentada como trabajo futuro.
- **§5 Lock-in** y **§10 Evasión**: aportan restricciones de diseño (RNF-06 y RNF-08), no funcionalidad nueva del prototipo.

---

## Referencias

- Gartner Magic Quadrant for Endpoint Protection Platforms (2024–2026).
- Forrester Wave: Extended Detection and Response Platforms, Q2 2026.
- MITRE ATT&CK Enterprise Evaluations (2024–2025).
- Omdia — estudios sobre volumen de alertas y ruido operativo en SOC.
- D3 Security — análisis sobre la brecha detección-investigación y el techo del paradigma XDR (2025).
- Documento interno: [mdr-xdr.md](./mdr-xdr.md).
