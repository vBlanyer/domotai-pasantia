import type { Red, Decision, NodoRed } from "@/api"

// Medidas del mapa en unidades del viewBox del SVG (escala con el ancho disponible).
export const DIM = {
  nodoAncho: 118, nodoAlto: 26, pasoCadena: 50, zonaHueco: 14, porFila: 4, margen: 16,
  // árbol: carril de orígenes, ramas (zonas) en fila y hojas (equipos) colgando de cada rama
  carrilAlto: 46, ramaAncho: 136, ramaAlto: 26, hojaAncho: 120, hojaAlto: 30, pasoHoja: 40,
  colAncho: 180, espina: 16, hojaDesplaz: 24, huecoRamaHoja: 19, huecoBus: 24,
  // compatibilidad con quien lea cajas de zona
  zonaAncho: 180, zonaCabecera: 26, zonaMargen: 19, pasoZona: 40,
}

export type Rama = {
  nombre: string; nodos: string[]; plegada: boolean
  x: number; y: number; w: number; h: number       // caja completa (píldora + hojas); x = borde izquierdo
  cx: number; h_pildora: number; espinaX: number
  hojas: { nombre: string; x: number; y: number }[]  // centros
}
export type Disposicion = {
  nodos: Record<string, { x: number; y: number }>   // centros de los nodos VISIBLES
  zonas: { nombre: string; x: number; y: number; w: number; h: number }[]
  ramas: Rama[]
  carril: { y: number; h: number } | null
  bus: { y: number; x1: number; x2: number } | null
  tronco: string[]                                   // de arriba abajo
  ancho: number
  alto: number
}

// Árbol: los externos van al carril de arriba (son «internet», el origen); los nodos que no están
// en ninguna zona forman el tronco (cortafuegos), de arriba abajo por profundidad según `enlaces`;
// de un bus horizontal cuelgan las zonas como ramas, en filas de `porFila`, y de cada rama sus
// equipos en columna con una espina. Una rama plegada solo muestra su píldora. Coordenadas = centro.
export function disposicion(red: Red, opciones: { plegadas?: Set<string>; carril?: boolean } = {}): Disposicion {
  const plegadas = opciones.plegadas ?? new Set<string>()
  const padre = new Map(red.enlaces.map(([h, p]) => [h, p]))
  const enZona = new Set(red.zonas.flatMap((z) => z.nodos))
  const externos = red.nodos.filter((n) => n.tipo === "externo" && !enZona.has(n.nombre)).map((n) => n.nombre)
  const troncal = red.nodos.map((n) => n.nombre).filter((n) => !enZona.has(n) && !externos.includes(n))
  const profundidad = (n: string) => {
    let d = 0, actual = n
    const visto = new Set<string>()
    while (padre.has(actual) && !visto.has(actual) && troncal.includes(padre.get(actual)!)) {
      visto.add(actual); actual = padre.get(actual)!; d++
    }
    return d
  }
  const niveles = new Map<number, string[]>()
  for (const n of troncal) niveles.set(profundidad(n), [...(niveles.get(profundidad(n)) ?? []), n])
  const nivelesOrdenados = [...niveles.keys()].sort((a, b) => a - b)

  const filas: (typeof red.zonas)[] = []
  for (let i = 0; i < red.zonas.length; i += DIM.porFila) filas.push(red.zonas.slice(i, i + DIM.porFila))
  const anchoTroncal = Math.max(0, ...[...niveles.values()].map((ns) => ns.length)) * (DIM.nodoAncho + DIM.zonaHueco)
  const anchoCarril = externos.length * (DIM.nodoAncho + 10)
  const ancho = Math.max(320, anchoTroncal, anchoCarril, ...filas.map((f) => f.length * DIM.colAncho)) + 2 * DIM.margen

  const nodos: Disposicion["nodos"] = {}
  let y = DIM.margen
  const carril = externos.length > 0 || opciones.carril ? { y, h: DIM.carrilAlto } : null
  if (carril) {
    externos.forEach((n, j) => { nodos[n] = { x: DIM.margen + 10 + DIM.nodoAncho / 2 + j * (DIM.nodoAncho + 10), y: y + DIM.carrilAlto / 2 } })
    y += DIM.carrilAlto + DIM.zonaHueco
  }
  const tronco: string[] = []
  nivelesOrdenados.forEach((nivel, i) => {
    const ns = niveles.get(nivel)!
    const total = ns.length * DIM.nodoAncho + (ns.length - 1) * DIM.zonaHueco
    ns.forEach((n, j) => {
      nodos[n] = { x: ancho / 2 - total / 2 + DIM.nodoAncho / 2 + j * (DIM.nodoAncho + DIM.zonaHueco), y: y + DIM.nodoAlto / 2 + i * DIM.pasoCadena }
      tronco.push(n)
    })
  })
  if (nivelesOrdenados.length) y += (nivelesOrdenados.length - 1) * DIM.pasoCadena + DIM.nodoAlto

  const ramas: Rama[] = []
  const zonas: Disposicion["zonas"] = []
  let bus: Disposicion["bus"] = null
  if (red.zonas.length) {
    const busY = tronco.length ? y + DIM.huecoBus : y
    y = busY + (tronco.length ? 14 : 0)
    for (const fila of filas) {
      const x0 = ancho / 2 - (fila.length * DIM.colAncho) / 2
      let altoFila = 0
      fila.forEach((z, j) => {
        const cx = x0 + j * DIM.colAncho + DIM.colAncho / 2
        const plegada = plegadas.has(z.nombre)
        const hojas = plegada ? [] : z.nodos.map((n, k) => ({
          nombre: n, x: x0 + j * DIM.colAncho + DIM.hojaDesplaz + DIM.hojaAncho / 2,
          y: y + DIM.ramaAlto + DIM.huecoRamaHoja + DIM.hojaAlto / 2 + k * DIM.pasoHoja,
        }))
        for (const h of hojas) nodos[h.nombre] = { x: h.x, y: h.y }
        const h = DIM.ramaAlto + (plegada ? 0 : DIM.huecoRamaHoja + z.nodos.length * DIM.pasoHoja)
        ramas.push({ nombre: z.nombre, nodos: z.nodos, plegada, x: x0 + j * DIM.colAncho, y, w: DIM.colAncho, h,
          cx, h_pildora: DIM.ramaAlto, espinaX: x0 + j * DIM.colAncho + DIM.espina, hojas })
        zonas.push({ nombre: z.nombre, x: x0 + j * DIM.colAncho, y, w: DIM.colAncho, h })
        altoFila = Math.max(altoFila, h)
      })
      y += altoFila + DIM.zonaHueco
    }
    const primera = ramas.slice(0, filas[0].length)
    bus = tronco.length ? { y: busY, x1: primera[0].cx, x2: primera[primera.length - 1].cx } : null
  }
  return { nodos, zonas, ramas, carril, bus, tronco, ancho, alto: y + DIM.margen }
}

