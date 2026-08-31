# Estado del arte: MDR y XDR en el mercado

Este documento resume las principales soluciones de **Managed Detection and Response (MDR)** y **Extended Detection and Response (XDR)** disponibles actualmente, su posicionamiento en el mercado y los factores que explican su éxito o sus limitaciones. Sirve como base para la Fase 2 del proyecto (revisión del estado del arte).

---

## Panorama del mercado

Tanto MDR como XDR responden a la misma presión: el volumen de alertas supera la capacidad de los equipos internos, la escasez de analistas de seguridad es crónica y las amenazas son cada vez más sofisticadas (ransomware, compromiso de identidades, ataques en la nube).

| Segmento | Tamaño estimado (2025–2026) | Proyección | CAGR estimado |
|----------|----------------------------|------------|---------------|
| **MDR** | USD 5–6 mil millones (2025–2026) | USD 13–18 mil millones hacia 2031 | ~21–23% |
| **XDR** | USD 3–4 mil millones (2024–2025) | Crecimiento sostenido hasta 2030+ | ~20–39%* |

\* Las estimaciones varían según la firma analista y el alcance que se le dé a la categoría (solo plataforma vs. servicios gestionados).

**Factores de adopción:**
- Escasez de talento en ciberseguridad: construir y operar un SOC interno 24/7 resulta inviable para la mayoría de las organizaciones.
- Consolidación de herramientas: XDR busca reemplazar o complementar SIEM, EDR, NDR y soluciones de correo con una capa unificada de correlación.
- Presión regulatoria y de cumplimiento (DORA, NIS2, etc.) que exige detección y respuesta demostrables.
- Adopción acelerada en PYMEs y mid-market, donde el MDR se percibe como la forma más accesible de tener operaciones de seguridad de nivel empresarial.

Según Gartner, se proyectaba que cerca del **50% de las organizaciones** utilizarían servicios MDR para monitoreo, detección y contención 24/7; en 2026 el MDR se considera un pilar central de la estrategia de ciberseguridad, no un complemento opcional.

---

## Principales plataformas XDR del mercado

El mercado XDR está **consolidado**: los cinco grandes (Palo Alto, Cisco, CrowdStrike, IBM y Microsoft) concentran aproximadamente el **50–60%** de la cuota. Las evaluaciones de Gartner (Magic Quadrant EPP/XDR) y Forrester (Wave XDR) sitúan de forma recurrente a un grupo reducido de líderes.

### Líderes de mercado

#### 1. CrowdStrike Falcon XDR
- **Posicionamiento:** Referencia en arquitectura cloud-native; sensor ligero único, consola unificada y módulos Falcon integrados.
- **Fortalezas:** Profundidad de telemetría en endpoints, threat intelligence de alto nivel, integraciones de terceros, caza de amenazas (threat hunting) y detección basada en IOAs (Indicators of Attack) personalizables.
- **Éxito:** Líder consistente en Gartner MQ EPP desde 2020 y en Forrester Wave XDR (Q2 2026), con la puntuación más alta en "Current Offering". Modelo de una sola plataforma que escala bien en entornos híbridos y multi-nube.
- **Limitaciones:** Coste elevado para organizaciones pequeñas; mayor valor cuando se adopta el ecosistema Falcon completo.

#### 2. Microsoft Defender XDR
- **Posicionamiento:** XDR nativo para organizaciones ya invertidas en Microsoft 365 / Azure / Entra ID.
- **Fortalezas:** Correlación entre endpoint, identidad, correo, aplicaciones cloud y datos; coste incremental bajo o nulo si ya se dispone de licencias E5; integración profunda con el ecosistema Microsoft.
- **Éxito:** Líder en Gartner MQ; adopción masiva en empresas que estandarizaron Microsoft. Fuerte en evaluaciones MITRE ATT&CK.
- **Limitaciones:** Menor flexibilidad en entornos multi-vendor; dependencia del stack Microsoft.

