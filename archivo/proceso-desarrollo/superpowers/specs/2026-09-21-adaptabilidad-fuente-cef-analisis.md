# Adaptabilidad de la fuente: segundo formato (CEF) — análisis previo a decidir

> **Estado: análisis, no spec aprobado.** Recoge lo explorado el 21/09/2026 para retomarlo con calma.
> Nada de esto está implementado. Antes de escribir el spec y el plan hay que resolver las decisiones
> abiertas de la §10.

## 1. Qué se quiere demostrar y por qué

No sabemos qué SIEM tendrá el cliente ni en qué formato entregará sus alertas: puede ser JSON o texto
por syslog. El prototipo tiene que funcionar **igual** con cualquiera de los dos.

El criterio de éxito es concreto: añadir una fuente nueva debería consistir en **un adaptador nuevo
(un fichero Python, igual que `adaptador_wazuh.py`) y una línea en el registro de `ingesta.py`**. Y la
misma alerta, llegue en el formato que llegue, debe producir **la misma decisión y la misma asistencia**:
la clase, la prioridad, la acción, el filtro, lo que recupera el RAG y la justificación.

Se eligió **CEF** (*Common Event Format*, creado por ArcSight) como segundo formato por tres motivos:

- es texto, no JSON, así que pone a prueba el supuesto más profundo;
- lo emiten muchos SIEM, cortafuegos e IDS;
- según su documentación, Trellix ESM, el SIEM que mencionó el tutor, reenvía eventos por syslog y
  documenta CEF.

Integrar un Trellix ESM real en el laboratorio **no es viable**. Es comercial y necesita un código de
activación que se renueva contra la nube de Trellix, lo que choca con un laboratorio aislado (RNF-01). Se
distribuye como dispositivo virtual y no como contenedor. No se verificaron sus requisitos de hardware.

## 2. Estado actual verificado

**El motor ya es agnóstico.** La clasificación, la política, el filtro y el impacto consumen solo el
esquema normalizado: `familia`, `servicio`, `origen_ip`, `activo` y `mitre`. `regla_id` se trata como
una etiqueta opaca que solo se cita.

**La entrada no lo es.** Hay cuatro supuestos de Wazuh fuera del adaptador:

| # | Dónde | Supuesto | Efecto con otra fuente |
|---|---|---|---|
| A1 | `prototipo/stream.py:12` | Adaptador de Wazuh fijo en el código | El daemon no puede recibir otra fuente |
| A2 | `stream._parsear` y `ingesta.ingerir_fichero` | `json.loads` **antes** del adaptador | Una línea CEF se descarta como si estuviera corrupta y nunca llega al adaptador |
| A3 | `agrupacion.py:28`, `evaluacion/baseline.py:14`, `evaluacion/entrenado.py` | Campo `nivel_wazuh` | Sin él, el representante del incidente se elige solo por fecha (sin error visible), y el baseline y el árbol fallan |
| A4 | `stream.py` (fuentes de líneas) | Solo lee fichero o stdin | Los SIEM reenvían por **syslog** (UDP/TCP); hoy hace falta un `nc` intermedio |

Hay además un acoplamiento menor. **El ancla de la traza** (`traza.py`) se envía como syslog al SIEM, y
`leer_anclas` la busca por texto en el fichero donde el SIEM la guarda. Funciona con cualquier SIEM que
guarde el mensaje en texto legible, pero solo está probado con el `alerts.json` de Wazuh. La regla local
100100 que la reconoce también es propia de Wazuh.

## 3. Evidencia: CEF real del laboratorio

Se capturó en `lab/campañas/2026-09-21-captura-cef/`: Wazuh 4.14.7 emitiendo **los mismos 11 eventos**
en CEF y en JSON por `syslog_output` (demonio `wazuh-csyslogd`). Una línea real:

```
<132>Sep 21 20:12:02 CEF:0|Wazuh Inc.|Wazuh|v4.14.7|5760|sshd: authentication failed.|5|dvc=wazuh
cs1=objetivo-vuln->172.20.20.7 cs1Label=Location cat=syslog,sshd,authentication_failed,gdpr_...,
src=192.168.1.10 spt=41 shost=192.168.1.10 suser=root suser=root msg=Sep 21 16:12:01 objetivo-vuln
sshd[91]: Failed password for root from 192.168.1.10 port 41 ssh2
```

| Dato del esquema | JSON de Wazuh | CEF de Wazuh | Valoración |
|---|---|---|---|
| `origen_ip` | `data.srcip` | `src` (estándar) | ✅ Equivalente |
| `severidad` | `rule.level` (0–15) | `Severity` de la cabecera, **con la escala de Wazuh (0–15)** y no la 0–10 que fija CEF | ✅ Sirve, pero no se ajusta al estándar |
| `familia` | `rule.groups` | `cat=` con los **grupos de Wazuh** separados por comas | ⚠️ El campo es estándar, el vocabulario no |
| `servicio` | grupos o `program_name` | Solo por `cat` (`sshd`). No hay `dpt` ni `app` | ⚠️ Depende del emisor |
| `activo` | `predecoder.hostname` | Solo en `cs1` con `cs1Label=Location` (`host->ip`). No hay `dhost` ni `dst` | ⚠️ Campo personalizado de Wazuh |
| `mitre` | `rule.mitre.id` (`T1110.001`, `T1021.004`) | **No viene** | ❌ Ver §5 |
| `id_alerta` | `id` (único) | **No viene** | ❌ Hay que derivarlo |
| `timestamp` | ISO 8601 con año y zona (`2026-09-21T20:12:06.759+0000`) | Cabecera syslog **sin año ni zona** (`Sep 21 20:12:02`). No hay `rt` | ❌ Ver §7, riesgo R3 |
| `evento_crudo` | `full_log` | `msg` | ✅ Equivalente |

**Conclusión de la evidencia:** el formato CEF es común, pero **cada emisor lo rellena a su manera**. Un
adaptador CEF necesita un lector genérico más una tabla de conocimiento por emisor
(`Device Vendor|Device Product`). Así funcionan las integraciones CEF reales.

## 4. Diseño propuesto (pendiente de decidir)

**Paso 1. Corregir A1–A4 sin añadir fuentes**, con la suite y la campaña idénticas:

1. Cada adaptador recibe la **línea cruda** y la interpreta; el de Wazuh hace su `json.loads`. El
   registro de `ingesta` pasa a guardar fuentes (`nombre → fábrica de adaptador`).
2. El daemon admite `--fuente wazuh|cef`.
3. Se añade el campo normalizado `severidad`. La agrupación, el baseline y el árbol lo leen, con
   `nivel_wazuh` como respaldo solo para el dataset antiguo. Ningún código requiere ya `nivel_wazuh`.
4. El daemon admite `--escuchar-udp PUERTO`: recibe syslog, un datagrama por mensaje.
5. **MITRE completado desde la familia en el motor:** si la alerta llega sin técnica, se usan las que
   declara `familias.yml` y la traza registra de dónde salió el dato (`mitre_por: fuente | familia`).

**Paso 2. Añadir CEF:** `prototipo/adaptador_cef.py` y una línea en el registro.

- **Lector genérico:** la cabecera de siete campos, las extensiones `clave=valor` con sus escapes
  (`\=`, `\|`, `\\`, `\n`) y la cabecera syslog opcional. Usa los campos estándar cuando existen:
  `src`, `dhost`/`dst`, `dpt`, `app`, `rt`, `externalId`, `Severity`.
- **Tabla por emisor** dentro del mismo fichero, con Wazuh como primera entrada: el activo se toma de la
  `Location` en `cs1`, la familia y el servicio se traducen desde `cat`, y los eventos propios del triaje
  (el ancla) se descartan.
- **Lo que falta no se inventa:** `id_alerta` se calcula como un hash determinista de la línea.

**Prueba de equivalencia** («mismo evento, dos formatos, misma decisión»):

