# Políticas: Resumen en tres columnas e intocables sin pestaña — plan de implementación

> **Para agentes:** sub-skill obligatoria: superpowers:executing-plans (ejecución en esta sesión, como
> pidió el usuario). Los pasos usan casillas (`- [ ]`).

**Objetivo:** la pestaña Resumen de Políticas cuenta la política en tres columnas (solo / espera a un
analista / nunca solo); la pestaña Intocables desaparece y sus servicios llevan un candado en la fila de
su equipo.

**Arquitectura:** lógica pura nueva en `visor/src/politicas.ts`, a partir de los datos que ya sirve
`/api/politica`. `Politicas.tsx` solo pinta. El backend gana un campo: `funcion` en cada intocable.

**Tecnologías:** Python (stdlib, unittest); React + TypeScript + Zod + vitest.

**Spec:** [diseno-politicas-resumen-intocables.md](diseno-politicas-resumen-intocables.md)

## Restricciones globales

- No cambia el motor ni la política: solo cómo se enseña.
- El texto de `mdr explicar-politica` no se quita: va a un desplegable «Ver la política en texto».
- Sin la línea «respuestas que solo observan».
- Un intocable sin zona sale igualmente en la columna ámbar del Resumen.
- Una familia sin nombre legible sale con su identificador.
- Pestañas: `Resumen · Por tipo de ataque · Por zona y dispositivo · Confianza` (sin «Intocables»).

## Revisión: lo que más puede fallar

1. Una familia o una acción desconocidas: no deben romper la vista. Salen con su identificador.
2. Un servicio anterior sin `intocables`, `confianza` o `funcion`: la vista se pinta igual.
3. Un intocable cuyo equipo no está en ninguna zona: sigue en el Resumen.
4. Zona protegida: sus filas también muestran el candado.
5. Sin ninguna familia en automático: la columna verde dice «Nada, todo pasa por un analista».

---

### Tarea 1: `funcion` en los intocables (backend)

**Ficheros:** modificar `prototipo/servicio/tablero.py` (el bloque de `est["intocables"]`). Prueba en
`prototipo/tests/test_tablero.py`.

**Interfaces:** produce `intocables: [{activo, servicio, origen, funcion}]`. `funcion` es la de
`perfil.activos[activo].funcion`, o `None`.

- [ ] Prueba `test_intocables_dicen_que_es_el_equipo`: con un perfil cuyo activo `db` tiene
  `funcion: "base de datos"` y la excepción `{activo: db, servicio: 5432, regla: nunca_automatica}`,
  `politica_estado` (o `GET /api/politica`) devuelve `intocables[0]["funcion"] == "base de datos"`. Un
  activo sin función da `None`.
- [ ] Ver que falla, implementarlo, ver que pasa. Commit.

### Tarea 2: lógica pura `visor/src/politicas.ts`

**Ficheros:** crear `visor/src/politicas.ts` y `visor/src/politicas.test.ts`. Añadir `funcion` (opcional
y nulable) al esquema de intocables en `visor/src/api.ts`.

**Interfaces que produce:**
- `nombreFamilia(f: string): string`. Tabla de las 10 familias; si no está, el identificador.
  - `acceso_credenciales` → «Fuerza bruta»
  - `reconocimiento` → «Reconocimiento (escaneo)»
  - `servicio_expuesto` → «Servicio expuesto»
  - `acceso_consumado` → «Intrusión consumada»
  - `explotacion_conocida` → «Explotación conocida»
  - `abuso_de_cuenta` → «Abuso de cuenta»
  - `integridad_fichero` → «Cambios en ficheros vigilados»
  - `denegacion_servicio` → «Denegación de servicio»
  - `exfiltracion` → «Exfiltración / C2»
  - `malware` → «Malware»
- `accionEnPalabras(accion?: string | null, ruta?: string | null): string`. Si no está en la tabla, la
  acción tal cual; sin acción, «sin acción».
  - `BLOQUEAR_IP` → «bloquea el origen»
  - `MATAR_CONEXION` → «corta la sesión abierta»
  - `BLOQUEAR_PUERTO` → «cierra el puerto»
  - `AISLAR_NODO` → «aísla el equipo»
  - `LIMITAR_BANDA` → «limita la banda»
  - `FORZAR_CAMBIO_PASS` → «bloquea la cuenta»
  - `BLOQUEAR_DESTINO` → «corta el destino»
  - sin acción y con ruta → «se tría y se enruta»
