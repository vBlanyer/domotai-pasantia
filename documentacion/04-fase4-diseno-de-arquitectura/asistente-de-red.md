# Asistente de red: del escaneo al perfil — diseño

> **Estado (11/11/2026): diseño revisado (revisor + respuestas del usuario), sin implementar.** Rama `asistente-de-red`; no se integra en
> `main` hasta probarlo en el laboratorio nuevo. Mockup aprobado:
> https://claude.ai/artifact/YFPUdzq8afwbqsHyyoFckA (tres pantallas: Escanear, Revisar, Validar y exportar).

## 1. Por qué

Instalar el MDR en un cliente exige escribir a mano el esqueleto del perfil (equipos, zonas, cadena de
cortafuegos, redes internas, gestión). Es tedioso y es donde un técnico se equivoca: el manual dedica
secciones enteras a «añadir una red» y «borrar un equipo» porque hay cuatro sitios que mantener
coherentes. Desde la consola solo se puede dar de alta un equipo dentro de una zona que ya exista.

El usuario quiere **simular la instalación en un cliente nuevo**: levantar una red que el MDR no conoce,
describírsela, conectarlo por SSH con cada equipo y ver cómo se forma la topología en la vista Red. Un
escaneo con Nmap ahorra la parte mecánica (quién hay, qué ofrece, por dónde se llega) y deja al técnico lo
que solo sabe el cliente.

## 2. Objetivos

1. **Un laboratorio nuevo de Containerlab**, más pequeño que el banco, que haga de cliente desconocido.
2. **Descubrimiento** de esa red con Nmap desde el MDR: equipos vivos, servicios y caminos (traceroute).
3. **Un asistente en la consola** en tres pasos (Escanear → Revisar → Validar y exportar) que convierte el
   descubrimiento en una **propuesta** de `perfil.yml`, `postura.json` y `politica.yml`, con el mapa
   dibujándose mientras se revisa.
4. Que el usuario pueda hacer la instalación entera **a mano, siguiendo la documentación**, sin tocar
   código: escaneo, revisión, exportación, instalación del perfil, alta de cada equipo en Conectividad y un
   ataque real contenido al final.

## 3. No objetivos y antiobjetivos

- **Antiobjetivo: la consola nunca escribe el perfil vivo** ni `politica.yml`. Propone y exporta; el técnico
  revisa, instala (`mdr validar-perfil`, copiar, reiniciar). Es la misma regla que ya sigue el proyecto: lo
  que cambia dónde y cómo contiene el MDR pasa por un fichero revisado. Si el asistente aplicara algo por su
  cuenta, habría fallado aunque funcione.
- **Antiobjetivo: aprovisionar solos los equipos.** El laboratorio nuevo **no** se aprovisiona para el
  conector (a diferencia del banco, que tiene `banco.sh aprovisionar`): el acceso SSH se da con el paquete de
  alta de Conectividad, como en un cliente.
- No es objetivo: editar zonas o cortafuegos en vivo desde la consola; re-escaneo periódico y detección de
  deriva (posible extensión); descubrir dependencias entre servicios (Nmap no las ve); dispositivos que no
  sean Linux con SSH.
- No toca el motor de decisión ni las cifras de la evaluación.

## 4. Restricciones

- Mismo stack: Python con biblioteca estándar + PyYAML; visor React/TS con zod y vitest; Nmap del sistema.
- **Seguridad (fail-closed, como Políticas y Conectividad):**
  - Escanear exige un **operador identificado** (token personal); sin él, 403 (con el mismo opt-in de
    laboratorio que las otras vistas, si se mantiene ese patrón).
  - Exige marcar la **autorización por escrito** del cliente; queda registrada en la traza firmada junto al
    operador, los rangos y la hora.
  - Los **argumentos de Nmap son fijos**: el usuario solo elige rangos (validados con `ipaddress`, privados
    o los que el técnico declare, con un tamaño máximo por rango), ritmo (suave/normal) y puertos (los 1000
    comunes o una lista de números). Nunca se pasa texto libre a la línea de órdenes.
  - Ningún escaneo simultáneo; plazo máximo por equipo (como `mdr escanear`, 120 s).
  - La API nunca devuelve claves ni secretos; el descubrimiento solo contiene IPs, puertos, servicios,
    saltos y nombres.
- **Por dónde sale el escaneo:** desde el equipo del MDR **por la red del cliente**, no por la interfaz de
  gestión de Containerlab (desde ahí todo está a un salto y no se ve ningún cortafuegos). En el laboratorio,
  con el mismo mecanismo que hoy usa el conector (`TRIAJE_NODO_GESTION` → `docker exec` en el nodo del MDR);
  en un cliente, directamente.
- Un equipo que el escaneo no puede clasificar no se inventa: queda como «¿?» para que decida el técnico.

