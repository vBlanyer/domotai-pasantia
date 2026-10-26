# Manual del analista — consola web del MDR

**Para quién es.** Para el analista de seguridad (SOC) que trabaja con el sistema ya en marcha:
cómo leer lo que el MDR decide, aprobar o corregir una respuesta, seguir un incidente y llevar su
caso. **No** cubre instalar ni desplegar el sistema — eso está en
[`guia-de-operacion.md`](guia-de-operacion.md) (administrador) y en [`RUNBOOK.md`](../../RUNBOOK.md).

**Qué es esta consola.** Una pantalla web (solo accesible en el propio equipo de gestión,
`http://127.0.0.1:8787`) donde el MDR muestra, en vivo, las alertas que ya **refinó** del SIEM del
cliente: cuáles son amenazas reales, qué respuesta propone y con qué consecuencia. **La decisión de
ejecutar una contención que roza un servicio la tomas tú**: el sistema propone, tú apruebas.

**Idea clave que conviene tener presente.** El MDR **no detecta** (eso es el SIEM); **refina** su
telemetría. Y la acción contra un activo **nunca** la decide el modelo de lenguaje: la propone una
política determinista y la filtra el perfil del cliente (permite / degrada / veta). El LLM solo
**explica**. Lo que no encaja en su alcance se marca con honestidad («no soportada»), no se inventa.

---

## 1. Las vistas de un vistazo

| Vista | Qué ves | Cuándo la usas |
|-------|---------|----------------|
| **Panel** | Estado general y actividad reciente | Para orientarte al llegar |
| **Métricas e informe** | Cifras (FP, escalado, MTTR), matriz ATT&CK, informe exportable a PDF por periodo | Revisión, reporte a coordinación |
| **Estado de servicios** | Salud de los servicios del cliente | Ver si algo del cliente está caído |
| **Red** | Mapa de la red del cliente con la actividad | Ubicar de dónde viene un ataque |
| **Decisiones** | Historial de decisiones (filtrable) | Buscar/repasar una decisión; abrir su incidente |
| **Aprobaciones** | **La cola de lo que espera tu decisión** | Tu trabajo principal (§3) |
| **Consola** | El registro vivo del daemon: incidentes, bloqueos con su comando SSH, verificaciones, reversiones y avisos (filtrable, auto-scroll, últimas 1.000 líneas) | Ver en directo cómo el sistema interactúa con la red; lo mismo que narra su terminal |
| **Contenciones activas** | Lo que está bloqueado ahora + *kill switch* | Revertir, pausar la automatización |
| **Trazas** | El registro auditable encadenado | Auditoría, verificar integridad |

El **distintivo ámbar** sobre «Aprobaciones» (y el número en la pestaña del navegador) te dice
cuántas decisiones esperan.

---

## 2. Antes de empezar: identifícate

- En la cabecera, el campo **token** solo hace falta si la consola exige autenticación (si está en
  blanco y funciona, no hace falta).
- En **Aprobaciones**, arriba, escribe tu **nombre de operador**. Queda en la traza: cada veredicto
  que apruebes lleva tu nombre (**no repudio**). Si cada analista tiene su token, el nombre sale del
  token automáticamente.
- El icono de **campana** 🔔 en la cabecera activa los **avisos**: cuando llega una decisión nueva,
  el navegador te lo notifica (aunque estés en otra pestaña) con un aviso y un sonido corto. Al
  activarlo el navegador te pedirá permiso una vez. Todo se queda en tu equipo; no sale nada fuera.

---

## 3. El flujo principal: resolver la cola de Aprobaciones

Cada tarjeta de **Aprobaciones** es una decisión que el MDR retiene para ti (porque la acción toca
un servicio, un activo propio, o es de las que nunca se automatizan).

### 3.1 Leer la tarjeta
- **Clase** y **severidad (P1–P4)**: qué amenaza es y su gravedad.
- **Origen / Activo / Servicio**: quién ataca y a qué.
- **Pendiente desde hace X**: cuánto lleva esperando (si pasa de 5 min se resalta en rojo — tu SLA).
- **«sigue atacando · +N»**: llegaron N repeticiones mientras esperaba (la misma amenaza insiste).
- **Consecuencia**: a quién bloquea y qué servicios detiene la acción propuesta. Si aparece
  **⚠ en cascada**, bloquear ese origen dejaría sin servicio a los activos que dependen de él.
