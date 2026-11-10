# Diseño — Editor de políticas de respuesta en el visor

> **Estado (10/11/2026): implementado** el 03/11/2026 (commits `ffb6752` → `c7b073e`; retoques de estilo
> el 04/11). Es la vista «Políticas de respuesta» del grupo Configurar: solo puede **quitar** automatización
> respecto al perfil, nunca añadirla; los cambios van a un overlay auditado (`politica-operativa.yml` y
> `politica-auditoria.jsonl`, junto a la traza). Plan de implementación en la
> [Fase 5](../05-fase5-implementacion-del-prototipo/plan-editor-politicas-respuesta.md). Lo que sigue es el
> diseño tal como se acordó antes de implementarlo.

> Documento de diseño (previo al plan de implementación). Recoge lo acordado en la fase de
> exploración para que un implementador pueda planificarlo sin volver a preguntar. Lo que queda a
> criterio del implementador está marcado como tal.
>
> Mockup de referencia (converge el diseño visual): el panel «Políticas» con dos vistas + nota de
> interferencia. Es un prototipo desechable, no la implementación.

## 1. Contexto y por qué

Hoy la postura de automatización del MDR se configura en **dos sitios**: el perfil del cliente
(`prototipo/perfiles/<cliente>.yml`, bloque `continuidad` + `excepciones` + `actores`) y, para el mapa
clase→acción, el código (`prototipo/motor/politica.py`). La vista «Políticas» del visor ya muestra ese
playbook **en solo lectura** (`prototipo/servicio/tablero.py::politica_resumen`).

Queremos convertir esa vista en una **superficie editable**, al estilo de las *response policies* de los
MDR comerciales, para que el operador del SOC pueda **ver y ajustar qué tipos de ataque y qué
zonas/dispositivos tienen contención automática y cuáles exigen aprobación humana**, con transparencia
del impacto (radio de cascada) y **sin poder debilitar nunca los frenos de seguridad**.

Nota de alcance: esto **reabre el desarrollo del visor más allá de v1.4** (antes cerrado «salvo consejo
del tutor»). Es una decisión explícita del usuario que impulsa esta funcionalidad.

## 2. Objetivos

- Vista «Políticas» **editable** con **dos lentes** sobre la misma decisión:
  - **Por tipo de ataque (familia):** interruptor AUTO / HUMANO por familia.
  - **Por zona y dispositivo:** postura por defecto por **zona** (DMZ/Core/Sucursal/SOC) con **override
    por dispositivo** (hereda / auto / humano).
- **Nota de interferencia** en cada vista que avise de que la efectiva depende también de la otra
  dimensión (opción «a» del mockup).
- Información **de solo lectura** del impacto: acción de mitigación, dónde se ejecuta y **radio de
  cascada** real (reusa `motor/impacto.afectados_en_cascada`), con un **aviso honesto de cascada
  posiblemente incompleta** (heurística: un activo sin `depende_de` ni dependientes puede tener
  dependencias no declaradas; el caso K3 del `atm` lo ilustra). Es un **límite del inventario rotulado
  como tal, no una detección** (la dependencia real del `atm` vive en el laboratorio, no en el perfil).
- **Gobernanza:** editar exige el **token de operador** ya existente; cada cambio queda **auditado**
  (quién, qué, antes→después, cuándo).
- **Persistencia** en una **copia operativa** del perfil; el perfil canónico queda congelado.

## 3. No-objetivos y anti-objetivos

- **No** editar las cadenas de comando del catálogo (`catalogo.yml`) desde el visor. La frontera de
  privilegio (el sudoers por dispositivo se deriva del catálogo) sigue gobernada por git + re-aprovisionamiento.
  Un catálogo editable desde la web sería una vía de escalada de privilegio y crearía deriva con el sudoers real.
- **No** permitir poner en AUTO una acción **destructiva** (`AISLAR_NODO`, `LIMITAR_BANDA`,
  `BLOQUEAR_DESTINO`, `FORZAR_CAMBIO_PASS`, `REINICIAR_NODO`): el freno duro `nunca_automatica` del
  catálogo es **absoluto** y el editor no lo puede levantar.