## 5. Qué se decidió (con el usuario)

- Asistente en la consola que **propone y exporta**, no que aplica (opción preferida frente a editar el
  perfil en vivo o escribirlo a mano).
- El escaneo con Nmap como punto de partida («nos ahorra mucho trabajo»).
- Tres pantallas como en el mockup:
  1. **Escanear:** rangos (pasan a `redes_internas`), IP del MDR (pasa a `ip_gestion` y se propone como
     origen legítimo en `politica.yml`), una dirección de fuera para trazar la salida, ritmo (suave por
     defecto, por equipos frágiles), puertos, casilla de autorización, qué hará, último escaneo.
  2. **Revisar:** tabla por equipo (incluir, nombre en el SIEM, IP, servicios, «llega por», zona, papel,
     criticidad), casos especiales (sin nombre en el SIEM con su DNS como pista; equipo frágil; equipo sin
     servicios descartado), mapa en vivo con los caminos deducidos en discontinuo, dependencias a mano, lista
     de lo que falta.
  3. **Validar y exportar:** las comprobaciones de `perfil.validar` (más las propias del asistente),
     descarga de `perfil.yml`, `postura.json` y una propuesta de `politica.yml`, vista previa, pasos
     siguientes (validar, instalar, reiniciar, Conectividad).
- Trabajo en la rama `asistente-de-red`; se integra en `main` solo tras probarlo en el laboratorio nuevo.
- **Arranque de una instalación nueva (respuesta del usuario, 11/11): perfil mínimo.** El asistente vive en
  la consola y la consola necesita el servicio en marcha. `mdr configurar`, cuando no hay perfil, pregunta
  los rangos de la red y la IP del MDR y escribe un **perfil mínimo**: `ip_gestion`, `redes_internas` y los
  dos frenos de `continuidad`, sin equipos (comprobado: pasa `perfil.validar` sin avisos). El servicio
  arranca, el MDR reconoce como propia la actividad de su IP de gestión (incluido su escaneo) y, mientras
  no haya perfil completo, no contiene nada porque no conoce ningún equipo. El perfil que exporta el
  asistente sustituye al mínimo. Hoy `configurar` copia la plantilla y no arranca: eso cambia.
- **Laboratorio (respuesta del usuario, 11/11): como el resto de laboratorios.** El servicio corre en la
  máquina del usuario y actúa por dentro de la red a través del nodo `mdr` (`TRIAJE_NODO_GESTION`, como el
  banco), tanto para el escaneo como para el conector SSH. El recorrido de la prueba se escribe en el
  **manual de usuario** (que es el del laboratorio); el manual de producción recoge el asistente y el perfil
  mínimo, sin laboratorio.

### Decisiones del diseñador (revisables)

- **Equipos fuera de la cadena de contención.** El motor no cambia: un equipo que no está en `topologia` se
  contiene en los **cortafuegos perimetrales** (`cadena_de_contencion`), y `AISLAR_NODO`/`BLOQUEAR_DESTINO`
  quedan vetados para él. El asistente lo dice tal cual en la revisión y en la validación para cada equipo
  que el técnico deje fuera (los críticos marcados «no tocar directamente» y los frágiles); por defecto
  propone dentro de la cadena a todo equipo con SSH y fuera solo a lo que el técnico marque.
- **Solo instalaciones nuevas.** Volver a escanear un cliente instalado y comparar con el perfil vigente
  (fusionando rutas, excepciones, dependencias, Políticas y el inventario de Conectividad) queda como
  extensión futura.
- **La IP de cada cortafuegos es la que ve el MDR.** En `topologia` va la IP por la que el traceroute desde
  el MDR alcanza al cortafuegos, que es la que usará el conector SSH. El asistente propone añadir a
  `redes_internas` los segmentos donde aparecen saltos (tránsito y gestión), para que esos equipos no cuenten
  como externos; en el laboratorio, esos segmentos van ya en los rangos por defecto.
- **Prueba de aceptación:** un ataque desde `internet` contenido. Un ataque interno desde `puesto` es una
  prueba adicional, no condición: en la misma subred que sus víctimas no cruza ningún cortafuegos.

## 6. Cómo funciona

### 6.1 Descubrimiento

Tres pasadas de Nmap con argumentos fijos, desde el equipo del MDR:

1. **Quién hay:** barrido de los rangos → IPs vivas, DNS inverso, fabricante (si está en el mismo segmento).
2. **Qué ofrece:** puertos y servicios de cada IP viva (los 1000 comunes o la lista dada; detección de
   versión ligera). Este resultado se convierte también en la **postura** en el formato que ya consume el
   motor (el de `escanear_postura.py`).