- **Recomendado**: la respuesta dirigida que el triaje sugiere valorar (asesora; no es obligatoria).

### 3.2 Decidir
Tres botones (y un submenú al reclasificar):

| Acción | Qué hace |
|--------|----------|
| **Aprobar** | Ejecuta la acción propuesta (contención). Si hay cascada, pide una confirmación extra. |
| **Rechazar** | Retiene sin ejecutar nada. La amenaza queda registrada, pero no se contiene. |
| **Reclasificar** | La clase estaba mal: eliges la correcta de una lista cerrada. No ejecuta la acción; queda como corrección (feedback). |

Si apruebas y la víctima no responde, el sistema **escala** la contención a su cortafuegos de borde
y te presenta ESE salto como una tarjeta nueva para que lo apruebes también (nunca se aplica solo).

### 3.3 Seguir el incidente (vista Incidente)
Desde **Decisiones**, abre una decisión para ver su **Incidente**: el grafo del ataque sobre el mapa
de la red (origen → activo → cascada), el detalle (severidad, acción, desenlace), la técnica
**MITRE ATT&CK** y el hash de la traza.

### 3.4 Llevar el caso
En la misma vista de Incidente, el **panel «Caso»** te deja gestionarlo como en un SOC:
- **Estado**: nuevo → en revisión → resuelto (o reabrir).
- **Responsable**: a quién se asigna.
- **Notas**: lo que observas o concluyes.

Cada cambio queda **encadenado en la traza** con tu nombre y la hora (no se puede falsear ni borrar
el historial del caso).

---

## 4. Contención en marcha y marcha atrás

- **Contenciones activas** lista lo que está bloqueado ahora mismo y te deja **revertir** una
  contención (deshace la regla en el equipo y lo registra).
- **Kill switch / pausa**: el botón de pausa detiene toda la automatización — a partir de ahí, *toda*
  contención espera tu aprobación. Útil ante un comportamiento raro. Hay también un **des-bloqueo en
  masa** para revertir todo de golpe. Cuando la automatización está en pausa, lo ves en una banda
  arriba de cualquier pantalla.

---

## 5. Panorama y reporte

- **Métricas e informe**: elige el periodo (en vivo / mes / año / rango) y mira FP, tasa de escalado,
  tiempo medio de respuesta (MTTR) y la **matriz ATT&CK** (qué técnicas cubre el MDR). Desde ahí
  **exportas un informe a PDF** del periodo.
- **Red**: el mapa del cliente; desde un equipo puedes saltar a sus decisiones.

---

## 6. Trazas y auditoría

**Trazas** muestra el registro encadenado por hash (cada decisión, veredicto, reversión y cambio de
caso). Sirve para auditar: el Panel indica si la **cadena está íntegra**. Una decisión se puede
**re-derivar** exactamente a partir de su traza (ver `guia-de-operacion.md` §7).

---

## 7. Qué NO esperar de la consola (límites honestos)

- **No es un EDR/antivirus de endpoint ni un SIEM**: no ve procesos ni genera la alerta original;
  **refina** lo que el SIEM del cliente ya detecta.
- Lo que cae fuera de las familias soportadas se marca **«no soportada»** (o se escala a tu revisión
  si es grave): el sistema prefiere decir «esto no lo triajo» a inventar una respuesta.
- Lo que el SIEM **no detecta** (p. ej. C2 cifrado por comportamiento), el MDR tampoco lo ve: es
  trabajo de otra capa de la defensa en profundidad.

---

## 8. Problemas comunes

| Síntoma | Qué pasa / qué hacer |
|---------|----------------------|
| «sin conexión con el daemon» | El servicio no está en marcha o no es accesible. Avisa al administrador (`guia-de-operacion.md`). |
| La API responde «no autorizado» | Falta el **token** en la cabecera (la consola exige autenticación). |
| «No se aplicó el veredicto» | La tarjeta ya no estaba vigente (la resolvió otro, o cambió el menú). Vuelve a mirar la cola. |
| No me llegan avisos | Activa la **campana** y acepta el permiso del navegador. Solo avisa de decisiones *nuevas*. |
| «Nada que aprobar» | No hay nada pendiente ahora mismo; aparecerá en cuanto una decisión necesite un humano. |
