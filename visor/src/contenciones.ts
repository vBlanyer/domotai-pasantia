import { quienDecidio } from "@/datos"
// Lógica pura de «Contenciones activas»: lo que la vista cuenta de cada contención cruzándola con la
// traza (país, clase, quién decidió, si sigue parando intentos), el resumen, el orden y la agrupación.
import type { Contencion, Decision } from "@/api"

// Una contención sin actividad desde hace tanto es candidata a revisarse. Propuesta: acordar el umbral.
export const UMBRAL_VIEJA_MS = 7 * 24 * 3600_000

const ms = (iso?: string | null) => { const t = iso ? Date.parse(iso) : NaN; return Number.isNaN(t) ? null : t }

// ¿Cuenta como «intento» del origen? Las decisiones y las supresiones (que agrupan N alertas).
const peso = (d: Decision) => (d.tipo === "actividad_suprimida" ? d.alertas_suprimidas ?? 1 : d.tipo ? 0 : 1)
// Bloqueos de DESTINO (exfiltración) cortan tráfico de salida: no hay «intentos del origen» que contar.
const cuentaIntentos = (c: Contencion) => !!c.ip && !c.accion_id.includes("DESTINO")

export type ContencionVista = {
  c: Contencion; decision: Decision | null; pais: string | null; alcance: string | null
  clase: string | null; confianza: number | null; decidio: string; enBorde: boolean
  edadMs: number; vieja: boolean; intentos: number | null; ultimoIntento: string | null
}

export function enriquecer(cs: Contencion[], trazas: Decision[], ahora: number): ContencionVista[] {
  return cs.map((c) => {
    const decision = trazas.find((t) => c.indice != null && t.indice === c.indice)
      ?? trazas.find((t) => !t.tipo && t.id_decision === c.id_decision) ?? null
    const desde = ms(c.ts)
    let intentos: number | null = null, ultimoIntento: string | null = null
    if (cuentaIntentos(c) && desde != null) {
      intentos = 0
      for (const t of trazas) {
        const tt = ms(t.timestamp)
        if (t.origen_ip !== c.ip || tt == null || tt <= desde) continue
        intentos += peso(t)
        if (!ultimoIntento || t.timestamp! > ultimoIntento) ultimoIntento = t.timestamp!
      }
    }
    const edadMs = desde == null ? 0 : Math.max(0, ahora - desde)
    return {
      c, decision,
      pais: decision?.enriquecimiento_origen?.geo?.pais ?? null, alcance: decision?.enriquecimiento_origen?.alcance ?? null,
      clase: decision?.clase ?? null, confianza: decision?.confianza ?? null,
      decidio: c.via_escalada ? "vía escalada"
        : decision?.veredicto_humano ? quienDecidio(decision)!
        : decision ? "automática" : "—",
      enBorde: !!c.nodo && c.nodo !== c.activo,
      edadMs, vieja: edadMs >= UMBRAL_VIEJA_MS, intentos, ultimoIntento,
    }
  })
}

export function resumenContenciones(es: ContencionVista[], _ahora?: number) {
  const masAntigua = es.reduce<ContencionVista | null>((m, e) => (!m || e.edadMs > m.edadMs ? e : m), null)
  const porAccion = new Map<string, number>()
  for (const e of es) porAccion.set(e.c.accion_id, (porAccion.get(e.c.accion_id) ?? 0) + 1)
  return {
    activas: es.length,
    hoy: es.filter((e) => e.edadMs < 24 * 3600_000).length,
    enBorde: es.filter((e) => e.enBorde).length,
    enEquipos: es.filter((e) => !e.enBorde).length,
    masAntigua: masAntigua ? { edadMs: masAntigua.edadMs, activo: masAntigua.c.activo } : null,
    insisten: es.filter((e) => (e.intentos ?? 0) > 0).length,
    viejas: es.filter((e) => e.vieja).length,
    porAccion: [...porAccion.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])),
  }
}

export type OrdenContencion = "reciente" | "antigua" | "intentos"
export const ORDENES_CONTENCION: { id: OrdenContencion; nombre: string }[] = [
  { id: "reciente", nombre: "Más recientes" }, { id: "antigua", nombre: "Más antiguas" }, { id: "intentos", nombre: "Más intentos parados" },
]
export function ordenarContenciones(es: ContencionVista[], orden: OrdenContencion): ContencionVista[] {
  return [...es].sort((a, b) =>
    orden === "reciente" ? a.edadMs - b.edadMs
    : orden === "antigua" ? b.edadMs - a.edadMs
    : (b.intentos ?? -1) - (a.intentos ?? -1) || a.edadMs - b.edadMs)
}

export type AgrupacionContencion = "donde" | "accion" | "activo" | "ninguno"
export const AGRUPACIONES_CONTENCION: { id: AgrupacionContencion; nombre: string }[] = [
  { id: "donde", nombre: "Por dónde se aplica" }, { id: "accion", nombre: "Por acción" },
  { id: "activo", nombre: "Por equipo protegido" }, { id: "ninguno", nombre: "Sin agrupar" },
]
export type GrupoContencion = { clave: string; etiqueta: string; cabecera: boolean; items: ContencionVista[] }
export function agruparContenciones(es: ContencionVista[], modo: AgrupacionContencion): GrupoContencion[] {
  if (modo === "ninguno") return [{ clave: "todo", etiqueta: "", cabecera: false, items: [...es] }]
  const grupos = new Map<string, GrupoContencion>()
  for (const e of es) {
    const [clave, etiqueta] = modo === "donde"
      ? [`n:${e.c.nodo}`, `${e.c.nodo ?? "—"} · ${e.enBorde ? "contiene para otros equipos" : "en el propio equipo"}`]
      : modo === "accion" ? [`a:${e.c.accion_id}`, e.c.accion_id]
      : [`p:${e.c.activo}`, `protege ${e.c.activo ?? "—"}`]
    const g = grupos.get(clave) ?? { clave, etiqueta, cabecera: true, items: [] }
    g.items.push(e)
    grupos.set(clave, g)
  }
  return [...grupos.values()]
}

// Intentos por hora del origen: 4 horas antes del bloqueo y hasta 6 después (o hasta ahora).
export function serieIntentos(trazas: Decision[], ip: string | null | undefined, ts: string | null | undefined, ahora: number) {
  const desde = ms(ts)
  if (!ip || desde == null) return []
  const H = 3600_000
  const despues = Math.max(1, Math.min(6, Math.ceil((ahora - desde) / H)))
  const bins = [...Array.from({ length: 4 }, (_, i) => ({ n: 0, despues: false, ini: desde - (4 - i) * H })),
                ...Array.from({ length: despues }, (_, i) => ({ n: 0, despues: true, ini: desde + i * H }))]
  for (const t of trazas) {
    const tt = ms(t.timestamp)
    if (t.origen_ip !== ip || tt == null) continue
    const b = bins.find((x) => tt >= x.ini && tt < x.ini + H && (x.despues ? tt > desde : tt <= desde))
    if (b) b.n += peso(t)
  }
  return bins.map(({ n, despues: d }) => ({ n, despues: d }))
}
