// Rango de fechas (YYYY-MM-DD) de un preset del informe. Se calcula de partes locales (no toISOString,
// que pasa a UTC y puede correr un día). `hasta` incluye el último día del periodo.
export type Preset = "mes" | "año"

const dd = (y: number, m: number, d: number) =>
  `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`

export function rangoDe(preset: Preset, hoy: Date): { desde: string; hasta: string } {
  const y = hoy.getFullYear(), m = hoy.getMonth()
  if (preset === "año") return { desde: dd(y, 0, 1), hasta: dd(y, 11, 31) }
  const ultimo = new Date(y, m + 1, 0).getDate()        // día 0 del mes siguiente = último de este
  return { desde: dd(y, m, 1), hasta: dd(y, m, ultimo) }
}

// Etiqueta legible del periodo para la cabecera del informe.
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
export function etiquetaPeriodo(desde?: string | null, hasta?: string | null): string {
  if (!desde && !hasta) return "Todo el histórico"
  if (desde && hasta) {
    const [ay, am] = desde.split("-"), [by, bm, bd] = hasta.split("-")
    if (ay === by && am === bm && desde.endsWith("-01") && bd === String(new Date(+by, +bm, 0).getDate()))
      return `${MESES[+am - 1]} de ${ay}`                 // mes completo
    if (ay === by && desde === `${ay}-01-01` && hasta === `${by}-12-31`) return `Año ${ay}`
    return `${desde} a ${hasta}`
  }
  return desde ? `desde ${desde}` : `hasta ${hasta}`
}

// ---- informe en PDF ------------------------------------------------------------------------------
import type { Metricas } from "@/api"

const ultimoDia = (y: number, m: number) => new Date(y, m + 1, 0).getDate()      // m: 0..11
const esMesCompleto = (desde: string, hasta: string) => {
  const [ay, am, ad] = desde.split("-").map(Number), [by, bm, bd] = hasta.split("-").map(Number)
  return ay === by && am === bm && ad === 1 && bd === ultimoDia(by, bm - 1)
}

// El periodo con el que comparar: el mes anterior si es un mes completo; si no, otro de igual
// duración inmediatamente antes.
export function periodoAnterior(desde: string, hasta: string): { desde: string; hasta: string } {
  const [ay, am] = desde.split("-").map(Number)
  if (esMesCompleto(desde, hasta)) {
    const y = am === 1 ? ay - 1 : ay, m = am === 1 ? 11 : am - 2
    return { desde: dd(y, m, 1), hasta: dd(y, m, ultimoDia(y, m)) }
  }
  const a = new Date(`${desde}T00:00:00`), b = new Date(`${hasta}T00:00:00`)
  const dias = Math.round((b.getTime() - a.getTime()) / 86_400_000) + 1
  const fin = new Date(a); fin.setDate(fin.getDate() - 1)
  const ini = new Date(fin); ini.setDate(ini.getDate() - (dias - 1))
  return { desde: dd(ini.getFullYear(), ini.getMonth(), ini.getDate()), hasta: dd(fin.getFullYear(), fin.getMonth(), fin.getDate()) }
}

// Nombre del PDF (el navegador usa el título del documento): sin extensión, la pone él.
export function nombreArchivo(desde: string, hasta: string): string {
  if (esMesCompleto(desde, hasta)) return `Informe-MDR-${desde.slice(0, 7)}`
  if (desde.endsWith("-01-01") && hasta.endsWith("-12-31") && desde.slice(0, 4) === hasta.slice(0, 4)) return `Informe-MDR-${desde.slice(0, 4)}`
  return `Informe-MDR-${desde}_a_${hasta}`
}

// ¿Cae `ts` en el periodo? Por día (los extremos incluidos), como agrega el daemon.
export function enPeriodo(ts: string | null | undefined, desde: string, hasta: string): boolean {
  if (!ts) return false
  const dia = ts.slice(0, 10)
  return dia >= desde && dia <= hasta
}

const pc = (x?: number | null) => `${(Math.round((x ?? 0) * 1000) / 10).toLocaleString("es")} %`
const num = (x: number) => x.toLocaleString("es")

export function resumenRedactado(m: Metricas, periodo: string): string {
  let s = `En ${periodo} el servicio trató ${num(m.total)} amenazas sobre las alertas del SIEM.`
  s += ` El ${pc(m.pct_auto)} se contuvo en automático y el ${pc(m.pct_humano)} pasó por un analista`
  s += m.tasa_override ? `, que corrigió al motor en el ${pc(m.tasa_override)} de los casos.` : "."
  s += ` Los falsos positivos se quedaron en el ${pc(m.tasa_fp)}`
  s += m.mttr_mediano_seg != null ? ` y el tiempo mediano de respuesta humana en ${Math.round(m.mttr_mediano_seg)} s.` : "."
  return s
}

// Recomendaciones que los datos justifican (ninguna inventada): SLA incumplidos, falsos positivos
// altos, contenciones fallidas, incidentes abiertos y el equipo más atacado.
export function recomendaciones(m: Metricas, fallidas: number, abiertos: number): string[] {
  const r: string[] = []
  const sla = m.sla_incumplidos ?? 0
  if (sla > 0) r.push(sla === 1 ? "Revisar el caso que superó el SLA de respuesta humana y su causa." : `Revisar los ${sla} casos que superaron el SLA de respuesta humana y su causa.`)
  if (m.total && m.tasa_fp > 0.05) r.push(`Ajustar las reglas del SIEM: el ${pc(m.tasa_fp)} de falsos positivos genera ruido para el equipo.`)
  if (fallidas > 0) r.push(fallidas === 1 ? "Una contención falló: comprobar la conectividad del conector con ese equipo." : `${fallidas} contenciones fallaron: comprobar la conectividad del conector con esos equipos.`)
  if (abiertos > 0) r.push(abiertos === 1 ? "Queda un incidente abierto al cierre del periodo: asignarle responsable." : `Quedan ${abiertos} incidentes abiertos al cierre del periodo: asignarles responsable.`)
  const top = m.top_activos?.[0]
  if (top && m.total && top.n / m.total > 0.25) r.push(`Endurecer ${top.nombre}: concentró el ${pc(top.n / m.total)} de los ataques.`)
  return r
}