#### 3. Palo Alto Networks Cortex XDR
- **Posicionamiento:** XDR integrado con el ecosistema Palo Alto (firewalls, Prisma Cloud, Cortex).
- **Fortalezas:** Correlación red + endpoint + nube; detección validada en MITRE; valor diferencial cuando ya existen inversiones en infraestructura Palo Alto.
- **Éxito:** Líder en Gartner; fuerte en sectores regulados y grandes empresas con despliegue Palo Alto existente.
- **Limitaciones:** Menor ventaja como XDR standalone sin el resto del ecosistema; reglas de detección menos tunables que CrowdStrike.

#### 4. SentinelOne Singularity XDR
- **Posicionamiento:** Respuesta autónoma e IA nativa; enfoque en automatización y simplicidad operativa.
- **Fortalezas:** Storyline (correlación automática de eventos), respuesta autónoma en endpoint, buen rendimiento en evaluaciones MITRE, precio competitivo.
- **Éxito:** Líder en Gartner MQ; preferido cuando la prioridad es respuesta automatizada y reducir carga del analista.
- **Limitaciones:** Ecosistema de terceros menos maduro que CrowdStrike; menor presencia en servicios gestionados propios.

### Otros actores relevantes

| Proveedor | Enfoque diferencial |
|-----------|---------------------|
| **Trend Micro (Vision One)** | XDR con sensores nativos multi-capa; fuerte en APAC |
| **Sophos** | XDR integrado con MDR post-adquisición de Secureworks |
| **IBM (QRadar Suite)** | Correlación enterprise con SIEM heredado |
| **Cisco (SecureX / XDR)** | Integración red + endpoint para clientes Cisco |
| **Fortinet** | XDR ligado a FortiGate y FortiEDR |
| **Elastic Security** | XDR open, basado en Elasticsearch; flexible pero exige más ingeniería |
| **Stellar Cyber / Cynet** | XDR para mid-market con despliegue rápido y menor TCO |

### Métricas de éxito en XDR

Las evaluaciones independientes (MITRE ATT&CK Evaluations, Gartner Peer Insights, Forrester Wave) miden principalmente:

- **MTTD (Mean Time to Detect):** Los líderes apuntan a detección en menos de 60 minutos para escenarios de ataque cubiertos.
- **Tasa de falsos positivos:** Diferenciador clave; alto volumen de alertas ruidosas sigue siendo la principal queja de los analistas.
- **Cobertura de técnicas ATT&CK:** Porcentaje de técnicas adversarias detectadas en evaluaciones públicas.
- **Integración multi-fuente:** Capacidad de ingerir telemetría de endpoints, red, identidad, correo y cloud en una sola capa analítica.

**Conclusión XDR:** La selección suele ser una **decisión de ecosistema**, no solo de capacidades técnicas. Las cuatro plataformas líderes son técnicamente capaces; la diferencia real está en alineación con el stack existente, TCO y requisitos de cumplimiento.

---

## Principales proveedores MDR del mercado

El mercado MDR experimentó **consolidación acelerada** en 2025: Sophos adquirió Secureworks (USD 859M), Arctic Wolf adquirió Cylance (BlackBerry) y Cybereason se fusionó con Trustwave. La tendencia es clara: quien controla la tecnología (EDR/XDR) y el servicio gestionado obtiene mejores resultados de detección y respuesta.

### Líderes de mercado

#### 1. CrowdStrike Falcon Complete
- **Modelo:** MDR sobre la plataforma Falcon; un solo vendor para agentes, analítica y respondedores.
- **Fortalezas:** Responders nativos Falcon, APIs de respuesta, detecciones propietarias, escala global.
- **Éxito:** Líder en KuppingerCole Leadership Compass MDR 2026; referencia para organizaciones que ya despliegan Falcon y quieren externalizar la operación del SOC.
- **Ideal para:** Empresas que apuestan por stack único CrowdStrike.