3. **Por dónde se llega:** traceroute a cada IP viva y a la dirección de fuera. De los saltos se deducen:
   - los **cortafuegos candidatos** (IPs que aparecen como salto intermedio);
   - la **zona candidata** de cada equipo (los que comparten el último salto, y su subred);
   - el `gateway` de cada equipo (su último salto) y la **cadena hacia fuera** (los saltos del traceroute a la
     dirección externa).

Resultado: un `descubrimiento.json` junto a la traza, con la fecha, el operador, los rangos y lo encontrado.
Si un cortafuegos no responde a las sondas, el camino queda incompleto y se marca para que el técnico lo
complete; nunca se rellena por suposición.

### 6.2 Nombres del SIEM

El MDR reconoce al equipo atacado por el nombre de host que trae la alerta (`resolver_activo`: el host de
la línea syslog o el nombre del agente). El asistente propone para cada IP el nombre que el SIEM usa,
cruzándolo con las alertas recientes; si no hay correspondencia, propone el DNS inverso y exige que el
técnico lo escriba. **Pendiente de comprobar en la implementación:** de qué campo de la alerta sale la IP
del emisor (en Wazuh, `location` para syslog remoto o `agent.ip` para agentes). Si no hay forma fiable, el
nombre se pide siempre a mano con el DNS como pista.

### 6.3 Revisión y borrador

Lo que el técnico acepta, corrige o descarta se guarda como **borrador** junto a la traza (sobrevive a
recargar la página y a reiniciar el servicio), con quién lo tocó. El mapa de la pantalla 2 se dibuja con el
mismo componente de la vista Red a partir del perfil que saldría del borrador.

### 6.4 Validación y exportación

El perfil propuesto pasa por `perfil.validar` y por comprobaciones del asistente (cadena que llega al borde,
gestión fuera de la cadena, todos con nombre del SIEM, dependencias dentro del inventario). La exportación
genera tres ficheros para descargar; el `politica.yml` es una propuesta con el MDR como administrador, todo
en `con_analista` y `aprobada_por: "[pendiente de aprobación]"`. Exportar **no** cambia nada del servicio.

### 6.5 Laboratorio `oficina`

Una red de Containerlab propia (no convive con el banco ni con la red pequeña, igual que ellos), con la red
del mockup:

| Nodo | Papel | Red |
|---|---|---|
| `internet` | atacante externo / dirección de fuera para el traceroute | fuera de `fw-borde` |
| `fw-borde` | cortafuegos de borde | 10.0.0.1 |
| `fw-interno` | cortafuegos interno | 10.0.0.2 |
| `mdr` | equipo del MDR (gestión), con Nmap; por él salen el escaneo y el conector | 10.99.0.10, detrás de `fw-borde` |
| `srv-web01`, `srv-correo01` | servidores de la DMZ (SSH, web, correo) | 172.16.10.0/24, detrás de `fw-borde` |
| `srv-app01`, `srv-db01`, `nas01` | servidores internos (SSH, app, PostgreSQL, Samba) | 10.20.0.0/24, detrás de `fw-interno` |
| `impresora` | equipo frágil (HTTP, 9100), sin SSH | 10.20.0.0/24 |
| `puesto` | equipo interno sin servicios (y atacante interno) | 10.20.0.0/24 |

Los cortafuegos tienen interfaz en el segmento de tránsito (10.0.0.0/24) y en los de cada zona; el
direccionamiento exacto lo fija quien construya el laboratorio, cuidando que lo que ve el traceroute desde
`mdr` sea coherente con la tabla. Los servicios pueden ser simulados (puertos que escuchan y dejan registro), como los señuelos del banco. Los
registros de cada equipo llegan a Wazuh con su nombre de host, para que el SIEM y el asistente conozcan los
mismos nombres. Ningún equipo trae el usuario ni el sudoers del conector: los deja el paquete de alta.

## 7. Qué queda a quien lo construya

- La forma exacta de `descubrimiento.json` y del borrador, y los endpoints de la API.
- Cómo se ejecuta Nmap con privilegios desde el servicio (el servicio corre como `triaje`).
- La imagen y los servicios simulados del laboratorio, y cómo se reenvían sus registros a Wazuh.
- El componente de mapa reutilizado y la disposición exacta de las tablas.
- Pruebas: parseo de la salida de Nmap (incluido traceroute incompleto), deducción de zonas y cadena,
  generación del perfil, validación, permisos de la API, vitest de las tres pantallas.

## 8. Cómo se sabe que funciona

En el laboratorio `oficina`, con el MDR sin perfil de esa red, el usuario sigue la documentación: escanea,
revisa, exporta, instala el perfil, da de alta los equipos en Conectividad y lanza un ataque desde
`internet`; el MDR lo contiene en el cortafuegos o el equipo que corresponda, y la vista Red muestra la
topología real. Lo que no se pueda hacer sin tocar código o ficheros que la documentación no mencione es un
fallo del diseño.