- **Real:** los pares JSON/CEF capturados se pasan por los dos adaptadores y se exige la misma decisión.
- **A escala:** un conversor reproduce el CEF de Wazuh a partir de las alertas crudas de las campañas
  (`lab/campañas/*/alerts.json`). Su fidelidad se valida contra la captura real. Después se pasan las 300
  alertas de evaluación por los dos caminos y se exige que la clase, la prioridad, la confianza, la
  acción y el filtro sean idénticos.
- **Asistencia:** para las mismas alertas se comparan los pasajes que recupera el RAG con MITRE de la
  fuente y con MITRE de la familia. Hace falta el embedder local.

**Laboratorio:** `wazuh-run.sh` gana una opción reproducible que activa la salida CEF y JSON.

## 5. MITRE: lo que se juega la asistencia

La **decisión** no usa MITRE (`analisis.clasificar`). La **asistencia** sí:

- la consulta del RAG (`rag.py:47`: `tecnica MITRE {mitre} {familia} servicio …`);
- el justificador (`justificador_llm.py`), que comprueba el anclaje contra las técnicas propias;
- la plantilla (`analisis.py:78`);
- la pantalla del analista (`validacion.py`).

Sin técnica, el RAG recupera con menos información y la justificación dice «s/técnica».

Completarla desde la familia no es inventar, porque es la correspondencia declarada. Tiene dos límites:

- **Es menos específica:** `T1110` en vez de `T1110.001`.
- **Una familia puede declarar técnicas que no aplican a esta alerta concreta.** `acceso_credenciales`
  declara `T1110` y `T1078`. Una fuerza bruta mostraría también «cuentas válidas», que solo es cierto
  si el acceso se consumó. Mostrárselo así al analista puede **confundirle**.

Hay dos variantes para garantizar el mismo comportamiento con cualquier fuente. Se decide midiendo:

| Variante | Qué hace | A favor | En contra |
|---|---|---|---|
| **M1** | La consulta del RAG usa **siempre** las técnicas de la familia; la subtécnica de la fuente, si existe, solo se muestra | Igual por construcción, venga de donde venga | Puede empeorar el RAG que hoy tiene Wazuh: las cifras medidas (MRR 0,70; 18/18 ancladas) se obtuvieron con subtécnicas. Habría que volver a medir |
| **M2** | Usa la técnica de la fuente cuando viene y la de la familia cuando no | No toca lo medido con Wazuh | El comportamiento **depende de la fuente**: dos clientes con el mismo ataque recibirían asistencias distintas |

## 6. Qué será determinista y qué no

| Pieza | ¿Determinista? | Nota |
|---|---|---|
| Lectura de CEF, tabla por emisor, traducción a familia y servicio | Sí | Funciones puras sobre la línea |
| `id_alerta` por hash de la línea | Sí | Misma línea, mismo id (ver riesgo R5) |
| MITRE desde la familia | Sí | Sale de `familias.yml` |
| `severidad`, agrupación, ráfaga | Sí, **si el `timestamp` es fiable** | Con CEF sin año ni zona deja de serlo (R3) |
| Clasificación, política, filtro, impacto | Sí | Sin cambios |
| Recuperación del RAG | Sí con el mismo índice y embedder | Cambia si cambia la consulta (M1/M2) |
| Justificación con LLM | **No** del todo | Solo con temperatura 0 o semilla fija; la plantilla sí es determinista |
| Recepción por UDP | **No** | Puede perder, duplicar o desordenar datagramas (R1) |

## 7. Qué se puede romper (riesgos)

