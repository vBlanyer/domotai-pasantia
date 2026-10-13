# Hoja de ruta a producción — pendientes para el producto final

> Compañera de [`integracion-en-produccion.md`](integracion-en-produccion.md). Aquélla dice **cómo** se
> configura el prototipo para un cliente; ésta lista **lo que falta cerrar** para pasar de prototipo a producto
> final, con estado y criterio de cierre, para abordarlo **progresivamente**.
>
> No es el plan de trabajo oficial (eso va a coordinación): es detalle de trabajo. Se actualiza la columna
> **Estado** a medida que se cierra cada punto.

## Cómo leer esta hoja

Cada punto indica **quién lo cierra**:

- **🛠 Prototipo** — es código nuestro; lo cerramos aquí con TDD.
- **🤝 Integración** — se cierra al desplegar en un cliente concreto (configuración + infraestructura).
- **🏢 Empresa / gobernanza** — lo aporta la organización (autenticación, custodia de secretos, autorización,
  hardware); nuestra parte es documentar el requisito y dejar el enganche listo.

## Tablero de estado

| # | Punto | Quién | Prioridad | Estado |
|---|---|---|---|---|
| 1 | Receptor de alertas de red (SIEM remoto) | 🛠 Prototipo | Alta | **Hecho (transporte)** |
| 2 | Validar el contenido de detección del SIEM del cliente | 🤝 Integración | Alta | Pendiente |
| 3 | Desplegar el auditor (postura/Nmap) en producción | 🤝 Integración | Media | Pendiente |
| 4 | Persistencia de estado al reiniciar | 🛠 Prototipo | Alta | **Hecho** |
| 5 | Supervisión y resiliencia del daemon | 🛠 Prototipo + 🤝 | Alta | **Hecho** |
| 6 | Rotación y retención de la traza | 🛠 Prototipo | Media | **Hecho (retención)** |
| 7 | Sincronización de reloj (NTP) y manejo de tiempos | 🤝 + 🛠 | Media | Pendiente |
| 8 | Autorización para actuar + *kill switch* | 🏢 + 🛠 | Alta | **Hecho (🛠)** · falta 🏢 |
| 9 | Gestión de secretos del conector | 🏢 Empresa | Media | Parcial |
| 10 | Control de cambios de catálogo y perfil | 🏢 Gobernanza | Baja | Pendiente |
| 11 | Modelo de análisis y hardware | 🏢 + 🛠 | Media | Parcial |
| 12 | Escala y volumen real | 🛠 Prototipo | Media | Pendiente |

---

## A. Integración que aún no está construida

### 1. Receptor de alertas de red (SIEM remoto) — 🛠 Prototipo · Alta · **TRANSPORTE HECHO**
**Lo que era.** `stream.py` solo leía fichero/stdin; un SIEM remoto no tenía por dónde entregar las alertas.
**Lo que se hizo.** `prototipo/receptor.py`: servidor **TCP** (`escuchar(...)`, generador que rinde líneas +
`None` en reposo, encaja en el bucle como la fuente de stdin) con **lista blanca de IPs** (`--permitir`: solo
el SIEM; el resto se cierra al instante → mitiga el DoS por alertas falsas, R1), **TLS opcional**
(`--tls-cert/--tls-clave`, o terminado por un proxy de la empresa), tope de tamaño de línea y de conexiones.
Flag del daemon: `--escuchar host:puerto`.
**Frontera de alcance.** Es el **transporte**: asume el mismo formato de línea que el daemon ya parsea (un JSON
de alerta por línea). El **enmarcado syslog / multi-formato CEF** (el adaptador recibe la línea cruda, campo
`severidad`) sigue siendo un ítem aparte (el análisis CEF).
**Criterio de cierre.** ✔ El daemon recibe alertas por red, descarta las de orígenes no permitidos, y una
alerta recibida produce la misma decisión que por fichero.

