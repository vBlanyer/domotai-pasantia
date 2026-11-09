# Plan: manejo de los fallos de contención sin malinterpretar un error real

> **Problema.** Cuando una contención falla, el MDR hoy no distingue *por qué*. «Equipo sin
> aprovisionar», «equipo inalcanzable», «sudo deniega la acción» y «alguien suplanta al equipo» salen
> igual: «NO verificada» y «el activo no respondió». Mejorarlo es delicado: algunas de esas causas son
> **configuración** (se arreglan en Conectividad) y otras pueden ser **un ataque** (el atacante corta el
> acceso del SOC, cambia la clave del host o deshace la contención). Si el MDR clasifica mal un ataque
> como «mala configuración», lo esconde.
>
> **Regla que manda en todo el plan:** *ante la duda, se trata como lo más grave*. La clasificación solo
> puede **añadir** información o **mandar a un humano**; nunca puede quitar una alerta, rebajar una
> gravedad, saltarse una escalada que hoy ocurre ni dar algo por contenido.
>
> Medido el 9 nov 2026 en el banco: 33 contenciones fallidas en una sesión, de 3 a 308 s cada una.

---

## 1. Lo que pasa hoy (hechos del código)

En `prototipo/servicio/lazo.py`, `aplicar_veredicto`:

1. `conector.ejecutar_orden` (`prototipo/accion/conector.py`) hace hasta **tres** SSH al equipo:
   - comprueba antes de actuar (si la regla ya está, no repite: idempotencia);
   - ejecuta el comando;
   - vuelve a comprobar.
2. `verificacion.confirmar` (`prototipo/accion/verificacion.py`) hace una **cuarta** comprobación.
3. Si no hubo éxito y verificación, y la acción es sobre el **origen** (bloquear IP, cortar conexión), se
   **escala** por la topología (`explicacion/agente_mitigacion.escalar_determinista`): en cada salto
   (fw-core, fw-edge) se repite la misma secuencia.
4. La traza guarda el código de salida y la salida en bruto. La consola (`servicio/stream.py`,
   `_lineas_ejecucion`) escribe «✗ NO verificada» y «⇪ el activo no respondió → …».

Consecuencias observadas:

| Síntoma | Causa |
|---|---|
| «NO verificada» aunque no se ejecutó nada | La verificación se informa siempre, también cuando ni se entró en el equipo |
| «→ None: None (fallido)» | La consola imprime el dispositivo de la escalada aunque la escalada falló |
| 16 a 70 s por contención en un equipo inalcanzable | Cuatro SSH que esperan cada uno a que expire la conexión, más dos saltos de escalada |
| 8 intentos en atm, sin clave del host fijada | El MDR no consulta lo que ya sabe Conectividad |
| 25 fallos seguidos en web-banking | No hay memoria de fallos: cada alerta vuelve a pagar el tiempo de espera |
| web-banking «verificada» en Conectividad mientras fallaba todo | Conectividad solo ve el botón Probar, no las contenciones reales |

El clasificador ya existe, pero solo lo usa el botón Probar: `conectividad.diagnosticar` en
`prototipo/accion/conectividad.py`.

---

## 2. Qué se mantiene igual (invariantes)

Cada fase tiene que demostrar que no rompe ninguna de estas reglas, con su prueba.

1. **Fail-closed.** Sin clave no se ejecuta nada; nunca se cae a la contraseña del laboratorio.
2. **Nunca se acepta sola una clave del host.** Cambiarla sigue exigiendo a un humano en Conectividad.
3. **Nunca «contenida» sin verificación positiva** en el equipo que ejecutó.
4. **La escalada al borde se mantiene** para las acciones sobre el origen en todos los fallos en los que
   hoy ocurre, salvo cuando sea *imposible* (el destino no está aprovisionado), y entonces va a un humano.
5. **No se corrige nada en los equipos de forma automática.** Ni aprovisionar, ni reinstalar el sudoers,
   ni reintentar con otra credencial.
