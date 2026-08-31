# Diseño — Política de decisión y perfil de cliente (revisión pendiente de la Fase 4)

**Fecha:** 2026-08-31
**Fase:** 4 — Diseño de la arquitectura (cierre de su revisión pendiente)
**Requisitos que cierra:** RF-17, RF-18, RF-19, RF-20, RNF-14, y la actividad del roadmap
*«establecer reglas de decisión y umbrales»*.

---

## 1. Objetivo y motivación

La Fase 4 se declaró cerrada, pero la Fase 1 produjo **después** cinco requisitos y una restricción
del roadmap que ningún artefacto de la Fase 4 recoge:

- **RF-17** — cada acción debe declarar su impacto sobre el servicio.
- **RF-18** — no se propone ninguna acción cuya reversión no esté definida y sea verificable.
- **RF-19** — se rechaza toda acción que dejaría el activo fuera del plano de gestión.
- **RF-20** — hay que calcular dos métricas de continuidad.
- **RNF-14** — adaptarse a un cliente nuevo es configurar V1–V5, sin tocar código.
- **Roadmap** — no existe la *regla que traduce clasificación en acción*.

Este diseño cierra esos huecos. La mayor parte del diseño conceptual ya existe en
[caso de uso §8–10](../../../documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md)
(niveles de respuesta, política de continuidad, métricas); el trabajo es **bajarlo a los artefactos
de la Fase 4** y añadir la pieza que falta de verdad: la política de decisión.

### Qué NO cubre

- La implementación (es diseño de Fase 4; la construcción es Fase 5).
- Los umbrales numéricos de confianza y de `LIMITAR_BANDA`: se calibran en la Fase 6; aquí se
  declara que son parámetros del perfil, no valores mágicos.
- El catálogo de acciones en sí (ya existe); esto lo anota y corrige, no lo reinventa.

---

## 2. El marco de tres capas

La decisión clasificación→acción **no la toma el modelo** — sería no determinista (viola RNF-03) y
rompería las abstracciones del diseño (la interfaz de análisis devuelve *clase*, no *acción*). Se
resuelve con tres capas separadas:

```
  1. CATÁLOGO ──► qué es técnicamente posible      (existe, genérico, no cambia)
  2. POLÍTICA ──► qué acción propone una alerta     (genérica, determinista)   ── PROPONE
  3. PERFIL   ──► qué está permitido en ESTE cliente (configurable, V3/V4)     ── FILTRA
```

La **política propone** una acción candidata; el **perfil filtra** con tres salidas, y **nunca
descarta en silencio** (RNF-09):

| Salida del filtro | Qué hace |
|-------------------|----------|
| **permite** | La acción sigue tal cual |
| **degrada** | La sustituye por una de menor impacto (cerrar el 443 → bloquear las IP atacantes) |
| **veta y escala** | La retiene para validación humana, con su justificación |

Es lo que hace el prototipo adaptable sin tocar código (RNF-14): dos clientes con el mismo catálogo
y la misma política, distinto perfil, producen decisiones distintas. Cada capa cambia por un motivo
distinto y por eso viven separadas.

---

## 3. La política de decisión (la regla que faltaba)

Una tabla **determinista** indexada por **clase × postura del activo × criticidad**, que devuelve una
acción candidata. La clase sale de
[caso de uso §6](../../../documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md); las
acciones, del [catálogo](../../../documentacion/04-fase4-diseno-de-arquitectura/catalogo-de-acciones.md).

| Clase de la alerta | Acción candidata que **propone** la política | Por qué |
|--------------------|---------------------------------------------|---------|
| **VP · acceso consumado** | `MATAR_CONEXION` de la sesión + `BLOQUEAR_IP` del origen; si persiste, `AISLAR_NODO` | Hay alguien dentro: cortar el acceso vivo primero, contener después |
| **VP · intento de acceso** | `BLOQUEAR_IP` del origen | Contención localizada en el atacante; no toca el servicio |
| **VP · exposición de gestión** | `CERRAR_SERVICIO` o `BLOQUEAR_PUERTO` del servicio mal expuesto | No hay ataque aún: se corrige la configuración que lo permitiría |
| **FP · actividad legítima** | `OBS_*` (registrar) o ninguna | No es amenaza: nada que contener, se deja traza |
| **FP · exposición inexistente** | Ninguna | La postura ya dijo que no hay superficie real |
| **No soportada** | Ninguna → cola manual | Fuera del perímetro, severidad intacta |

Dos ejes modulan la propuesta **antes** de pasar al perfil:

- **La postura del activo** decide si `VP · intento` merece contención o solo observación.
- **La criticidad** ([caso de uso §7](../../../documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md))
  fija la **prioridad** de la orden (para ordenar la cola), no la acción.

**Decisión de diseño (no un detalle):** la política propone **la acción de menor impacto que
resuelve la amenaza**. Nunca propone por su cuenta `REINICIAR_NODO` ni `RESTAURAR_CONFIG` —
remediación de alto impacto que solo llega por escalado humano. Así la degradación del perfil
siempre **baja** el impacto, nunca lo sube, y el peor caso automático está acotado por construcción.

---

## 4. El perfil de cliente (V3/V4, configurable)

Un fichero de configuración versionado, uno por despliegue. Declara dos cosas.

### V4 · Inventario y criticidad

Qué activos hay, cuáles importan, y qué servicios presta cada uno de forma legítima (para juzgar
«esta acción alcanza un servicio del cliente»):

```yaml
activos:
  servidor-web:   { criticidad: alta,    servicios_prestados: [443, 80] }
  cpe-abonado:    { criticidad: media,   servicios_prestados: [] }
  controlador-ot: { criticidad: critica, servicios_prestados: [502] }   # IoT/OT: valor del cliente
```

### V3 · Política de continuidad

Para cada nivel de impacto de una acción (el de RF-17), qué se permite — con excepciones por
servicio:

```yaml
continuidad:
  impacto_ninguno:          automatica
  impacto_localizado:       automatica_si_confianza
  impacto_alcanza_servicio: humano_siempre
  reversibilidad_obligatoria: true    # RF-18
  no_cortar_gestion: true             # RF-19
excepciones:
  - servicio: 443
    activo: servidor-web
    regla: nunca_automatica           # el 443 del banco se degrada, no se corta solo
```

### Cómo lee esto el filtro — el ejemplo del banco de punta a punta

1. La política propone `BLOQUEAR_PUERTO 443` (VP·intento intenso contra el servidor web).
2. El filtro mira el **impacto** de la acción (RF-17: `BLOQUEAR_PUERTO` → `alcanza_servicio`) y la
   **criticidad** del activo (`alta`), y encuentra la excepción del 443 → `nunca_automatica`.
3. **Degrada** a `BLOQUEAR_IP` de los orígenes atacantes (`localizado`, permitido). Si ni eso
   resuelve, **veta y escala** a humano.
4. La traza registra las tres cosas: qué propuso la política, qué vetó el perfil, con qué se quedó.

### RF-18 y RF-19 como precondiciones duras

Van en el perfil como precondiciones, **no** como criterios de escalado:

- `reversibilidad_obligatoria` — una acción sin procedimiento de reversión verificable **no se
  propone**. Fuerza a distinguir en el catálogo (§5) la reversión *auto/transitoria* de la
  *indefinida*.
- `no_cortar_gestion` — una acción que dejaría el activo inalcanzable por el plano de gestión se
  **rechaza antes de evaluar su impacto**: impediría la verificación y la siguiente respuesta (C6).

### Nota metodológica

El perfil usa información privilegiada (sabemos qué presta cada activo porque lo declaramos) para
**filtrar**; el clasificador **no** la recibe — debe inferir. Es la misma separación que en el
dataset de la Fase 3: el ground truth puede saber cosas que el modelo debe deducir.

### Demostración de RNF-14

Para el laboratorio se escriben **dos perfiles de ejemplo** —un operador residencial y uno con
clientes empresariales— y se demuestra que la *misma* alerta produce decisiones distintas. Es una
prueba de adaptabilidad mejor que cualquier afirmación.

---

## 5. Cambios en el catálogo de acciones (RF-17, RF-18, RF-19)

Ediciones a
[catalogo-de-acciones.md](../../../documentacion/04-fase4-diseno-de-arquitectura/catalogo-de-acciones.md).
No es diseño nuevo: propaga lo anterior.

### 5.1 Columna de impacto (RF-17)

Cada acción gana su nivel de impacto, que es lo que el filtro del perfil lee:

| Impacto | Acciones |
|---------|----------|
| `ninguno` | Todas las `OBS_*` |
| `localizado` (en el atacante) | `BLOQUEAR_IP`, `MATAR_CONEXION` |
| `alcanza_servicio` | `BLOQUEAR_PUERTO`, `LIMITAR_BANDA`, `AISLAR_NODO`, `CERRAR_SERVICIO`, `FORZAR_CAMBIO_PASS`, `REINICIAR_NODO`, `RESTAURAR_CONFIG` |

### 5.2 Corregir las dos entradas señaladas por el caso de uso §9

