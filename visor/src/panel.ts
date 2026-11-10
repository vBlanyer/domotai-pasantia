// Lógica pura del Panel: la salud de la plataforma en una línea, lo que le toca al analista
// (aprobaciones más cerca del SLA, incidentes sin responsable, contenciones fallidas), la actividad
// de las últimas 24 h por hora y la comparación con ayer. Todo sale de datos que el visor ya recibe.
import type { CausaFallo, Decision, Pendiente } from "@/api"
import { msDesde } from "@/alertas"
import { esDecision, claveIncidenteDe } from "@/datos"
import { ordenarCola, slaMs } from "@/aprobaciones"
import type { IncidenteVista } from "@/incidentes"

export type Tono = "ok" | "aviso" | "critico" | "neutro"
const HORA = 3600_000
const ts = (d: Decision) => (d.timestamp ? Date.parse(d.timestamp) : NaN)

// ---- salud en una línea ---------------------------------------------------------------------------
export type Indicador = { nombre: string; valor: string; tono: Tono }
export type EntradaSalud = {
  conectado: boolean
  servicios: { total: number; caidos: number; caidosNombres: string[] } | null
  ingestaSilencioS: number | null | undefined          // undefined = no se sabe (sin latido)
  trazaOk: boolean | null                               // null = no verificada
  conector: { modo: string; problemas: number; verificados: number; contenibles: number } | null
}
const PEOR: Record<Tono, number> = { neutro: 0, ok: 1, aviso: 2, critico: 3 }

