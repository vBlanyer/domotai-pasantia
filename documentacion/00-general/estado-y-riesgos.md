# Estado del proyecto, incongruencias y riesgos

Documento de trabajo interno. Recoge qué está decidido, qué está bloqueado y qué contradicciones existen hoy entre los documentos del proyecto. **No sustituye al [plan de trabajo](./planDeTrabajoActualizado.md) ni al [roadmap](./roadmap.md)**, que son los documentos que van a coordinación y que no cambian con esta revisión.

Su propósito principal es preparar la reunión con la empresa: las incongruencias 1, 3 y 4 solo pueden resolverlas ellos.

---

## 1. Estado por fase

*Actualizado a 10/09/2026.*

| Fase | Estado | Qué hay hecho / qué falta |
|------|--------|----------------------------|
| 1 — Análisis del módulo propietario | **Completa por modelado** | Ejecutada por modelado al no haber cliente: [modelo de cliente genérico](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md) y [caso de uso acotado](../01-fase1-analisis-del-modulo/caso-de-uso-acotado.md), con las limitaciones y los cinco puntos de variabilidad. Sigue abierto solo lo que depende de la empresa (I-4). |
| 2 — Estado del arte | **Completa** | Estado del arte MDR/XDR **y de los modelos de lenguaje aplicados a seguridad**, con la comparación reglas frente a IA. **34 requisitos** (20 RF + 14 RNF) en un [registro único](../02-fase2-estado-del-arte/requisitos.md). Encuadre de mercado reorientado del segmento PYME al cliente modelado en la Fase 1. |
| 3 — Entorno de pruebas | **Completa** | Red del cliente de 7 nodos, Metasploitable con ground truth, Wazuh generando alertas reales, auditor Nmap normalizado, todo reproducible con `lab/lab.sh` y con [guía de instalación](../../lab/docs/instalacion.md). **Dataset de alertas etiquetado entregado** (`lab/dataset/etiquetado.jsonl`: 466 alertas de tres familias —acceso a credenciales, reconocimiento y servicio expuesto—, 54 VP / 30 FP / 8 PROPIA, particionado). Falta solo: equipo de borde OpenWrt real (vrnetlab bloqueado). |
| 4 — Arquitectura | **Cerrada** | Flujo, protocolos, auditoría, modelo (perfiles A/B), catálogo de acciones con impacto, métricas y baseline, arquitectura consolidada, y la [política de decisión y perfil de cliente](../04-fase4-diseno-de-arquitectura/politica-decision-continuidad.md) (revisión RF-17 a RF-20 y RNF-14 absorbida el 31/08). Único hueco: probar el catálogo sobre OpenWrt real. |
| 5 — Implementación | **Completa** | El prototipo vive en [`prototipo/`](../../prototipo/) (**427 tests**): decisión (5A), lazo en vivo con conector SSH y validación humana (5B), justificador con LLM real (5C, servidor residente con Llama-3.1-**8B**; el 1B sigue disponible), **RAG local con embedder dedicado bge-m3, consulta agéntica y recuperación dependiente de la clase (5D)**, **daemon en tiempo real** (`stream.py`, agrupación en incidentes RF-11) y **agente de mitigación ReAct** (`agente_mitigacion.py`, escalada host→cortafuegos). El **codificador con ajuste fino se descartó** a favor de un **árbol de decisión** (`arbol.py`), la escala honesta para un dataset de unos cientos de filas (un modelo grande memoriza y no se valida sin fuga): el árbol **valida y descubre reglas** que se promueven al clasificador determinista auditable (p. ej. la 6ª regla, la de ráfaga, con evidencia 79/79). El sistema clasifica a la granularidad **VP/FP/no_soportada** que las etiquetas del dataset soportan; distinguir las 6 clases finas exigiría etiquetas finas de las que hoy no se dispone — límite de datos, no una pieza pendiente. La **taxonomía de familias** es un **registro extensible alineado a MITRE** (`familias.yml`) con tres niveles de respuesta —**actuar** (contener), **triar_y_enrutar** (clase `amenaza_enrutada`: clasificar y encaminar a un equipo, sin contener) y **no_soportada**—, y un **perfil de cliente bancario** (`perfiles/bancario.yml`, continuidad extrema, joyas de la corona intocables). La **conciencia de impacto** (21/09, RF-17/RF-19): cada contención determina a quién bloquea y qué servicios detiene desde el inventario del perfil (`actores.py`, `impacto.py`), el filtro retiene para el humano el bloqueo de lo propio (D16), el canal de gestión real (el auditor) es intocable y `inventario.py` reconcilia lo declarado con lo que ve el auditor. Con **dependencias declaradas** entre activos y radio de impacto en cascada (Nivel 2). |
| 6 — Evaluación | **Completa** | Marco de medición en [`evaluacion/`](../../evaluacion/) (**56 tests**) y campaña ejecutada. Resultado (tres familias, 11/09/2026): el prototipo **elimina los FP** (tasa 0.000 vs 0.296 del nivel de regla de Wazuh) y **detecta más amenazas** (recall 1.0 vs 0.741: el baseline deja pasar las de baja severidad) y sin acciones disruptivas indebidas, tras usar orígenes legítimos para distinguir admin de atacante (RF-03). Escala al humano el **29,7 %** (89/300) desde la conciencia de impacto (21/09): el 6,7 % por confianza (ráfagas desde el origen de administración) más todo bloqueo de un activo interno (D16), con **0** contenciones automáticas indebidas (antes 2, invisibles al indicador de continuidad). La **ablación de postura** mide margen 0 para un LLM en la decisión (D15). Ver [informe](../06-fase6-evaluacion-del-prototipo/informe-evaluacion.md). |
| 7 — Documentación final | **Borrador entregado** | Informe final en LaTeX según la norma del Decanato de Estudios Profesionales, en [`documentacion/report/`](../report/): 53 páginas, compila limpio, con los datos administrativos del plan oficial CCT-002-2026 y las cifras sincronizadas con la Fase 6. Pendiente solo lo que no depende del proyecto: revisión de los tutores y el Acta de Evaluación. |