#### 2. Arctic Wolf
- **Modelo:** Concierge Security Team — analistas dedicados por cliente sobre plataforma Aurora (open XDR).
- **Fortalezas:** Integración con múltiples tecnologías de terceros (no exige un EDR específico), gestión de vulnerabilidades incluida, precio accesible para mid-market, modelo concierge con revisiones estratégicas periódicas.
- **Éxito:** Segundo lugar global en KuppingerCole 2026; uno de los MDR más grandes de Norteamérica. Adquisición de Cylance añadió tecnología EDR propia.
- **Ideal para:** PYMEs y mid-market que necesitan MDR sin estandarizar en un solo vendor de endpoint.

#### 3. Sophos MDR (+ Secureworks)
- **Modelo:** Tras la adquisición de Secureworks (feb. 2025), combina la práctica MDR de Sophos con Taegis XDR y el Counter Threat Unit de Secureworks.
- **Fortalezas:** Mayor footprint MDR puro del mercado (>28.000 organizaciones post-integración), inteligencia de amenazas X-Ops, décadas de experiencia en respuesta a incidentes.
- **Éxito:** Líder en KuppingerCole 2026; transformación de un MDR ligado al ecosistema Sophos a una operación de seguridad gestionada de nivel enterprise.
- **Ideal para:** Clientes Sophos existentes y empresas que buscan MDR respaldado por investigación de amenazas de primer nivel.

#### 4. Expel
- **Modelo:** Transparencia radical — el cliente ve en tiempo real lo que hacen los analistas (Workbench).
- **Fortalezas:** Integración profunda con Microsoft; servicios gestionados de SIEM (Splunk, Sentinel); motor Ruxie para enriquecimiento automatizado con analistas humanos en veredictos finales.
- **Éxito:** Referente en transparencia operativa; preferido en stacks heterogéneos donde el equipo interno quiere colaborar con el MDR, no solo recibir informes.
- **Limitaciones:** Dependencia de la calidad de los logs del cliente; menor valor si la telemetría de origen es deficiente.

#### 5. eSentire / Red Canary / ReliaQuest
- **eSentire:** MDR con enfoque en sectores regulados; fuerte en Canadá y enterprise.
- **Red Canary:** Especializado en detección sobre telemetría existente; buen equilibrio entre automatización y expertise humano.
- **ReliaQuest:** Plataforma GreyMatter que unifica herramientas del cliente con operación gestionada; orientado a enterprise multi-vendor.

### Otros actores relevantes

| Proveedor | Enfoque diferencial |
|-----------|---------------------|
| **Secureworks (Taegis)** | Ahora integrado en Sophos; referencia histórica en MSSP |
| **Rapid7 MDR** | Integrado con InsightIDR y Velociraptor |
| **Tata Communications / Atos** | MDR a escala global con herencia telco/MSSP |
| **Check Point MDR** | Servicio gestionado sobre Infinity platform |
| **ESET MDR** | Mid-market europeo con footprint creciente |

### Métricas de éxito en MDR

- **SLA de respuesta:** Compromisos de tiempo para triaje, escalado y contención (varían por severidad y contrato).
- **Tasa de escalación:** Proporción de alertas que requieren acción del cliente vs. resueltas de forma autónoma.
- **Cobertura de telemetría:** Fuentes monitorizadas (endpoint, red, identidad, cloud, OT).
- **Transparencia operativa:** Visibilidad del cliente sobre investigaciones, playbooks y decisiones.
- **Retención y NPS:** Indicadores de satisfacción; los líderes reportan tasas de renovación altas en mid-market.

**Conclusión MDR:** El éxito del MDR depende menos de la marca de la plataforma subyacente y más de **cómo se opera el servicio**: calidad del triaje, comunicación con el cliente, SLAs cumplidos y capacidad de reducir ruido antes de escalar.

---

## Tendencias que definen el éxito actual