### 2. Validar el contenido de detección del SIEM del cliente — 🤝 Integración · Alta
**Estado.** `adaptador_wazuh.familia_de` mapea grupos/reglas de Wazuh → familia. Si el cliente usa otro
*ruleset* (otros IDs/grupos), el adaptador clasifica como `otra` y el motor no actúa.
**Qué falta.** Por cliente: inventariar qué reglas genera su SIEM, confirmar que cubren las 5 familias, y
ajustar el mapeo (o su adaptador). Es tarea de alta de cliente.
**Criterio de cierre.** Un catálogo de alertas de prueba del cliente cae en las familias correctas, verificado
en el banco de pruebas con sus reglas.

### 3. Desplegar el auditor (postura/Nmap) en producción — 🤝 Integración · Media
**Estado.** El auditor aparece **dos veces** en el flujo (contexto de postura antes de decidir; reverificación
después de actuar), pero el doc de integración lo trató como opcional. En el laboratorio es un contenedor con
Nmap; Greenbone (CVE) no está desplegado.
**Qué falta.** Decidir por cliente: dónde corre el auditor, su alcance de red (qué puede escanear), y si basta
Nmap (expuesto sí/no) o se quiere Greenbone (CVE). Credenciales y segmentación del plano de gestión.
**Criterio de cierre.** El auditor entrega postura real de los activos del cliente y la reverificación
confirma la contención sobre dispositivos reales.

---

## B. Operación Día-2

### 4. Persistencia de estado al reiniciar — 🛠 Prototipo · Alta · **HECHO**
**Lo que era.** La memoria de supresión (`MemoriaDecisiones`) vivía en proceso y se perdía al reiniciar; no
había registro de bloqueos activos (el MDR no «recordaba» qué tenía contenido).
**Lo que se hizo.** Reconstrucción **desde la propia traza** (fuente de verdad, sin fichero paralelo):
`MemoriaDecisiones.desde_traza(previos, perfil)` repone la supresión al arrancar (excluye las revertidas y las
no re-clavables sin `contexto`); `prototipo/contenciones.py:activas(regs, catalogo)` deriva las contenciones
activas (ejecutadas, verificadas, reversibles `definida`, no revertidas) y `/api/contenciones` las sirve; el
visor las lista en **«Contenciones activas»**. Para que persista entre reinicios, el daemon usa un `--salida`
estable (ver [integración §2.5](integracion-en-produccion.md)).
**Queda como mejora (no bloquea):** reverificar los bloqueos contra los dispositivos al arrancar (requiere
conectividad en el *boot*) y el TTL de bloqueos (#7). El des-bloqueo en masa llega con el *kill switch* (#8).
**Criterio de cierre.** ✔ Tras reiniciar, la supresión se recupera y el visor lista los bloqueos activos.

### 5. Supervisión y resiliencia del daemon — 🛠 Prototipo + 🤝 · Alta · **HECHO**
**Lo que era.** Existía el latido de ingesta (aviso tras 120 s de silencio), pero nada vigilaba el proceso
desde fuera: si el daemon caía, no había reinicio ni señal.
**Lo que se hizo.** Healthcheck HTTP **`GET /healthz`** (clase `Latido` en `stream.py`: el lazo llama a
`tick()` en cada iteración → `ok=false` si se cuelga; `alerta()` alimenta `ingesta_silencio_s` y el conteo).
Es la salud del **propio MDR**, distinta de `/api/salud` (servicios del cliente). Artefactos de despliegue en
**`deploy/`**: unidad **systemd** (`mdr-triaje.service`, `Restart=on-failure` + endurecimiento), wrapper del
*pipe* (`arrancar-mdr.sh`) y `triaje.env.ejemplo`; `deploy/README.md` con la instalación y la sonda local de
`/healthz`.
**Parte 🤝 (del cliente):** elegir el monitor local que sondea `/healthz` y la alta disponibilidad del nodo de
gestión (fuera del código). No se usa sd_notify/WatchdogSec (requeriría `python-systemd`, fuera de la
biblioteca estándar).
**Criterio de cierre.** ✔ `Restart=on-failure` cubre la caída dura; `/healthz` detecta el cuelgue del lazo.

### 6. Rotación y retención de la traza — 🛠 Prototipo · Media · **RETENCIÓN HECHA**
**Lo que era.** Los ficheros de traza se acumulaban en `run/` sin política; un daemon de larga vida con
`--salida` fijo podía crecer sin límite.
**Lo que se hizo.** Comando de **retención offline** `python3 -m prototipo.retener_trazas <dir> [--max N |
--max-dias D] [--excepto RUTA] [--aplicar]`: poda los ficheros `trazas-*.jsonl` antiguos por número o
antigüedad, **nunca el más reciente** (el activo) ni el nombrado con `--excepto` (el `$TRIAJE_SALIDA` vivo), ni
uno cuya cadena **no verifique** (se conserva con aviso); sin `--aplicar` simula. Verifica con HMAC, así que el
cron debe llevar el mismo `TRIAJE_TRAZA_CLAVE` (documentado en `deploy/README.md`); si falta, no poda nada y
avisa. Helper `traza.leer_familia(ruta)` (concatena segmentos `<base>.<N>.jsonl` + activo) añadido como
building block.
**Decisión de alcance.** NO se hace **rotación en caliente** del fichero vivo: partir la cadena encadenada
tamper-evident en segmentos choca con el ancla, el flock multi-escritor y los índices de reversión; el patrón
seguro para un log encadenado es **sellar entre arranques**. La rotación por tamaño queda como mejora (Opción
B) para un único daemon de muy larga vida; **cuando se aborde**, debe cablear `leer_familia` en la
reconstrucción de #4 **y** pasar la exclusión de revertidas a basarse en el `hash` del registro (no en el
índice posicional), para que la concatenación de segmentos sea consistente (lo detectó la revisión Opus).
**Criterio de cierre.** ✔ (retención) `run/` no crece sin límite; la poda verifica la cadena y respeta el
activo y las evidencias.