### Progreso del laboratorio (Fase 3, verificado)

Lo que funciona hoy, medido y reproducible (`sh lab/lab.sh up && sh lab/lab.sh test`):

- **Red del cliente**: punto de entrega → equipo de borde → switch → {puesto, iot, servidor vulnerable}, más auditor en el plano de gestión. Conectividad de extremo a extremo, 2 saltos por el borde. Los identificadores de nodo del `.clab.yml` siguen la terminología actual: `proveedor`, `borde`, `sw-lan`, `puesto`, `iot`, `objetivo-vuln` y `auditor`.
- **Superficie de ataque real**: el `iot` expone telnet sin auth y web; el `objetivo-vuln` es Metasploitable con 19 puertos y CVEs documentados (puerta trasera vsftpd, ingreslock, Samba…).
- **Alertas reales**: Wazuh recibe syslog del objetivo y clasifica — login fallido → nivel 5, fuerza bruta correlacionada → nivel 10, con IP y usuario parseados. Visor en vivo (`lab/scripts/ver-alertas.sh`).
- **Memoria medida**: laboratorio + Wazuh < 0,8 GB, frente a los ~6 GB estimados. El único límite real es el entorno de desarrollo.

**Límite estructural del laboratorio:** el equipo de borde es un contenedor Linux provisional (solo encamina), no OpenWrt, porque el arranque de vrnetlab se cuelga. Deja de ser bloqueante desde que el caso de uso se acota por familia de alerta y no por equipo —el nodo IoT y el servidor vulnerable ya ejercitan la misma superficie—, pero el borde con firmware real sigue siendo el escenario más representativo. Ver [lab/docs/mediciones.md](../../lab/docs/mediciones.md).

---

**Revisión requisito-a-requisito (02/09/2026).** Cerrado el «grupo B»: RF-01 (ingesta de producto) y
RF-11 (agrupación por incidente) implementados; RF-03 mejorado (fp_actividad_legitima → precisión de
la Fase 6 a 1.0); RF-05 (justificación estructurada), RF-07 (umbral configurable), RF-08 (reclasificar
real), RF-09/RNF-03 (justificador+modelo en la traza) programados; RF-04, RF-12, RF-13, RNF-04, RNF-10,
RNF-12, RNF-14 resueltos por documentación. `prototipo/` quedó independiente de `lab/`. Pendiente: solo
la Fase 7 (informe final + matriz de trazabilidad).

## 2. Decisiones cerradas

