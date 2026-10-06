# Correspondencia servicio↔vulnerabilidad y respuesta dirigida — diseño

**Fecha:** 2026-10-06
**Estado:** propuesta, a la espera de revisión del usuario antes de pasar al plan de implementación.

## Contexto y entendimiento compartido

El MDR ya cumple los requisitos del plan de trabajo. Esta pieza es **perfeccionamiento**
hacia un nivel de producción/comercial, no un requisito nuevo.

Observación del usuario (confirmada en código): el prototipo **ya es consciente del servicio
en la "entrada"**, pero **decide por equipo + IP de origen**. En concreto:

- El servicio existe en el inventario (`activos[x].servicios_prestados` = puertos), en la
  postura del auditor ([postura.py](../../../../prototipo/postura.py): «¿está expuesto *este*
  servicio en *este* activo?»), en las excepciones por `(servicio, activo)` y en el catálogo
  (`CERRAR_SERVICIO`, `BLOQUEAR_PUERTO`).
- Pero [analisis.clasificar](../../../../prototipo/analisis.py) emite una de 4 clases coarse y
  [politica.proponer](../../../../prototipo/politica.py) las traduce, en la práctica del baseline,
  **siempre a `BLOQUEAR_IP`** del origen. Las acciones por servicio cuelgan de clases finas
  (`vp_exposicion_gestion`, `vp_acceso_consumado`) que el clasificador determinista **no llega a
  emitir** (falta de etiquetas finas en el dataset, límite ya documentado). El `servicio` hoy
  solo decide VP/FP (vía postura) y rellena la justificación — **nunca cambia qué acción se toma
  ni cuánto pesa el riesgo**.

### Decisiones ya tomadas (con el usuario)

1. **Prioridad del perfeccionamiento:** correspondencia servicio↔vulnerabilidad + respuesta
   dirigida (incluye criticidad por servicio). Los ataques realistas se añadirán **después**, para
   que cada ataque nuevo tenga una respuesta modelada.
2. **Alcance de la respuesta (conservador):** el servicio cambia la **prioridad/severidad** y la
   **acción recomendada** que ve el analista/agente, pero **la contención automática sigue siendo
   `BLOQUEAR_IP`** del origen, y todo lo que toca un servicio sigue pasando por humano. Coherente con
   `impacto_alcanza_servicio: humano_siempre` del perfil bancario y con un MDR comercial serio.
   Matiz asumido: bloquear la IP del atacante suele ser la acción de **menor** radio de impacto;
   cerrar un puerto/servicio afecta a todos sus clientes legítimos. Por eso no se automatiza.
3. **Fuera de alcance (no-goals):** sin acciones automáticas nuevas por servicio; **sin reetiquetar
   el dataset**; sin clases finas nuevas en el clasificador; sin login en el visor; **sin mover las
   métricas canónicas**.

## Objetivo

Que el servicio sea ciudadano de primera en la **decisión**, de forma **puramente aditiva**:

- **G1** — la criticidad del **servicio atacado** (no solo la del equipo) pondera la prioridad.
- **G3** — un registro de **correspondencia** mapea `(familia [+ servicio])` → una **respuesta
  recomendada** de un conjunto cerrado.
- **G2 (suave)** — esa recomendación se **expone** al humano, al agente, a la traza y al visor,
  **sin cambiar** `accion_final` ni `requiere_humano`.

## Garantía de invariancia de métricas (requisito duro)

Las métricas canónicas no pueden cambiar: recall 1,000; FP 0,000 (eval)/0,009 (todas); escalado
0,297; matriz {174,4,422,0} sobre 600; partición eval {87,2,211,0}, 89/300. Cómo lo protege el diseño:

- **Criticidad por servicio** se calcula con *fallback* a la criticidad del activo. Los perfiles de
  evaluación declaran `servicios_prestados` como **enteros** (sin criticidad por servicio) → la
  criticidad efectiva es idéntica a hoy → `prioridad` idéntica.
- **`recomendacion`** es un campo **nuevo**: no entra en `clase`, `confianza`, `prioridad`,
  `accion_final`, `resultado_filtro` ni `requiere_humano`. No puede mover ninguna métrica.
- El test `evaluacion/tests/test_canonicos.py` debe seguir en verde **sin retocar los números**.
  Es la red de seguridad de todo el trabajo.

