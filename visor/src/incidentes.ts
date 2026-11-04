// Lógica pura de «Incidentes»: cada incidente es una campaña /24 con su caso (estado, responsable,
// notas). Junta las decisiones del bloque, cuánto se contuvo por equipo, si sigue activo, el resumen
// de casos, los filtros y la historia del ataque en una frase. Sin backend: todo sale de la traza.
import type { Decision } from "@/api"
import { campanasDe, estadoDeCasos, claveDeCampana, claveIncidenteDe, type CasoEstado } from "@/datos"
import { edadTexto } from "@/alertas"

export const ACTIVO_MS = 3600_000          // atacó en la última hora = «activo ahora»

export type IncidenteVista = {
  clave: string; cidr: string; prefijo: string; pais: string | null; alcance: string | null
  ips: number; n: number; prioridad: number; primera: string | null; ultima: string | null
  activo: boolean; contenidas: number; aprobadas: number; frenadas: number
  objetivos: { equipo: string; n: number; contenidas: number }[]
  caso: CasoEstado
}

const objetivosDe = (d: Decision) => Object.entries(d.relaciones ?? {}).filter(([, e]) => (e ?? []).includes("objetivo")).map(([eq]) => eq)

export function incidentesDe(regs: Decision[], ahora: number): IncidenteVista[] {
  const casos = estadoDeCasos(regs)
  return campanasDe(regs).map((c) => {
    const clave = claveDeCampana(c.prefijo)
    const suyas = regs.filter((d) => (!d.tipo || d.tipo === "decision") && d.origen_ip && claveIncidenteDe(d.origen_ip) === clave && objetivosDe(d).length)
    const porEquipo = new Map<string, { n: number; contenidas: number }>()
    for (const d of suyas) for (const eq of objetivosDe(d)) {
      const e = porEquipo.get(eq) ?? { n: 0, contenidas: 0 }
      e.n += 1
      if (d.contencion === "contenida") e.contenidas += 1
      porEquipo.set(eq, e)
    }
    const ult = c.ultima ? Date.parse(c.ultima) : NaN
    return {
      clave, cidr: c.cidr, prefijo: c.prefijo, alcance: c.alcance ?? null,
      pais: suyas.find((d) => d.enriquecimiento_origen?.geo?.pais)?.enriquecimiento_origen?.geo?.pais ?? null,
      ips: c.ips, n: c.n, prioridad: c.prioridad, primera: c.primera, ultima: c.ultima,
      activo: !Number.isNaN(ult) && ahora - ult < ACTIVO_MS,
      contenidas: suyas.filter((d) => d.contencion === "contenida").length,
      aprobadas: suyas.filter((d) => d.veredicto_humano === "aprobar").length,
      frenadas: suyas.filter((d) => d.resultado_filtro === "degrada" || (d.resultado_filtro === "veta" && !d.accion_final)).length,
      objetivos: [...porEquipo.entries()].map(([equipo, v]) => ({ equipo, ...v })).sort((a, b) => b.n - a.n),
      caso: casos[clave] ?? { estado: "nuevo", asignado: null, notas: [] },
    }
  })
}

const abierto = (e: IncidenteVista) => e.caso.estado !== "resuelto"

export function resumenIncidentes(es: IncidenteVista[], operador: string) {
  const ab = es.filter(abierto)
  return {
    total: es.length, abiertos: ab.length,
    sinAsignar: ab.filter((e) => !e.caso.asignado).length,
    activos: es.filter((e) => e.activo).length,
    nuevos: es.filter((e) => e.caso.estado === "nuevo").length,
    enRevision: es.filter((e) => e.caso.estado === "en_revision").length,
    mios: operador ? es.filter((e) => e.caso.estado === "en_revision" && e.caso.asignado === operador).length : 0,
    resueltos: es.filter((e) => e.caso.estado === "resuelto").length,
  }
}

export type FiltroIncidente = "abiertos" | "nuevos" | "en_revision" | "resueltos" | "todos"
export const FILTROS_INCIDENTE: { id: FiltroIncidente; nombre: string }[] = [
  { id: "abiertos", nombre: "Abiertos" }, { id: "nuevos", nombre: "Nuevos" }, { id: "en_revision", nombre: "En revisión" },
  { id: "resueltos", nombre: "Resueltos" }, { id: "todos", nombre: "Todos" },
]
// `soloDe`: si no está vacío, solo los casos asignados a ese operador.
export function pasaFiltroIncidente(e: IncidenteVista, f: FiltroIncidente, soloDe: string): boolean {
  if (soloDe && e.caso.asignado !== soloDe) return false
  switch (f) {
    case "abiertos": return abierto(e)
    case "nuevos": return e.caso.estado === "nuevo"
    case "en_revision": return e.caso.estado === "en_revision"
    case "resueltos": return e.caso.estado === "resuelto"
    case "todos": return true
  }
}

export type OrdenIncidente = "reciente" | "gravedad" | "antiguo"
export const ORDENES_INCIDENTE: { id: OrdenIncidente; nombre: string }[] = [
  { id: "reciente", nombre: "Actividad más reciente" }, { id: "gravedad", nombre: "Gravedad" }, { id: "antiguo", nombre: "Abiertos hace más tiempo" },
]
export function ordenarIncidentes(es: IncidenteVista[], orden: OrdenIncidente): IncidenteVista[] {
  const t = (s: string | null) => (s ? Date.parse(s) || 0 : 0)
  return [...es].sort((a, b) =>
    orden === "reciente" ? t(b.ultima) - t(a.ultima)
    : orden === "antiguo" ? t(a.primera) - t(b.primera)
    : b.prioridad - a.prioridad || t(b.ultima) - t(a.ultima))
}

const plural = (n: number, s: string, p = `${s}s`) => `${n} ${n === 1 ? s : p}`

export function duracion(e: IncidenteVista): string {
  const a = e.primera ? Date.parse(e.primera) : NaN, b = e.ultima ? Date.parse(e.ultima) : NaN
  if (Number.isNaN(a) || Number.isNaN(b)) return "un momento"
  const ms = b - a
  if (ms < 3600_000) return plural(Math.max(1, Math.round(ms / 60_000)), "minuto")
  if (ms < 86_400_000) return plural(Math.round(ms / 3600_000), "hora")
  return plural(Math.round(ms / 86_400_000), "día")
}

export function historiaDe(e: IncidenteVista, ahora: number): string {
  const ips = e.ips === 1 ? "Una IP" : `${e.ips} IPs del mismo bloque`
  const principal = e.objetivos[0]?.equipo
  let s = `${ips} ${e.ips === 1 ? "atacó" : "atacaron"} ${plural(e.objetivos.length, "equipo")} durante ${duracion(e)}`
  s += principal && e.objetivos.length > 1 ? `, sobre todo ${principal}.` : principal ? ` (${principal}).` : "."
  s += ` Se contuvieron ${e.contenidas} de ${plural(e.n, "intento")}`
  const partes = [e.aprobadas ? `${e.aprobadas} los aprobó un analista` : null, e.frenadas ? `${e.frenadas} se frenaron por la política` : null].filter(Boolean)
  s += partes.length ? `; ${partes.join(" y ")}.` : "."
  if (e.activo && e.ultima) s += ` Sigue activo: el último intento fue ${edadTexto(ahora - Date.parse(e.ultima))}.`
  return s
}