- **No** tocar el perfil canónico de evaluación ni las cifras congeladas (recall 1.0 / FP 0.009, n=300).
- **Anti-objetivo:** una configuración que pueda **debilitar silenciosamente** la seguridad (p. ej.
  auto-contener un activo propio, cortar el plano de gestión, o automatizar algo irreversible). Si eso
  fuera posible, la funcionalidad sería un fracaso aunque «funcione».
- **Fuera de alcance ahora (futuro):** la **matriz combinada familia × zona** (opción «b» del mockup).
  El motor ya la soporta; añadirla luego es barato.

## 4. Restricciones

- Python: **stdlib + PyYAML**, sin dependencias nuevas.
- Visor: stack actual (React/TS/Vite/Zod/shadcn/Tailwind), sin dependencias nuevas.
- **Offline / sin egreso** (RNF-01).
- **Aditivo al motor:** con las claves nuevas **ausentes**, el comportamiento es idéntico al de hoy →
  la evaluación canónica no se mueve.
- No tocar el núcleo determinista de decisión salvo para **añadir compuertas que solo endurecen**
  (nunca que relajen).

## 5. Modelo de decisión (lo decidido)

Las dos vistas son **dos lentes sobre la misma decisión** (auto vs humano para un incidente concreto,
que tiene a la vez una **familia** y un **activo** afectado en una **zona**).

**Regla de composición: gana la más restrictiva.** La respuesta es automática **solo si TODAS** las
compuertas lo permiten. Es un *Y lógico* de permisos, coherente con cómo el motor ya compone sus
compuertas en `motor/perfil.filtrar` (continuidad por impacto, `nunca_automatica`, política de actores,
`excepciones` por activo, `no_cortar_gestion`, umbral): cada una solo puede **degradar a humano**,
ninguna puede subir a auto.

Las dos vistas nuevas son **dos compuertas más** dentro de ese mismo modelo:

```
efectiva(incidente) = la más restrictiva de:
    postura por familia            (nueva)
    postura por zona del activo    (nueva)
    override por dispositivo        (nueva, endurece sobre la zona)
    + TODAS las compuertas actuales (continuidad, nunca_automatica, actores,
      excepciones, no_cortar_gestion, umbral)
```

- `auto` en estas posturas significa «auto **si confianza ≥ umbral**», sujeto a la lógica de impacto
  existente. **Nunca** levanta un freno: una acción `nunca_automatica` sigue en humano aunque familia y
  zona digan auto.
- `override` por dispositivo: `hereda` (usa la zona) | `auto` | `humano`. Solo tiene sentido endurecer o
  igualar; relajar por dispositivo está acotado por los frenos igual que todo lo demás.
- La zona SOC (`no_cortar_gestion`) es **protegida**: no se configura.

## 6. Cambios en el motor (aditivos)

**Nuevas claves opcionales del perfil** (nombres propuestos; el implementador los confirma):

```yaml
automatizacion_por_familia:        # override por tipo de ataque
  reconocimiento: humano           # ausente = sin override (comportamiento de hoy)
politicas_por_zona:                # postura por defecto por zona (zonas de red.zonas)
  Core: { automatizacion: humano }
overrides_por_activo:              # endurece sobre la zona
  atm: { automatizacion: humano }
```

- **Integración:** `filtrar`/`_filtrar_reglas` reciben hoy `activo` y `servicio`, **pero NO la
  familia/clase**, y no se puede derivar de `accion_id` (es muchos-a-uno). Hay que **añadir un
  parámetro opcional `familia=None`** a `filtrar` (default que preserva el comportamiento) y pasarlo
  desde `triaje.procesar` (la familia está en `triaje.py:41`). La compuerta por zona resuelve la zona
  del activo desde `red.zonas`. Ver la resolución completa en la sección 12.
- **Default-ausente = sin efecto.** Tests deben fijar que, sin las claves nuevas, la salida de
  `filtrar` es idéntica (y los conteos de evaluación no cambian).
- **Los frenos duros se evalúan igual y mandan:** el guard de `nunca_automatica`
  (`perfil.py:271`), `no_cortar_gestion`, `reversibilidad_obligatoria`, actores y umbral siguen
  actuando después, sin cambios.

## 7. Backend (`prototipo/servicio/tablero.py`)