### 1. Consolidación plataforma + servicio
Los proveedores que poseen EDR/XDR y MDR (CrowdStrike, Sophos, Arctic Wolf) optimizan detección y respuesta al controlar toda la cadena. La tendencia M&A continúa.

### 2. MXDR (Managed XDR)
El segmento de MDR extendido (telemetría multi-capa: endpoint + red + identidad + cloud) crece al **~27% CAGR**, más rápido que el MDR centrado solo en endpoints. Refleja la demanda de visibilidad unificada.

### 3. IA y agentes autónomos
- **En XDR:** Correlación automática, priorización de alertas, respuesta autónoma (SentinelOne, CrowdStrike).
- **En MDR:** Enriquecimiento automatizado de evidencias (Expel Ruxie, Arctic Wolf Aurora Agentic SOC), con analistas humanos como autoridad final en veredictos.
- Riesgo: la promesa de "SOC autónomo" aún no reemplaza la validación humana en decisiones críticas.

### 4. CTEM (Continuous Threat Exposure Management)
Gartner promueve la gestión continua de exposición como complemento del MDR: no solo detectar ataques, sino reducir la superficie de ataque de forma proactiva.

### 5. Adopción en PYMEs
El MDR democratiza acceso a operaciones de seguridad 24/7. Proveedores como Arctic Wolf, Sophos y Cynet compiten por precio y simplicidad en este segmento.

---

## Limitaciones e implicaciones para el proyecto

Este documento describe **qué hay en el mercado**. El análisis de **qué sigue sin resolverse** —y
qué hueco ocupa por tanto este prototipo— vive en un solo sitio, para que las dos versiones no
diverjan:

- [Limitaciones de XDR](./limitacionesDeXDR.md) — las diez limitaciones documentadas, con las
  implicaciones para el proyecto y el destinatario al que va dirigido.
- [Modelos de lenguaje aplicados a la seguridad](./llm-en-seguridad.md) — qué aportan y qué
  riesgos introducen los modelos en el camino de una alerta, y la comparación entre reglas y IA.
- [Requisitos del prototipo](./requisitos.md) — el registro único al que llegan ambos análisis.

En una línea: el mercado valida la demanda —crecimiento sostenido en MDR y XDR— pero las
plataformas líderes siguen dependiendo del analista para el triaje y la investigación final, y
**ninguna sabe si la respuesta que propone va a interrumpir un servicio**. Ese es el hueco.

---

## Referencias

Enlaces verificados el **25/08/2026**.

| Fuente | Qué aporta | Enlace |
|--------|------------|--------|
| MITRE ATT&CK Evaluations — Enterprise | Resultados públicos de detección por plataforma | https://attackevals.mitre-engenuity.org/ |
| NIS2 — Directiva (UE) 2022/2555 | Presión regulatoria como factor de adopción | https://eur-lex.europa.eu/eli/dir/2022/2555 |
| DORA — Reglamento (UE) 2022/2554 | Ídem, sector financiero | https://eur-lex.europa.eu/eli/reg/2022/2554 |

### Fuentes pendientes de verificación directa

**Todas las cifras de mercado de este documento** —tamaños de segmento, proyecciones, CAGR, cuotas
y posicionamiento de proveedores— proceden de informes de firmas analistas de acceso restringido,
recogidos de forma indirecta: Gartner (*Magic Quadrant for Endpoint Protection Platforms*),
Forrester (*Wave: Extended Detection and Response Platforms*), KuppingerCole (*Leadership Compass:
MDR*), MarketsandMarkets, Mordor Intelligence y Frost & Sullivan.

Las operaciones societarias citadas (adquisiciones y fusiones del mercado MDR) son públicas y
verificables en las notas de prensa de las compañías implicadas.

**Antes de llevar cualquier cifra al informe final de la Fase 7**, hay que citarla contra el informe
original con edición y fecha, o sustituirla por una formulación cualitativa. Una cifra concreta sin
fuente localizable no se sostiene en una revisión.
