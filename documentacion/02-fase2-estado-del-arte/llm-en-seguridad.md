# Modelos de lenguaje aplicados a la seguridad

El objetivo 2 del [plan de trabajo](../00-general/planDeTrabajoActualizado.md) pide analizar dos
cosas: las soluciones MDR/XDR del mercado **y las aplicaciones de modelos de lenguaje en el ámbito
de la ciberseguridad**. Lo primero está en [mdr-xdr.md](./mdr-xdr.md) y
[limitacionesDeXDR.md](./limitacionesDeXDR.md). Esto es lo segundo, junto con la comparación entre
enfoques basados en reglas y enfoques asistidos por IA que el [roadmap](../00-general/roadmap.md)
enumera como actividad de esta fase.

Importa porque **el proyecto entero apuesta por un modelo de lenguaje**. Elegir uno es trabajo de
la Fase 4; justificar que la apuesta es defendible —y conocer dónde falla— es trabajo de esta.

---

## 1. Tres formas de aplicar un modelo de lenguaje al triaje

No son alternativas de la misma familia: resuelven partes distintas del problema y se pueden
combinar.

| Enfoque | Qué hace | Coste | Dónde falla |
|---------|----------|-------|-------------|
| **Encoder clasificador** (BERT y derivados, ~100M parámetros, con ajuste fino) | Asigna una clase y una confianza numérica a cada alerta | Muy bajo: milisegundos en CPU | No explica nada. Necesita datos etiquetados. No generaliza fuera de lo que vio |
| **LLM generativo instruido** (varios miles de millones de parámetros) | Redacta el razonamiento, resume el incidente, mapea a técnicas conocidas | Alto: segundos y varios GB de memoria | No es fiable como clasificador numérico ni es determinista por defecto |
| **Modelo especializado de dominio** | Lo mismo, con vocabulario y conocimiento de seguridad preentrenado | Igual que el anterior | Sigue sin ser determinista; su ventaja es de vocabulario, no de garantías |

La conclusión que sostiene el diseño de este proyecto: **clasificar y justificar son tareas
distintas y conviene resolverlas con piezas distintas.** Un encoder da una clase estable, barata y
con confianza calibrable; un generativo da el texto que una persona necesita leer para decidir.
Pedirle las dos cosas al mismo componente es lo que produce puntuaciones inventadas con aspecto de
cálculo.

---

## 2. Modelos preentrenados sobre corpus de seguridad

La línea empezó con encoders: **SecureBERT** (2022) demostró que continuar el preentrenamiento de
un encoder general sobre corpus de ciberseguridad —informes de amenazas, bases de vulnerabilidades,
documentación técnica— mejora las tareas de clasificación del dominio frente al modelo genérico.
Le siguieron variantes equivalentes con distintos corpus.

En generativos, la referencia pública actual es **Foundation-Sec-8B** (Cisco Foundation AI), un
Llama-3.1-8B con preentrenamiento continuado sobre corpus de seguridad, publicado con pesos
abiertos. Su variante instruida y su variante de razonamiento declaran explícitamente el **triaje y
el resumen de casos de SOC** como caso de uso objetivo. Es la que la Fase 4 selecciona; el detalle
y los perfiles de despliegue están en [selección del modelo](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md).

**Lo que la especialización aporta y lo que no.** Aporta vocabulario: el modelo reconoce un CVE, una
técnica ATT&CK o un nombre de familia de malware sin que haya que explicárselo, y eso reduce la
longitud del prompt y la tasa de confusión terminológica. **No aporta garantías**: un modelo
especializado sigue pudiendo afirmar con seguridad algo que no está en la alerta. La especialización
mejora el punto de partida, no elimina ninguno de los riesgos de la sección 4.

**Un desajuste que conviene tener presente.** Estos modelos se preentrenan sobre *prosa* —informes,
artículos, avisos—. La entrada de un sistema de triaje son **eventos estructurados**: campos, IPs,
marcas de tiempo, cadenas de log. Comparten vocabulario técnico pero no género textual, y esa
distancia es medible: comparar el modelo especializado contra uno genérico sobre las alertas reales
es un experimento barato y honesto para la Fase 6.

---

## 3. Qué está haciendo el mercado

Las plataformas líderes han incorporado asistentes basados en modelos de lenguaje: Microsoft
Security Copilot, CrowdStrike Charlotte AI, SentinelOne Purple AI, y las capacidades generativas
integradas en las operaciones de seguridad de Google Cloud. Sus alcances difieren, pero el patrón
es común y es lo relevante aquí:

- **Resumen y redacción**, no decisión. Explican el incidente, redactan el informe, traducen una
  consulta en lenguaje natural al lenguaje de búsqueda de la plataforma.
