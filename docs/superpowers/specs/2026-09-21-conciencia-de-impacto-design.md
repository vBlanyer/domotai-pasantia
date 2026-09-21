# Diseño: conciencia de impacto — inventario reconciliado e impacto determinado (RF-17)

**Fecha:** 2026-09-21 · **Estado:** diseño para revisión · **Alcance:** Nivel 1 (obligatorio) +
Nivel 2 (opcional) · Nivel 3 documentado como fuera de alcance.

## 1. Problema (medido, no supuesto)

El agente sabe bien lo que **no puede hacer** (catálogo cerrado, esquema derivado, filtro de continuidad,
reversibilidad, veto de comandos destructivos), pero **no sabe qué afecta con lo que sí hace**. Evidencia
del 21/09/2026 sobre la partición de evaluación (300 alertas, perfil `empresarial`):

1. **Cinco fuentes de inventario desconectadas.** Perfil `activos` (criticidad + `servicios_prestados`),
   perfil `topologia` (rol, IP, gateway), hallazgos del auditor (puerto/servicio/estado),
   `orden.IP_DE_NODO` (mapa fijo en código) y `excepciones`/`ip_gestion`/`origenes_legitimos`. La IP de
   un mismo nodo vive en tres sitios.
2. **El inventario del perfil describe un cliente hipotético, no la red vigilada.** `empresarial.yml`
   declara `servidor-web` y `controlador-ot`, que **no existen en el laboratorio**; los nodos reales
   (`objetivo-vuln` con 16 servicios abiertos, `iot`, `puesto`, `borde`) **no están en `activos`**.
3. **`servicios_prestados` tiene 0 usos.** La política de la Fase 4 lo diseñó «para poder juzgar "esta
   acción alcanza un servicio del cliente"», pero ningún código lo lee. `criticidad` solo sube la prioridad;
   no protege. No hay campo de función ni de dependencias.
4. **El impacto se declara, no se determina.** Es una etiqueta fija por tipo de acción en el catálogo
   (`BLOQUEAR_IP` siempre «localizado», bloquee a quien bloquee). RF-17 exige *determinarlo*.
5. **El 100 % de los bloqueos automáticos cae sobre un activo interno del cliente sin saberlo.** Las 69
   contenciones automáticas bloquean `192.168.1.10` (el `puesto`); 2 son falsos positivos: un empleado
   desconectado sin aprobación de nadie. Las 20 que van al humano bloquearían `192.168.1.1`, que es a la
   vez origen de administración y **gateway** del activo.
6. **RF-19 protege una IP fantasma.** La `ip_gestion` de `empresarial.yml` es `192.168.1.100`, que **no
   existe en el laboratorio**. El canal de gestión real es el **auditor** (`172.20.20.4`): el conector
   lanza el SSH desde dentro de él (`conector._ssh_en_auditor`). El auditor hoy solo está a salvo de
   rebote, porque figura como origen legítimo; ninguna salvaguarda de RF-19 lo protege.
7. **La vista del agente es solo nombres y roles.** `consultar_topologia` devuelve
   `"nodos: gateway=firewall_perimetral, …"`: ni servicios, ni criticidad, ni función.

## 2. Objetivo y alcance

**Objetivo (Nivel 1):** que cada decisión de contención **determine** su impacto a partir del inventario
—qué servicios toca y **a quién** bloquea—, que ese conocimiento gobierne la política, quede en la traza,
lo vea el analista y lo vea el agente. Completa RF-17 y repara RF-19.

**Nivel 2 (opcional):** dependencias declaradas entre activos y radio de impacto en cascada.

**Nivel 3 (fuera de alcance, §9):** descubrimiento automático de dependencias, uso en tiempo real e
integración con CMDB.

**No-objetivos:** no cambia la clasificación (recall y tasa de FP deben quedar idénticos); no amplía el
catálogo de acciones; no hace alcanzables las acciones hoy inalcanzables.

## 3. Decisiones tomadas