| # | Decisión | Documento |
|---|----------|-----------|
| D1 | El plan de trabajo y el roadmap **no se modifican**; la información nueva va al detalle de fases | — |
| D2 | El sandbox es **la red del cliente desde el ODF hacia dentro** (borde, red interna, servidores, puestos); los objetivos prioritarios son los **servicios de gestión expuestos**. *Sustituye al encuadre FTTx/CPE de agosto 2026.* | [sandbox](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) · [Fase 1](../01-fase1-analisis-del-modulo/) |
| D3 | Plataforma de laboratorio: **Containerlab**. Descartados Packet Tracer (simula, no virtualiza) y CML (tope de nodos) | [sandbox §2](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) |
| D4 | Canal motor de triaje → sandbox: **SSH**, acotado a un **catálogo cerrado de acciones**. TR-069/TR-369 como evolución | [protocolos](../04-fase4-diseno-de-arquitectura/protocolos-comunicacion-sandbox.md) |
| D5 | Auditoría limitada a **escaneo de red**: Nmap inventaría, Greenbone dictamina. Sin análisis de firmware. **Implementado: solo Nmap** — Greenbone no cabe en memoria junto al resto (Fase 3); la postura (expuesto sí/no) sale de Nmap, sin dictamen de CVE | [auditoría](../04-fase4-diseno-de-arquitectura/auditoria-de-vulnerabilidades-del-sandbox.md) |
| D6 | Modelo en **dos perfiles**: A híbrido (equipo actual), B con Foundation-Sec-8B (si hay hardware) | [modelo](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) |
| D10 | El **módulo de ingesta ocupa el papel del playbook** en el laboratorio; no se crea una caja aparte | [flujo §3](../04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md) |
| D8 | **Wazuh dentro del sandbox** como fuente de alertas y **su nivel de regla como baseline** | [sandbox §5.1](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) |
| D9 | El Perfil A incorpora un **modelo de 3B en línea** para la justificación breve de la validación humana | [modelo §3](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) |
| D7 | Dos abstracciones sostienen el diseño: el **conector** (acciones abstractas) y la **interfaz de análisis** (`clasificar`/`justificar`) | [protocolos](../04-fase4-diseno-de-arquitectura/protocolos-comunicacion-sandbox.md), [modelo §5](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) |
| D11 | La interacción humana del prototipo es **por terminal (TUI/CLI)**; **sin UI gráfica**. Una UI gráfica queda como **trabajo futuro** tras culminar el prototipo | [flujo §7](../04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md) |
| D12 | La recuperación del RAG es **agéntica**: el propio modelo decide qué consultar al corpus, y la consulta y los pasajes quedan en la traza (`consulta_rag`/`pasajes_usados`). El corpus se mantiene **curado y pequeño** (29 fichas ATT&CK/D3FEND): crecerlo con el embedder 1B **degrada** la recuperación (MRR 0.41→0.19), medido y revertido | [rendimiento §hallazgo](../../docs/pruebas/06-rendimiento-y-hardware.md) |
| D13 | El prototipo opera además como **daemon en tiempo real** (`prototipo/stream.py`): sigue la fuente sin cerrarse, agrupa la ráfaga en **incidentes** (RF-11) y valida con el analista por `/dev/tty`. **La decisión y la contención son deterministas e instantáneas en los tres modos** (`--sin-llm`/`--con-llm`/`--agente`); el LLM solo explica | [pruebas 03](../../docs/pruebas/03-lab-en-vivo.md) |
| D14 | La mitigación multi-nodo la resuelve un **agente ReAct** (`prototipo/agente_mitigacion.py`) que escala de dispositivo (host → cortafuegos) **sobre el catálogo cerrado**, consultando ATT&CK/D3FEND como herramienta y **aprobando por paso**. No amplía el repertorio de acciones: elige dentro de él | [pruebas 04](../../docs/pruebas/04-escenarios-de-ataque.md) |
| D15 | **Los modelos de lenguaje asisten el triaje; no deciden la clase ni la prioridad.** Reconcilia el objetivo 5 («clasificación y priorización asistida por modelos de lenguaje»). *Historia:* el diseño lo cumplía con un encoder ajustado (un modelo de lenguaje) que se descartó porque con unos cientos de filas memoriza; lo sustituye un árbol que descubre reglas deterministas. *Dónde asisten:* justifican cada clasificación con RAG, formulan la consulta de recuperación, vectorizan (bge-m3) y deciden la escalada del agente. *Por qué no deciden:* (1) el umbral de RF-07 exige una confianza comparable que un generativo solo autodeclara; (2) reproducibilidad, medida: mismo prompt a temperatura 0 dio salidas distintas en 4 de 12 casos con caché de prefijos; (3) seguridad (RNF-08): el contenido de la alerta lo escribe el atacante y un LLM que decide la clase es superficie de inyección para evadir la contención; (4) **evidencia**: el determinista satura el dataset y la ablación de postura mide **margen 0** para un LLM con la configuración real (2 alertas irrecuperables sin postura). *Camino abierto:* la interfaz `clasificar` no cambia y el bucle de feedback (RF-12) acumula los datos que un encoder necesitaría | [resultados §ablación](../../evaluacion/resultados/README.md) · [Fase 5](../05-fase5-implementacion-del-prototipo/README.md) |
| D16 | **Bloquear lo propio exige humano por defecto.** Una contención que recae sobre un activo interno o un dispositivo de red del cliente queda retenida para validación humana (`continuidad.actores`, por defecto `humano_siempre`, configurable por perfil); bloquear el canal de gestión es veto duro (RF-19). El impacto se **determina** desde el inventario (a quién bloquea, qué servicios detiene) y nunca queda por debajo del catálogo. *Coste medido:* el escalado sube de 6,7 % a 29,7 % en el laboratorio, porque allí el atacante es interno; la automatización queda para los orígenes externos | [spec](../../docs/superpowers/specs/2026-09-21-conciencia-de-impacto-design.md) · [resultados](../../evaluacion/resultados/README.md) |

---

## 3. Incongruencias

Clasificadas por severidad. **Bloqueante** = impide avanzar. **Estructural** = el plan asume algo que no se cumple. **De diseño** = dos documentos nuestros se contradicen. **Menor** = riesgo de confusión.

---

### I-1 · No existe la fuente de alertas — ~~BLOQUEANTE~~ **RESUELTA**

El flujo previsto es `logs → playbook → motor de triaje`. El sistema de logs y el playbook son de la empresa, y **no hay empresa ni sistema definidos**.

Agravante detectado al revisar: el [diseño del sandbox](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) **no contempla ningún componente que genere alertas**. Produce telemetría de red y vulnerabilidades, pero nada que el motor de triaje pueda triar. **El motor de triaje no tiene entrada.**

**Choca con:** el criterio de cierre de la Fase 3 — *«el entorno procesa alertas de prueba de punta a punta»*.