- **Enriquecimiento del contexto** antes de que el analista lo pida.
- **La autoridad final sigue siendo humana** en las decisiones que importan. Ninguno de los
  proveedores líderes vende hoy el veredicto autónomo como sustituto del analista.
- **Dependencia del ecosistema y de la nube del proveedor**, con el coste y el problema de
  privacidad que eso implica para una organización que no quiere que sus alertas salgan.

Dos lecturas para este proyecto. La primera, de validación: **el patrón «el modelo redacta, la
persona decide» es el estándar del mercado**, no una limitación autoimpuesta de este prototipo. La
segunda, de oportunidad: todos esos asistentes son servicios en la nube del proveedor. Un módulo
que haga lo mismo **en local, sobre hardware modesto y sin que la alerta salga de la red** ocupa un
hueco real, y es lo que fija RNF-01 y RNF-05.

---

## 4. Riesgos de poner un modelo de lenguaje en el camino de una alerta

Esta sección es la que más consecuencias tiene sobre el diseño, y la que más se omite en la
literatura de producto.

**Inyección de prompt desde campos controlados por el atacante.** Es el riesgo número uno del
catálogo OWASP para aplicaciones con LLM, y aquí **no es hipotético**: el contenido del log —el
nombre de usuario probado, el `user-agent`, la cadena completa del evento— lo escribe quien está
atacando. Si esos campos se concatenan al prompt sin distinguirlos de las instrucciones, el atacante
tiene un canal directo al modelo que decide sobre su propio ataque. La consecuencia de diseño es
inmediata: **los campos de la alerta son datos, nunca instrucciones**, y deben ir delimitados y
tratados como tales.

**Alucinación con apariencia de fundamento.** El fallo peligroso no es el error evidente, es la
justificación bien redactada que cita un detalle que la alerta no contiene. Un analista con prisa la
acepta precisamente porque suena a análisis. El contrapeso es exigir **anclaje verificable**: toda
afirmación de la justificación debe poder rastrearse a un campo concreto de la alerta o del
contexto, y eso es comprobable de forma automática.

**No determinismo.** La misma alerta puede producir dos justificaciones distintas en dos
ejecuciones. Para operar es incómodo; para **evaluar es descalificante**, porque hace que los
resultados de la Fase 6 no sean reproducibles. Se controla con temperatura baja, prompts
versionados y registro de la versión de modelo en cada ejecución.

**Corte de conocimiento.** El modelo no sabe nada publicado después de su entrenamiento: ni un CVE
reciente, ni una campaña nueva. Cualquier afirmación suya sobre el panorama actual de amenazas es
sospechosa por construcción. El conocimiento fresco tiene que entrar por el contexto —la postura que
devuelve el auditor—, no salir del modelo.

**Coste y latencia en local.** Ejecutar sin nube significa aceptar los límites del hardware
disponible. Es una restricción real de este proyecto y la razón de que existan dos perfiles de
despliegue.

**Superficie nueva.** Añadir un modelo añade un componente que puede fallar, colgarse o ser atacado.
De ahí la exigencia de degradación controlada: si el modelo no responde, la alerta va a cola manual
y **nunca se descarta en silencio**.

---

## 5. Reglas y firmas frente a análisis asistido por IA

La comparación que pide el roadmap. Conviene hacerla sin caricatura: el enfoque de reglas no es el
pasado que la IA viene a sustituir.

| | **Reglas y firmas** | **Análisis asistido por modelo** |
|---|---|---|
| **Decisión** | Determinista y repetible | Probabilístico; repetible solo si se fuerza |
| **Auditabilidad** | Total: se lee la regla que disparó | Indirecta: se lee la justificación, no el cálculo |
| **Coste de ejecución** | Muy bajo | De milisegundos (encoder) a segundos (generativo) |
| **Contexto del activo** | Ninguno: la regla no sabe si el equipo es vulnerable | Es su mejor aportación, si se le da el contexto |
| **Explicación** | Nombre de la regla | Razonamiento en lenguaje natural |
| **Generalización** | Nula: lo no previsto no dispara | Parcial: reconoce variantes de lo que ha visto |
| **Mantenimiento** | Alto y continuo: hay que escribir y afinar reglas | Del prompt y del conjunto etiquetado |
| **Fallo típico** | Falso positivo por falta de contexto | Afirmación segura y equivocada |

**No compiten: se apilan.** Las reglas son buenas detectando y malas decidiendo qué importa; el
modelo es malo detectando y bueno explicando y priorizando. El diseño sensato usa las reglas como
**fuente** y el modelo como **capa de triaje** sobre ellas — que es exactamente el flujo de este
proyecto: Wazuh detecta, el motor de triaje decide.

