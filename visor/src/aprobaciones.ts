// Lógica pura de la bandeja de Aprobaciones: orden por urgencia, agrupación por campaña /24, salud de
// la cola, a dónde salta el inspector tras decidir, memoria del origen y «si apruebas» en una frase.
import { parsearPendiente, type Decision, type Pendiente } from "@/api"
import { msDesde } from "@/alertas"
import { etiquetaClase, nivelPrioridad, ubicacionLabelDe, quienDecidio } from "@/datos"
import { campanaDe } from "@/trazas"

export const SLA_MS = 15 * 60_000          // SLA por defecto, si el daemon no manda el suyo

// El SLA de una pendiente: el que manda el daemon (TRIAJE_SLA_SEG, el mismo de /api/metricas).
export const slaMs = (p?: { sla_seg?: number | null }) => (p?.sla_seg ? p.sla_seg * 1000 : SLA_MS)
export const fueraDeSla = (p: Pendiente, ahora: number) => edad(p, ahora) >= slaMs(p)

const edad = (p: Pendiente, ahora: number) => msDesde(p.encolado_en, ahora)

// Fuera de SLA primero, luego gravedad, luego la que más lleva esperando. No muta la entrada.
export function ordenarCola(xs: Pendiente[], ahora: number): Pendiente[] {
  return [...xs].sort((a, b) => {
    const fa = fueraDeSla(a, ahora) ? 1 : 0, fb = fueraDeSla(b, ahora) ? 1 : 0
    return fb - fa || (b.severidad ?? 0) - (a.severidad ?? 0) || edad(b, ahora) - edad(a, ahora)
  })
}

// Grupo de una pendiente: su campaña /24 (misma clave que Incidentes), la red interna o sin origen.
export function grupoDe(p: Pendiente): { clave: string; etiqueta: string } {
  if (!p.origen_ip) return { clave: "sin-origen", etiqueta: "Sin origen" }
  if (p.enriquecimiento_origen?.alcance === "interno") return { clave: "interna", etiqueta: "Red interna" }
  const c = campanaDe(p.origen_ip)
  if (!c) return { clave: `ip:${p.origen_ip}`, etiqueta: p.origen_ip }
  const pais = p.enriquecimiento_origen?.geo?.pais
  return { clave: c.clave, etiqueta: pais ? `${c.cidr} · ${pais}` : c.cidr }
}

// Agrupa conservando el orden de entrada (ya ordenada por urgencia): cada grupo aparece donde está su
// miembro más urgente.
export function agrupar(xs: Pendiente[]): { clave: string; etiqueta: string; items: Pendiente[] }[] {
  const grupos = new Map<string, { clave: string; etiqueta: string; items: Pendiente[] }>()
  for (const p of xs) {
    const g = grupoDe(p)
    const actual = grupos.get(g.clave) ?? { ...g, items: [] }
    actual.items.push(p)
    grupos.set(g.clave, actual)
  }
  return [...grupos.values()]
}

export function saludCola(xs: Pendiente[], ahora: number) {
  const edades = xs.map((p) => edad(p, ahora))
  const criticas = xs.filter((p) => (p.severidad ?? 0) >= 4)
  return {
    total: xs.length,
    ultimaHora: edades.filter((e) => e < 60 * 60_000).length,
    fueraSla: xs.filter((p) => fueraDeSla(p, ahora)).length,
    masAntiguaMs: Math.max(0, ...edades),
    criticas: criticas.length,
    criticasConCascada: criticas.filter((p) => efectoAprobar(p).cascada.length > 0).length,
  }
}

// Tras decidir `actual`, la siguiente de `orden` que no esté resuelta; si no queda ninguna detrás,
// la anterior; si no queda nada, null.
export function siguienteTras(orden: string[], actual: string, resueltas: Set<string>): string | null {
  const i = orden.indexOf(actual)
  const libre = (id: string) => id !== actual && !resueltas.has(id)
  return orden.slice(i + 1).find(libre) ?? [...orden.slice(0, Math.max(0, i))].reverse().find(libre) ?? null
}

const SISTEMA = new Set(["actividad_suprimida", "actividad_propia", "reversion", "error", "actualizacion_caso"])

// Lo que ya pasó con un origen según la traza: decisiones con hora, lo más reciente primero.
export function historialOrigen(trazas: Decision[], ip: string | null | undefined, max = 5) {
  if (!ip) return []
  return trazas
    .filter((d) => d.origen_ip === ip && d.timestamp && !(d.tipo && SISTEMA.has(d.tipo)))
    .sort((a, b) => (a.timestamp! < b.timestamp! ? 1 : -1))
    .slice(0, max)
    .map((d) => ({
      ts: d.timestamp!,
      texto: [d.activo, d.clase ? etiquetaClase(d.clase) : null].filter(Boolean).join(" · ") + (d.accion_final ? ` → ${d.accion_final}` : ""),
      quien: quienDecidio(d) ?? "automática",
      desenlace: d.contencion ?? null,
    }))
}