- **`GET /api/politica`:** devuelve la postura efectiva por familia **y** la estructura
  **zona → dispositivos** (postura por defecto + overrides) con el **radio de cascada** por activo
  (`impacto.afectados_en_cascada`) y el aviso de cascada posiblemente incompleta. **Esto cambia la
  forma de la respuesta de array a objeto** (hoy `politica_resumen` devuelve una lista y `getPolitica`
  usa `pedirLista`): hay que **reestructurar** el endpoint y el contrato del componente, no solo
  «ampliarlo». GET cubierto por el `_auth_ok` actual.
- **`POST /api/politica` (nuevo, autenticado):** aplica un cambio de postura (familia, zona o
  dispositivo). **Hay que AÑADIR `/api/politica` a la allow-list de rutas POST (`tablero.py:970`) y
  colocar su `if` ANTES de la caída genérica (`tablero.py:1064-1071`)**, que trata cualquier ruta
  permitida no manejada como resolución de una decisión pendiente. Autenticación con el token de
  operador (`resolver_operador`/`operador_de`, `tablero.py:792-807`): **ojo, hoy el token es OPCIONAL**
  (#6) — este endpoint es **fail-closed**: responde 403 si no hay token + mapa `operadores` configurado,
  para que el «quién» de la auditoría sea real y no falseable (opt-in de laboratorio por variable de
  entorno, al estilo `TRIAJE_SSH_MODO=password`). Flujo: validar el cambio (familia/zona/activo
  conocidos; **rechazar** poner en auto cualquier acción `nunca_automatica`) → `perfil.validar` →
  escribir a la **copia operativa** → **registrar auditoría**.
- **Persistencia — copia operativa:** el daemon carga el perfil canónico y, **si existe**, una capa
  operativa (p. ej. `perfiles/<cliente>.operativo.yml` o un fichero de overlay en `run/`). El canónico
  (`bancario.yml`) **no se escribe nunca** desde el visor. (El implementador decide: overlay separado
  que se fusiona al cargar, vs. copia completa.)
- **Auditoría (no repudio, #8):** registro **append-only** de `{operador, objetivo (familia/zona/activo),
  antes, después, timestamp}`. Reusar el patrón de registros encadenados `actualizacion_caso`
  (`casos.py`) o un log dedicado; el implementador decide.

## 8. Visor (`visor/src/components/Politicas.tsx`)

- Pasar la vista de **solo-lectura a editable**, con un **conmutador de dos pestañas** (Por tipo de
  ataque / Por zona y dispositivo) y la **nota de interferencia** en cada una.
- Controles: segmento AUTO/HUMANO por familia; postura por zona; override (hereda/auto/humano) por
  dispositivo. Las acciones destructivas se muestran con el interruptor **bloqueado** y la razón
  («freno duro»). El panel de detalle muestra, en solo lectura, la acción de mitigación, dónde se
  ejecuta, reversibilidad, **cascada** y, en joyas de la corona, por qué escala al borde.
- `visor/src/api.ts`: schemas Zod (ampliar el de `/api/politica`; **declararlos**, el schema no tiene
  `.passthrough()`) + `getPolitica` (ampliar) + `actualizarPolitica` (POST con token).
- Reusar `useSondeo`, `bits.tsx`, `ClaseBadge`/`etiquetaClase`, patrón de otras vistas. Navegación por
  el `useState<Vista>` existente, sin router nuevo.

## 9. Protección de lo congelado

- La evaluación (`evaluacion/`) sigue usando el **perfil canónico**; la copia operativa es aparte.
- Claves nuevas ausentes ⇒ comportamiento idéntico ⇒ cifras canónicas intactas. Un test lo fija.

## 10. Qué queda a criterio del implementador

- Nombres exactos de las claves del perfil y si la política por zona se pliega en `continuidad` o es un
  mapa aparte.
- Mecanismo exacto de la copia operativa (overlay fusionado vs copia completa) y su ruta.
- Almacenamiento exacto de la auditoría (reusar `actualizacion_caso` vs log dedicado).
- Forma exacta de los endpoints y de los schemas Zod.
- Plan TDD (tests **RED** primero): composición «gana la más restrictiva»; **absolutismo de los frenos
  duros** (destructivo nunca pasa a auto); **ausencia de claves = sin cambio** (y conteos de evaluación
  iguales); autenticación y auditoría del POST; componentes del visor (render, toggles, bloqueo de
  destructivas, nota de interferencia).

## 11. Verificación (antes de dar por hecho)

- Suites Python tocadas en verde (motor + `test_tablero`) y **conteos canónicos sin regresión**.
- Gate del visor: `cd visor && npm run typecheck && npx vitest run && npm run build`.
- Humo: daemon `--web`, abrir «Políticas», cambiar una postura con token, ver la efectiva **al
  instante** (en vivo, sin reiniciar); luego reiniciar el daemon y confirmar que el cambio **persiste**
  en la copia operativa y aparece en la **auditoría**; confirmar que el `bancario.yml` canónico no cambió.

## 12. Resolución de la revisión de diseño (huecos cerrados contra el código)

Una revisión independiente contra el código real cerró estos puntos; el plan los sigue:

- **P1 · Cómo llega la familia a `filtrar`.** `filtrar`/`_filtrar_reglas` NO reciben familia/clase hoy,
  y no se puede derivar de `accion_id` (`ACCION_POR_CLASE` es muchos-a-uno). **Resolución:** añadir un
  parámetro **opcional `familia=None`** a `filtrar`, con default que preserva el comportamiento, y
  pasarlo desde `triaje.procesar` (`triaje.py:22`; la familia está en `:41`). La compuerta por familia
  solo actúa si se pasa la familia **y** el perfil trae `automatizacion_por_familia`. Los ~60 call
  sites sin el parámetro siguen igual.
- **P2 · En vivo, no en frío.** El edit se aplica **en vivo** (el perfil es un objeto compartido
  lazo↔web). Para evitar la **carrera de hilos**, no se muta el dict en sitio: se construye el perfil
  fusionado, se valida y se **reemplaza atómicamente la referencia** compartida (lazo y servidor leen
  de un único contenedor que se intercambia). El GET refleja el cambio al instante.
- **P3 · La capa operativa NO contamina la evaluación.** El overlay se fusiona **solo en el arranque
  del daemon** (`stream.main`, tras `perfilm.cargar`), **nunca dentro de `cargar`**. El lote de
  evaluación (`triaje_lote.py:18`) llama a `cargar` directo → nunca ve el overlay → cifras canónicas
  intactas. Un test lo fija.
- **P4 · El «hueco de inventario» es un límite honesto, no una detección.** `afectados_en_cascada`
  solo lee `depende_de`; la dependencia real no declarada del `atm` vive en `lab/banco/red.py`, que el
  daemon no carga. Se rotula como **heurística** («activo sin `depende_de` ni dependientes → su cascada
  podría estar incompleta»), no se promete detectar huecos.
- **P5 · Vocabulario y forma de las claves.** Forma **uniforme** para las tres dimensiones:
  `{ automatizacion: <valor> }`, usando el **enum del motor** (`automatica_si_confianza` |
  `humano_siempre`), sin vocabulario nuevo. La UI muestra AUTO/HUMANO y mapea a esos valores.
- **Forma del GET.** Cambia de array a objeto (`{ familias: [...], zonas: [...] }`): reestructurar
  endpoint + schema Zod (sin `.passthrough()`, declarar cada campo) + `Politicas.tsx`.
- **Colocación de la compuerta.** Solo **degrada**, y se evalúa de modo que los **frenos duros sigan
  mandando después** (`nunca_automatica` `perfil.py:271`, `no_cortar_gestion`, fail-closed de
  AISLAR/LIMITAR_BANDA/BLOQUEAR_DESTINO `perfil.py:278-331`). Tests de «solo endurece».
- **Zona de un activo fuera de `red.zonas`.** Un activo sin zona (p. ej. `objetivo-vuln` de los tests)
  **no recibe compuerta de zona**: cae al resto de compuertas como hoy (default seguro, sin efecto nuevo).
- **Default-ausente = sin efecto.** Test que fija salida idéntica de `filtrar` y conteos de evaluación
  sin las claves nuevas.
- **Gobernanza real.** El POST es **fail-closed**: sin token + mapa `operadores` configurado se rechaza
  (403), para que la auditoría de no repudio sea real.