| # | Decisión | Por qué |
|---|---|---|
| C1 | **Por defecto, bloquear un activo interno o un dispositivo de red exige humano** (`humano_siempre`), configurable por perfil | Decisión del usuario (21/09). Alinea el comportamiento por defecto con el plan: validación humana en lo crítico, respuesta automatizada como trabajo futuro |
| C2 | **El impacto determinado nunca baja del nivel del catálogo** (solo lo mantiene o lo sube) | El inventario puede estar incompleto; un inventario incompleto no debe poder rebajar una protección |
| C3 | **La resolución de actores es solo del perfil**, sin `IP_DE_NODO` | Agnóstico del cliente: lo que el MDR sabe de una IP lo declara el cliente. `IP_DE_NODO` queda solo como respaldo heredado para resolver la IP de ejecución |
| C4 | **Bloquear el canal de gestión es veto duro** (RF-19), no «pregúntale al humano» | RF-19 es precondición: cortar el canal impide la siguiente respuesta y la verificación |
| C5 | **La conciencia de actores vive dentro de `perfil.filtrar`** | El filtro se aplica en cada punto de decisión, incluidos los saltos de la escalada (`herramienta_ejecutar_comando`): no se puede olvidar en un sitio |
| C6 | **Un nombre por IP, y la criticidad declarada de los nodos del laboratorio reproduce la efectiva hoy** (`media`, el valor por defecto) | Evitar dos identidades para un mismo equipo, y no alterar la priorización validada (±1 0,981) con un cambio que no va de priorización. Subir criticidades es una decisión aparte |

## 4. Diseño del Nivel 1

### 4.1 Inventario unificado (esquema del perfil)

`activos` pasa a ser el inventario de la red protegida. Campos nuevos opcionales `ip` y `funcion`:

```yaml
activos:
  objetivo-vuln: { ip: 192.168.1.30, funcion: "servidor con servicios expuestos",
                   criticidad: media, servicios_prestados: [22, 80] }
  puesto:        { ip: 192.168.1.10, funcion: "puesto de trabajo de un empleado",
                   criticidad: media, servicios_prestados: [] }
redes_internas: ["192.168.1.0/24"]   # opcional: una IP de estos rangos no inventariada = activo interno
ip_gestion: 172.20.20.4              # el canal por el que el MDR actúa y verifica (RF-19)
continuidad:
  actores:                           # C1: por defecto humano_siempre si la clave no está
    activo_interno:  humano_siempre  # | automatica_si_confianza
    dispositivo_red: humano_siempre  # | automatica_si_confianza
```

`topologia` no cambia (grafo de contención: rol, IP, gateway; referencia activos por nombre).

**Resolución de la IP de ejecución** (`perfil.ip_de(perfil, nodo)`): `activos[nodo].ip` →
`topologia[nodo].ip` → `orden.IP_DE_NODO[nodo]` (respaldo heredado). `orden.construir` recibe el perfil
y usa esta resolución. Cierra el trabajo futuro «IP del activo desde la topología del perfil».

### 4.2 Resolución de actores: ¿quién es esta IP?

Módulo nuevo `prototipo/actores.py`, función `quien_es(ip, perfil) -> {"tipo": str, "nombre": str|None}`.
Orden de precedencia (la primera que encaja):

| # | Tipo | Cuándo | Política |
|---|---|---|---|
| 1 | `gestion` | `ip == ip_gestion` | **veto duro** (RF-19, C4) |
| 2 | `dispositivo_red` | IP de un nodo de `topologia` con rol `firewall_perimetral` | `continuidad.actores.dispositivo_red` |
| 3 | `activo_interno` | IP de un activo del inventario, **o** de otro nodo de `topologia`, **o** dentro de `redes_internas`, **o** en `origenes_legitimos` | `continuidad.actores.activo_interno` |
| 4 | `desconocido` | ninguna de las anteriores | reglas de continuidad por impacto, como hoy |

CIDR con `ipaddress` (stdlib). Un perfil sin inventario con IPs resuelve todo a `desconocido`: su
comportamiento no cambia (las fixtures de test actuales siguen igual).

### 4.3 Impacto determinado

Módulo nuevo `prototipo/impacto.py`, función
`determinar(accion_id, params, activo, perfil, catalogo, hallazgos=None) -> dict`:

```python
{"nivel": "ninguno|localizado|alcanza_servicio",   # determinado, nunca por debajo del catálogo (C2)
 "nivel_catalogo": "...",                            # el del catálogo, para la trazabilidad
 "servicios_afectados": [{"puerto": 443, "servicio": "https", "declarado": True, "abierto": True}],
 "actor": {"tipo": "activo_interno", "nombre": "puesto"} | None,
 "motivo": "texto explicable, en una línea"}
```

Reglas por familia de acción:

- **Sobre una IP** (`BLOQUEAR_IP`, `BLOQUEAR_IP_FIREWALL`, `MATAR_CONEXION`): `actor = quien_es(ip)`. Si el
  actor es `dispositivo_red`, el nivel sube a `alcanza_servicio` (bloquear un gateway puede cortar todo lo
  que enruta; con NAT, todo). `servicios_afectados = []`.
- **Sobre un puerto o servicio** (`BLOQUEAR_PUERTO`, `CERRAR_SERVICIO`): `servicios_afectados` = ese puerto
  o servicio del activo, marcando si está **declarado** (`servicios_prestados`) y **abierto** (hallazgos).