## Arquitectura — 3 piezas aditivas

### Pieza 1 — Criticidad por servicio en el inventario (G1)

**Esquema del perfil (retrocompatible).** Hoy `servicios_prestados: [443, 80]` (lista de enteros).
Se admite además la forma de diccionario, mezclable:

```yaml
servicios_prestados:
  - 443                                  # entero → hereda criticidad del activo (como hoy)
  - { puerto: 80,  criticidad: media }
  - { puerto: 22,  servicio: ssh, rol: gestion }
```

Campos del diccionario: `puerto` (obligatorio), `servicio` (nombre opcional, p.ej. `https`),
`criticidad` (opcional; *fallback* a la del activo), `rol` (opcional; p.ej. `gestion`).

**Normalización centralizada en [perfil.py](../../../../prototipo/perfil.py)** (una sola fuente de
verdad para todos los consumidores):

- `servicios_de(perfil, activo) -> list[dict]` — normaliza enteros y dicts a
  `{puerto:int, servicio:str|None, criticidad:str, rol:str|None}`, resolviendo `criticidad` con
  *fallback* a `criticidad_de(perfil, activo)`.
- `puertos_declarados(perfil, activo) -> set[int]` — el conjunto de puertos, construido desde
  `servicios_de`. **Sustituye** el `_declarados` local de [impacto.py](../../../../prototipo/impacto.py)
  y el cálculo equivalente de [inventario.py](../../../../prototipo/inventario.py), para que enteros y
  dicts se traten igual en los dos sitios.
- `criticidad_servicio(perfil, activo, servicio, hallazgos=None) -> str` — criticidad del servicio
  atacado. Emparejamiento: (a) por nombre contra `entry.servicio` (con la traducción de
  [postura._protocolos](../../../../prototipo/postura.py), p.ej. `apache`→`http/https`); si no, (b)
  por puerto, traduciendo nombre→puerto con `impacto.puertos_abiertos` (hallazgos `{puerto:servicio}`);
  si nada empareja, *fallback* a `criticidad_de`.

**Uso:** [analisis.enriquecer](../../../../prototipo/analisis.py) pasa a leer
`criticidad = perfilm.criticidad_servicio(perfil, activo, alerta.get("servicio"), hallazgos)` en vez
de la del activo. El resto de consumidores de criticidad de activo (texto de impacto en
`impacto._motivo_base` para `AISLAR_NODO`, vista «Red», prompt del agente) **no cambian**: ahí la
criticidad del **nodo** es lo correcto (la acción toca el nodo, no el servicio atacado).

**Validación:** [perfil.validar](../../../../prototipo/perfil.py) añade avisos no fatales si un dict de
`servicios_prestados` no trae `puerto`, o si `criticidad` no está en el vocabulario
(`baja|media|alta|critica`). Nunca lanza (como el resto de `validar`).

### Pieza 2 — Registro de correspondencia servicio↔amenaza (G3)

**Dato nuevo:** `prototipo/correspondencia.yml`. Mapea por **familia** (agnóstico del SIEM, como
[familias.yml](../../../../prototipo/familias.yml)), con afinamiento opcional por **servicio**:

```yaml
# respuesta ∈ {contener_origen, endurecer_servicio, enrutar, observar}
por_familia:
  acceso_credenciales:  { respuesta: contener_origen }
  reconocimiento:       { respuesta: contener_origen, nota: "escaneo: bloquear/monitorizar el origen" }
  servicio_expuesto:    { respuesta: endurecer_servicio, nota: "exposición del servicio: cerrar/endurecer o quitar la exposición" }
  explotacion_conocida: { respuesta: enrutar, ruta: appsec }
# afinamiento por nombre de servicio (opcional; prevalece sobre la familia)
por_servicio:
  rdp:   { respuesta: endurecer_servicio, nota: "RDP expuesto: alto riesgo, cerrar o tras VPN" }
  smb:   { respuesta: endurecer_servicio, nota: "SMB no debería estar expuesto en el borde" }
  telnet:{ respuesta: endurecer_servicio, nota: "telnet en claro: desactivar, migrar a SSH" }
```

**Módulo nuevo `prototipo/correspondencia.py`:**

