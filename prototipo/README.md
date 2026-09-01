# `prototipo/` — el núcleo de decisión (Fase 5A)

Este paquete implementa el **subproyecto 5A**: el lazo de decisión completo del motor de triaje,
**hasta antes de ejecutar** ninguna acción sobre un nodo. Es offline, sin SSH, sin dependencias
pesadas (solo `pyyaml`), y corre sobre ficheros ya congelados de la Fase 3.

La Fase 5 completa se divide en tres subproyectos:

- **5A (este paquete)** — el núcleo de decisión: ingesta → análisis → política → perfil → traza.
- **5B** — el lazo en vivo: conector SSH que ejecuta las acciones, validación humana por TUI/CLI,
  verificación por reescaneo del auditor.
- **5C** — el clasificador y el justificador reales (encoder con fine-tuning + modelo generativo
  pequeño), enchufados detrás de la misma interfaz que hoy usa el baseline.

Diseño completo: [`docs/superpowers/specs/2026-08-31-fase5a-nucleo-decision-design.md`](../docs/superpowers/specs/2026-08-31-fase5a-nucleo-decision-design.md).
Regla de negocio (política + perfil): [`documentacion/04-fase4-diseno-de-arquitectura/politica-decision-continuidad.md`](../documentacion/04-fase4-diseno-de-arquitectura/politica-decision-continuidad.md).

---

## 1. El lazo

```
alerta normalizada ──► enriquecer con postura (hallazgos.json)
                         ▼
              clasificar()  [interfaz — BASELINE]  ──► clase · prioridad · confianza
                         ▼
              justificar()  [interfaz — plantilla] ──► texto que cita campos (RNF-02)
                         ▼
              política de decisión  ──► acción candidata (catálogo)
                         ▼
              perfil de cliente / filtro  ──► permite · degrada · veta · sin_accion
                         ▼
              traza de decisión (RF-09)     [SIN ejecutar: eso es 5B]
```

Cada paso vive en su propio módulo, con una responsabilidad y un motivo de cambio distintos:

| Módulo | Responsabilidad |
|--------|------------------|
| `prototipo/analisis.py` | Interfaz `enriquecer` / `clasificar` / `justificar` + implementación baseline |
| `prototipo/catalogo.py` | El catálogo de acciones como dato (impacto, reversión, comando) — carga `catalogo.yml` |
| `prototipo/politica.py` | Tabla determinista clase → acción candidata (principio de mínimo impacto) |
| `prototipo/perfil.py` | El perfil de cliente (V3/V4) y el filtro `permite`/`degrada`/`veta` (RNF-14, RF-17 a RF-19) |
| `prototipo/traza.py` | Construye el registro de decisión auditable (RF-09) |
| `prototipo/triaje.py` | Orquesta el lazo completo y expone el CLI |

## 2. El clasificador es un baseline, no un modelo

`analisis.clasificar` y `analisis.justificar` son la **interfaz** que el resto del motor consume.
Hoy, detrás de esa interfaz hay una implementación **determinista y explicable** (sin ML): mira si
la alerta pertenece a una familia de ataque soportada y si el hallazgo de Nmap/Greenbone (postura
del activo) confirma que el servicio está expuesto. No aprende, no generaliza y no tiene ningún
parámetro ajustado sobre el dataset — es una regla fija, elegida como placeholder honesto para
poder construir y probar el resto del lazo (política, perfil, traza) sin depender de `torch`,
`transformers` ni de un runtime de LLM, que la máquina de desarrollo no tiene.

El clasificador real y el justificador generativo (**5C** — encoder con fine-tuning + modelo
pequeño, ver [`seleccion-del-modelo.md`](../documentacion/04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md))
se enchufan **detrás de la misma interfaz** (`clasificar`/`justificar` con la misma firma y el mismo
contrato de salida: `clase`, `prioridad`, `confianza`, `justificacion`), sin tocar `politica.py`,
`perfil.py`, `traza.py` ni `triaje.py`. Esa frontera es la que hace posible medir 5A ahora y
sustituir solo esa pieza más adelante.

