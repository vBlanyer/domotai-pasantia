import type { Red } from "@/api"

// Medidas del mapa en unidades del viewBox del SVG (escala con el ancho disponible).
export const DIM = { nodoAncho: 118, nodoAlto: 26, pasoCadena: 50, zonaAncho: 140, zonaHueco: 14,
                     zonaCabecera: 20, zonaMargen: 10, pasoZona: 34, porFila: 4, margen: 16 }

export type Disposicion = {
  nodos: Record<string, { x: number; y: number }>
  zonas: { nombre: string; x: number; y: number; w: number; h: number }[]
  ancho: number
  alto: number
}

// Árbol por zonas: los nodos que no están en ninguna zona forman la troncal (internet y
// cortafuegos), de arriba abajo por profundidad según `enlaces`; debajo, las zonas en el orden
// declarado, en filas de `porFila`, con sus nodos en columna. Coordenadas = centro del nodo.
export function disposicion(red: Red): Disposicion {
  const padre = new Map(red.enlaces.map(([h, p]) => [h, p]))
  const enZona = new Set(red.zonas.flatMap((z) => z.nodos))
  const troncal = red.nodos.map((n) => n.nombre).filter((n) => !enZona.has(n))
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

  const filas: (typeof red.zonas)[] = []
  for (let i = 0; i < red.zonas.length; i += DIM.porFila) filas.push(red.zonas.slice(i, i + DIM.porFila))
  const anchoFila = (k: number) => k * DIM.zonaAncho + Math.max(0, k - 1) * DIM.zonaHueco
  const anchoTroncal = Math.max(0, ...[...niveles.values()].map((ns) => ns.length)) * (DIM.nodoAncho + DIM.zonaHueco)
  const ancho = Math.max(320, anchoTroncal, ...filas.map((f) => anchoFila(f.length))) + 2 * DIM.margen

  const nodos: Disposicion["nodos"] = {}
  const nivelesOrdenados = [...niveles.keys()].sort((a, b) => a - b)
  nivelesOrdenados.forEach((nivel, i) => {
    const ns = niveles.get(nivel)!
    const total = ns.length * DIM.nodoAncho + (ns.length - 1) * DIM.zonaHueco
    ns.forEach((n, j) => {
      nodos[n] = { x: ancho / 2 - total / 2 + DIM.nodoAncho / 2 + j * (DIM.nodoAncho + DIM.zonaHueco),
                   y: DIM.margen + DIM.nodoAlto / 2 + i * DIM.pasoCadena }
    })
  })

  const zonas: Disposicion["zonas"] = []
  let y = DIM.margen + nivelesOrdenados.length * DIM.pasoCadena + DIM.zonaHueco
  for (const fila of filas) {
    let x = ancho / 2 - anchoFila(fila.length) / 2
    let altoFila = 0
    for (const z of fila) {
      const h = DIM.zonaCabecera + DIM.zonaMargen + Math.max(1, z.nodos.length) * DIM.pasoZona
      zonas.push({ nombre: z.nombre, x, y, w: DIM.zonaAncho, h })
      z.nodos.forEach((n, j) => {
        nodos[n] = { x: x + DIM.zonaAncho / 2, y: y + DIM.zonaCabecera + DIM.nodoAlto / 2 + j * DIM.pasoZona }
      })
      altoFila = Math.max(altoFila, h)
      x += DIM.zonaAncho + DIM.zonaHueco
    }
    y += altoFila + DIM.zonaHueco
  }
  return { nodos, zonas, ancho, alto: y + DIM.margen }
}
