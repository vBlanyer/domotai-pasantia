// Datos del informe en PDF: qué secciones hay y cómo se reúne todo lo que pinta el documento
// (métricas del periodo y del anterior, verificación de la cadena y la traza del periodo).
import { getMetricas, getTrazas, getVerificacion, operadorActual, type Metricas, type Decision } from "@/api"
import { etiquetaPeriodo, periodoAnterior, nombreArchivo, enPeriodo } from "@/informe"
import { incidentesDe, type IncidenteVista } from "@/incidentes"

export type Seccion = "resumen" | "indicadores" | "amenazas" | "humanas" | "incidentes" | "attack" | "integridad" | "detalle"
export const SECCIONES: { id: Seccion; nombre: string; defecto: boolean }[] = [
  { id: "resumen", nombre: "Resumen ejecutivo", defecto: true }, { id: "indicadores", nombre: "Indicadores y SLA", defecto: true },
  { id: "amenazas", nombre: "Amenazas y orígenes", defecto: true }, { id: "humanas", nombre: "Decisiones humanas", defecto: true },
  { id: "incidentes", nombre: "Incidentes del periodo", defecto: true },
  { id: "attack", nombre: "Cobertura ATT&CK", defecto: true }, { id: "integridad", nombre: "Integridad de la traza", defecto: true },
  { id: "detalle", nombre: "Detalle de cada decisión (anexo)", defecto: false },
]

export type DatosInforme = {
  periodo: { desde: string; hasta: string; etiqueta: string; etiquetaAnterior: string }
  nombre: string; para: string; generado: { en: string; por: string }
  m: Metricas; anterior: Metricas | null
  verificacion: { ok: boolean; roto_en?: number | null } | null; ultimoHash: string | null
  incidentes: IncidenteVista[]; fallidas: { activo: string; n: number }[]; decisiones: Decision[]
  secciones: Set<Seccion>
}

const TRAZAS_INFORME = 5000

export async function datosInforme(m: Metricas, desde: string, hasta: string, para: string, secciones: Set<Seccion>, ahora = new Date()): Promise<DatosInforme> {
  const ant = periodoAnterior(desde, hasta)
  const [a, v, t] = await Promise.all([getMetricas(ant), getVerificacion(), getTrazas(TRAZAS_INFORME)])
  const regs: Decision[] = Array.isArray(t) ? t : []
  // las decisiones del periodo; las actualizaciones de caso se conservan todas (el estado actual del caso)
  const delPeriodo = regs.filter((r) => (r.tipo && r.tipo !== "decision") || enPeriodo(r.timestamp ?? "", desde, hasta))
  const decisiones = delPeriodo.filter((r) => !r.tipo || r.tipo === "decision")
  const fallidas = new Map<string, number>()
  for (const d of decisiones) if (d.contencion === "fallida") fallidas.set(d.activo ?? "—", (fallidas.get(d.activo ?? "—") ?? 0) + 1)
  const ultimo = [...regs].reverse().find((r) => r.hash)
  return {
    periodo: { desde, hasta, etiqueta: etiquetaPeriodo(desde, hasta), etiquetaAnterior: etiquetaPeriodo(ant.desde, ant.hasta) },
    nombre: nombreArchivo(desde, hasta), para,
    generado: { en: ahora.toLocaleString("es", { dateStyle: "long", timeStyle: "short" }), por: operadorActual() },
    m, anterior: "error" in a ? null : a,
    verificacion: "error" in v ? null : v, ultimoHash: ultimo?.hash ?? null,
    incidentes: incidentesDe(delPeriodo, ahora.getTime()),
    fallidas: [...fallidas.entries()].map(([activo, n]) => ({ activo, n })).sort((x, y) => y.n - x.n),
    decisiones: [...decisiones].reverse(), secciones,
  }
}