### 7. Sincronización de reloj (NTP) y manejo de tiempos — 🤝 + 🛠 · Media
**Estado.** La regla de ráfaga y la correlación dependen de timestamps; ya se midió desfase de reloj como
problema de latencia. El análisis CEF avisó de timestamps ambiguos (sin año/zona).
**Qué falta.** NTP entre SIEM/MDR/dispositivos (🤝 infraestructura); en código, normalizar zona/formato de
tiempo y tolerar desfase en la ventana de ráfaga (🛠).
**Criterio de cierre.** Reloj sincronizado y timestamps normalizados; la ráfaga no se rompe por desfase.

---

## C. Gobernanza y seguridad operativa

### 8. Autorización para actuar + *kill switch* — 🏢 + 🛠 · Alta · **🛠 HECHO**
**Lo que era.** El motor respetaba vetos y retenía a humano, pero no había interruptor global para desactivar
la automatización al instante ni des-bloqueo en masa si el MDR se equivocaba.
**Lo que se hizo (🛠).** *Kill switch* en dos piezas: **pausa global** (`EstadoTablero.pausar/pausada`;
`procesar_lazo(pausa=)` fuerza `requiere_humano` cuando la pausa está activa **y** hay `accion_final`, marcando
`pausa_automatizacion` en la traza; `/api/pausa` GET/POST) y **des-bloqueo en masa**
(`revertir.revertir_todas` sobre las contenciones activas, anotando reversiones con `indice_revertido` +
operador; `/api/revertir-todo`). Visor: **banner de pausa** persistente en todas las vistas + **toggle** y
botón **«Revertir todo»** (con confirmación) en «Contenciones activas».
**Falta (🏢, de la empresa):** las **reglas de enganche por escrito** (qué se puede bloquear, cuándo, sobre qué
activos). La pausa es estado de sesión: un reinicio la limpia (el operador la re-activa). El des-bloqueo es
síncrono (acotado por el timeout del conector); para escala iría en segundo plano (#12). Seguimiento menor:
anotar en la traza **quién** activó/soltó la pausa (no-repudio, como en aprobaciones/reversiones); hoy no deja
rastro.
**Revisión Opus:** cerrado 1 importante (la pausa también cubre la **escalada** de una contención ya aprobada
—antes el bloqueo perimetral de un externo se auto-aplicaba—) y 2 menores de UI (botón «Revertir todo»
deshabilitado mientras revierte; pausa optimista).
**Criterio de cierre.** ✔ (parte 🛠) Un operador pausa toda la automatización y revierte los bloqueos en un paso.

### 9. Gestión de secretos del conector — 🏢 Empresa · Media (Parcial)
**Estado.** La clave SSH del conector se pasa por variable de entorno; existe `rotar-clave-conector.sh`
(rotación todo-o-nada, anotada en Wazuh).
**Qué falta.** Custodia en un *vault* (no variable suelta), política de rotación y de quién tiene acceso.
**Criterio de cierre.** El secreto vive en un almacén gestionado con rotación y acceso auditados.

### 10. Control de cambios de catálogo y perfil — 🏢 Gobernanza · Baja
**Estado.** Catálogo y perfil son ficheros versionables, sin proceso formal de cambio.
**Qué falta.** Quién aprueba añadir una acción al catálogo o aflojar la automatización de un perfil; versionado
y revisión.
**Criterio de cierre.** Todo cambio de catálogo/perfil pasa por revisión registrada.

---

## D. El modelo de análisis

### 11. Modelo de análisis y hardware — 🏢 + 🛠 · Media (Parcial)
**Estado.** Dos perfiles de modelo (A híbrido ejecutable sin GPU; B de un solo 8B con GPU). En el equipo
actual el 8B no corre, así que la demo va **determinista por defecto** (`--con-llm` experimental). El
clasificador con *fine-tuning* sigue bloqueado por dataset.
**Qué falta.** Definir qué perfil corre en el cliente y su **hardware** (GPU para el 8B); documentar el
requisito; desbloquear el clasificador si se persigue el perfil con aprendizaje.
**Criterio de cierre.** El cliente tiene el hardware del perfil elegido y el análisis corre con él de forma
estable.

---

## E. Escala

### 12. Escala y volumen real — 🛠 Prototipo · Media
**Estado.** El banco genera pocos eventos; un SIEM real genera muchos más. El daemon es de **proceso único**.
**Qué falta.** Medir throughput, *back-pressure* de la ventana de agrupación bajo carga, y el límite del proceso
único (¿particionar por zona/activo?).
**Criterio de cierre.** Medido el volumen que aguanta un daemon y documentado el punto de partición.

---

## Orden recomendado (progresivo)

Por retorno y dependencias, no por número:

- **Ola 1 — Robustez del propio prototipo (🛠, mayor retorno, bajo riesgo):** #4 persistencia al reiniciar ·
  #6 rotación de traza · #5 systemd + healthcheck · #8 *kill switch* (la parte de código).
- **Ola 2 — Integración real (🛠+🤝):** #1 receptor syslog TCP+TLS · #7 manejo de tiempos · #12 escala.
- **Ola 3 — Despliegue en cliente (🤝):** #2 validar reglas del SIEM · #3 auditor en producción · #11 hardware
  del modelo.
- **Transversal (🏢, en paralelo, lo lleva la empresa):** #8 autorización por escrito · #9 vault · #10 control
  de cambios.

Cada punto 🛠 se aborda con su propio ciclo (diseño breve → TDD → revisión → fusión), y se marca **Hecho** en el
tablero al cerrarse.