De ahí sale además la elección de baseline de la Fase 6. Comparar el prototipo contra el **nivel de
regla** no es comparar contra un rival débil: es comparar contra el método que hoy está en
producción en la mayoría de las organizaciones, y es la única comparación que responde a la pregunta
que el proyecto plantea — *¿aporta algo el triaje asistido sobre lo que ya hay?*

---

## 6. Criterios de diseño que se derivan de este análisis

Cada uno se convierte en requisito en [requisitos.md](./requisitos.md):

| Criterio | Por qué | Requisito |
|----------|---------|-----------|
| Separar clasificar de justificar | Son tareas distintas con piezas distintas (§1) | RF-03, RF-05 |
| Anclaje verificable de la justificación | Contra la alucinación con apariencia de fundamento (§4) | RNF-02 |
| Los campos de la alerta son datos, no instrucciones | Contra la inyección de prompt (§4) | RNF-08 |
| Confianza explícita y umbral de escalado | El modelo debe poder decir que no está seguro | RF-06, RF-07 |
| Prompts versionados y temperatura baja | Sin reproducibilidad no hay evaluación (§4) | RNF-03 |
| El conocimiento fresco entra por el contexto | Corte de conocimiento (§4) | RF-02 |
| Degradación a cola manual | El modelo es un componente que puede fallar (§4) | RNF-07, RNF-09 |
| Ejecución local | Privacidad y hueco de mercado (§3) | RNF-01 |
| Comparación obligatoria contra el baseline de reglas | Es la pregunta del proyecto (§5) | RF-14 |

---

## 7. Qué queda fuera de esta revisión

- **Ajuste fino de modelos generativos.** El proyecto usa el generativo como está y ajusta, si
  acaso, el encoder. Entrenar un generativo propio excede el alcance y el hardware.
- **Agentes autónomos con herramientas.** El motor de triaje decide una acción de un catálogo
  cerrado; no es un agente que planifica y encadena herramientas por su cuenta. La diferencia es
  deliberada y es lo que mantiene el sistema auditable.
- **Generación de reglas de detección.** Es otra aplicación legítima de los modelos de lenguaje en
  seguridad, pero no es el problema de este proyecto.

---

## Referencias

Enlaces verificados el **25/08/2026**.

| Fuente | Qué aporta | Enlace |
|--------|------------|--------|
| SecureBERT — *A Domain-Specific Language Model for Cybersecurity* (Aghaei et al., 2022) | Preentrenamiento continuado de encoders sobre corpus de seguridad | https://arxiv.org/abs/2204.02685 |
| Foundation-Sec-8B — Cisco Foundation AI | Modelo generativo abierto especializado en seguridad; declara el triaje de SOC como caso de uso | https://huggingface.co/fdtn-ai/Foundation-Sec-8B |
| OWASP Top 10 for LLM Applications | Catálogo de riesgos; LLM01 es la inyección de prompt | https://genai.owasp.org/llm-top-10/ |
| MITRE ATLAS | Panorama de amenazas contra sistemas de IA | https://atlas.mitre.org/ |
| NIST AI Risk Management Framework — Generative AI Profile (AI 600-1) | Marco de gestión de riesgo aplicable al componente de IA | https://www.nist.gov/itl/ai-risk-management-framework |
| MITRE ATT&CK | Taxonomía de técnicas usada en la justificación estructurada (RF-05) | https://attack.mitre.org/ |
| CyberSecEval / Purple Llama (Meta) | Evaluación de modelos en tareas y riesgos de seguridad | https://arxiv.org/abs/2312.04724 |
| *Lost in the Middle* (Liu et al., 2023) | Degradación del uso del contexto según su posición; relevante al construir el prompt | https://arxiv.org/abs/2307.03172 |
| Documentación de Wazuh | Reglas, niveles y formato de alerta de la fuente del laboratorio | https://documentation.wazuh.com/ |

**Sobre las capacidades de producto** citadas en la §3 (Security Copilot, Charlotte AI, Purple AI y
equivalentes): se describen a partir de la documentación pública de cada proveedor. El alcance de
estos productos cambia con frecuencia; **cualquier afirmación concreta debe reverificarse contra la
documentación del proveedor antes de incorporarla al informe final de la Fase 7.**

---

## Documentos relacionados

- [Requisitos del prototipo](./requisitos.md) — donde aterrizan los criterios de la §6.
- [Estado del arte MDR/XDR](./mdr-xdr.md) · [Limitaciones de XDR](./limitacionesDeXDR.md)
- [Selección del modelo](../04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) — la decisión concreta, que consume este análisis.