Las clases que produce el baseline hoy son solo **tres**: `no_soportada` (familia sin soporte de
acción), `vp_intento_acceso` (familia de ataque con el servicio expuesto, o postura desconocida con
confianza baja) y `fp_exposicion_inexistente` (familia de ataque con el servicio no expuesto). Las
otras tres etiquetas del caso de uso — `vp_acceso_consumado`, `vp_exposicion_gestion`,
`fp_actividad_legitima` — son clases que el dataset de la Fase 3 conoce (mismas etiquetas que usa
`lab/dataset/etiquetar.py`) pero que el baseline **no puede producir**: exigen contexto que una
regla determinista no tiene (por ejemplo, distinguir un acceso ya consumado de un intento, o una
exposición de gestión de una exposición de servicio). Ese límite documentado es exactamente lo que
motiva **5C** (ver [spec §3](../docs/superpowers/specs/2026-08-31-fase5a-nucleo-decision-design.md#3-el-clasificador-baseline)).

## 3. El esquema de la traza (RF-09)

Cada línea de la salida (`.jsonl`) es una decisión de triaje:

```json
{
  "id_decision": "d3",
  "timestamp": "2026-08-31T16:44:...",
  "id_alerta": "1788194...",
  "activo": "servidor-web",
  "clase": "vp_intento_acceso",
  "prioridad": 3,
  "confianza": 1.0,
  "justificacion": "Alerta ... [justificación de plantilla — baseline, no modelo]",
  "accion_propuesta": "BLOQUEAR_IP",
  "impacto": "localizado",
  "perfil_aplicado": "empresarial",
  "resultado_filtro": "permite",
  "accion_final": "BLOQUEAR_IP",
  "requiere_humano": false,
  "version_baseline": "baseline-0",
  "version_perfil": "v0"
}
```

`resultado_filtro` es siempre uno de `permite` | `degrada` | `veta` | `sin_accion`.
`version_baseline` deja constancia en la propia traza de que la clasificación es placeholder — se
incrementará cuando 5C sustituya el baseline por el modelo real, para poder distinguir en las
métricas de la Fase 6 qué decisiones vinieron de cuál.
`version_perfil` es la versión del perfil de cliente aplicado (clave `version` en el YAML del
perfil, `v0` mientras no cambie el esquema), para poder distinguir en las trazas y en las métricas
qué versión de la regla de negocio produjo cada decisión.

## 4. Cómo correr el CLI

Desde la raíz del repo (para que `import prototipo` y `from lab.dataset...` resuelvan):

```bash
python3 -m prototipo.triaje <alertas.jsonl> <perfil.yml> <hallazgos.json> <salida.jsonl>
```

Ejemplo, sobre el dataset etiquetado real de la Fase 3 y los hallazgos de la campaña de evaluación:

```bash
python3 -m prototipo.triaje lab/dataset/etiquetado.jsonl prototipo/perfiles/empresarial.yml \
  "lab/campañas/2026-08-31-evaluacion/hallazgos.json" /tmp/trazas-emp.jsonl
```

Imprime cuántas decisiones escribió. Cada línea de `<alertas.jsonl>` debe ser un objeto JSON con,
al menos, `activo`, `servicio`, `familia`, `origen_ip`, `regla_id`, `mitre`. `<perfil.yml>` es uno
de `prototipo/perfiles/empresarial.yml` o `prototipo/perfiles/residencial.yml` (o uno nuevo con el
mismo esquema).

## 5. Perfiles y RNF-14: dónde coinciden, dónde divergen

RNF-14 exige que el motor sea **configurable por cliente** sin cambiar código. `prototipo/perfil.py`
lo cumple con dos perfiles de ejemplo, `empresarial.yml` y `residencial.yml`, que difieren en cómo
tratan el impacto de una acción, no en qué acción proponen (eso lo decide la política, igual para
todos).

- **Acciones de impacto `localizado` (p. ej. `BLOQUEAR_IP`) — los perfiles COINCIDEN.** Ambos
  perfiles fijan `impacto_localizado: automatica_si_confianza`: con confianza alta, ambos permiten
  la acción sin intervención humana. Es el caso mayoritario en la corrida real (ver §6).

- **Acciones de impacto `alcanza_servicio` (p. ej. `BLOQUEAR_PUERTO` sobre el 443 de
  `servidor-web`) — los perfiles DIVERGEN.** El perfil `residencial` trata ese impacto igual que el
  localizado (`automatica_si_confianza`): con confianza alta, permite. El perfil `empresarial`
  declara una **excepción** explícita — el 443 de `servidor-web` es "nunca automática" porque es el
  puerto público del banco — y en su lugar **degrada** a `BLOQUEAR_IP` (localizado), reteniendo para
  humano si la confianza no alcanza. Es el ejemplo del banco: la misma alerta, el mismo hallazgo, dos
  decisiones distintas, ambas trazables a una regla del perfil y no a un capricho del modelo.

Esto está verificado en `prototipo/tests/test_rnf14.py` (`test_localizado_coincide_en_ambos` y
`test_misma_accion_alcanza_servicio_diverge_por_perfil`), llamando `perfil.filtrar(...)`
directamente con `BLOQUEAR_PUERTO`.

**Por qué la divergencia no se ve corriendo el CLI.** El baseline (§2) solo produce
`vp_intento_acceso`, `fp_exposicion_inexistente` y `no_soportada`; nunca produce
`vp_exposicion_gestion`, que es la única clase que la política traduce en una acción de impacto
`alcanza_servicio` (`BLOQUEAR_PUERTO`/`CERRAR_SERVICIO`). Por eso, corriendo
`python3 -m prototipo.triaje` sobre el dataset real con `residencial.yml` y con `empresarial.yml`,
las decisiones **coinciden** siempre: toda la actividad que el baseline sabe clasificar propone
`BLOQUEAR_IP` (impacto `localizado`), y ningún perfil degrada ni veta ese impacto. La divergencia
demostrada arriba es real y trazable a una regla del perfil, pero hoy solo se ejercita a nivel de
filtro (unit); la divergencia end-to-end por CLI llega con **5C**, cuando el clasificador real
produzca `vp_exposicion_gestion`.

## 6. Corrida sobre el dataset real de la Fase 3

```bash
python3 -m prototipo.triaje lab/dataset/etiquetado.jsonl prototipo/perfiles/empresarial.yml \
  "lab/campañas/2026-08-31-evaluacion/hallazgos.json" /tmp/trazas-emp.jsonl
```

Sobre las 410 alertas del dataset etiquetado (`lab/dataset/etiquetado.jsonl`), con el perfil
`empresarial` y los hallazgos de la campaña `2026-08-31-evaluacion`:

- **Clases:** `no_soportada`: 374, `vp_intento_acceso`: 36.
- **`resultado_filtro`:** `sin_accion`: 374, `permite`: 36.

El dataset actual es de una sola familia con soporte de acción (`acceso_credenciales`); no incluye
todavía alertas que disparen `veta` o `degrada` sobre este perfil (esos casos están cubiertos por
`test_rnf14.py` con datos sintéticos). Detalle completo de la corrida y del criterio de cierre de
5A en `.superpowers/sdd/2026-08-31-fase5a-nucleo-decision/task-11-report.md`.

## 7. Tests

```bash
python3 -m unittest discover -s prototipo/tests
```

---

## 8. 5B — el lazo en vivo

5A se detiene justo antes de actuar: produce `accion_final`, pero nada la ejecuta. 5B cierra ese
tramo — orden → conector → validación humana → verificación — sin tocar ningún módulo de 5A.
Diseño completo: [`docs/superpowers/specs/2026-08-31-fase5b-lazo-en-vivo-design.md`](../docs/superpowers/specs/2026-08-31-fase5b-lazo-en-vivo-design.md).

```
decisión (5A) ──► ¿requiere_humano? ──sí──► validación por terminal ──rechazar/modificar──► fin (no se ejecuta)
                        │no                          │aprobar
                        ▼                             ▼
                   orden.construir()  ──►  conector.ejecutar_orden()  ──►  verificacion.confirmar()
                                                                                    │
                                                                                    ▼
                                                                          traza (RF-09, ampliada)
```

| Módulo | Responsabilidad |
|--------|------------------|
| `prototipo/orden.py` | Traduce la decisión + la alerta en una orden (acción, nodo, IP, params) — la frontera motor↔conector |
| `prototipo/conector.py` | Renderiza el comando del catálogo con los params de la orden y lo ejecuta con el ejecutor inyectado |
| `prototipo/validacion.py` | Muestra la decisión por terminal y captura el veredicto humano (RF-08) |
| `prototipo/verificacion.py` | Reejecuta el comando de verificación del catálogo para confirmar el efecto |
| `prototipo/lazo.py` | Orquesta decisión → validación → orden → conector → verificación, con CLI (`--auto` / vivo) |

**El conector (`conector.py`).**

- **La orden es la frontera de dato, no de instrucción.** `orden.construir` arma un diccionario con
  campos fijos (`accion_id`, `nodo_ip`, `params`) a partir de la decisión y la alerta; el conector
  nunca interpola texto libre de la alerta en un comando de shell. Antes de renderizar cualquier
  comando, `conector._params_seguros` exige que cada valor de `params` cumpla
  `^[A-Za-z0-9._:-]+\Z` (ancla `\Z`, no `$`, para que un salto de línea final no cuele como
  separador de comandos en el shell remoto) y que no empiece por `-` (para que no se interprete
  como un flag, p. ej. de `iptables`) — si algo en el `origen_ip` u otro campo trae metacaracteres
  de shell, la orden se rechaza (`"params rechazados: caracteres no permitidos"`) y no se ejecuta
  ni se verifica nada. Es la aplicación directa de RNF-08 (los campos del log los escribe quien
  ataca) al punto exacto donde ese texto podría llegar a un `subprocess`.
- **Idempotencia: verificar antes de actuar (solo para estado persistente).** `ejecutar_orden`
  primero corre el comando de `verificacion` del catálogo; si ya confirma el estado deseado (p. ej.
  la IP ya está bloqueada), devuelve éxito sin volver a aplicar la acción (`idempotente: true`) —
  reintentar el lazo sobre la misma alerta no duplica reglas de `iptables` ni repite efectos. Esto
  solo aplica a acciones cuya `verificacion` representa un estado final persistente
  (`reversion: definida` o `auto`). Para acciones con `reversion: transitoria` (`MATAR_CONEXION`),
  `rc0` en la verificación significa que el estado indeseado **sigue existiendo** (la conexión
  sigue viva), no que la acción ya se aplicó — por eso esas acciones nunca se saltan por
  idempotencia: siempre se ejecutan. Solo cuando no se salta por idempotencia se renderiza y
  ejecuta el comando real, y se vuelve a verificar después para confirmar el efecto.
- **El ejecutor es inyectable.** `ejecutar_orden(orden, catalogo, ejecutor, timestamp)` recibe el
  ejecutor como parámetro — una función `(nodo_ip, comando) -> (codigo_salida, salida)`. Los tests y
  el modo `--auto` de `lazo.py` usan un ejecutor falso (sin red, sin SSH); el modo vivo usa
  `conector.ejecutor_ssh_lab`, que hace `docker exec` sobre el auditor del laboratorio y `ssh` con
  `sshpass` contra el nodo objetivo. Esa frontera es la misma razón por la que 5C puede sustituir el
  clasificador sin tocar el conector: el contrato es la firma, no la implementación.

**Honestidad sobre el alcance de la demo en vivo.** El conector solo se ha ejecutado en vivo contra
`objetivo-vuln` (`192.168.1.30`), porque es el único nodo del laboratorio con `sshd` accesible desde
el auditor; los demás nodos del plano de datos no exponen SSH. La credencial usada es
`msfadmin`/`msfadmin` con `sudo -S` — es un **sustituto de laboratorio** de la clave de servicio
dedicada y de privilegio mínimo que un despliegue real usaría (ver la nota de RNF-08/conector en la
spec de 5B); no es la credencial de producción ni pretende serlo.

**La validación humana (`validacion.py`).** Cuando el filtro del perfil marca `requiere_humano`
(RF-08, RF-18), `lazo.procesar_lazo` no construye la orden todavía: llama a `validacion.pedir`, que
imprime por terminal la decisión completa (activo, clase, confianza, justificación, acción
propuesta e impacto) y lee un veredicto (`aprobar` / `rechazar` / `modificar`, con `rechazar` como
valor por defecto ante cualquier respuesta ambigua — seguro por defecto). Solo `aprobar` construye y
ejecuta la orden. `modificar` **no** sustituye la acción propuesta por una alternativa concreta —
eso es trabajo futuro — hoy es una salvaguarda honesta: retiene la alerta sin ejecutar nada, igual
que `rechazar`, y el veredicto queda registrado en la traza (`veredicto_humano: "modificar"`) como
semilla para esa sustitución futura.

**Honestidad sobre cuándo se dispara.** Sobre el dataset real de la Fase 3 (§6), el baseline no
produce ninguna decisión con `requiere_humano: true`: la única familia soportada
(`acceso_credenciales`) con postura conocida cae siempre en `permite` con confianza alta. Por eso la
validación humana se demuestra aquí con un **escenario provocado** — una alerta cuyo `activo` no
aparece en `hallazgos.json`, de forma que la postura queda en `None`, la confianza baja a `0.5` y el
perfil `empresarial` veta la acción automática:

```bash
python3 - <<'PY'
import json
from prototipo import lazo, catalogo, perfil
CAT = catalogo.cargar_catalogo("prototipo/catalogo.yml")
P = perfil.cargar("prototipo/perfiles/empresarial.yml")
H = json.load(open("prototipo/tests/fixtures/hallazgos.json"))
alerta = {"id_alerta":"prov","timestamp":"2026-08-31T00:00:00Z","activo":"nodo-sin-postura",
          "servicio":"ssh","familia":"acceso_credenciales","origen_ip":"192.168.1.10",
          "mitre":["T1110"],"regla_id":"5760","nivel_wazuh":5}
r = lazo.procesar_lazo(alerta, H, P, "empresarial", CAT,
                       lambda ip,c: (1,"") if "grep" in c else (0,""),
                       "prov", "2026-08-31T00:00:00Z", leer=lambda _: "aprobar")
print("requiere_humano:", r["requiere_humano"], "| veredicto:", r["veredicto_humano"],
      "| ejecuto:", r["ejecucion"] is not None)
PY
```

Salida: `requiere_humano: True | veredicto: aprobar | ejecuto: True` — la orden se retuvo, la
validación (simulada aquí con `leer=lambda _: "aprobar"`) la aprobó, y solo entonces se ejecutó.

**La verificación (`verificacion.py`).** Después de ejecutar, `lazo.procesar_lazo` llama siempre a
`verificacion.confirmar`, que reejecuta el comando `verificacion` del catálogo (independiente del
`ejecutor_ssh_lab` de la ejecución) y guarda `verificado` + `evidencia` en la traza. Es la misma
idea de "verificar, no asumir" que usa la idempotencia del conector, aplicada después del hecho en
vez de antes.

**El orquestador (`lazo.py`) y su CLI.**

```bash
python3 -m prototipo.lazo <alertas.jsonl> <perfil.yml> <hallazgos.json> <salida.jsonl> [--auto]
```

- **`--auto`** usa un ejecutor falso (sin red, sin laboratorio): útil para correr el lazo completo
  —incluida la construcción de la orden y el formato de la traza— sin depender de que el laboratorio
  esté arriba. Es lo que corren los tests y este mismo README para las demos que no tocan SSH.
- **Sin `--auto` (modo vivo)** usa `conector.ejecutor_ssh_lab`: requiere el laboratorio
  (`sh lab/lab.sh up`) arriba y `sshpass` instalado en el contenedor del auditor. Así se demostró el
  lazo extremo a extremo sobre `objetivo-vuln`: alerta VP real del dataset → `vp_intento_acceso` →
  `BLOQUEAR_IP` → ejecución por SSH con `exito: true` → verificación con `verificado: true` (detalle
  completo en `.superpowers/sdd/2026-08-31-fase5b-lazo-en-vivo/task-6-report.md`).

Cada línea de la salida de `lazo.py` extiende la traza de 5A (§3) con `veredicto_humano`, `orden`,
`ejecucion` y `verificacion` (cualquiera de los tres puede ser `null` si la decisión no requería
acción, o si la validación humana rechazó).