| # | Riesgo | Cómo se produce | Gravedad | Mitigación posible |
|---|---|---|---|---|
| **R1** | **Inyección de alertas falsas por syslog** | Un receptor UDP acepta cualquier datagrama. Alguien en la red puede enviar un CEF falso «desde» un socio legítimo y, si el origen es externo y la confianza alta, el MDR lo **bloquea solo**: la respuesta automática se convierte en arma de denegación de servicio. El camino actual (`docker exec … tail alerts.json`) no tiene esta exposición | **Alta** | Aceptar solo IPs del SIEM, escuchar solo en la interfaz de gestión, syslog por TCP+TLS (RFC 5425) y, para fuentes de red, exigir humano en la primera versión |
| **R2** | Pérdida o duplicado en UDP | UDP no garantiza entrega. Una ráfaga perdida baja el recuento de `rafaga` y puede cambiar la clase (la 6ª regla) | Media | TCP para producción; documentar que UDP es solo para el laboratorio |
| **R3** | **Marcas de tiempo ambiguas** | La cabecera syslog del CEF no lleva año ni zona. En la captura, la cabecera va en UTC (20:12) y el `msg` en la hora de `objetivo-vuln`, EDT (16:12): **cuatro horas de diferencia**. La ráfaga (ventana de 60 s), la agrupación y el orden dependen de la hora. A fin de año, «Dec 31» y «Jan 1» se cruzarían | **Alta** para la ráfaga | Preferir `rt` si el emisor lo manda; si no, hora de recepción del daemon en UTC, documentada; nunca interpretar la hora del `msg` |
| **R4** | Lectura de CEF frágil | Escapes (`\=` y `\|` dentro de valores), valores con espacios (el `msg` va hasta el final), **claves repetidas** (`suser=root suser=root` en la captura real), extensiones vacías, cabecera syslog RFC 3164 frente a RFC 5424, mensajes truncados por el tamaño del datagrama | Media | Tests con líneas reales y casos límite; ante una clave repetida se queda el primer valor, documentado |
| **R5** | Colisión del id por hash | Dos eventos idénticos byte a byte (mismo segundo, mismo texto) tendrían el mismo id. La agrupación los contaría una vez y la ráfaga podría quedarse corta | Baja | Añadir al hash la hora de recepción y un contador; o usar `externalId` si el emisor lo da |
| **R6** | Incidentes partidos por vocabulario | Si el adaptador CEF traduce el servicio distinto que el de JSON (por ejemplo `sshd` frente a `ssh`), la clave de agrupación cambia y un mismo ataque se parte en varios incidentes | Media | La prueba de equivalencia lo detecta; tabla de servicios compartida |
| **R7** | Activo sin nombre | Un emisor que solo manda `dst` (una IP) da un activo que no casa con el inventario ni con los hallazgos del auditor, que usan nombres. La postura pasa a «desconocida» y la confianza baja a 0,5 | **Alta** para emisores que no son Wazuh | Resolver IP → nombre con el inventario del perfil (`activos.*.ip`) en un paso genérico, no en cada adaptador |
| **R8** | Bucle con el ancla | Si el ancla de la traza llega por CEF y el adaptador no la descarta, cada ancla genera una decisión y cada decisión un ancla. Ya se midió con Wazuh: 14 registros por un solo ataque | **Alta** si se olvida | Descartar los eventos propios en la tabla del emisor, con un test específico |
| **R9** | Severidad fuera de escala | Wazuh pone 0–15 en un campo que CEF define como 0–10. Otro emisor puede usar `Low`/`Medium`/`High` | Baja | Solo se compara dentro de un incidente de la misma fuente; convertir las etiquetas a número en el lector |
| **R10** | Conversor circular | El conversor de alertas a CEF lo escribimos nosotros con la misma idea que el adaptador. Si los dos comparten un error, la equivalencia sale perfecta sin probar nada | Media | Validar el conversor contra la captura real, línea a línea, antes de usarlo a escala |
| **R11** | Captura con `logger` | Los eventos de la captura se inyectaron con `logger`, no con un `sshd` atacado de verdad. Wazuh los procesa igual, pero no es una sesión real | Baja | Repetir con `sshpass` desde un nodo que lo tenga, o instalarlo en el `puesto` |
| **R12** | El MITRE de la familia confunde | Ver §5 (`T1078` en una fuerza bruta) | Media | Mostrar solo la técnica principal de la familia, o marcarla como «técnica de la familia» en pantalla |
| **R13** | Regresión en Wazuh | Pasar el `json.loads` al adaptador cambia el camino que hoy funciona en vivo | Media | Suite y campaña idénticas como condición del paso 1, y prueba en el laboratorio antes de fusionar |