- `type Item = { titulo: string; detalle?: string }`
- `resumenPolitica(est: PoliticaEstado): { frase: string; solo: Item[]; humano: Item[]; nunca: Item[]; certeza: number | null; confianza: string | null }`. Columnas según
  `automatizacion_efectiva`:
  - **solo:** `automatica` o `automatica_si_confianza`. Ítem: nombre de la familia y la acción en palabras.
  - **nunca:** `nunca_automatica`, más el ítem fijo «Cortar la conexión del MDR con los equipos» (detalle
    «el canal de gestión»).
  - **humano:** el resto de familias, en este orden y después de ellas:
    - «Bloquear un equipo propio», si `confianza.equipos_propios !== "automatica_si_confianza"`;
    - cada intocable: título `activo · funcion` (solo `activo` si no hay función), detalle
      `puerto N`;
    - «Alertas que no reconoce, de nivel N o más» (detalle «a revisión, sin acción»), si
      `revisar_desde_nivel != null`.

  `frase`: «De N tipos de ataque, el MDR contiene X solo (si está seguro), deja Y a un analista y Z nunca
  los toca solo. Todo lo que hace se puede deshacer.» (`N` = familias; `X`, `Y` y `Z` cuentan solo
  familias.) `confianza`: «Se fía de A, B (administradores) salvo ráfaga de R alertas en S s», o `null`
  sin administradores.
- `intocablesDe(est: PoliticaEstado, activo: string): (number | string)[]`: los puertos intocables de un
  equipo.

- [ ] Pruebas, con los datos del perfil bancario del 18/11 como en el mockup:
  - la frase da «De 10 tipos de ataque, el MDR contiene 4 solo… deja 1… y 5 nunca»;
  - `solo` contiene «Fuerza bruta» con «bloquea el origen»;
  - `humano` contiene «core-db · base de datos del core bancario» con «puerto 1521», y el de un equipo
    sin zona;
  - `nunca` acaba en «Cortar la conexión del MDR con los equipos»;
  - una familia `nueva_x` sale como «nueva_x»;
  - con `confianza` e `intocables` ausentes no rompe;
  - sin automáticas, `solo` está vacío;
  - `intocablesDe(est, "core-db")` da `[1521]`.
- [ ] Ver que fallan, implementar, ver que pasan. Commit.

### Tarea 3: la vista

**Ficheros:** modificar `visor/src/components/Politicas.tsx` (y `Politicas.css` si hace falta) y
`visor/src/components/Politicas.test.tsx`.

**Consume:** las funciones de la Tarea 2.

- [ ] Pruebas en `Politicas.test.tsx`:
  - pestañas = `["Resumen", "Por tipo de ataque", "Por zona y dispositivo", "Confianza"]` (sin
    «Intocables»);
  - el Resumen muestra las tres columnas por su encabezado («Lo contiene solo», «Espera a un analista»,
    «Nunca lo hace solo»), la frase y el ítem de db01;
  - un desplegable «Ver la política en texto» que, al abrirlo, muestra las frases de
    `getPoliticaExplicar`;
  - los enlaces «Ver Confianza →» y «Ver cada tipo de ataque →» cambian de pestaña;
  - en «Por zona y dispositivo», la fila de un equipo con intocable muestra «puerto 5432: siempre con
    analista».

  Se adaptan o quitan las pruebas de la pestaña Intocables, y su caso de «equipos propios» pasa al
  Resumen.
- [ ] Ver que fallan, implementar (las columnas con el estilo del mockup A: borde superior verde, ámbar o
  rojo; el candado como icono SVG `Lock` de lucide), ver que pasan. Suite del visor, lint (sin
  advertencias nuevas) y `npm run build`. Commit.

### Tarea 4: documentación

- [ ] Manual de usuario y de producción: la sección de Políticas (pestañas, Resumen y candados) y sus PDF
  (`generar-pdf/generar.sh`).
- [ ] CHANGELOG.
- [ ] Prototipo completo en verde. Commit.