- **Sobre un nodo** (`AISLAR_NODO`): `servicios_afectados` = declarados ∪ abiertos del nodo. Es el **radio
  de impacto**: «aislar objetivo-vuln detiene 16 servicios».
- **Observación** (`OBS_*`): `ninguno`.

Los hallazgos del auditor se leen **por puerto** (hoy `postura_de` solo devuelve nombres de servicio y
`servicios_prestados` son puertos: el cruce debe ser por puerto).

### 4.4 Política (dentro de `perfil.filtrar`, C5)

`perfil.filtrar(..., hallazgos=None)` calcula `impacto.determinar` y aplica, en este orden:

1. Acción nula → `sin_accion` · fuera del catálogo → veto duro (como hoy).
2. RF-19: `no_cortar_gestion` por servicio (como hoy) **y** actor `gestion` → **veto duro** (`accion_final=None`).
3. RF-18: reversibilidad obligatoria (como hoy).
4. Excepciones del perfil (como hoy).
5. **Actor `activo_interno` o `dispositivo_red` con política `humano_siempre`** → retenida para validación
   humana (`resultado="veta"`, `accion_final` conservada, `requiere_humano=True`): el analista puede aprobarla.
6. Reglas de continuidad por impacto, usando el **nivel determinado** (C2).

El resultado incluye la clave `impacto` (el dict de §4.3). Llamadores que la ignoren siguen funcionando.

### 4.5 Conciencia en cada punto

- **Traza** (`traza.construir`): campo `impacto_determinado` (el dict de §4.3).
- **Analista** (`validacion.mostrar`): una línea legible, p. ej. *«Impacto: bloquea a **puesto** (activo
  interno: puesto de trabajo de un empleado) · 0 servicios detenidos»* o *«Impacto: detendría 16 servicios de
  objetivo-vuln (criticidad alta)»*.
- **Agente**: `resolver_topologia(perfil, hallazgos=None)` enriquece cada dispositivo con función,
  criticidad y servicios; `consultar_topologia` los devuelve. El prompt de sistema nombra la IP de gestión
  concreta en vez de la consigna genérica «nunca toques el plano de gestión».
- **Escalada**: hereda todo porque cada salto pasa por `perfil.filtrar` (C5).

### 4.6 Reconciliación declarado ↔ descubierto

Módulo nuevo `prototipo/inventario.py`, función `reconciliar(perfil, hallazgos) -> dict` y CLI
`python3 -m prototipo.inventario <perfil.yml> <hallazgos.json>`. Informa, por activo: servicios declarados
no abiertos (¿servicio caído?), abiertos no declarados (**exposición no reconocida**), nodos escaneados que
no están en el inventario y activos inventariados que el auditor no vio.

### 4.7 Métrica: bloqueos automáticos indebidos