export function saludPlataforma(e: EntradaSalud): { tono: Tono; titulo: string; indicadores: Indicador[] } {
  if (!e.conectado) return { tono: "critico", titulo: "Sin conexión con el daemon", indicadores: [] }
  const ind: Indicador[] = []
  const motivos: string[] = []
  if (e.servicios) {
    const { total, caidos } = e.servicios
    ind.push({ nombre: "Servicios", valor: `${total - caidos}/${total}`, tono: caidos ? "critico" : "ok" })
    if (caidos) motivos.push(`${caidos === 1 ? "1 servicio caído" : `${caidos} servicios caídos`}${e.servicios.caidosNombres.length ? `: ${e.servicios.caidosNombres.join(", ")}` : ""}`)
  } else ind.push({ nombre: "Servicios", valor: "sin muestra", tono: "neutro" })
  const s = e.ingestaSilencioS
  if (s === undefined) ind.push({ nombre: "Ingesta", valor: "sin latido", tono: "neutro" })
  else if (s === null) ind.push({ nombre: "Ingesta", valor: "sin alertas aún", tono: "neutro" })
  else {
    const tono: Tono = s < 120 ? "ok" : s < 900 ? "aviso" : "critico"
    ind.push({ nombre: "Ingesta", valor: `hace ${s < 120 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`}`, tono })
    if (tono === "critico") motivos.push(`sin alertas del SIEM desde hace ${Math.round(s / 60)} min`)
  }
  if (e.trazaOk === null) ind.push({ nombre: "Traza", valor: "sin verificar", tono: "neutro" })
  else {
    ind.push({ nombre: "Traza", valor: e.trazaOk ? "íntegra" : "rota", tono: e.trazaOk ? "ok" : "critico" })
    if (!e.trazaOk) motivos.push("la cadena de la traza está rota")
  }
  if (e.conector) {
    const c = e.conector
    if (c.modo === "sin_configurar") ind.push({ nombre: "Conector", valor: "sin configurar", tono: "aviso" })
    else if (c.problemas) ind.push({ nombre: "Conector", valor: `${c.problemas} con problemas`, tono: "aviso" })
    else ind.push({ nombre: "Conector", valor: `${c.verificados}/${c.contenibles} verificados`, tono: c.verificados ? "ok" : "neutro" })
  }
  const tono = ind.reduce<Tono>((a, i) => (PEOR[i.tono] > PEOR[a] ? i.tono : a), "ok")
  const titulo = tono === "critico" ? `Fallo en la plataforma: ${motivos.join(" · ")}`
    : tono === "aviso" ? "Plataforma operativa, con avisos" : "Plataforma operativa"
  return { tono, titulo, indicadores: ind }
}

// ---- lo que le toca al analista -------------------------------------------------------------------
export type Urgente = { p: Pendiente; edadMs: number; restanteMs: number; fraccion: number }

// Las n aprobaciones más urgentes (fuera de SLA, luego gravedad, luego antigüedad) con su reloj.
export function urgentes(xs: Pendiente[], ahora: number, n = 3): Urgente[] {
  return ordenarCola(xs, ahora).slice(0, n).map((p) => {
    const edadMs = msDesde(p.encolado_en, ahora)
    const sla = slaMs(p)
    return { p, edadMs, restanteMs: sla - edadMs, fraccion: Math.min(1, edadMs / sla) }
  })
}

export function textoSla(restanteMs: number): string {
  if (restanteMs <= 0) {
    const m = Math.max(1, Math.round(-restanteMs / 60_000))
    return `fuera de SLA ${m < 60 ? `${m} min` : `${Math.floor(m / 60)} h`}`
  }
  // cuenta atrás: 1 min 59 s son «quedan 2 min»; por debajo del minuto, «< 1 min»
  return restanteMs < 60_000 ? "queda < 1 min" : `quedan ${Math.ceil(restanteMs / 60_000)} min`
}

export function colaResumen(xs: Pendiente[], ahora: number) {
  const restantes = xs.map((p) => slaMs(p) - msDesde(p.encolado_en, ahora))
  return {
    total: xs.length,
    fueraSla: restantes.filter((r) => r <= 0).length,
    porVencer: restantes.filter((r) => r > 0 && r <= 5 * 60_000).length,
  }
}

// Una campaña sigue activa si su /24 tiene pendientes llegadas en la última hora, aunque la traza aún
// no las tenga (el daemon escribe las que esperan aprobación al resolverse).
export function conActividadDeCola(es: IncidenteVista[], pend: Pendiente[], ahora: number): IncidenteVista[] {
  const vivas = new Set(pend.filter((p) => p.origen_ip && ahora - Date.parse(p.encolado_en ?? "") < HORA).map((p) => claveIncidenteDe(p.origen_ip)))
  return es.map((e) => (!e.activo && vivas.has(e.clave) ? { ...e, activo: true } : e))
}

// Incidentes abiertos sin responsable, los activos primero y luego por volumen.
export function incidentesSinResponsable(es: IncidenteVista[], n = 2): IncidenteVista[] {
  return es.filter((e) => e.caso.estado !== "resuelto" && !e.caso.asignado)
    .sort((a, b) => Number(b.activo) - Number(a.activo) || b.n - a.n).slice(0, n)
}

// Contenciones fallidas de las últimas 24 h, una por equipo (la más reciente) con cuántas fallaron.
// Entra también lo que puede ser un ataque (clave del host cambiada, contención deshecha, un equipo que
// funcionaba y dejó de hacerlo) aunque la escalada lo contuviera en otro sitio: eso va primero y con
// su causa, nunca como un problema de configuración.
export type Fallida = { d: Decision; veces: number; causa: CausaFallo | null; ataque: boolean }
export function fallidasRecientes(regs: Decision[], ahora: number, n = 2): Fallida[] {
  const por = new Map<string, Fallida>()
  for (const d of regs) {
    const ataque = !!d.causa?.posible_ataque
    if (!esDecision(d) || (d.contencion !== "fallida" && !ataque) || !(ahora - ts(d) < 24 * HORA)) continue
    const k = ataque ? `!${d.causa?.dispositivo ?? d.activo ?? "—"}` : d.activo ?? "—"
    const prev = por.get(k)
    const ultima = !prev || ts(d) > ts(prev.d) ? d : prev.d
    por.set(k, { d: ultima, veces: (prev?.veces ?? 0) + 1, causa: ultima.causa ?? null, ataque })
  }
  return [...por.values()].sort((a, b) => Number(b.ataque) - Number(a.ataque) || ts(b.d) - ts(a.d)).slice(0, n)
}

// Equipos a los que el MDR perdió el acceso (memoria de fallos): UNA tarea por equipo, que se actualiza.
// Si el equipo estaba verificado, es una regresión: posible ataque (alguien pudo cortar al SOC).
export type SinAcceso = { nombre: string; desde: string; fallos: number; ataque: boolean }
export function sinAccesoDe(equipos: { nombre: string; protegido: boolean; sin_acceso?: { desde: string; fallos?: number | null; regresion?: boolean | null } | null }[]): SinAcceso[] {
  return equipos.filter((e) => !e.protegido && e.sin_acceso)
    .map((e) => ({ nombre: e.nombre, desde: e.sin_acceso!.desde, fallos: e.sin_acceso!.fallos ?? 0, ataque: !!e.sin_acceso!.regresion }))
    .sort((a, b) => Number(b.ataque) - Number(a.ataque) || a.desde.localeCompare(b.desde))
}

// ---- actividad -----------------------------------------------------------------------------------
export type Hora = { inicio: number; auto: number; humano: number; descartadas: number }
const esFp = (d: Decision) => (d.clase ?? "").startsWith("fp_")

// Las 24 horas que acaban en la hora en curso: cada decisión cae en su hora y se reparte entre
// contenida/decidida en automático, pasó por un analista o descartada como falso positivo. Las que
// esperan aprobación aún no están en la traza (el daemon las escribe al resolverse): cuentan como «a un
// analista» en la hora en que llegaron a la cola.
export function actividadPorHora(regs: Decision[], ahora: number, pend: Pendiente[] = []): Hora[] {
  const ultima = Math.floor(ahora / HORA) * HORA
  const horas: Hora[] = Array.from({ length: 24 }, (_, i) => ({ inicio: ultima - (23 - i) * HORA, auto: 0, humano: 0, descartadas: 0 }))
  for (const d of regs) {
    if (!esDecision(d)) continue
    const t = ts(d)
    const i = Math.floor((t - horas[0].inicio) / HORA)
    if (!(i >= 0 && i < 24)) continue
    if (esFp(d)) horas[i].descartadas += 1
    else if (d.requiere_humano || d.veredicto_humano) horas[i].humano += 1
    else horas[i].auto += 1
  }
  for (const p of pend) {
    const i = Math.floor((Date.parse(p.encolado_en ?? "") - horas[0].inicio) / HORA)
    if (i >= 0 && i < 24) horas[i].humano += 1
  }
  return horas
}

// Lo que llegó en los últimos 60 min: decisiones de la traza más las que esperan en la cola.
export function llegadasUltimaHora(regs: Decision[], pend: Pendiente[], ahora: number): number {
  const enHora = (t: number) => t > ahora - HORA && t <= ahora
  return regs.filter((d) => esDecision(d) && enHora(ts(d))).length + pend.filter((p) => enHora(Date.parse(p.encolado_en ?? ""))).length
}

// Desde cuándo cubre la ventana de trazas cargada (la más antigua de sus decisiones), o null si vacía.
export function cobertura(regs: Decision[]): number | null {
  const t = regs.filter(esDecision).map(ts).filter((x) => !Number.isNaN(x))
  return t.length ? Math.min(...t) : null
}

// Decisiones de hoy hasta ahora frente a ayer hasta la misma hora (UTC, como el daemon). Sin
// comparación (null) si la ventana de trazas está recortada y no llega al comienzo de ayer: un «▲»
// falso es peor que nada. `completa`: la ventana trae la traza entera (no se cortó por el límite).
export function comparaConAyer(regs: Decision[], ahora: number, completa = false): { hoy: number; ayer: number | null; ultimaHora: number } {
  const hoy0 = Date.UTC(new Date(ahora).getUTCFullYear(), new Date(ahora).getUTCMonth(), new Date(ahora).getUTCDate())
  const ayer0 = hoy0 - 24 * HORA
  const t = regs.filter(esDecision).map(ts).filter((x) => !Number.isNaN(x))
  const desde = cobertura(regs)
  return {
    hoy: t.filter((x) => x >= hoy0 && x <= ahora).length,
    ayer: completa || (desde != null && desde <= ayer0) ? t.filter((x) => x >= ayer0 && x <= ahora - 24 * HORA).length : null,
    ultimaHora: t.filter((x) => x > ahora - HORA && x <= ahora).length,
  }
}

export function variacion(hoy: number, ayer: number | null): { texto: string; sube: boolean } | null {
  // ayer en 0 no se compara: suele ser que la traza empieza hoy (laboratorio nuevo, retención), no calma
  if (ayer == null || ayer === 0) return null
  const pct = Math.round(((hoy - ayer) / ayer) * 100)
  return { texto: `${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct)} % sobre ayer a esta hora`, sube: pct >= 0 }
}

// Lo atacado en las últimas 24 h: por clase y por equipo (con lo contenido de cada uno).
export function atacadoEn24h(regs: Decision[], ahora: number) {
  const ds = regs.filter((d) => esDecision(d) && ahora - ts(d) < 24 * HORA && !esFp(d))
  const clases = new Map<string, number>(), equipos = new Map<string, { n: number; contenidas: number }>()
  for (const d of ds) {
    if (d.clase) clases.set(d.clase, (clases.get(d.clase) ?? 0) + 1)
    if (d.activo) {
      const e = equipos.get(d.activo) ?? { n: 0, contenidas: 0 }
      e.n += 1
      if (d.contencion === "contenida") e.contenidas += 1
      equipos.set(d.activo, e)
    }
  }
  return {
    clases: [...clases.entries()].map(([clase, n]) => ({ clase, n })).sort((a, b) => b.n - a.n),
    equipos: [...equipos.entries()].map(([equipo, v]) => ({ equipo, ...v })).sort((a, b) => b.n - a.n),
  }
}

export function ultimasDecisiones(regs: Decision[], n = 6): Decision[] {
  return regs.filter(esDecision).slice(-n).reverse()
}
