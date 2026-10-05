# Vista «Red»: mapa de la red del cliente con eventos por equipo

Fecha: 30/09/2026 · Estado: aprobado en conversación, pendiente de revisión escrita.

## 1. Propósito

El visor enseña decisiones, aprobaciones y trazas como listas. Para un operador (y para la demo al
tutor) falta ver **dónde** pasa cada cosa: por qué cortafuegos entra el atacante, qué activo se
atacó, dónde quedó contenido, qué depende de qué.

La vista «Red» dibuja la red del cliente como un árbol por zonas, colorea cada equipo según su
estado en vivo y, al pulsar un equipo, abre un panel con sus eventos. Así se filtra por equipo de
un vistazo.

**Criterio de éxito.** Con el banco en marcha, tras lanzar A1, D1 y E1, el operador ve:
- la taquilla en ámbar (espera decisión);
- web-banking atacado o contenido;
- fw-core con la contención escalada.

Al pulsar web-banking, sus tres eventos aparecen etiquetados, y «Ver en Decisiones» abre la tabla
ya filtrada.

## 2. Decisiones tomadas (30/09)

| Tema | Decisión |
|---|---|
| Fuente de la red | **El perfil del cliente**, no el fichero de Containerlab: agnóstico al cliente y `prototipo/` no importa `lab/`. |
| Disposición | **Árbol por zonas**: internet arriba, cortafuegos en medio, zonas como cajas. |
| Al pulsar un equipo | **Panel lateral**; el mapa sigue a la vista. |
| Ubicación | **Sustituye a la pestaña Equipos** (pasa a llamarse «Red»). |
| Eventos de un equipo | **Tres relaciones etiquetadas**: objetivo, origen y contuvo aquí. |

## 3. Datos: sección `red` del perfil (opcional)

Sección nueva, **separada de `topologia`**. La contención y la escalada siguen leyendo `topologia`
y no cambian: el mapa es solo presentación.

```yaml
red:
  nodos:                     # equipos que no están en `activos` ni en `topologia`
    internet: { tipo: externo }
    sw-soc:   { tipo: switch }
    auditor:  { tipo: gestion, ip: 10.100.0.20, funcion: "auditor de vulnerabilidades (Nmap)" }
  enlaces:                   # equipo -> equipo del que cuelga (hacia internet)
    fw-edge: internet
    fw-core: fw-edge
    web-banking: fw-core
    # … todos los del banco (ver lab/topologias/banco.clab.yml como referencia al escribirlo)
    sw-soc: fw-core
    mdr-siem: sw-soc
    auditor: sw-soc
  zonas:                     # orden = orden de izquierda a derecha en el mapa
    DMZ:      [web-banking, api-movil, swift-alliance]
    Core:     [middleware, core-db, hsm]
    Sucursal: [taquilla, atm]
    SOC:      [sw-soc, mdr-siem, auditor]
```

- **`tipo` de cada nodo** (para el icono): `externo | cortafuegos | switch | servidor | puesto | gestion`.
  - Si no se declara, se deduce como hoy (`tablero._categoria_equipo`): cortafuegos por rol,
    gestión por función, servidor si presta servicios y puesto en otro caso.
  - `internet` es `externo`.
- **Nodos sin enlace:** van a la zona «Sin ubicar».
- **Perfil sin `red`** (p. ej. `empresarial.yml`): el mapa se construye con lo que haya.
  - Enlaces = `topologia[n].gateway`.
  - Nodos = `activos` ∪ `topologia`.
  - Una única zona «Red» con todo lo que no es cortafuegos.
  - Nunca falla por faltar la sección.
- **Validación**, al cargar el perfil y sin romper:
  - un enlace o una zona que nombra un nodo inexistente produce un aviso y se ignora;
  - un ciclo en `enlaces` se corta, con un aviso.

## 4. API: `GET /api/red`

```json
{
  "nodos": [
    {"nombre": "web-banking", "ip": "10.10.0.10", "tipo": "servidor", "zona": "DMZ",
     "funcion": "banca en linea…", "criticidad": "alta", "servicios_prestados": [443, 80],
     "depende_de": ["middleware"], "salud": "ok|caido|null",
     "actividad": {"objetivo": 3, "origen": 0, "contuvo_aqui": 1, "pendientes": 1,
                   "estado": "pendiente|atacado|contenido|sin_actividad", "ultima": "ISO"}}
  ],
  "enlaces": [["web-banking", "fw-core"]],
  "dependencias": [["web-banking", "middleware"]],
  "zonas": ["DMZ", "Core", "Sucursal", "SOC"]
}
```

- **Datos de entrada.** Se calcula en el backend (`tablero.py`, función pura `estado_red(perfil,
  registros, pendientes, salud)`) a partir de:
  - la traza completa (como `metricas`);
  - la cola de pendientes;
  - la salud del monitor.
- **Registros que cuentan.** Solo los que son decisiones (`_NO_DECISIONES` fuera). Una
  `actividad_suprimida` suma a la última actividad, pero no cuenta como ataque nuevo.

### Relación evento ↔ equipo (un solo sitio: `relaciones(registro, perfil) -> {nombre: [etiquetas]}`)

| Etiqueta | Regla |
|---|---|
| `objetivo` | `registro.activo == nombre` |
| `origen` | la IP de origen del registro coincide con la IP del nodo (`actores._coincide`). Sale de `contexto.origen_ip`, o de la evidencia si el registro es antiguo. |
| `contuvo_aqui` | `escalada.dispositivo_ejecutor` o `mitigacion_agente.dispositivo_ejecutor` es el nodo, o `orden.nodo_objetivo` es el nodo con ejecución y verificación correctas. |