**Resolución (agosto 2026):** se despliega **Wazuh dentro del sandbox** como fuente de alertas de laboratorio — agentes en los nodos Linux y reenvío de syslog desde el equipo de borde OpenWrt. El proyecto deja de depender de la empresa para avanzar. Si su sistema llega, se integra como segunda fuente por el mismo módulo de ingesta. Ver [sandbox §5.1](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md).

---

### I-2 · Dos *ground truths* distintos tratados como uno — ~~BLOQUEANTE~~ **RESUELTA**

El diseño del sandbox afirma que «la topología es el dataset». Eso es cierto para **vulnerabilidades**: se sabe qué CVE hay en cada nodo. Pero el plan exige ground truth de **alertas**: verdadero positivo frente a falso positivo.

**No son lo mismo y no hay puente documentado entre ambos.** Es un error de redacción de la Fase 3 que debe corregirse explícitamente, no matizarse.

**Resolución (agosto 2026):** la sección 6 del diseño del sandbox se reescribió para separar ambos explícitamente y documentar el puente: cada alerta de Wazuh se contrasta contra el inventario de vulnerabilidades del nodo al que apunta, y de ahí sale la etiqueta de verdadero o falso positivo.

---

### I-3 · No hay baseline, luego la Fase 6 no es ejecutable — ~~BLOQUEANTE~~ **RESUELTA**

La evaluación compara el prototipo contra «el método tradicional de referencia», que en la práctica es la clasificación o severidad que asigna hoy el sistema existente. Sin ese sistema **no hay contra qué medir**, y la Fase 6 completa queda sin sustento.

**Resolución (agosto 2026):** el **nivel de regla de Wazuh** se adopta como método tradicional de referencia. Es literalmente el enfoque basado en reglas y firmas que el plan quiere como comparación, y viene incluido con la fuente de alertas. Si más adelante hay acceso al sistema de la empresa, su severidad se añade como segundo baseline.

---

### I-4 · La identidad del módulo propietario depende de la empresa — ESTRUCTURAL

~~La Fase 1 está vacía~~ **Ya no.** La Fase 1 se ejecutó **por modelado** (cliente genérico y caso de uso acotado), del mismo modo que I-1 se resolvió supliendo la fuente de alertas con Wazuh. Sus salidas —perímetro, clases, criticidad, política de continuidad— existen y las fases 3, 4 y 5 ya las consumen.

Lo único que **sigue abierto**, y solo lo puede resolver la empresa: **¿son la misma cosa «el módulo propietario» del plan y «el sistema existente que emite logs»?** No cambia el avance del prototipo —el diseño está aislado tras el módulo de ingesta—, pero sí afinaría el análisis si el sistema real llega.

**Quién puede resolverlo:** la empresa.

---

### I-5 · El estado del arte no apunta a donde va el proyecto — ESTRUCTURAL

[mdr-xdr.md](../02-fase2-estado-del-arte/mdr-xdr.md) y [limitacionesDeXDR.md](../02-fase2-estado-del-arte/limitacionesDeXDR.md) analizan plataformas XDR/MDR empresariales, operación de SOC y fatiga de alertas, con foco en PYMEs. El proyecto derivó a **seguridad de la red de un cliente**, desde el punto de entrega hacia dentro, que es otro mercado y otra superficie.

Los requisitos funcionales y no funcionales de la Fase 2 se derivaron del primer contexto. **No están necesariamente mal: están sin verificar** contra el segundo.

**Quién puede resolverlo:** nosotros, con una revisión acotada de los RF/RNF.

---

### I-6 · El Perfil A contradice el diseño del flujo — ~~DE DISEÑO~~ **RESUELTA** (forma; calidad en el hardware objetivo)

Dos choques directos entre [selección del modelo](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) y el [flujo de operación](../04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md):

- **Validación humana sin justificación.** El flujo establece: motor de triaje decide → justificación → validación humana → ejecución. Pero el Perfil A genera la justificación **en lote y fuera de línea**, así que el validador humano decidiría sin tener delante el razonamiento que debía darle criterio.
- **«Punta a punta» imposible.** El criterio de cierre de la Fase 3 lo exige; el Perfil A prohíbe tener sandbox y modelo vivos a la vez.

**Resolución (agosto 2026):** se añade al Perfil A un **tercer componente de 3B cuantizado** (Phi-4-mini o Llama 3.2 3B, ~2 GB) que redacta una justificación breve en 15–20 s, disponible para la validación humana. El 8B en lote queda para la justificación extensa de auditoría y evaluación. El camino interactivo —alerta, clasificación, justificación breve, validación, acción— **sí es demostrable en vivo** en el equipo actual, así que el criterio de cierre de la Fase 3 se sostiene sin reescribirse.

**Actualización (02/09/2026) — la resolución ya no se sostiene tal cual.** La medición propia en la
máquina de desarrollo dio **~3,7 tokens/s en CPU**, no los 10–12 t/s que suponía la resolución. Con
ese rendimiento el 3B interactivo no cabe en el presupuesto de latencia, así que la Fase 5C bajó a un
**Llama-3.2-1B** con justificación breve. Consecuencia en dos planos:

- **En forma, I-6 sigue resuelta:** el validador humano **sí tiene una justificación delante** en el
  momento de decidir; el lazo en vivo está demostrado.