- `cargar(ruta=<correspondencia.yml junto al módulo>) -> dict` (como `catalogo.cargar_catalogo`).
- `recomendar(familia, servicio, clase, expuesto, registro) -> dict|None` — devuelve el objeto
  `recomendacion` (abajo) o `None` cuando no hay nada que recomendar (FP / no_soportada).
  Resolución: parte de `por_familia[familia]`, lo refina con `por_servicio[servicio]` si existe, y
  traduce `respuesta` → `accion_sugerida` con el mapa por defecto (abajo), salvo override explícito.

**Objeto `recomendacion`** (lo que se guarda y se expone):

```python
{
  "respuesta": "contener_origen" | "endurecer_servicio" | "enrutar" | "observar",
  "accion_sugerida": <id de catálogo | None>,   # BLOQUEAR_IP / CERRAR_SERVICIO / None
  "ruta": <ruta lógica | None>,                 # p.ej. "appsec" para enrutar
  "servicio": <nombre del servicio atacado | None>,
  "nota": <frase corta para el analista>,
}
```

**Mapa por defecto `respuesta → accion_sugerida`:**

| respuesta | accion_sugerida | significado |
|---|---|---|
| `contener_origen` | `BLOQUEAR_IP` | bloquear al atacante (coincide con la acción automática de hoy) |
| `endurecer_servicio` | `CERRAR_SERVICIO` | cerrar/endurecer el servicio atacado (siempre humano) |
| `enrutar` | `None` | encaminar a una cola (appsec/parcheo), sin contención |
| `observar` | `None` (OBS_*) | solo observar/monitorizar |

En el caso común (`vp_intento_acceso`, atacante externo) `recomendacion.accion_sugerida` =
`BLOQUEAR_IP` = `accion_final`: **coinciden**, no hay contradicción. El valor aparece cuando divergen:
`servicio_expuesto` sobre un servicio expuesto no-gestión → recomendación «cerrar el servicio X»,
mientras `accion_final` sigue siendo `BLOQUEAR_IP` + humano. Eso es exactamente la recomendación
dirigida que se quería mostrar.

### Pieza 3 — Exponer la recomendación (G2 suave)

- **[triaje.procesar](../../../../prototipo/triaje.py):** tras `clasificar`, calcula
  `recomendacion = correspondencia.recomendar(alerta.familia, alerta.servicio, clas.clase,
  (ctx.postura or {}).get("expuesto"), registro)` y lo mete en `analisis_out`. El registro se carga
  una vez (como el catálogo) y se pasa a `procesar` (parámetro con *default*), para no leer disco por
  alerta. Para el daemon, se carga en el arranque de [stream.py](../../../../prototipo/stream.py).
- **[traza.construir](../../../../prototipo/traza.py):** `recomendacion` viaja dentro de
  `analisis_out` y queda en el registro de decisión y en la cadena de la traza. Campo nuevo y opcional:
  las cadenas existentes siguen válidas.
- **[tablero.py](../../../../prototipo/tablero.py):** la serialización de decisiones (`_resumen_traza`
  y el detalle de traza) expone `recomendacion`.
- **Visor:** `DecisionSchema` en [api.ts](../../../../visor/src/api.ts) añade
  `recomendacion` (objeto nullable opcional, validado con Zod). Se muestra en la tarjeta de decisión
  ([Decisiones.tsx](../../../../visor/src/components/Decisiones.tsx)) y, sobre todo, en la de
  aprobación ([Aprobaciones.tsx](../../../../visor/src/components/Aprobaciones.tsx)): «Recomendado:
  cerrar el servicio https (nota) — acción a ejecutar: BLOQUEAR_IP (humano)». Sin dependencias nuevas.

## Flujo de datos (de punta a punta)

```
alerta (familia, servicio, activo, origen_ip)
  └─ analisis.enriquecer → ctx {postura(expuesto), criticidad:=criticidad_servicio(servicio), ...}
       └─ analisis.clasificar → {clase, prioridad:=_priorizar(clase, criticidad_servicio), confianza}
            └─ politica.proponer → (accion_final, params)            # SIN CAMBIOS: BLOQUEAR_IP / humano
            └─ correspondencia.recomendar(familia, servicio, clase, expuesto) → recomendacion  # NUEVO
       └─ perfil.filtrar → resultado_filtro, requiere_humano          # SIN CAMBIOS
  └─ traza.construir(..., analisis_out{+recomendacion}, contexto) → registro encadenado
       └─ tablero (API) → visor (tarjeta de decisión / aprobación)
```