## 8. Pros y contras de hacerlo

**A favor**

- Convierte «es agnóstico» en algo **demostrado**, con una métrica: los ficheros tocados y la
  equivalencia de decisiones.
- Deja el daemon listo para la forma real en que los SIEM entregan alertas (syslog), incluido el de un
  cliente con Trellix ESM, al menos a nivel de formato.
- Los arreglos del paso 1 benefician a **cualquier** fuente futura, no solo a CEF.
- Obliga a explicitar una regla de diseño que hoy es implícita: *lo que la fuente no manda lo completa
  el motor desde la configuración, nunca el adaptador inventándolo*.

**En contra**

- Abre una superficie de ataque nueva (R1) que el prototipo no tenía.
- El problema de las marcas de tiempo (R3) no tiene una solución buena si el emisor no manda `rt`.
- Con un solo SIEM real (Wazuh emitiendo CEF) se demuestra la independencia del **formato**, no la del
  **SIEM**. Para eso haría falta un segundo motor de detección, como Elastic Security.
- La variante M1 obligaría a volver a medir el RAG, y cualquier cambio en la consulta pone en riesgo las
  cifras vigentes.
- Es trabajo de entrada, no de decisión: no mejora ninguna métrica de la Fase 6.

## 9. Qué se puede mejorar después

- **Resolver IP → activo con el inventario** (R7): un paso genérico que haría útil cualquier emisor que
  solo mande IPs.
- **Pasar la tabla por emisor a YAML** cuando haya más de dos emisores, para configurar sin programar.
  Lo mismo para la traducción de Wazuh.
- **Syslog por TCP+TLS** (RFC 5425) y lista de IPs permitidas.
- **LEEF** (el formato de IBM QRadar) como tercer formato: se parece a CEF y reutilizaría el lector.
- **Elastic Security como segundo SIEM**, para demostrar que tampoco importa qué motor detecta.
- **Tabla regla → subtécnica por emisor**, para recuperar la precisión de MITRE en emisores conocidos.
- **Validación del perfil** al arrancar: avisar de activos sin IP, de gestión no declarada y de fuentes
  sin tabla de emisor.

## 10. Decisiones abiertas

1. **M1 o M2** para MITRE (§5). Condiciona si hay que volver a medir el RAG.
2. **Qué se muestra al analista** cuando la técnica viene de la familia (R12).
3. **Qué hora manda** cuando el CEF no trae `rt` (R3): la de recepción del daemon o la de la cabecera.
4. **Seguridad del receptor** (R1): si la primera versión exige humano para todo lo que llegue por
   syslog, o si basta con filtrar por IP.
5. **Si la resolución IP → activo (R7) entra ya** o espera a un emisor que la necesite.
6. **Alcance de la prueba:** solo la captura real y la conversión, o también un ataque real con `sshpass`.
7. **Cuándo añadir un segundo SIEM** (Elastic), si se hace.

## 11. Criterios de éxito (cuando se implemente)

- **Paso 1:** la suite y la campaña vigente, idénticas, y Wazuh en vivo funcionando igual.
- **Paso 2:** un fichero nuevo y una línea tocada. Si no es así, cada fichero extra se justifica como un
  acoplamiento más encontrado.
- **Equivalencia:** el 100 % de las decisiones idénticas entre JSON y CEF en las 300 alertas de
  evaluación y en la captura real. Toda diferencia queda explicada.
- **Asistencia:** el solapamiento de los pasajes recuperados, medido y reportado, con la variante M1 o M2
  elegida en consecuencia.

## 12. Estado del laboratorio tras la exploración

La salida CEF y JSON de Wazuh y los receptores `nc` en el auditor se activaron **en caliente** el
21/09/2026. No sobreviven a un `wazuh-run.sh up`, que recrea el contenedor, y no están en el repositorio.
