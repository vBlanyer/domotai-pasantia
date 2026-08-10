# EDR, XDR, MDR y su relación con las herramientas de telemetría

Este documento explica la diferencia entre **EDR**, **XDR** y **MDR**, y cómo las soluciones **comerciales** obtienen y utilizan la telemetría. Aclara un punto clave para el proyecto: qué papel juegan herramientas de telemetría como [Sysmon](./symons.md), osquery, Zeek o auditd frente a los **agentes propietarios** de los productos comerciales, y cuándo unas complementan a los otros.

Complementa el [estado del arte de MDR/XDR](../mdr-xdr.md) (panorama de mercado) y el catálogo de [herramientas auxiliares](./herramientas-auxiliares.md) (fuentes de telemetría y análisis).

---

## 1. EDR, XDR y MDR: qué son y cómo se relacionan

Los tres términos se confunden con frecuencia, pero operan en planos distintos: **EDR** y **XDR** son *tecnologías* (dónde se recoge y correlaciona la telemetría), mientras que **MDR** es un *servicio* (quién la opera).

| Sigla | Qué es | Alcance de telemetría | Naturaleza |
|-------|--------|-----------------------|------------|
| **EDR** (Endpoint Detection & Response) | Detección y respuesta en el **endpoint**. | Solo endpoint (procesos, archivos, registro, red local). | Producto / agente |
| **XDR** (Extended Detection & Response) | Correlación **multi-capa** de varias fuentes en una sola plataforma. | Endpoint + red + identidad + correo + cloud. | Plataforma |
| **MDR** (Managed Detection & Response) | **Servicio gestionado** que opera EDR/XDR por el cliente (analistas 24/7). | El que ofrezca la tecnología subyacente. | Servicio (personas + proceso) |

### Relación entre ellos

```
        ┌─────────────────────── MDR (servicio: analistas 24/7) ───────────────────────┐
        │                                                                              │
        │   ┌──────────────────────────── XDR (plataforma) ──────────────────────────┐ │
        │   │                                                                         │ │
        │   │   ┌── EDR ──┐   ┌── NDR ──┐   ┌ Identidad ┐   ┌ Correo ┐   ┌─ Cloud ─┐  │ │
        │   │   │endpoint │   │  red    │   │  (IdP)    │   │(e-mail)│   │ (CSPM)  │  │ │
        │   │   └─────────┘   └─────────┘   └───────────┘   └────────┘   └─────────┘  │ │
        │   │                     ↑ fuentes de telemetría que alimentan el XDR        │ │
        │   └─────────────────────────────────────────────────────────────────────── ┘ │
        └──────────────────────────────────────────────────────────────────────────────┘
```

- El **EDR es una de las fuentes de telemetría del XDR** (la del endpoint). El XDR añade red, identidad, correo y cloud, y **correlaciona** todo en una capa analítica común.
- El **MDR envuelve** a EDR o XDR con un equipo humano que hace triaje, investigación y respuesta. Un MDR puede operar sobre un EDR (solo endpoint) o sobre un XDR (multi-capa) — a esto último se le llama **MXDR** (Managed XDR).
- **SIEM** y **SOAR** son el enfoque "clásico": el SIEM agrega logs de muchas fuentes y el SOAR automatiza respuesta. El XDR nace para simplificar ese modelo con integración nativa y menos ingeniería.

---

## 2. De dónde sacan la telemetría los productos comerciales

Aquí está el punto central: **los EDR/XDR comerciales no dependen de Sysmon ni de herramientas open source para su telemetría principal. Traen su propio agente (sensor) propietario**, más rico y con capacidad de respuesta en tiempo real.

### 2.1 El agente propietario como fuente primaria

Cada plataforma líder despliega su **propio sensor de endpoint** a nivel de kernel/driver, que captura telemetría equivalente (y superior) a la de Sysmon, pero además permite **respuesta** (aislar host, matar proceso, cuarentena):

| Producto comercial | Agente / sensor propio | ¿Usa Sysmon como fuente? |
|--------------------|------------------------|--------------------------|
| **CrowdStrike Falcon** | Falcon sensor (agente único ligero, cloud-native) | No para su EDR; su SIEM (Falcon Next-Gen SIEM / LogScale) **puede ingerir** Sysmon como fuente adicional. |
| **Microsoft Defender for Endpoint / Defender XDR** | Sensor EDR integrado en Windows | No lo necesita (sensor propio); **Sentinel** (SIEM) sí ingiere Sysmon vía Azure Monitor Agent. |
| **SentinelOne Singularity** | Agente Singularity (EDR/XDR autónomo) | No para su EDR; su data lake **ingiere** telemetría de terceros. |
| **Palo Alto Cortex XDR** | Cortex XDR agent (endpoint) + NGFW (red) | No para endpoint; **ingiere** logs de red, cloud y terceros. |
| **Trend Micro Vision One** | Agente propio multi-capa | Sensor propio; ingiere fuentes adicionales. |

**Por qué su agente supera a Sysmon:**
- Telemetría en **tiempo real** enviada a la nube (no solo escrita a Event Log).
- **Respuesta activa** integrada (containment, rollback, remediación) — Sysmon solo registra.
- Analítica, threat intelligence y ML aplicados sobre la telemetría del propio vendor.
- Anti-tamper: el agente se protege frente a manipulación.

### 2.2 Cuándo el mundo comercial sí consume telemetría open source

Los productos comerciales **sí ingieren** Sysmon, osquery, Zeek, auditd, etc. — pero como **fuente complementaria**, no como sustituto de su agente:

- **En la capa SIEM/data-lake del XDR:** plataformas como Microsoft Sentinel, Elastic Security, CrowdStrike Next-Gen SIEM o Splunk ingieren Sysmon y otros logs para ampliar cobertura (p. ej. servidores sin agente EDR, o telemetría extra de Windows).
- **XDR "abierto" (open XDR):** soluciones agnósticas de telemetría (Stellar Cyber, Elastic, Securonix) están diseñadas para **ingerir cualquier fuente**, incluida telemetría open source. Aquí Sysmon es un ciudadano de primera clase.
- **MDR telemetría-agnóstica:** algunos MDR no exigen un EDR concreto y operan sobre la telemetría que ya tenga el cliente (ver sección 4).
- **osquery como base de producto:** algunos comerciales se construyen sobre osquery (p. ej. Uptycs), demostrando que la frontera open/comercial no siempre es rígida.

### 2.3 Telemetría por capa (quién cubre qué en un XDR)

| Capa | Fuente comercial típica | Equivalente open source (proyecto low-cost) |
|------|-------------------------|---------------------------------------------|
| **Endpoint** | Agente EDR (Falcon, Defender, SentinelOne, Cortex) | [Sysmon](./symons.md), osquery, auditd + Wazuh |
| **Red (NDR)** | Sensores propios / NGFW (Palo Alto, Cisco) | Zeek, Suricata |
| **Identidad** | Entra ID / Okta / Ping (logs de IdP) | Logs de AD / LDAP + reglas |
| **Correo** | Defender for Office, Proofpoint | Logs de gateway de correo |
| **Cloud** | CSPM / logs nativos (CloudTrail, Azure) | Stratus + logs cloud + reglas |

---

## 3. Comparativa: EDR vs XDR vs MDR

| Dimensión | EDR | XDR | MDR |
|-----------|-----|-----|-----|
| **Qué provee** | Tecnología de endpoint | Plataforma multi-capa | Servicio operado por personas |
| **Telemetría** | Endpoint (agente propio) | Endpoint + red + identidad + correo + cloud | La de la tecnología subyacente |
| **Correlación** | Dentro del endpoint | Cross-domain automatizada | La hacen analistas + plataforma |
| **Respuesta** | En endpoint | Coordinada multi-capa (parcial) | Ejecutada/asesorada por el proveedor |
| **Quién opera** | El equipo interno del cliente | El equipo interno del cliente | El proveedor (SOC externo 24/7) |
| **Ideal para** | Organizaciones con SOC propio | Empresas que quieren visibilidad unificada | Quien no puede operar un SOC 24/7 (PYMEs) |

**Regla mnemónica:** *EDR mira el endpoint · XDR une las capas · MDR pone a la gente que lo opera.*

---

## 4. La telemetría en los MDR comerciales: dos modelos

En los MDR el uso de telemetría se divide claramente en dos filosofías, relevantes para decidir el enfoque del proyecto:

### Modelo A — Stack único (single-vendor)

El MDR usa el **agente propietario del mismo vendor**. Máxima integración y profundidad, mínima flexibilidad.

- **Ejemplo:** CrowdStrike Falcon Complete → telemetría del sensor Falcon.
- Sysmon y open source apenas intervienen; todo pasa por el agente del vendor.

### Modelo B — Telemetría-agnóstico (open / bring-your-own)

El MDR **ingiere la telemetría que el cliente ya tenga**, incluida open source. Más flexible, ideal para entornos heterogéneos y PYMEs.

- **Ejemplos:** Arctic Wolf (plataforma Aurora, open XDR), Expel (opera sobre las herramientas del cliente), Red Canary (fuerte con telemetría de endpoint existente, incluido Sysmon), Stellar Cyber.
- **Aquí encaja Sysmon:** estos MDR pueden tomar el canal `Microsoft-Windows-Sysmon/Operational` como fuente de detección sin exigir un EDR comercial.

---

## 5. Implicaciones para este proyecto

El proyecto no compite con un EDR/XDR comercial: se sitúa como **módulo de triaje inteligente** sobre telemetría, y por eso el **Modelo B (telemetría-agnóstico)** es el de referencia.

| Decisión de mercado | Implicación para el prototipo |
|---------------------|-------------------------------|
| Comerciales usan agente propietario rico + respuesta | El prototipo **no** intenta reemplazar el agente; consume la telemetría (Sysmon u otra) y aporta clasificación/priorización/explicabilidad. |
| XDR/MDR abiertos ingieren Sysmon y open source | Validar el prototipo con [Sysmon](./symons.md) + Wazuh/Elastic es representativo de un flujo real de Modelo B. |
| El diferencial comercial es la correlación, no solo la captura | El valor del prototipo está en el **triaje explicable**, capa donde los comerciales siguen dependiendo del analista. |
| MDR de bajo coste apuntan a PYMEs con telemetría existente | Encaja con el objetivo de una solución viable sin depender de servicios cloud externos. |

**Conclusión:** las herramientas de telemetría open source (Sysmon, Zeek, osquery, auditd) son la **materia prima** del XDR; los comerciales la sustituyen por agentes propietarios más potentes, pero los enfoques abiertos —y el módulo de triaje de este proyecto— demuestran su valor precisamente al operar sobre esa telemetría accesible. El proyecto se inserta en la **capa de análisis y triaje**, no en la de captura ni en la de respuesta.

---

## Referencias

- Ver [estado del arte MDR/XDR](../mdr-xdr.md) para el panorama de mercado y proveedores.
- Ver [herramientas auxiliares](./herramientas-auxiliares.md) para el catálogo de fuentes de telemetría y análisis.
- Ver [Sysmon](./symons.md) para la fuente de telemetría de endpoint de referencia del proyecto.
- Gartner Magic Quadrant for Endpoint Protection Platforms; Forrester Wave: XDR Platforms.
- KuppingerCole Leadership Compass: MDR.
- MITRE ATT&CK Evaluations (Enterprise).