// Lo que un registro de la traza cuenta de «quién atacó a quién»: el origen y los equipos que fueron
// objetivo (por `relaciones`, o el `activo` si no hay relaciones).
const NO_DECISION = new Set(["actividad_suprimida", "actividad_propia", "reversion", "error", "actualizacion_caso"])
function objetivosDe(d: Decision): string[] {
  const rel = Object.entries(d.relaciones ?? {}).filter(([, e]) => (e ?? []).includes("objetivo")).map(([eq]) => eq)
  return rel.length ? rel : d.activo ? [d.activo] : []
}

export type Origen = { ip: string; n: number; codigo?: string | null; pais?: string | null; alcance?: string | null; objetivos: Record<string, number> }

// Los orígenes que más atacan (para el carril del mapa): por nº de ataques, con país y objetivos;
// `resto` = cuántos orígenes quedan fuera de los `max` primeros.
export function origenesDe(trazas: Decision[], max = 4): { top: Origen[]; resto: number; total: number } {
  const acc = new Map<string, Origen>()
  for (const d of trazas) {
    if (!d.origen_ip || (d.tipo && NO_DECISION.has(d.tipo))) continue
    const o = acc.get(d.origen_ip) ?? { ip: d.origen_ip, n: 0, objetivos: {} }
    o.n += 1
    for (const eq of objetivosDe(d)) o.objetivos[eq] = (o.objetivos[eq] ?? 0) + 1
    const e = d.enriquecimiento_origen
    if (e) { o.codigo ??= e.geo?.codigo ?? null; o.pais ??= e.geo?.pais ?? null; o.alcance ??= e.alcance ?? null }
    acc.set(d.origen_ip, o)
  }
  const todos = [...acc.values()].sort((a, b) => b.n - a.n)   // empate: orden de aparición en la traza
  return { top: todos.slice(0, max), resto: Math.max(0, todos.length - max), total: todos.length }
}

// Aristas de cascada [caído, dependiente]: de cada equipo caído a todo el que depende de él, también
// a través de otros (transitivo), sin repetir y sin colgarse en ciclos.
export function cascadaDe(red: Red): [string, string][] {
  const caidos = red.nodos.filter((n) => n.actividad.estado === "caido" || (n.salud && n.salud !== "ok")).map((n) => n.nombre)
  const dependientes = new Map<string, string[]>()
  for (const [n, dep] of red.dependencias) dependientes.set(dep, [...(dependientes.get(dep) ?? []), n])
  const aristas: [string, string][] = []
  for (const c of caidos) {
    const vistos = new Set<string>()
    const cola = [...(dependientes.get(c) ?? [])]
    while (cola.length) {
      const n = cola.pop()!
      if (n === c || vistos.has(n)) continue
      vistos.add(n); aristas.push([c, n]); cola.push(...(dependientes.get(n) ?? []))
    }
  }
  return aristas
}

// Resumen y color de una rama (zona): cuántos equipos y el peor estado que contiene.
export function resumenRama(nodos: NodoRed[]): { texto: string; borde: string } {
  const c = (e: string) => nodos.filter((n) => n.actividad.estado === e).length
  const caidos = c("caido"), atacados = c("atacado"), esperan = c("pendiente")
  const partes = [`${nodos.length} ${nodos.length === 1 ? "equipo" : "equipos"}`]
  if (caidos) partes.push(`${caidos} ${caidos === 1 ? "caído" : "caídos"}`)
  if (atacados) partes.push(`${atacados} ${atacados === 1 ? "atacado" : "atacados"}`)
  if (esperan) partes.push(`${esperan} ${esperan === 1 ? "espera" : "esperan"}`)
  if (partes.length === 1) partes.push("tranquila")
  const borde = caidos ? "stroke-enrutado" : atacados ? "stroke-critico" : esperan ? "stroke-aviso" : "stroke-border"
  return { texto: partes.join(" · "), borde }
}
