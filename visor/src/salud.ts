// Lógica pura de la vista «Estado de servicios»: clasifica el inventario del monitor por lo que
// importa al analista (qué está caído, qué arrastra, qué sigue en pie) y mide la frescura de la muestra.
import type { Servicio } from "@/api"

export type EstadoFila = "caido" | "degradado" | "ok"
export type Fila = {
  nombre: string
  estado: EstadoFila
  causas: string[]      // degradado: los caídos de los que depende (aun transitivamente)
  afecta: string[]      // caído: los que dependen de él (aun transitivamente)
  sostiene: string[]    // dependientes directos
  depende_de: string[]
}

const RANGO: Record<EstadoFila, number> = { caido: 0, degradado: 1, ok: 2 }

// Alcanzables desde `inicio` siguiendo `vecinos`, sin el propio inicio; un ciclo no cuelga (visitados).
function alcance(inicio: string, vecinos: (n: string) => string[]): Set<string> {
  const vistos = new Set<string>()
  const cola = [...vecinos(inicio)]
  while (cola.length) {
    const n = cola.pop()!
    if (n === inicio || vistos.has(n)) continue
    vistos.add(n)
    cola.push(...vecinos(n))
  }
  return vistos
}

// Caídos primero, luego los que dependen de un caído, luego operativos; alfabético dentro de cada grupo.
// Una dependencia que no está en el inventario se ignora (no se puede saber su estado).
export function clasificar(servicios: Servicio[]): Fila[] {
  const conocido = new Map(servicios.map((s) => [s.nombre, s]))
  const caido = (n: string) => conocido.get(n)?.estado !== "ok"
  const deps = (n: string) => (conocido.get(n)?.depende_de ?? []).filter((d) => conocido.has(d))
  const dependientes = new Map<string, string[]>()
  for (const s of servicios) for (const d of deps(s.nombre)) dependientes.set(d, [...(dependientes.get(d) ?? []), s.nombre])
  const sobre = (n: string) => dependientes.get(n) ?? []

  const filas: Fila[] = servicios.map((s) => {
    const esCaido = caido(s.nombre)
    const causas = esCaido ? [] : [...alcance(s.nombre, deps)].filter(caido).sort()
    return {
      nombre: s.nombre,
      estado: esCaido ? "caido" : causas.length ? "degradado" : "ok",
      causas,
      afecta: esCaido ? [...alcance(s.nombre, sobre)].sort() : [],
      sostiene: [...sobre(s.nombre)].sort(),
      depende_de: deps(s.nombre),
    }
  })
  return filas.sort((a, b) => RANGO[a.estado] - RANGO[b.estado] || a.nombre.localeCompare(b.nombre))
}

// Muestra más vieja que esto = el monitor puede estar muerto y lo de abajo es lo último que se supo.
export const MUESTRA_VIEJA_MS = 60_000

// Edad de la muestra en ms contra `ahoraMs` (la hora del daemon, no la del navegador: drift en
// WSL2/VMs). Nunca negativa; null si la muestra no trae hora o no se entiende.
export function edadMuestraMs(t: string | null | undefined, ahoraMs: number): number | null {
  if (!t) return null
  const ms = Date.parse(t)
  if (Number.isNaN(ms)) return null
  return Math.max(0, ahoraMs - ms)
}