- **`BLOQUEAR_PUERTO`**: hoy «Requiere humano: No». Es incorrecto — cerrar un puerto puede tumbar un
  servicio de producción. Pasa a impacto `alcanza_servicio`; **el perfil decide** (automática solo
  si el puerto es de gestión y no un servicio prestado), no un «No» a secas.
- **`LIMITAR_BANDA`**: «Según umbral» sin umbral. Se fija: impacto `alcanza_servicio`, y el umbral
  concreto es **un parámetro del perfil**, no un valor mágico en el catálogo.

### 5.3 Reversibilidad: distinguir dos casos hoy confundidos (RF-18)

Algunas entradas dicen «reversión: no aplica». Hay que separar:

- **Auto-reversible o transitoria** — `REINICIAR_NODO` («vuelve solo») y `MATAR_CONEXION` (el
  usuario legítimo reconecta). RF-18 se cumple: la reversión existe, no hace falta deshacerla a mano.
- **Reversión indefinida** — acción peligrosa; RF-18 dice que **no se propone**. Ninguna del catálogo
  actual cae aquí, pero la precondición queda escrita para futuras entradas.

### 5.4 `no_cortar_gestion` por acción (RF-19)

`CERRAR_SERVICIO` sobre el propio canal SSH quedaría vetado; `AISLAR_NODO` ya preserva la gestión
por diseño («salvo gestión»). Se anota la precondición en las acciones afectadas.

---

## 6. Cambios en el plan de métricas (RF-20)

Ediciones a
[metricas-y-evaluacion.md](../../../documentacion/04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md).
Las dos métricas de continuidad de
[caso de uso §10](../../../documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md):

- **Acciones disruptivas indebidas** — respuestas de impacto sobre el servicio que se habrían
  ejecutado a partir de una alerta que era falso positivo. Es el daño que el prototipo habría
  causado.
- **Retención correcta** — de esas, cuántas quedaron efectivamente retenidas por la validación
  humana. Mide si la regla del perfil funciona.

Ambas exigen que **cada orden lleve su impacto declarado en la traza** — un añadido pequeño al
contrato de la orden de acción ([flujo §5](../../../documentacion/04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md)),
que también absorbe RF-17.

Razón de medirlas: *un triaje con buen F1 que corta el servicio del cliente es peor que el sistema
al que sustituye.* Sin estas dos métricas el informe no puede demostrar lo contrario.

---

## 7. Trazabilidad requisito → sección

| Requisito | Dónde se cierra |
|-----------|-----------------|
| RF-17 (impacto de cada acción) | §5.1 (catálogo) + §6 (traza) |
| RF-18 (reversión verificable) | §4 (precondición del perfil) + §5.3 (catálogo) |
| RF-19 (no cortar gestión) | §4 (precondición del perfil) + §5.4 (catálogo) |
| RF-20 (métricas de continuidad) | §6 (métricas) |
| RNF-14 (configurar V1–V5) | §2 (marco) + §4 (perfil) |
| Roadmap: reglas de decisión | §3 (política de decisión) |

---

## 8. Artefactos que produce esta revisión

- **Nuevo:** `documentacion/04-fase4-diseno-de-arquitectura/politica-decision-continuidad.md` — el
  marco de tres capas, la política de decisión y el perfil de cliente (§2–§4).
- **Editado:** `catalogo-de-acciones.md` — columna de impacto, corrección de `BLOQUEAR_PUERTO` y
  `LIMITAR_BANDA`, precondiciones RF-18/RF-19 (§5).
- **Editado:** `metricas-y-evaluacion.md` — las dos métricas de continuidad (§6).
- **Editado:** `flujo-triaje-playbook-sandbox.md` — el contrato de la orden de acción gana el campo
  `impacto` (§6).
- **Editado:** el README de la Fase 4 — el estado pasa de «cerrada, con revisión pendiente» a
  «cerrada».

Los umbrales concretos (confianza, `LIMITAR_BANDA`) siguen calibrándose en la Fase 6; esta revisión
solo declara que son parámetros del perfil.

---

## Documentos relacionados

- [Caso de uso acotado §6–10](../../../documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md) — clases, criticidad, niveles de respuesta y política de continuidad de los que esto deriva.
- [Catálogo de acciones](../../../documentacion/04-fase4-diseno-de-arquitectura/catalogo-de-acciones.md) · [Métricas y evaluación](../../../documentacion/04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md) · [Flujo](../../../documentacion/04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md)
- [Requisitos](../../../documentacion/02-fase2-estado-del-arte/requisitos.md) — RF-17 a RF-20, RNF-14.
