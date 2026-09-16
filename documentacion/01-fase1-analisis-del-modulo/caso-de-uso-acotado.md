# Caso de uso acotado

Define el **perímetro del prototipo**: qué alertas entra a triar, cuáles marca como no soportadas,
con qué categorías las clasifica, sobre qué activos actúa y bajo qué condición puede actuar.

Se deriva del [modelo de cliente genérico](./modelo-de-cliente-generico.md) y es el entregable que
las fases 4, 5 y 6 consumen: el catálogo de acciones lo respeta, la implementación lo codifica y la
evaluación mide dentro de él.

---

## 1. El enunciado

> **Acceso no autorizado a servicios de gestión expuestos en la red del cliente.**

Todo lo que el prototipo clasifica, prioriza, justifica y responde cae dentro de esa frase. Lo que
no cae dentro, no se clasifica: se marca.

---

## 2. Por qué se acota por familia de alerta

La alternativa natural era acotar por activo — «todo lo que apunte al enrutador de borde». Se
descarta por tres razones, en orden de peso:

**Porque la superficie de gestión está en todas las capas.** El [modelo](./modelo-de-cliente-generico.md#2-la-infraestructura-de-red-de-una-empresa-cualquiera)
muestra que borde, cortafuegos, conmutación, DMZ, servidores internos e IoT exponen todos alguna
forma de administración remota. Un perímetro por activo dejaría fuera la misma amenaza solo por
llegar a otro equipo.

**Porque el prototipo debe reconocer un patrón, no una dirección.** Un intento de acceso por fuerza
bruta se parece a sí mismo en un switch y en un servidor de ficheros. Aprender «lo que le pasa al
borde» es aprender el activo; aprender «acceso no autorizado a gestión» es aprender el fenómeno, y
generaliza a los equipos que el cliente tenga.

**Porque hace el perímetro independiente del laboratorio.** Acotar por activo ataba la evaluación a
tener un equipo de borde con firmware real, hoy bloqueado. Acotado por familia, la misma superficie
la ejercita cualquier nodo con un servicio de gestión expuesto.

---

## 3. Dentro del perímetro

| Familia | Señal típica en la alerta | Por qué entra |
|---------|---------------------------|---------------|
| **Fuerza bruta contra un servicio de gestión** | Ráfaga de autenticaciones fallidas contra SSH, Telnet, RDP o un panel web de administración | Es el intento de acceso no autorizado en su forma más directa |
| **Acceso con credencial por defecto o débil** | Autenticación **correcta** con un usuario de fábrica o de una lista conocida | El caso peligroso: no hay fallo que contar, el acceso simplemente funciona |
| **Servicio de gestión alcanzable desde donde no debería** | Administración accesible desde el exterior, desde la red de invitados o entre segmentos que no deberían verse | No es un ataque: es la exposición que lo hace posible. Entra porque es la causa |
| **Protocolo de administración inseguro en uso** | Telnet, HTTP sin cifrar o SNMP con comunidad por defecto transportando administración real | Credenciales en claro; convierte cualquier posición en la red en acceso |
| **Sesión administrativa anómala** | Acceso correcto pero fuera de horario, desde un origen inhabitual o hacia un equipo que ese usuario no administra | Cubre el acceso ya consumado, que las tres anteriores no ven |

Las cinco comparten una propiedad que las hace tratables juntas: **el activo afectado tiene una
postura comprobable**. El auditor puede responder si ese servicio de gestión está realmente
expuesto, y esa respuesta es lo que separa un verdadero positivo de un falso positivo.

---

## 4. Fuera del perímetro

| Queda fuera | Motivo |
|-------------|--------|
| Malware y actividad de endpoint | Otra telemetría, otra respuesta, otro tipo de producto |
| Exfiltración de datos | Exige análisis de contenido y de volumen sostenido, no de eventos de acceso |
| Denegación de servicio | La respuesta es de capacidad y de red, no de triaje de acceso |
| Phishing, correo e identidad | El vector no pasa por los servicios de gestión |
| Vulnerabilidades de aplicación | El código de lo que corre en los servidores no se analiza |
| Alertas de la nube y de SaaS | Fuera del modelo de infraestructura: el modelo se detiene en el perímetro |

Nada de esto se descarta por poco importante. Se descarta porque **el prototipo no tendría con qué
fundamentar una decisión**: no hay postura del activo que contrastar, y el sistema acabaría
emitiendo clasificaciones que no puede justificar. Eso es exactamente lo que viene a corregir.

---

## 5. La regla de «no soportada»

Toda alerta que no encaje en una de las cinco familias de la §3 recibe la clase **no soportada** y
pasa a la cola manual **con su severidad de origen intacta**.

No soportada **no significa descartada, ni benigna, ni de baja prioridad**. Significa: *este sistema
no tiene criterio fundado sobre esta alerta*. Una alerta grave fuera del perímetro sigue siendo
grave; simplemente la juzga una persona.

Es la aplicación directa de una limitación que el sistema actual del cliente no tiene: **decir que
no se sabe**. Un sistema que clasifica todo lo que le llega miente en los bordes de su competencia,
y el analista no puede distinguir dónde empieza la invención.

---

## 6. Categorías de clasificación

Lo que el motor de triaje devuelve para cada alerta:

| Clase | Cuándo | Qué implica |
|-------|--------|-------------|
| **VP · acceso consumado** | Autenticación correcta no legítima, o sesión administrativa anómala confirmada | Máxima prioridad. Hay alguien dentro |
| **VP · intento de acceso** | Fuerza bruta o sondeo contra un servicio de gestión que **existe y está expuesto** | Prioridad alta si el servicio es alcanzable desde fuera |
| **VP · exposición de gestión** | El servicio no debería ser alcanzable desde donde lo es. Sin ataque asociado todavía | Es una corrección de configuración, no un incidente |
| **FP · actividad administrativa legítima** | El patrón coincide, pero el origen, el horario y el usuario corresponden a administración normal | El falso positivo dominante en este dominio |
| **FP · exposición inexistente** | La alerta señala una superficie que el inventario del activo dice que no está presente | El falso positivo que el contexto de postura elimina — la brecha [L1](./modelo-de-cliente-generico.md#51-del-sistema-base--lo-que-el-prototipo-viene-a-cubrir) del sistema base |
| **No soportada** | Fuera de las cinco familias | A cola manual, severidad intacta |

**FP · actividad administrativa legítima** merece atención especial. Un administrador que se
equivoca tres veces de contraseña produce la misma señal que un ataque, y es la causa más común de
ruido en este dominio. Distinguirlo exige exactamente lo que el sistema base no tiene: contexto del
activo, del origen y del momento.

### Los tres niveles de respuesta y el registro de familias

La familia de una alerta determina no sólo su clase sino **qué hace el motor con ella**, según el
registro extensible `prototipo/familias.yml` (familia → técnica MITRE + nivel):

- **actuar** — el motor clasifica VP/FP y propone contención del catálogo cerrado. Las familias de
  plano de gestión (`acceso_credenciales`, `reconocimiento`, `servicio_expuesto`).
- **triar_y_enrutar** — el motor clasifica, prioriza y **encamina** a un equipo con contexto MITRE,
  **sin** contener automáticamente (p. ej. `explotacion_conocida` → AppSec). Para amenazas que no
  deben auto-contenerse (romperían el servicio) pero sí triarse.
- **no soportada** — familia ausente del registro: a cola manual con su severidad.

Añadir una familia = una línea en el registro. La cobertura real por cliente es *registro ∩ lo que
detecta su SIEM*. **Fuera de alcance conocido** (hoy → no soportada, por decisión, no por olvido):
malware/C2, movimiento lateral, manipulación de red (MITM/ARP), DoS, y fraude de pagos/ATM.

---

## 7. Criticidad de los activos

La prioridad no sale solo de la clase: sale de la clase **por** lo que cuelga del activo. Derivada
de las capas del modelo:

| Criticidad | Activos | Razón |
|------------|---------|-------|
| **Crítica** | Borde, cortafuegos, núcleo de conmutación, directorio, plano de gestión | Su compromiso o su caída arrastra a todo lo demás |
| **Alta** | DMZ y servicios publicados, servidores de datos y copias de seguridad, hipervisores | Lo ve el cliente del cliente, o contiene lo que hay que proteger |
| **Media** | Conmutación de acceso, controladoras WiFi, servidores departamentales | Afecta a un segmento o a un área |
| **Baja** | Puestos, impresoras, red de invitados | Afecta a personas concretas |

La excepción declarada: **IoT y OT no tienen criticidad fija**. Una cámara es baja; un
controlador industrial en línea de producción es crítico. Es un valor que el cliente aporta, no que
el prototipo deduzca — es parte del punto de variabilidad [V4](./modelo-de-cliente-generico.md#6-puntos-de-variabilidad).

---

## 8. Respuestas aplicables

El prototipo no ejecuta comandos: **emite una intención de respuesta**, que el conector traduce. En
este perímetro, tres niveles por impacto:

| Nivel | Intención | Efecto sobre el servicio |
|-------|-----------|--------------------------|
| **Observación** | Recoger conexiones, sesiones, configuración o servicios a la escucha del activo | Ninguno |
| **Contención localizada** | Bloquear un origen concreto, cerrar una sesión concreta | Afecta al atacante, no al servicio |
| **Reducción de superficie** | Cerrar o restringir el servicio de gestión expuesto, invalidar una credencial, aislar el activo | **Afecta al servicio.** Puede dejar el equipo sin administrar |

El repertorio concreto y sus comandos son la Fase 4
([catálogo de acciones](../04-fase4-diseno-de-arquitectura/catalogo-de-acciones.md)). Lo que fija
esta fase es que **toda respuesta debe caer en uno de estos tres niveles y llevar su nivel
declarado**, porque de ahí sale la regla de la sección siguiente.

---

## 9. La política de continuidad

La restricción [C1](./modelo-de-cliente-generico.md#52-operativas-del-cliente--lo-que-el-prototipo-debe-respetar) del modelo —*los servicios no se detienen*— deja de ser un principio y pasa a ser
una regla que decide, alerta a alerta, si una acción se ejecuta sola o espera a una persona:

| Impacto de la respuesta | ¿Reversible? | Decisión |
|-------------------------|--------------|----------|
| Ninguno (observación) | — | **Automática** |
| Localizado en el origen del ataque | Sí | **Automática** si la confianza supera el umbral |
| Alcanza a un servicio que el cliente presta | Sí | **Humano, siempre** |
| Cualquiera | **No** | **Humano, siempre** |

Dos consecuencias que no son negociables:

- **La irreversibilidad manda sobre el impacto.** Una acción irreversible pasa por una persona
  aunque parezca inocua, porque [C3](./modelo-de-cliente-generico.md#52-operativas-del-cliente--lo-que-el-prototipo-debe-respetar) —sin manos en el equipo— convierte cualquier error en una visita
  técnica.
- **Ninguna respuesta puede cortar el plano de gestión** del activo sobre el que actúa. Es
  precondición, no criterio de escalado: una acción que deja el equipo inalcanzable impide la
  siguiente respuesta y la propia verificación ([C6](./modelo-de-cliente-generico.md#52-operativas-del-cliente--lo-que-el-prototipo-debe-respetar)).

> **A verificar en la Fase 4.** Al aplicar esta regla al catálogo actual, dos entradas pueden
> quedar mal clasificadas: `BLOQUEAR_PUERTO`, hoy automática, puede tumbar un servicio si el puerto
> cerrado es de producción y no solo de gestión; y `LIMITAR_BANDA` figura como «según umbral» sin
> umbral escrito. Se señala aquí; corregirlo es trabajo de la Fase 4, no de esta.

---

## 10. Cómo se comprueba que se respetó

La continuidad no se declara: se mide. Además de las métricas de clasificación, la Fase 6 registra
dos que solo tienen sentido en este perímetro:

- **Acciones disruptivas indebidas** — respuestas de impacto sobre el servicio que se habrían
  ejecutado a partir de una alerta que era falso positivo. Es el daño que el prototipo habría
  causado.
- **Retención correcta** — de esas respuestas, cuántas quedaron efectivamente retenidas por la
  validación humana. Mide si la regla de la §9 funciona.

La razón de medirlas: **un triaje con buen F1 que corta el servicio del cliente es peor que el
sistema al que sustituye.** Sin estas dos métricas, el informe final no podría demostrar lo
contrario.

Requiere que cada respuesta lleve su nivel de impacto declarado en la traza. Es un añadido pequeño
al [plan de métricas](../04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md) y al contrato de
la orden de acción, pendiente de aplicar.

---

## 11. Límites conocidos de este perímetro

- **Depende de que el auditor sepa responder.** La distinción entre VP y FP se apoya en la postura
  del activo. Donde el auditor no llega, la clasificación pierde su fundamento y debe degradar a
  baja confianza en vez de suponer.
- **La sesión administrativa anómala es la familia más difícil.** Requiere una noción de
  normalidad —horarios, orígenes, quién administra qué— que un cliente nuevo no tiene el primer
  día. Es la última en dar resultados útiles.
- **No cubre el compromiso ya persistente.** Si el acceso no autorizado ocurrió antes de que el
  sistema estuviera en marcha, no hay evento de acceso que triar.
- **El MDR tría lo detectado; no detecta.** El sistema es la capa de **triaje y respuesta aguas
  abajo** del SIEM del cliente: solo actúa sobre alertas que el SIEM ya generó. Cualquier capacidad
  que exija *detectar* (en vez de triar lo detectado) queda fuera por diseño. Caso concreto: la
  **contención lateral / este-oeste** (aislar a un atacante interno que pivota entre segmentos hacia
  activos críticos) se estudió y **se descartó del alcance** porque presupone dos cosas ajenas al
  MDR: (1) **detección este-oeste** —telemetría interna: NetFlow, EDR, IDS interno— que es del SIEM
  y del cliente; y (2) **puntos de aplicación internos** —switches gestionables/NAC más la
  resolución de identidad en capa 2 (IP→puerto→endpoint) y sus conectores— que es infraestructura y
  producción. En consecuencia, el movimiento lateral se trata **honestamente**: si el SIEM no manda
  la alerta, el MDR no la ve; si la manda, cae en `no soportada` o se **encamina** (nivel
  `triar_y_enrutar`) a NetEng/SOC con su contexto MITRE, sin fingir una contención que el sistema no
  posee. Mismo techo comparten malware/C2 y DoS.
- **El perímetro es del prototipo, no del riesgo del cliente.** Que una alerta quede fuera no
  significa que la empresa esté cubierta en ese frente.

---

## Documentos relacionados

- [Modelo de cliente genérico](./modelo-de-cliente-generico.md) — de dónde salen las capas, las limitaciones y los puntos de variabilidad.
- [Catálogo de acciones](../04-fase4-diseno-de-arquitectura/catalogo-de-acciones.md) · [Métricas y evaluación](../04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md)
- [Requisitos](../02-fase2-estado-del-arte/requisitos.md) — RF-03 (clasificar), RF-10 (marcar no soportada), RF-08 (validación humana), RF-17 a RF-20 (continuidad).