`evaluacion/metricas.py`: `bloqueos_automaticos_indebidos(registros)` = acciones con `accion_final` y
**sin** humano cuya verdad es `FP` o `PROPIA`, **sea cual sea su impacto**. La campaña la reporta junto a la
tasa de ejecución automática. Corrige el punto ciego del indicador actual, que solo cuenta acciones que
alcanzan un servicio (cierra también la solución B del análisis #4).

### 4.8 Perfiles

- **`empresarial.yml`** pasa a describir **la red real del laboratorio**: `borde` (192.168.1.1), `puesto`
  (.10), `iot` (.20) y `objetivo-vuln` (.30), con función, servicios declarados y criticidad `media` (la
  efectiva hoy, C6); `redes_internas: ["192.168.1.0/24"]`; **`ip_gestion: 172.20.20.4`** (repara RF-19).
  **Un nombre por equipo (C6):** el laboratorio, el auditor y `orden.IP_DE_NODO` llaman `borde` a la `.1`,
  y la topología de `empresarial` la llamaba `gateway`; se renombra el nodo de la topología a `borde`. Sin
  eso, la reconciliación (§4.6) mostraría una discrepancia falsa («`borde` no inventariado» y «`gateway` no
  escaneado»). Arrastra cambios mecánicos: el guion de `demo-agente-escalado.py` y los textos de
  `demo-escalada-determinista.py` y de `docs/pruebas` que nombran `gateway`. Se retiran
  `servidor-web` y `controlador-ot` (y su excepción del 443), que no existen en el laboratorio; el patrón
  «nunca automática» sigue demostrado en `bancario.yml`.
- **`bancario.yml`** gana `ip` y `funcion` en cada activo (hoy van en comentarios) y
  `redes_internas: ["10.0.0.0/8"]`.
- **`residencial.yml`** no cambia: perfil ilustrativo permisivo sin inventario con IPs (todo resuelve a
  `desconocido`, comportamiento idéntico).

## 5. Nivel 2 (opcional): dependencias y cascada

- Campo opcional `depende_de: [activo, …]` por activo («si cae uno de estos, este se ve afectado»).
- `impacto.afectados_en_cascada(activo, perfil) -> list`: cierre transitivo **inverso** (quién depende,
  directa o indirectamente, del activo tocado), con **guardia de ciclos**.
- `determinar` añade `activos_afectados_en_cascada` para acciones sobre nodos y servicios; aparece en la
  traza, en el prompt del analista y en la vista del agente.
- `bancario.yml` declara las dependencias: `web-banking` y `api-movil` → `middleware`; `middleware` →
  `core-db`, `hsm`; `swift-alliance` → `hsm`. Resultado demostrable: «aislar middleware afecta en cascada a
  web-banking y api-movil».
- Riesgo propio: una dependencia no declarada da un falso «sin cascada»; se documenta como límite.

## 6. Efecto esperado (lo mide el plan, no se supone)

Sobre la partición de evaluación con `empresarial.yml` corregido:

| Métrica | Hoy | Esperado |
|---|---|---|
| Recall · tasa de FP (clasificación) | 1,000 · 0,009 | **idénticos** (no cambia la clasificación) |
| Priorización (±1 · Spearman) | 0,981 · 0,935 | **idéntica** (criticidad efectiva conservada, C6) |
| Contenciones automáticas | 69 | **0** (todas bloquean activos internos o el gateway) |
| Escalado a humano | 20 / 300 (6,7 %) | **89 / 300 (29,7 %)** |
| Bloqueos automáticos indebidos | 2 (invisibles al indicador) | **0** |

El compromiso es real: el analista revisa 4,5 veces más decisiones porque **en el laboratorio el atacante
es interno** (`puesto`). Un cliente que prefiera automatizar el bloqueo de activos internos lo declara con
`activo_interno: automatica_si_confianza`. La automatización sigue disponible para **orígenes externos
desconocidos** con confianza alta.

## 7. Testing (TDD, `unittest`)

- `actores`: cada tipo y la precedencia; CIDR; perfil sin inventario → todo `desconocido`.
- `impacto`: cada familia de acción; nunca por debajo del catálogo; cruce por puerto; radio de nodo.
- `perfil.filtrar`: veto de gestión; retención por actor interno y dispositivo de red; política
  configurable; perfil sin inventario → comportamiento idéntico al actual (regresión).
- `inventario.reconciliar`: las cuatro categorías de discrepancia.
- `orden.construir`: IP desde el perfil, con respaldo heredado.
- Traza, `validacion.mostrar` y herramienta de topología del agente: la información aparece.
- `metricas.bloqueos_automaticos_indebidos`.
- **Regresión global:** suites de `prototipo`, `dataset` y `evaluacion` verdes; clasificación idéntica; las
  métricas operativas cambian **exactamente** como en §6.
- Nivel 2: cierre transitivo, ciclos, perfil bancario.

## 8. Riesgos

- **Inventario incompleto:** una IP interna no inventariada y fuera de `redes_internas` resuelve a
  `desconocido` y puede auto-bloquearse. Mitigación: `redes_internas` por CIDR y el informe de reconciliación.
- **Declaraciones erróneas** (misma clase de riesgo que `origenes_legitimos`): el informe de reconciliación
  hace visibles las discrepancias entre lo declarado y lo descubierto.
- **Radio = servicios expuestos, no uso real:** un puerto abierto no implica que alguien lo use; el radio es
  una cota superior. El uso real es Nivel 3.
- **Cambio de comportamiento visible:** tests, demos y documentación que esperan el auto-bloqueo del
  `puesto` deben actualizarse. Es el efecto buscado (C1), no una regresión.

## 9. Nivel 3: fuera de alcance (documentado)

Queda fuera, y se registra en `estado-y-riesgos` §7 como límite por diseño:

- **Descubrimiento automático de dependencias** (NetFlow/IPFIX, service mesh, trazas de aplicación).
- **Integración con CMDB/ITSM** como fuente del inventario.
- **Uso en tiempo real** (cuántos usuarios usan un servicio en este momento).
- **Descubrimiento automático de la función** de un activo.

Motivo: exigen telemetría que el prototipo no tiene y son la **integración multicapa en producción** que el
plan de trabajo excluye explícitamente. El Nivel 1 deja la interfaz preparada: el inventario es un dato del
perfil, así que una fuente automática lo podría alimentar sin tocar el motor.