- **En calidad, I-6 se reabre:** la evaluación de la Fase 6 midió que las justificaciones del 1B
  **anclan al 100 % pero son semánticamente poco fiables** (describen la regla y la técnica MITRE al
  revés). Un validador humano que se apoye en ellas recibe un texto que cita los campos correctos y
  los explica mal. El problema que I-6 atacaba —decidir sin criterio— **no está del todo cerrado**.

**Actualización (10/09/2026) — resuelta en calidad en el hardware objetivo.** Con el generador como
**servidor residente** y un modelo generalista de 8B (`llama-3.1-8b-instruct-q4`) en la máquina objetivo
(9800X3D + RTX 5070), la campaña de evaluación midió **18/18 justificaciones ancladas, 0 degradadas y
0 contradicciones con la decisión del motor** (`llm-4`, con RAG cuya consulta y corpus dependen de la
clase decidida; ver [resultados](../../evaluacion/resultados/README.md#corridas-con-modelo-de-8b-10092026)).
Las 18 se leyeron una a una: los descartes citan el motivo real y las amenazas citan origen, activo y
servicio expuesto. El problema que I-6 atacaba —que el validador humano decida sin criterio— **queda
cerrado donde el sistema está pensado para operar**. Dos matices que se mantienen:

- En hardware **sin GPU** (la máquina de desarrollo) el 1B sigue siendo poco fiable: ahí la calidad no
  está resuelta, y la vía honesta es la plantilla determinista (`--sin-llm`).
- La lectura de las 18 la hizo quien construyó el sistema; la **revisión manual independiente** de las
  justificaciones (`evaluacion/resultados/revision-manual.csv`) sigue pendiente. Está preparada para
  entregarla a alguien ajeno al proyecto, junto con una hoja ciega de 24 decisiones escaladas al humano
  (`revision-escalados.csv`), la [guía del revisor](../06-fase6-evaluacion-del-prototipo/guia-revision-independiente.md)
  y el puntuador (`python3 -m evaluacion.puntuar_revision`).

**Resuelto por:** nosotros, sustituyendo el generador por el 8B residente. La interfaz
`justificar_llm`/`adaptador` lo permitió **sin tocar el motor**, como estaba previsto; exigía GPU, que es
lo que aportó la máquina objetivo (pregunta 7 de la §5).

---

### I-7 · Tensión de alcance gestionada, no resuelta — DE DISEÑO

El sandbox se encuadró como «entorno controlado de validación» para no tocar el alcance aprobado. Funciona sobre el papel, pero **el motor de triaje sigue decidiendo y ejecutando acciones**, que es respuesta automatizada — declarada trabajo futuro en el plan. Una lectura atenta desde coordinación podría objetarlo.

**Quién puede resolverlo:** coordinación, si se decide plantearlo abiertamente.

---

### I-8 · Material de referencia con premisa superada — MENOR

[symons.md](../archivo/symons.md) y [herramientas-auxiliares.md](../archivo/herramientas-auxiliares.md) llevan una nota de condicionalidad, pero su contenido interno —el stack Atomic Red Team → Sysmon → Sigma— sigue contradiciendo el diseño actual. Está señalado, no reescrito.

---

### I-9 · Dos planes de trabajo conviviendo — MENOR

[planDeTrabajo.md](../archivo/planDeTrabajo.md) (6 objetivos, objetivo 4 con la frase cortada) sigue junto a [planDeTrabajoActualizado.md](./planDeTrabajoActualizado.md) (7 objetivos). Riesgo de que alguien lea el equivocado.

---

### I-12 · El RAG del objetivo general nunca se diseñó ni se implementó — ~~BLOQUEANTE~~ **RESUELTA**

El **objetivo general oficial** del proyecto exige «un módulo de generación aumentada por recuperación
(RAG) ejecutado sobre un modelo desplegado de forma local». Detectado el 02/09/2026:

- La copia del plan en el repo (`planDeTrabajoActualizado.md`) **omitía** el objetivo general y no
  mencionaba RAG. **Sincronizada** con el oficial en esa misma fecha; el objetivo general con RAG ya
  consta.
- **Ningún requisito (RF/RNF), ningún documento de la Fase 4 y nada del código** cubren RAG. El
  justificador de la Fase 5C inyecta en el prompt la **postura del auditor** y la **criticidad del
  perfil** (enriquecimiento de contexto), pero eso **no es RAG**: no hay base de conocimiento, ni
  embeddings, ni recuperación.
- **Conexión con la Fase 6:** la evaluación midió que el justificador 1B *ancla al 100 % pero es
  semánticamente poco fiable* (describe la técnica MITRE y la regla de Wazuh al revés). RAG ataca
  exactamente ese fallo: recuperar la descripción real de la técnica/regla desde una base local y
  fundamentar la justificación.

**Resuelta (02/09/2026):** implementado como subproyecto **5D** (`prototipo/rag.py` + corpus curado en
`prototipo/corpus/`), detrás de la interfaz `justificar_llm`. Corpus de técnicas MITRE, reglas de Wazuh
y vulnerabilidades del lab; embeddings con `llama-embedding` del entorno conda de 5C; coseno en Python
puro. **Contraste medido** con RAG vs sin RAG sobre las 18 soportadas: RAG corrige la corrección
semántica de la justificación (de «la regla 5760 es un protocolo de seguridad» a «indica un ataque de
fuerza bruta SSH»), manteniendo el anclaje al 100 %. Ver [informe §5.bis](../06-fase6-evaluacion-del-prototipo/informe-evaluacion.md) y `prototipo/README.md §10`.

**Seguimiento (10/09/2026):** lo que entonces era trabajo futuro se hizo y se midió, en
[`evaluacion/resultados/README.md`](../../evaluacion/resultados/README.md) y `prototipo/README.md §10.quater`:
modelo de 8B servido de forma residente (campaña de 51 s en vez de 11 min); embedder dedicado **bge-m3**
(MRR 0.47 → 0.70, la ficha correcta siempre entre las 5 primeras; crecer el corpus ya no degrada la
recuperación); enunciado, consulta y corpus **dependientes de la clase decidida**, con tres fichas de
descarte, de modo que los falsos positivos reciben una justificación generada y correcta en lugar de la
plantilla (18/18 ancladas, **0 contradicciones** con el motor; la tasa pasó por 1.00 → 0.61 → 1.00 y el
mismo número significó cosas opuestas); reproducibilidad garantizada desactivando la caché de prefijos del
servidor (RNF-03); y el anclaje verifica también que las técnicas MITRE citadas sean las de la alerta.

**Segunda familia (11/09/2026):** dos campañas reales de reconocimiento (`campana-recon.sh`) llevan el
dataset a 440 alertas y la evaluación a 31 soportadas de dos familias. Hizo aflorar que el prototipo habría
bloqueado a su propio auditor (corregido por configuración del perfil), que la familia tiene que ir en el
enunciado del justificador, y que la explicación hereda las etiquetas MITRE de Wazuh (argumento medido para
una clase propia de reconocimiento, propuesta en el informe). Clasificación: precisión 1.000, FP 0.000
sobre 220. Detalle en `evaluacion/resultados/README.md`.

**Endurecimiento (11/09/2026):** traza encadenada por hash (`python3 -m prototipo.traza --verificar`;
detecta alteración, borrado, inserción y reorden; no el truncado final, que exige anclar el último hash
fuera) y conector de mínimo privilegio (usuario `triaje` con clave, host verificado, sudoers **generado
desde el catálogo**; `lab/scripts/aprovisionar-minimo-privilegio.sh`; verificado en vivo). Embedder
residente (`llm-server.sh --embedder`): justificación en el daemon 7.5 s → 2.8 s. Reversión desde la traza
(`python3 -m prototipo.revertir`, RF-18) y **guía de operación** en la Fase 7, validada con un ensayo
completo del modo tiempo real. **Escalada determinista por defecto** con el filtro del perfil en cada salto
(cierra la Fase 3 del plan de excelencia técnica), verificada en vivo con la topología de cortafuegos.
**Ancla de la traza en Wazuh** (`TRIAJE_ANCLA`): el truncado final ya se detecta; el verificador distingue
truncada / rehecha / alterada, los tres reproducidos en vivo. **Rotación de la clave del conector** todo o
nada (`rotar-clave-conector.sh`), verificada en vivo con su camino de aborto. **Tercera familia** (telnet,
`servicio_expuesto`): 466 alertas, 42 soportadas en evaluación; el prototipo mantiene 1.000/1.000/0.000 y el
baseline **pierde 7 amenazas** (exhaustividad 0.741): las conexiones en claro son nivel 3, bajo su umbral.
**Nivel 4 (clasificador entrenado):** campaña de casos donde las reglas fallan con verdad declarada por el
experimento (600 alertas, 106 soportadas en evaluación); las 5 reglas caen a exhaustividad 0.770; un árbol CART
redescubre las reglas y añade la de ráfaga; adoptada como sexta regla determinista → 1.000 / 0.978 / 0.009.

**Quién lo resuelve:** nosotros. Es la pieza que faltaba para que el prototipo cumpla su objetivo
general, no un extra.

---

### I-13 · El plan oficial omite el objetivo de implementar — ~~ESTRUCTURAL~~ **RESUELTA**

Detectado el 10/09/2026 al contrastar el informe final contra el **plan oficial firmado
CCT-002-2026** (el PDF de la raíz del repositorio). Ese documento lista **seis** objetivos
específicos y salta de *«Diseñar la arquitectura del sistema»* directamente a *«Evaluar el
prototipo»*: **no hay ningún objetivo que mande construirlo**, aunque toda la Fase 5 existe y es el
grueso del trabajo.

Dos consecuencias que conviene dejar escritas, porque un lector externo llegará a ellas solo:

- El archivo [`documentacion/archivo/planDeTrabajo.md`](../archivo/planDeTrabajo.md) —movido a
  `archivo/` por la incongruencia **I-9** como si fuera un borrador superado— es en realidad **el
  plan oficial**: mismos seis objetivos, misma frase cortada en el objetivo 4. Lo que I-9 trató como
  «el plan viejo» es el documento vigente ante la Universidad.
- [`planDeTrabajoActualizado.md`](./planDeTrabajoActualizado.md), con **siete** objetivos, es una
  ampliación interna no firmada.

**Resolución (10/09/2026):** es un **error de tipeo del documento oficial, no una decisión de
alcance**. Lo confirma el propio plan: su **cronograma de actividades sí incluye «Desarrollar el
prototipo (flujos, reglas e integración)»** en las semanas 8 a 15. La referencia válida para los
objetivos del proyecto son, por tanto, **los siete** de `planDeTrabajoActualizado.md`, y el informe
final de la Fase 7 los lista así. **No hay que alinear el informe con los seis del PDF firmado.**

**Recomendación operativa:** si el plan puede corregirse y volver a firmarse antes de la entrega,
mejor; si no, el informe ya explica la trazabilidad objetivo→fase, de modo que la diferencia queda
justificada ante el jurado.

---

## 4. Propuesta: Wazuh como generador de alertas del sandbox

Una sola decisión resuelve **I-1, I-2 e I-3** a la vez: desplegar **Wazuh dentro del sandbox**, con agentes en los nodos OpenWrt y Linux, un manager que correlaciona, y sus alertas como entrada del motor de triaje.

| Incongruencia | Cómo la resuelve |
|---------------|------------------|
| **I-1** — sin fuente de alertas | El motor de triaje pasa a tener entrada real, generada en el propio laboratorio |
| **I-2** — ground truth equivocado | Las alertas de Wazuh sobre nodos con vulnerabilidades conocidas **sí** se pueden etiquetar como VP/FP |
| **I-3** — sin baseline | El **nivel de regla de Wazuh es exactamente «el método tradicional basado en reglas y firmas»** contra el que el plan quiere comparar. El baseline sale gratis |

Encaja con lo ya escrito: el roadmap tiene la casilla «Evaluar si herramientas como Wazuh se usarán como base de ingestión», sin marcar, y [edr-xdr-mdr-telemetria.md](../04-fase4-diseno-de-arquitectura/edr-xdr-mdr-telemetria.md) ya lo encuadra como infraestructura y no como solución del prototipo. Solo falta **decidirlo y meterlo en la topología**, donde hoy no aparece.

**Coste:** RAM en un equipo que ya va justo. Habrá que comprobar si Wazuh y Greenbone pueden convivir o si también se separan en el tiempo, como el modelo. Ver el presupuesto de memoria en [selección del modelo §2](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md).

---

## 5. Preguntas para la empresa

Consolidadas. **Ninguna bloquea ya el avance** tras adoptar Wazuh como fuente de alertas y baseline, pero todas mejoran el resultado y deben plantearse en la reunión.

1. **¿Son la misma cosa «el módulo propietario» y «el sistema existente que emite logs»?** (I-4)
2. **¿Cuál es el formato exacto de salida de ese sistema?** Bloquea la especificación del módulo de ingesta.
3. **¿Qué severidad o clasificación asigna hoy?** Es el baseline de la Fase 6 (I-3).
4. **¿Tendremos acceso real a ese sistema y al playbook, o construimos un sustituto en el laboratorio?** (I-1)
5. **¿El playbook espera respuesta del motor de triaje, o es asíncrono?** Determina el presupuesto de latencia y si la validación humana en línea es viable.
6. **¿Existe ya un catálogo de acciones que el playbook sepa ejecutar?**
7. **¿Hay alguna máquina de laboratorio disponible?** Con 32 GB o una GPU dedicada, el Perfil B pasa a ser viable y el prototipo pierde un componente entero.

---

## 6. Estado de resolución

| # | Incongruencia | Severidad | Responsable | Estado |
|---|---------------|-----------|-------------|--------|
| I-1 | Sin fuente de alertas | Bloqueante | Nosotros | **Resuelta** — Wazuh en el sandbox |
| I-2 | Dos ground truths | Bloqueante | Nosotros | **Resuelta** — sandbox §6 reescrita |
| I-11 | Playbook sin sustituto en el laboratorio | Estructural | Nosotros | **Resuelta** — lo ocupa la ingesta (D10) |
| I-12 | RAG del objetivo general nunca diseñado ni implementado | Estructural | Nosotros | **Resuelta** — módulo RAG 5D implementado y su mejora medida (contraste con/sin RAG) |
| I-3 | Sin baseline | Bloqueante | Nosotros | **Resuelta** — nivel de regla de Wazuh |
| I-4 | Identidad del módulo propietario | Estructural | Empresa | **Parcial** — Fase 1 hecha por modelado; solo queda la pregunta de identidad, que depende de la empresa |
| I-5 | Estado del arte desalineado | Estructural | Nosotros | **Resuelta** — revisión de requisitos contra el contexto del cliente |
| I-6 | Perfil A vs flujo | De diseño | Nosotros | **Resuelta** — justificación en línea (forma) y, con el 8B residente + RAG en la máquina objetivo, 18/18 ancladas y 0 contradicciones (calidad). Sin GPU, el 1B sigue siendo poco fiable; revisión manual independiente pendiente |
| I-7 | Tensión de alcance | De diseño | Coordinación | Gestionada |
| I-8 | Material con premisa superada | Menor | Nosotros | **Resuelta** — movido a documentacion/archivo/ |
| I-9 | Dos planes conviviendo | Menor | Nosotros | **Resuelta con matiz** — el plan movido a `archivo/` resultó ser el oficial firmado; ver I-13 |
| I-13 | El plan oficial omite el objetivo de implementar | Estructural | Nosotros | **Resuelta** — es un error de tipeo del documento oficial; el cronograma sí incluye desarrollar el prototipo. Vale la lista de 7 objetivos |
| I-10 | El componente central se llamaba «EDR» siendo el motor de triaje de un XDR | De diseño | Nosotros | **Resuelta** — renombrado a «motor de triaje» |

## 7. Trabajo futuro y cabos sueltos conocidos

Lista **consolidada** de lo pendiente y de los límites conscientes (para la defensa: nada de esto es un
olvido, cada punto es una decisión). El detalle de cada uno vive donde se indica.

### Trabajo futuro (extendería el sistema)

- **Filtrado VP/FP dentro del nivel `triar_y_enrutar`.** El nivel enrutado clasifica y encamina sin adjudicar
  VP/FP; un WAF ruidoso se encamina igual. Detalle en el spec de familias (`docs/superpowers/specs/2026-09-16-taxonomia-familias-extensible-design.md`, §7).
- **Entrega real de la ruta.** La traza registra la ruta (`ruta`), pero ningún conector la **entrega** a la
  cola/equipo del cliente (correo/ticket). Es la misma capa de producción que el conector SSH.
- **Consumo automático del feedback (RF-12).** El «cosechador» que lee las reclasificaciones del periodo y
  propone cambios de perfil/corpus/reglas. Diseño en [bucle-de-feedback-rf12.md](bucle-de-feedback-rf12.md).
- **Calibración del umbral de escalado (RF-07).** `continuidad.umbral_confianza` sin calibrar (0,7 por
  defecto). Escalado por confianza en la campaña vigente: **0,067** (20/300, todas VP: las ráfagas desde el origen de
  administración, 6ª regla); el total es 0,297 porque el perfil retiene además el bloqueo de lo propio (D16). Falta el barrido del umbral (curva escalado ↔ errores de auto-bloqueo).
- **Segunda opinión del LLM en los casos grises (mejora B.1).** Que un LLM *proponga* una clase, con su
  razonamiento, cuando el determinista duda; decide el humano. Haría literal el objetivo 5, pero la
  [ablación de postura](../../evaluacion/resultados/README.md) mide **margen 0** con la configuración real y 2
  alertas irrecuperables sin postura (decisión D15). Si se implementa, el diseño de seguridad es obligatorio:
  (1) **solo informativa**, nunca cambia la acción por defecto; (2) la ráfaga va **en la pregunta**, no solo en
  los datos (el modelo explicaba como legítimo un origen de admin en ráfaga cuando no); (3) **aviso** si propone
  FP con ráfaga sobre el umbral; (4) salida **cerrada por esquema** a las clases válidas; (5) métrica principal:
  la **tasa de propuestas falso-negativas** (propone FP cuando es VP), no la exactitud. Exige el 8B.
- **Clases finas (6 categorías).** `vp_acceso_consumado` y `vp_exposicion_gestion` exigen etiquetas finas que
  el dataset no aporta — límite de datos, no pieza pendiente (ver Fase 5, arriba).

### Fuera de alcance por diseño (no se hará, y por qué)

- **Contención lateral / este-oeste y, en general, cualquier capacidad que exija *detección primaria*
  nueva** (malware/C2, DoS, MITM/ARP). El MDR **no genera la detección primaria** (la alerta desde
  telemetría cruda: eso es del SIEM); **la refina**: detecta cuáles de esas alertas son amenazas reales
  (FP 0,296→0,000; exhaustividad 0,741→1,000 frente al nivel de regla de Wazuh). Detalle y defensa en
  [caso-de-uso-acotado.md §11](../01-fase1-analisis-del-modulo/caso-de-uso-acotado.md#11-límites-conocidos-de-este-perímetro).
- **Descubrimiento automático del inventario y uso en tiempo real (Nivel 3 de la conciencia de impacto).**
  Descubrir dependencias (NetFlow/IPFIX, service mesh, trazas de aplicación), integrar una CMDB/ITSM, medir
  cuántos usuarios usan un servicio en este momento o descubrir la función de un activo exige telemetría que
  el prototipo no tiene, y es la integración multicapa en producción que el plan excluye. El inventario es un
  dato del perfil: una fuente automática lo podría alimentar sin tocar el motor. Límites que esto deja: el
  radio de impacto es una **cota superior** (un puerto abierto no implica uso) y una IP interna no
  inventariada y fuera de `redes_internas` resuelve a desconocido; una dependencia no declarada da un falso
  "sin cascada" (el radio en cascada solo ve lo que el perfil declara). Detalle en el
  [spec](../../docs/superpowers/specs/2026-09-21-conciencia-de-impacto-design.md) §8–§9.

### Menores (cosméticos)

- **Caché de `familias.py`.** `registro()` solo cachea desde la ruta por defecto; `cargar_registro(otra_ruta)`
  no se refleja. Sin impacto (el camino productivo usa el registro por defecto; `clasificar` acepta `registro=`).
- **`lab/dataset/etiquetar.py`** lista `explotacion_conocida` como familia soportada: es correcto (su VP/FP es
  el ground truth), y ya lleva una nota de coherencia con el nivel enrutado del producto.