Dos entradas por servicio alimentan el resultado: `criticidad_servicio` sube la **prioridad**;
`recomendar` produce la **recomendación**. `accion_final` y `requiere_humano` quedan intactos.

## Casos límite y manejo de errores

- **Alerta sin `servicio`** o `servicio == "desconocido"`: `criticidad_servicio` cae al *fallback*
  del activo; `recomendar` usa solo la familia (sin afinamiento por servicio). Igual que hoy.
- **`servicios_prestados` con dict sin `puerto`:** `servicios_de` lo ignora para el conjunto de
  puertos y `perfil.validar` avisa. No rompe el cruce con el auditor.
- **Puerto como texto** (`"80"`): se normaliza con `impacto.como_puerto` (ya existe), reutilizado por
  `servicios_de`.
- **Familia ausente del registro** (no_soportada) o **clase sin amenaza** (FP): `recomendar`
  devuelve `None`; el visor no muestra bloque de recomendación.
- **Perfil con `servicios_prestados` de enteros** (los actuales): comportamiento **idéntico** a hoy
  (criticidad heredada, mismos puertos declarados).
- **Nombre↔puerto sin hallazgos:** si no hay auditor, `criticidad_servicio` solo puede emparejar por
  nombre (`entry.servicio`); si tampoco, *fallback* al activo. Nunca inventa.

## Estrategia de pruebas (TDD)

- **Red de seguridad primero:** `test_canonicos.py` en verde sin tocar números (se corre al inicio y
  al final de cada tarea del plan).
- **perfil:** `servicios_de`/`puertos_declarados` normalizan entero y dict igual; `criticidad_servicio`
  empareja por nombre, por puerto (vía hallazgos) y cae al activo; `validar` avisa de dict sin puerto y
  criticidad fuera de vocabulario.
- **impacto/inventario:** `_declarados`/`reconciliar` dan el mismo conjunto para `[443,80]` y para
  `[{puerto:443},{puerto:80}]` (no-regresión del cruce con el auditor).
- **correspondencia:** `recomendar` resuelve familia, afina por servicio, mapea `respuesta→accion_sugerida`,
  respeta overrides, y devuelve `None` en FP/no_soportada.
- **analisis:** un golpe a un servicio `critica` sube la prioridad por encima del mismo golpe a un
  servicio `baja` en el mismo activo; sin criticidad por servicio, prioridad idéntica a hoy.
- **triaje/traza:** el registro de decisión incluye `recomendacion`; la cadena de traza sigue válida
  (`traza.verificar`).
- **tablero/visor:** la API expone `recomendacion`; `DecisionSchema` la valida; la tarjeta de aprobación
  la muestra (vitest). `tsc`/`lint`/`build` en verde.

## Descomposición orientativa (para el plan)

1. `perfil.servicios_de` / `puertos_declarados` / `criticidad_servicio` + validación, y migrar
   `impacto`/`inventario` a `puertos_declarados` (retrocompat probada).
2. `analisis.enriquecer` usa `criticidad_servicio` (prioridad ponderada por servicio).
3. `correspondencia.yml` + `correspondencia.py` (`cargar`, `recomendar`).
4. Cableado en `triaje.procesar` y carga única en `stream.py`; `recomendacion` en la traza.
5. `tablero` expone `recomendacion`; visor (`api.ts` + tarjetas) la muestra.
6. Cierre: 5 suites + visor en verde, `test_canonicos` intacto, revisión de rama.

## Contenido a confirmar por el usuario

El **contenido** de `correspondencia.yml` (qué servicios de alto riesgo, qué respuesta para cada uno)
es un borrador con valores sensatos. Puntos a validar antes de implementar:

- El conjunto cerrado de `respuesta` (`contener_origen`, `endurecer_servicio`, `enrutar`, `observar`)
  y su mapa a acciones de catálogo.
- Los servicios del borrador `por_servicio` (rdp, smb, telnet) y si quieres añadir otros (sql, http…).
- Que la recomendación se muestre **también** en la tarjeta de decisión, no solo en la de aprobación.