Un evento puede llevar varias etiquetas (p. ej. «objetivo» y «contuvo aquí» si se contuvo en el propio host).

### Estado del nodo (el color)

Se aplica la **primera** regla que se cumple:

| Prioridad | Estado | Condición |
|---|---|---|
| 1 | `caido` | salud ≠ ok (monitor) |
| 2 | `pendiente` | hay en la cola una decisión con este nodo como objetivo u origen |
| 3 | `atacado` | la última decisión con este nodo como **objetivo** es de clase `vp_*` o `amenaza_enrutada` y no quedó contenida (fallida, sin acción o escalada fallida) y el analista no la rechazó |
| 4 | `contenido` | hay alguna contención efectiva como objetivo o contuvo aquí |
| 5 | `sin_actividad` | ninguna de las anteriores |

Para las pendientes, la vista de la cola (`_vista_pendiente`) añade `activo` y `origen_ip` de la
alerta, que hoy se descartan con `alerta`.

**Panel de un equipo.** No necesita endpoint nuevo: el visor filtra `/api/trazas` (ya acotado a 500)
con la misma regla. Para no duplicar la lógica en TypeScript, `_resumen_traza` expone:
- `relaciones`: la lista de nodos con sus etiquetas, calculada por `relaciones()`;
- `contencion` y `dispositivo`: el desenlace legible.

Esto adelanta A10 de la Tanda 2 (`PLAN-TANDAS.md`).

## 5. Visor

**Pestaña «Red»** (sustituye a `Equipos.tsx`; se reutilizan sus estilos y `bits.tsx`):
- **Mapa** (`MapaRed.tsx`): SVG propio, **sin dependencias nuevas** (regla del visor: solo devDeps de test).
  - La disposición la calcula una función pura `disposicion(red) -> {nodo: {x, y}, zonas: [{x, y, w, h}]}`, testeable sin DOM:
    - niveles: externo, cortafuegos en cadena (siguiendo `enlaces`) y zonas;
    - las zonas van en fila en el orden declarado y sus nodos en columna;
    - si hay muchas zonas, se pasa a dos filas.
  - Enlaces como líneas; dependencias como líneas discontinuas, con una casilla para ocultarlas.
  - Colores del estado con su texto o icono (⚠ atacado, ✓ contenido, ⏸ pendiente, ✕ caído), nunca solo el color, y una leyenda arriba.
  - **Accesible:** cada nodo es un `<g role="button" tabindex="0" aria-label="web-banking, atacado">` que responde a Enter y Espacio.
- **Panel lateral** (`PanelEquipo.tsx`):
  - ficha: IP, zona, función, criticidad, servicios y dependencias;
  - contadores (recibidos, originados, contenidos aquí, pendientes);
  - línea de eventos (hora local, etiquetas, origen, clase o familia, desenlace), con las repeticiones suprimidas plegadas;
  - «Ver en Decisiones»: cambia de pestaña con el filtro por equipo puesto.
  - Sin selección: una indicación («Pulsa un equipo para ver sus eventos»).
- **Decisiones** acepta un filtro por equipo, además del texto y la clase, y lo muestra como una etiqueta que se puede quitar.
- **Pantalla estrecha:** el panel pasa debajo del mapa. El mapa escala con `viewBox`, sin scroll horizontal de página.
- **Sondeo:** `/api/red` con el mismo `useSondeo` (2 s), banner de desconexión como el resto.

## 6. Pruebas (TDD)

**Backend** (`prototipo/tests/test_tablero.py` y `test_perfil.py`):
- `red` completa;
- perfil sin `red` (reconstrucción desde `topologia`);
- enlace a un nodo inexistente (aviso, sin romper);
- ciclo en enlaces;
- `relaciones()` con las tres etiquetas y el caso múltiple;
- precedencia de estados (caído > pendiente > atacado > contenido);
- `/api/red` responde;
- `_resumen_traza` expone `relaciones`, `contencion` y `dispositivo`;
- la vista de pendientes expone `activo` y `origen_ip`;
- los valores canónicos no cambian (`test_canonicos`).

**Visor** (Vitest y Testing Library):
- `disposicion()`: posiciones deterministas, zonas en el orden declarado, cadena de cortafuegos, dos filas;
- `MapaRed`: cada estado se pinta con su texto; el clic y el Enter seleccionan;
- `PanelEquipo`: contadores y eventos etiquetados;
- «Ver en Decisiones» aplica el filtro y la etiqueta se puede quitar;
- esquema Zod de `/api/red`.

## 7. Fuera de alcance

- Enlaces descubiertos automáticamente (tráfico, CMDB): el inventario es un dato del perfil (N3 de la conciencia de impacto).
- Mover o arrastrar nodos, o guardar disposiciones.
- Animación del recorrido del ataque.
- Métricas por zona.

## 8. Riesgos

- **El perfil del banco con `red` puede quedar desalineado con el laboratorio.** Se escribe mirando
  `banco.clab.yml` y un test del banco compara ambos, en `lab/banco/tests`: allí sí se puede leer `lab/`.
- **Legibilidad del mapa:** 15 nodos caben en el árbol. Una red mucho mayor necesitaría plegar
  zonas, que queda para después.
