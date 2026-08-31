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
| Falsos positivos y fatiga de alertas (§1) | Clasificación y priorización con **contexto de la postura real del activo**, que es lo que la regla no tiene |
| Brecha entre detección e investigación (§2) | El prototipo no investiga por el analista, pero le entrega la alerta ya clasificada, priorizada y **justificada** |
| Explicabilidad limitada (§9) | Razonamiento explicable con anclaje verificable a los campos de la alerta |
| Dependencia de la nube del proveedor (§5, §8) | Ejecución **local**, sobre hardware modesto, sin que la alerta salga de la red del cliente |
| Complemento, no sustituto (§5) | Capa de triaje **sobre** el sistema de reglas que el cliente ya tiene; no compite con él ni lo reemplaza |

### Sobre a quién va dirigido

El análisis de mercado señala repetidamente a las **PYMEs** como el segmento peor cubierto, y así
figura en las fuentes. Conviene no confundir esa observación con el destinatario de este proyecto.

El plan de trabajo declara el *«despliegue y escalabilidad en entornos de clientes PYME»* **fuera
del alcance**, como trabajo futuro. El cliente que el prototipo modela es el descrito en la
[Fase 1](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md): una **organización con red
propia** —borde, conmutación, servidores, servicios publicados— que quiere protegerse **sin
interrumpir lo que presta**. Ese cliente puede ser pequeño o grande; lo que lo define no es su
tamaño sino su restricción de continuidad.

La distinción tiene consecuencias reales. Justificar el proyecto sobre el precio de las licencias
enterprise apunta a un problema de presupuesto; justificarlo sobre la **restricción de continuidad**
apunta a un problema que ninguna plataforma del mercado resuelve hoy, porque **ninguna sabe si la
respuesta que propone va a cortar un servicio**. Esa es la limitación §9 llevada hasta su
consecuencia operativa, y es el hueco que este prototipo ocupa.

---

## Los requisitos que se derivan de aquí

El análisis anterior es el origen de la mayor parte de los requisitos del prototipo, pero **la lista
no vive en este documento**: vive en el [registro único de requisitos](./requisitos.md), junto con
los que derivan del [análisis de modelos de lenguaje](./llm-en-seguridad.md) y de las restricciones
del [cliente modelado](../01-fase1-analisis-del-modulo/).

Cada requisito de ese registro cita en su columna «Deriva de» la sección de este documento que lo
motiva. Mantener una sola lista evita el problema que ya se dio una vez: requisitos nuevos anotados
en un documento aparte que la tabla maestra nunca recogió.

---

## Referencias

Enlaces verificados el **25/08/2026**.

| Fuente | Qué aporta | Enlace |
|--------|------------|--------|
| MITRE ATT&CK Evaluations — Enterprise | Cobertura de técnicas y volumen de alertas por plataforma | https://attackevals.mitre-engenuity.org/ |
| MITRE ATT&CK | Taxonomía de técnicas adversarias | https://attack.mitre.org/ |
| OWASP Top 10 for LLM Applications | Riesgos del componente de IA (§9 y RNF-08) | https://genai.owasp.org/llm-top-10/ |
| NIS2 — Directiva (UE) 2022/2555 | Presión regulatoria citada en §8 | https://eur-lex.europa.eu/eli/dir/2022/2555 |
| DORA — Reglamento (UE) 2022/2554 | Ídem, sector financiero | https://eur-lex.europa.eu/eli/reg/2022/2554 |
| Documento interno | Estado del arte MDR/XDR | [mdr-xdr.md](./mdr-xdr.md) |
| Documento interno | Modelos de lenguaje aplicados a seguridad | [llm-en-seguridad.md](./llm-en-seguridad.md) |

### Fuentes pendientes de verificación directa

Las cifras concretas de este documento —el porcentaje de alertas que siguen siendo ruido operativo,
el tiempo medio de investigación por alerta, la proporción de *burnout* entre analistas y las cuotas
de mercado— proceden de **informes de firmas analistas de acceso restringido** (Gartner, Forrester,
Omdia, KuppingerCole) recogidos de forma indirecta.

| Informe | Uso en este documento |
|---------|----------------------|
| Gartner — Magic Quadrant for Endpoint Protection Platforms | Posicionamiento de plataformas (§5) |
| Forrester — Wave: Extended Detection and Response Platforms | Ídem |
| Omdia — estudios sobre volumen de alertas en SOC | Cifra de ruido operativo (§1) |
| KuppingerCole — Leadership Compass: MDR | Posicionamiento de proveedores MDR |
| D3 Security — análisis sobre la brecha detección-investigación | §2 |

**Antes de incorporar cualquiera de esas cifras al informe final de la Fase 7 hay que citarlas
contra el informe original**, con edición y fecha, o sustituirlas por una formulación cualitativa.
Una cifra concreta sin fuente localizable no se sostiene en una revisión.