// Cuántas resolvió hoy el operador, por el día de SU decisión (no el de la alerta, que pudo llegar ayer).
export function resueltasHoyPor(trazas: Decision[], operador: string, hoy: string): number {
  if (!operador) return 0
  return trazas.filter((d) => d.veredicto_humano && d.veredicto_por === operador && (d.decidido_en ?? d.timestamp ?? "").startsWith(hoy)).length
}

// «Si apruebas», en una frase: qué se ejecuta, contra qué, su consecuencia y la cascada (si la hay y
// si de verdad se ejecuta algo: una vetada sin sustituta no ejecuta nada).
export function efectoAprobar(p: Pendiente): { titulo: string; detalle: string | null; cascada: string[]; ejecuta: boolean } {
  const v = parsearPendiente(p)
  if (p.tipo === "escalada")
    return { titulo: `Se ejecuta la escalada${p.accion_final ? ` (${p.accion_final})` : ""} en el perímetro`, detalle: v.consecuencia ?? null, cascada: v.cascada, ejecuta: true }
  if (p.accion_final === null)
    return { titulo: "La acción está vetada: aprobar no ejecuta nada", detalle: v.consecuencia ?? null, cascada: [], ejecuta: false }
  const accion = p.accion_final ?? "la acción propuesta"
  return { titulo: `Se ejecuta ${accion}${p.origen_ip ? ` contra ${p.origen_ip}` : ""}`, detalle: v.consecuencia ?? null, cascada: v.cascada, ejecuta: true }
}

// ---- criterios elegibles de orden y agrupación ---------------------------------------------------
export type Orden = "reciente" | "antigua" | "urgencia" | "gravedad"
export const ORDENES: { id: Orden; nombre: string }[] = [
  { id: "reciente", nombre: "Más recientes primero" }, { id: "antigua", nombre: "Más antiguas primero" },
  { id: "urgencia", nombre: "Urgencia (fuera de SLA)" }, { id: "gravedad", nombre: "Gravedad" },
]
export type Agrupacion = "ninguno" | "pais" | "campana" | "activo" | "clase" | "gravedad"
export const AGRUPACIONES: { id: Agrupacion; nombre: string }[] = [
  { id: "ninguno", nombre: "Sin agrupar" }, { id: "pais", nombre: "Por país" }, { id: "campana", nombre: "Por campaña /24" },
  { id: "activo", nombre: "Por activo" }, { id: "clase", nombre: "Por familia" }, { id: "gravedad", nombre: "Por gravedad" },
]

export function ordenarPor(xs: Pendiente[], orden: Orden, ahora: number): Pendiente[] {
  if (orden === "urgencia") return ordenarCola(xs, ahora)
  return [...xs].sort((a, b) =>
    orden === "reciente" ? edad(a, ahora) - edad(b, ahora)
    : orden === "antigua" ? edad(b, ahora) - edad(a, ahora)
    : (b.severidad ?? 0) - (a.severidad ?? 0) || edad(b, ahora) - edad(a, ahora))
}

export type Grupo = { clave: string; etiqueta: string; cabecera: boolean; items: Pendiente[] }

// Agrupa conservando el orden recibido: cada grupo aparece donde está su primer miembro. «Sin
// agrupar» es un solo grupo sin cabecera.
export function agruparPor(xs: Pendiente[], modo: Agrupacion): Grupo[] {
  if (modo === "ninguno") return [{ clave: "todo", etiqueta: "", cabecera: false, items: [...xs] }]
  const de = (p: Pendiente): { clave: string; etiqueta: string } => {
    switch (modo) {
      case "pais": { const u = ubicacionLabelDe(p); return { clave: `pais:${u}`, etiqueta: u } }
      case "campana": return grupoDe(p)
      case "activo": return { clave: `activo:${p.activo ?? ""}`, etiqueta: p.activo ?? "Sin activo" }
      case "clase": return p.clase ? { clave: `clase:${p.clase}`, etiqueta: etiquetaClase(p.clase) } : { clave: "clase:", etiqueta: "Sin clase" }
      case "gravedad": { const n = nivelPrioridad(p.severidad); return { clave: `sev:${n?.n ?? 0}`, etiqueta: n?.etiqueta ?? "Sin gravedad" } }
    }
  }
  const grupos = new Map<string, Grupo>()
  for (const p of xs) {
    const g = de(p)
    const actual = grupos.get(g.clave) ?? { ...g, cabecera: true, items: [] }
    actual.items.push(p)
    grupos.set(g.clave, actual)
  }
  return [...grupos.values()]
}