6. **El motor no cambia sus decisiones.** Clase, acción propuesta, filtro, veto y automatización siguen
   igual: las cifras de la evaluación (63 pruebas, recall 1.0 / FP 0.009) no se mueven. Todo el plan vive
   en la ejecución, la escalada, la traza y la vista.
7. **«Verificada» en Conectividad solo la pone el botón Probar.** Las contenciones pueden **quitar**
   confianza (aviso), nunca darla.

---

## 3. Taxonomía de fallos

Cada fallo se clasifica con **evidencia inequívoca** (código de salida + texto), en el orden de la tabla:
la primera que encaja gana. Lo que no encaja en ninguna es **F10, desconocido**, y se trata como hoy.

«Regresión» = el equipo estaba **verificado** con la clave actual del conector y su clave del host
actual. La misma evidencia significa cosas distintas si el equipo nunca funcionó (configuración) o si
funcionaba y dejó de hacerlo (posible ataque).

| | Causa | Evidencia inequívoca | Qué puede ser | Respuesta |
|---|---|---|---|---|
| **F1** | Orden rechazada antes de salir | `rc = -1` con «nodo_ip rechazado» o «params rechazados» (en banda) | Alerta forjada o error del motor | Como hoy: fallida, sin escalada. Mensaje propio |
| **F3** | **Clave del host cambiada** | «REMOTE HOST IDENTIFICATION HAS CHANGED» | **Suplantación del equipo** o reinstalación | **Crítico.** No reintentar contra ese equipo. Escalar (acción sobre origen) y avisar en Aprobaciones: «el equipo presenta otra clave: posible suplantación». Nunca «configuración» |
| **F2** | Sin aprovisionar | «No … host key is known» o «Host key verification failed» **y** el equipo no tiene huella en el known_hosts | Equipo nuevo o nunca dado de alta | Configuración. Escalar si es sobre el origen; si no, al analista: «aprovisiona X en Conectividad» |
| **F4** | Sin credencial | «Permission denied (publickey» | Nunca aprovisionado, o **alguien quitó la clave del conector** | Sin regresión: configuración. **Con regresión: anomalía** («el equipo dejó de aceptar la clave del conector») |
| **F5** | Inalcanzable | `rc 255` con «timed out», «Connection refused», «No route to host», «Network is unreachable»; o `rc 124` | Equipo caído, red… **o el atacante cortó al SOC** (caso E1 del banco) | Escalar como hoy. **Con regresión: alerta** «el MDR perdió acceso a X» |
| **F9** | Conector sin configurar | `rc 126` del ejecutor que rechaza | Falta la clave del conector | Configuración del MDR: «genera la clave en Conectividad» |
| **F6** | sudo deniega | «a password is required», «not allowed to execute», «may not run sudo», el aviso de sudo («usual lecture») | Papel que no incluye la acción, binario ausente… **o sudoers cambiado** | Si la regla figura entre las que faltan en la última prueba vigente: «no ejecutable en este equipo» (configuración). Si no figura y el equipo estaba verificado: **deriva**, anomalía. Escalar como hoy |
| **F7** | La acción falla dentro del equipo | Se entró (sin los textos anteriores), `rc ≠ 0` de la ejecución | Error del comando | Como hoy, con la salida del comando como evidencia |
| **F8** | **Ejecutó pero no se verifica** | Ejecución `rc 0` y la verificación da negativo | **Alguien deshizo la contención**, o carrera | **Anomalía.** Escalar como hoy y avisar: «se aplicó y no está: posible contramedida». Nunca configuración |
| **F10** | Desconocido | Nada de lo anterior | — | **Exactamente como hoy.** Se marca «causa no identificada» y se guarda la salida |

**Ambigüedades conocidas, resueltas a favor de lo grave:**
- **Verificación con `rc 1`.** «La regla no está» (el grep no encontró nada) y «sudo me denegó el
  listado» devuelven lo mismo. Primero se buscan los textos de sudo (F6); si no aparecen, es «no está».
  Si la ejecución dio `rc 0`, eso es F8, nunca F6.
- **Idioma.** Los textos de sudo dependen del idioma del equipo. Se fuerza `LC_ALL=C` delante del
  comando remoto (no cambia lo que sudo permite) y los patrones se prueban con salidas reales en inglés.
- **Versiones de OpenSSH.** Los textos cambian entre versiones (Alpine con OpenSSH 9, Metasploitable
  con 4.7). Los patrones se fijan con salidas **capturadas de verdad** en el laboratorio, no inventadas.
- **«Host key verification failed» con huella conocida.** Si el known_hosts sí tiene la huella del
  equipo, no es F2: se trata como F3 (algo no cuadra con la clave del host).

---

## 4. Fases

Cada fase va en su propio commit, con su interruptor cuando cambia comportamiento, y no se empieza la
siguiente sin cumplir los criterios de la anterior.

### Fase 0 · Banco de fallos reproducibles y línea base (sin tocar el código del MDR)

Objetivo: tener cada fallo **provocado a voluntad** en el laboratorio, con su salida real capturada, y
saber exactamente qué hace hoy el MDR en cada uno.

| Fallo | Cómo provocarlo en el banco (y deshacerlo) |
|---|---|
| F2 | Un equipo recién desplegado sin aprovisionar (`pagos-qr` sin dar de alta) |
| F3 | En un equipo aprovisionado: regenerar sus claves del host (`rm /etc/ssh/ssh_host_*; ssh-keygen -A`) y reiniciar sshd. Deshacer: aceptar la clave nueva en Conectividad |
| F4 | Vaciar `~triaje/.ssh/authorized_keys`. Deshacer: volver a ejecutar su paquete |
| F5 | Caso E1 (`iptables -I INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP`) y, aparte, parar sshd. Deshacer: `banco.sh restaurar` |
| F6 | Equipo con papel sin la acción, y acción con binario ausente (cortar conexión en el banco) |
| F7 | Hacer fallar el comando con sudo permitido: por ejemplo, una regla de bloqueo con la tabla de iptables bloqueada por otro proceso (solo en el laboratorio) |
| F8 | Un bucle en el equipo que borra cada regla de bloqueo nada más aparecer |
| F9 | Daemon sin clave del conector |

Entregables:
1. `lab/banco/fallos.py` (o un apartado en `banco.sh`): provocar y deshacer cada fallo.
2. Las **salidas reales** de ssh y sudo de cada caso, guardadas como fixtures de prueba.
3. Una tabla «comportamiento actual» por caso: estado en la traza, escalada, tiempo, mensajes en
   consola y en la vista. Es la referencia contra la que se compara cada fase.

Criterio de salida: cada caso se provoca y se deshace sin dejar restos (comprobado con `banco.sh test`).

### Fase 1 · Clasificar sin cambiar nada (solo observación)

1. `clasificar_fallo(rc, salida, contexto)` en `prototipo/accion/`. Es una función **pura**, con la tabla
   de la sección 3, y reutiliza los patrones de `conectividad.diagnosticar`, que pasan a vivir en un solo
   sitio. `contexto` = si el equipo tiene huella en el known_hosts y si estaba verificado (regresión).
2. Cada intento (ejecución, verificación y cada salto de la escalada) guarda en la traza un campo nuevo
   `causa: {clase, evidencia, regresion}`. Es un campo **añadido**: no cambia ninguno existente.
3. `LC_ALL=C` delante del comando remoto (se comprueba que no altera las reglas del sudoers).

Criterios de salida:
- Las fixtures reales de la fase 0 dan su clase en el 100 % de los casos. Lo no reconocido da F10.
- **Prueba de no interferencia:** el mismo escenario con y sin la clasificación produce registros
  idénticos salvo el campo `causa`: misma contención, misma escalada, mismo veredicto.
- Evaluación (63 pruebas) y banco idénticos.

### Fase 2 · Mensajes y vista (sin cambiar decisiones)

1. Consola: un mensaje por clase. «NO verificada» solo cuando **sí** se ejecutó algo. La escalada fallida
   dice en qué equipos falló y por qué, sin «None: None».
2. Decisiones, Trazas y el Panel («Te toca», contenciones fallidas): la causa en lenguaje claro, con lo
   que hay que hacer. Por ejemplo, F2: «atm no está aprovisionado: dalo de alta en Conectividad».
3. **F3, F8, y F4/F5/F6 con regresión** se marcan como **posible ataque**, en rojo y en «Te toca», nunca
   como configuración.

Criterios: una prueba de presentación por clase. F3 y F8 nunca aparecen con texto de configuración.

### Fase 3 · Conectividad se entera

1. Cada fallo de contención actualiza un **estado operativo** del equipo, aparte de la prueba: «la última
   contención falló: inalcanzable, hace 1 min». La prueba verde sigue ahí, con un aviso encima.
2. El estado operativo **nunca** pone «verificada»: solo resta confianza. Se limpia con una prueba o una
   contención correctas.

Criterios: tras el caso E1, web-banking deja de verse solo como «verificada» en menos de un ciclo de sondeo.

### Fase 4 · Dejar de hacer trabajo inútil, sin ocultar nada (con interruptores)

Tres cambios independientes, cada uno con su variable (apagada por defecto hasta validarla):

1. **Cortar la secuencia cuando ni se entró** (`TRIAJE_FALLO_RAPIDO=1`). Si la primera conexión falla
   por F2, F3, F4, F5 o F9, no se hacen las otras tres al mismo equipo: no entraron, así que no pueden
   cambiar nada. La escalada sigue igual.
2. **No intentar en un equipo sin aprovisionar** (`TRIAJE_PRECHECK_APROVISIONADO=1`). Sin huella en el
   known_hosts (F2 sabido de antemano): no se intenta. Si la acción es sobre el origen, se escala; si no,
   va al analista con el motivo. **Solo F2:** un equipo con huella que falla sigue intentándose (podría ser
   F3, F4 o F5).
3. **Saltar destinos de escalada sin aprovisionar** (`TRIAJE_ESCALADA_SOLO_APROVISIONADOS=1`). Se registra
   «salto omitido: fw-core sin aprovisionar». Si no queda ningún destino, la contención va al analista
   («no hay dónde contener»): no se da por cerrada en silencio.

Criterios:
- Matriz de la fase 0 con los tres interruptores: las mismas contenciones conseguidas que con ellos
  apagados, y menos tiempo en F2/F5.
- F3, F6, F7 y F8 se comportan **exactamente** igual que con ellos apagados.
- Cuando estén validados, se encienden por defecto en un commit aparte (fácil de revertir).

### Fase 5 · Memoria de fallos por equipo (la más delicada)

**Para qué sirve:** que 25 alertas seguidas contra un equipo inalcanzable no paguen 25 veces la espera.
**Riesgo:** que esconda que un atacante dejó al SOC sin acceso. Por eso solo **acelera** la escalada y
**sube** la alerta; nunca calla nada.

1. Solo para F5 (inalcanzable) y F4 (sin credencial). **Nunca** para F3, F6, F7 ni F8.
2. Se abre tras 3 fallos seguidos del mismo equipo en 5 minutos. Mientras está abierta:
   - no se intenta directamente en el equipo: se escala desde el principio (acciones sobre el origen) o
     va al analista;
   - se crea **una** alerta destacada «el MDR no tiene acceso a X desde las hh:mm», en «Te toca» y en
     Conectividad, que se actualiza en vez de repetirse;
   - se sondea el equipo cada 60 s con un comando inocuo; al primer éxito se cierra y se anota.
3. Interruptor `TRIAJE_MEMORIA_FALLOS=1`, apagado por defecto hasta validarlo.

Criterios:
- Caso E1: la primera contención escala como hoy; las siguientes escalan directamente en pocos segundos.
  El analista ve la alerta «sin acceso» desde el tercer fallo. Tras `banco.sh restaurar`, se cierra en
  menos de 60 s.
- F3 con la memoria activa: sigue sin intentar contra ese equipo y sigue avisando como crítico.

### Fase 6 · Acciones que el equipo no puede ejecutar

Si la **última prueba vigente** (misma clave del conector y del host, de menos de 24 h) dice que falta
la regla de una acción, por ejemplo cortar conexión sin `ss`:

1. En la ejecución, esa acción se trata como «no ejecutable en este equipo»: no se intenta, y se escala
   (sobre el origen) o va al analista con el motivo.
2. El **motor no cambia**: su decisión queda igual en la traza (invariante 6). Esto vive en la capa de
   ejecución.
3. Sin prueba vigente, o con una prueba vieja, se intenta como hoy.

Criterios: en el banco, cortar conexión en web-banking deja de pedir contraseña a sudo y escala directo.
Con una prueba de hace más de 24 h, se intenta como siempre.

---

## 5. Matriz de pruebas final

Se ejecuta al cerrar cada fase, con los casos de la fase 0 en el laboratorio:

| Caso | Clase esperada | Contención | Escalada | Aviso | Conectividad |
|---|---|---|---|---|---|
| Equipo sin dar de alta | F2 | No se intenta (fase 4) | Sí, si es sobre el origen | «Aprovisiona X» | Sin aprovisionar |
| Clave del host regenerada | F3 | No | Sí, si es sobre el origen | **Posible suplantación** | Clave del host cambiada |
| authorized_keys vaciado (estaba verificado) | F4 con regresión | Fallida | Sí | **Anomalía** | Aviso sobre «verificada» |
| Caso E1 | F5 con regresión | Fallida, luego directa a escalada (fase 5) | Sí | **«Sin acceso a X»** | Aviso sobre «verificada» |
| sshd parado (nunca verificado) | F5 | Fallida | Sí | Inalcanzable | — |
| Cortar conexión sin `ss` | F6, falta en la prueba | No se intenta (fase 6) | Sí | No ejecutable en este equipo | Incompletas |
| Regla añadida fuera del papel | F6 con deriva | Fallida | Sí | **Deriva** | No coinciden (al probar) |
| Comando que falla | F7 | Fallida | Sí | Error del comando | — |
| Regla borrada nada más aplicarse | F8 | Fallida | Sí | **Posible contramedida** | — |
| Daemon sin clave | F9 | No | No | Genera la clave | Falta la clave |
| Salida desconocida | F10 | Como hoy | Como hoy | Causa no identificada | — |

Además, en cada fase: Python, visor, banco (157) y **evaluación (63) idénticos**.

---

## 6. Riesgos y cómo se cubren

| Riesgo | Cobertura |
|---|---|
| Un ataque clasificado como configuración | F3 y F8 nunca son configuración; F4, F5 y F6 con regresión suben a anomalía; lo dudoso es F10 y sigue como hoy |
| Patrones de texto que no casan en otro equipo | Fixtures reales por versión, `LC_ALL=C`, y lo no reconocido es F10 (comportamiento actual) |
| La memoria de fallos esconde un corte del SOC | Solo acelera la escalada y crea una alerta destacada; se reprueba cada 60 s |
| Saltarse una escalada necesaria | Solo se salta un destino sin aprovisionar, y sin destinos va al analista |
| Una prueba vieja decide | Solo cuenta la prueba vigente y de menos de 24 h |
| Cambio de comportamiento difícil de revertir | Fases 4 a 6 con interruptores, apagados por defecto hasta validarlos |

## 7. Fuera de este plan

- Arreglar los equipos de forma automática (reaprovisionar, aceptar claves): lo decide un humano.
- Cambiar las decisiones del motor o sus cifras.
- Los puntos de seguridad de la vista Conectividad
  ([CONECTIVIDAD-PENDIENTE-REVISION.md](CONECTIVIDAD-PENDIENTE-REVISION.md)).

---

## Anexo A · Línea base y avance

### Fase 0: salidas reales capturadas (9/11/2026)

`python3 -m lab.banco.fallos capturar api-movil` no toca ningún equipo: cambia solo lo que usa el conector
(un known_hosts o una clave temporales en `/tmp` del nodo de gestión, un puerto cerrado, una IP sin
equipo, una orden que sudo permite pero falla). Guarda la salida en
`prototipo/tests/fixtures/fallos_conector.json` (OpenSSH 9.7p1, sudo 1.9.15).

| Caso | rc | Última línea de la salida real | Clase |
|---|---|---|---|
| ok / ok con `LC_ALL=C` | 0 | (listado de iptables) | — |
| Verificación sin la regla (`grep` sin coincidencias) | 1 | (vacía) | no es fallo de ejecución: F8 si se ejecutó |
| known_hosts sin la clave del equipo | 255 | `Host key verification failed.` (antes: `No ED25519 host key is known for …`) | F2 |
| pagos-qr sin dar de alta | 255 | ídem | F2 |
| known_hosts con otra clave para el equipo | 255 | `Host key verification failed.` (antes: `REMOTE HOST IDENTIFICATION HAS CHANGED!`) | F3 |
| Clave que el equipo no conoce | 255 | `Permission denied (publickey,password,keyboard-interactive).` | F4 |
| Puerto sin sshd | 255 | `Connection refused` | F5 |
| IP sin equipo | 255 | `Host is unreachable` | F5 |
| Red sin ruta | 255 | `Operation timed out` | F5 |
| Binario ausente (`ss`) | 1 | `sudo: a password is required` | F6 |
| Comando fuera del sudoers (con y sin `LC_ALL=C`) | 1 | `sudo: a password is required` | F6 |
| Reversión de una regla que no existe | 1 | `iptables: Bad rule (does a matching rule exist in that chain?).` | F7 |
| Daemon sin clave | 126 | `conector sin configurar: …` (sintética: la produce el propio conector) | F9 |

Lo que confirma la captura:
- La última línea de F2 y F3 es **la misma**. Solo las anteriores las distinguen; por eso F3 se reconoce
  primero y, con la huella fijada en la consola, una F2 sube a F3.
- Binario ausente y comando fuera del sudoers dan **la misma** salida. Solo la última prueba de
  Conectividad (la regla que falta en el sudoers) los separa.
- Con `NOPASSWD`, sudo no pregunta: «a password is required» significa «no está en el sudoers».

### Fase 0: comportamiento actual (antes de la fase 1)

| Clase | Contención | Escalada | Tiempo | Consola |
|---|---|---|---|---|
| F1 | No sale | No | Inmediato | «orden no ejecutable» |
| F2, F3, F4 | Fallida (rc 255) | Sí, si es sobre el origen | ~1 s por salto | «✗ NO verificada» y «⇪ … el activo no respondió» |
| F5 rechazada | Fallida (rc 255) | Sí | ~1 s por salto | ídem |
| F5 sin respuesta | Fallida (rc 255) | Sí | 5 s de espera por SSH, hasta 4 SSH por salto: **16 a 70 s** medidos | ídem |
| F6, F7 | Fallida (rc 1) | Sí | ~1 s por salto | ídem |
| F8 | Fallida (rc 0, sin verificar) | Sí | ~1 s por salto | ídem |
| F9 | Fallida (rc 126) | Sí, y falla igual | Inmediato | ídem |
| Escalada sin destino | — | «→ None: None (fallido)» | — | bug de texto (fase 2) |

Medido en el sistema en marcha el 9/11 (laboratorio a medio aprovisionar y caso E1 del banco activo):
33 contenciones fallidas, de 3 a 308 s cada una. Todas se mostraron igual en la consola,
fuera cual fuese la causa.

**Pendiente de la fase 0:** la pasada completa con los casos que SÍ modifican un equipo
(`python3 -m lab.banco.fallos provocar|deshacer e1|sshd|sin-clave|clave-host|contramedida EQUIPO`),
con el daemon en marcha y `banco.sh test` al deshacer. No se hizo durante el aprovisionamiento manual
del laboratorio para no interferir con él.

### Fase 1: hecho

- `prototipo/accion/fallos.py`: `clasificar_fallo` (pura) y `patron`, la única lista de patrones.
  `conectividad.diagnosticar` la usa también, así que la prueba de conexión y las contenciones
  diagnostican igual.
- Campos añadidos, sin cambiar ninguno existente:
  - `causa_fallo` en el registro de la contención, **solo** si no quedó contenida.
  - `causa` en cada paso de la escalada que falló.
  - `causa` en cada verificación negativa de la escalada.
- Contexto de la consola: `conectividad_web.contexto_equipo`, de solo lectura y sin SSH al equipo.
  Da si el equipo tiene la huella fijada, si está verificado con las claves actuales (regresión) y qué
  regla de la acción falta en el sudoers. Lo engancha el daemon al arrancar. Sin consola (pruebas, lote),
  el contexto queda vacío y la clasificación es la más conservadora.
- `LC_ALL=C` delante de `sudo -S` en el comando remoto: capturado con y sin él, con salida idéntica.
  No cambia lo que permite el sudoers.
- Pruebas (`prototipo/tests/test_fallos.py`):
  - Las salidas reales dan su clase en el 100 % de los casos.
  - Prueba de no interferencia en cinco escenarios: host caído que escala y contiene, todo caído,
    contramedida, regresión y contención correcta. Los registros con y sin clasificador son
    idénticos salvo `causa_fallo` y `causa`.
- Evaluación 63 y banco 157 sin cambios.

### Fase 2: hecho

- Consola (`stream._lineas_ejecucion`):
  - «✗ … NO verificada en X» solo cuando la orden llegó a ejecutarse (F7, F8).
  - En el resto: «✗ … no se ejecutó en X — qué pasó — qué hacer», más una línea con la evidencia.
  - La escalada dice dónde contuvo o en qué equipos falló y por qué. Ya no aparece «None: None».
  - Lo que puede ser un ataque va en su propia línea, que empieza por «POSIBLE ATAQUE».
- Resumen de cada decisión (`tablero.causa_de`): campo `causa`, con lo que puede ser ataque primero,
  esté en el activo o en un salto de la escalada.
- Visor:
  - Decisiones: el detalle muestra la causa del activo y la de cada salto fallido (`LineaCausa`).
  - Trazas: «Causa del fallo» en el detalle del registro.
  - «Te toca»: los posibles ataques van primero, en rojo, aunque la escalada contuviera. El resto
    muestra la causa en vez del genérico «revisar el conector».
- Pruebas: una de presentación por clase (F1..F10). F3, F8 y la regresión nunca llevan texto de
  configuración. Python 1180, visor 440, evaluación 63 y banco 157.


### Fase 3: hecho

- `fallos.observar(ip, causa)`: el lazo y cada salto de la escalada cuentan cómo fue la contención en
  cada equipo. `causa` None significa que quedó contenida y verificada ahí. Si el observador falla,
  la contención no cambia (probado).
- `conectividad_web.registrar_operativo` guarda en memoria, por IP, el último fallo: clase,
  descripción, qué hacer, si puede ser ataque, si es regresión y cuándo. La evidencia en bruto **no**
  viaja a Conectividad: está en la traza de la decisión. Una contención verificada o una prueba
  correcta quitan el aviso.
- Visor:
  - Conectividad: el aviso va encima de la prueba, que no se toca. Va en la fila («la última
    contención falló» o «posible ataque») y en el detalle, con «vuelve a probar para confirmarlo».
  - Un equipo con el aviso deja de contar como verificado.
  - El indicador «Conector» del Panel lo cuenta como problema.
- Criterio: tras el caso E1, web-banking deja de verse solo como «verificada» con su primera
  contención fallida. La vista sondea, así que lo enseña en el siguiente refresco. Queda por confirmar
  en la pasada completa del laboratorio (pendiente de la fase 0).
- Límite conocido: el estado operativo vive en memoria. Al reiniciar el daemon se pierde, y lo
  vuelve a poner la siguiente contención fallida.
