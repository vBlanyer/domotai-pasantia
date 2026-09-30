import { z } from "zod"
import { useEffect, useState } from "react"

// Base de la API: relativa (mismo origen) en el build que sirve el daemon --web (funciona en
// cualquier puerto); en desarrollo (Vite en :5173) apunta al daemon en :8787; VITE_API lo sobreescribe.
export function baseApi(env: { VITE_API?: string; DEV?: boolean }): string {
  return env.VITE_API ?? (env.DEV ? "http://127.0.0.1:8787" : "")
}
const BASE = baseApi(import.meta.env)

export const ServicioSchema = z.object({ nombre: z.string(), estado: z.string(), depende_de: z.array(z.string()) })
export const SaludSchema = z.union([
  z.object({ sin_datos: z.literal(true) }),
  z.object({ t: z.string().nullable(), servicios: z.array(ServicioSchema), caidos: z.number(), total: z.number() }),
])
export const DecisionSchema = z.object({
  id_decision: z.string().nullable().optional(), timestamp: z.string().nullable().optional(),
  activo: z.string().nullable().optional(), clase: z.string().nullable().optional(),
  confianza: z.number().nullable().optional(), origen_ip: z.string().nullable().optional(),
  accion_final: z.string().nullable().optional(), requiere_humano: z.boolean().nullable().optional(),
  impacto: z.string().nullable().optional(), motivo: z.string().nullable().optional(),
  cascada: z.array(z.string()).nullable().optional(),
  version_justificador: z.string().nullable().optional(),
  tecnica_mitre: z.array(z.string()).nullable().optional(), con_rag: z.boolean().nullable().optional(),
  hash: z.string().nullable().optional(), hash_previo: z.string().nullable().optional(),
  tipo: z.string().nullable().optional(), alertas_suprimidas: z.number().nullable().optional(),
  // gravedad (1..4), propuesta vs final y cómo la trató el filtro, y el desenlace humano
  prioridad: z.number().nullable().optional(), accion_propuesta: z.string().nullable().optional(),
  resultado_filtro: z.string().nullable().optional(), veredicto_humano: z.string().nullable().optional(),
  clase_reclasificada: z.string().nullable().optional(),
  // posición en la cadena completa: identidad de la fila (los id_decision se repiten)
  indice: z.number().nullable().optional(),
})
// Detalle completo de una decisión (/api/traza/<id>): el texto de la justificación y los pasajes
// del RAG. Laxo a propósito (`passthrough`): la traza lleva muchos más campos que no renderizamos.
export const PasajeSchema = z.object({
  id: z.string().optional(), titulo: z.string().nullable().optional(), texto: z.string().nullable().optional(),
}).passthrough()
// Plan de mitigación (escalada determinista o agente): resultado y dispositivo que contuvo.
const PlanSchema = z.object({
  resultado: z.string().nullable().optional(), escalado: z.boolean().nullable().optional(),
  dispositivo_ejecutor: z.string().nullable().optional(),
  // la orden que contuvo de verdad (en el dispositivo al que se escaló)
  orden_efectiva: z.object({
    accion_id: z.string().nullable().optional(), nodo_objetivo: z.string().nullable().optional(),
  }).passthrough().nullable().optional(),
  // el impacto de esa orden, con lo que enruta el dispositivo (no el del bloqueo en el activo)
  impacto_efectivo: z.object({
    dispositivo: z.string().nullable().optional(), motivo: z.string().nullable().optional(),
  }).passthrough().nullable().optional(),
}).passthrough()
export const DetalleSchema = z.object({
  id_decision: z.string().nullable().optional(),
  justificacion: z.string().nullable().optional(),
  version_justificador: z.string().nullable().optional(),
  consulta_rag: z.string().nullable().optional(),
  recuperacion_agentica: z.boolean().nullable().optional(),
  pasajes_usados: z.array(z.string()).nullable().optional(),   // IDs; el backend los resuelve en `pasajes`
  pasajes: z.array(PasajeSchema).nullable().optional(),         // {id, titulo, texto} del corpus
  accion_propuesta: z.string().nullable().optional(), accion_final: z.string().nullable().optional(),
  // cómo trató el filtro del perfil la propuesta (veta/degrada/permite) y si pidió humano
  resultado_filtro: z.string().nullable().optional(), requiere_humano: z.boolean().nullable().optional(),
  justificacion_estructurada: z.object({
    evidencia: z.record(z.string(), z.unknown()).nullable().optional(),
    tecnica_mitre: z.array(z.string()).nullable().optional(),
    accion_sugerida: z.string().nullable().optional(),
  }).passthrough().nullable().optional(),
  impacto_determinado: z.object({
    nivel: z.string().nullable().optional(), motivo: z.string().nullable().optional(),
    activos_afectados_en_cascada: z.array(z.string()).nullable().optional(),
  }).passthrough().nullable().optional(),
  // Desenlace de la contención: la orden, si se ejecutó y se verificó en el activo, y —si el activo
  // no respondió— la escalada hacia el perímetro (o el plan del agente en modo --agente).
  veredicto_humano: z.string().nullable().optional(),
  veredicto_escalada: z.string().nullable().optional(),   // aprobar/rechazar la escalada diferida
  ruta: z.string().nullable().optional(),                  // destino de una amenaza enrutada
  orden: z.object({
    accion_id: z.string().nullable().optional(), nodo_objetivo: z.string().nullable().optional(),
  }).passthrough().nullable().optional(),
  ejecucion: z.object({
    exito: z.boolean().nullable().optional(), comando_ejecutado: z.string().nullable().optional(),
  }).passthrough().nullable().optional(),
  verificacion: z.object({ verificado: z.boolean().nullable().optional() }).passthrough().nullable().optional(),
  escalada: PlanSchema.nullable().optional(),
  mitigacion_agente: PlanSchema.nullable().optional(),
}).passthrough()
export const EquipoSchema = z.object({
  nombre: z.string(), ip: z.string().nullable().optional(),
  funcion: z.string().nullable().optional(), criticidad: z.string().nullable().optional(),
  categoria: z.string(), servicios_prestados: z.array(z.number()).nullable().optional(),
  depende_de: z.array(z.string()).nullable().optional(), estado: z.string().nullable().optional(),
})
export const PendienteSchema = z.object({
  id: z.string(), tipo: z.string(), prompt: z.string(), lineas: z.array(z.string()),
  // cola no bloqueante: orden por severidad y cuántas repeticiones llegaron mientras espera.
  severidad: z.number().nullable().optional(), suprimidas: z.number().nullable().optional(),
  // menú que se está mostrando: se reenvía al responder para que el backend descarte una
  // respuesta a un menú ya superado (p. ej. «Aprobar» justo después de «Reclasificar»).
  paso: z.number().nullable().optional(),
  // null = vetada sin sustituta: aprobarla no ejecuta nada (ausente en daemons antiguos)
  accion_final: z.string().nullable().optional(),
})
export const VerificacionSchema = z.object({
  ok: z.boolean(), roto_en: z.number().nullable().optional(), motivo: z.string().optional(),
})
export const MetricasSchema = z.object({
  total: z.number(), fp: z.number(), tasa_fp: z.number(),
  auto: z.number(), pct_auto: z.number(), suprimidas: z.number(),
  mttr_seg: z.number().nullable(),
  por_clase: z.record(z.string(), z.number()), veredictos: z.record(z.string(), z.number()),
  por_dia: z.array(z.object({ dia: z.string(), n: z.number() })),
  top_activos: z.array(z.object({ nombre: z.string(), n: z.number() })),
  mitre: z.array(z.object({ tecnica: z.string(), n: z.number() })),
})

export type Salud = z.infer<typeof SaludSchema>
export type Equipo = z.infer<typeof EquipoSchema>
export type Decision = z.infer<typeof DecisionSchema>
export type Detalle = z.infer<typeof DetalleSchema>
export type Pasaje = z.infer<typeof PasajeSchema>
export type Pendiente = z.infer<typeof PendienteSchema>
export type Verificacion = z.infer<typeof VerificacionSchema>
export type Metricas = z.infer<typeof MetricasSchema>

async function pedir<T>(ruta: string, esquema: z.ZodType<T>): Promise<T | { error: string }> {
  try {
    const r = await fetch(BASE + ruta)
    if (!r.ok) throw new Error(`HTTP ${r.status}`)   // 404 del detalle -> rama de error, no se parsea
    return esquema.parse(await r.json())
  } catch (e) {
    return { error: String(e) }
  }
}

export const getSalud = () => pedir("/api/salud", SaludSchema)
export const getEquipos = () => pedir("/api/equipos", z.array(EquipoSchema))
export const getDecisiones = () => pedir("/api/decisiones", z.array(DecisionSchema))
export const getPendientes = () => pedir("/api/pendientes", z.array(PendienteSchema))
export const getTrazas = () => pedir("/api/trazas", z.array(DecisionSchema))
// Con `indice` el backend devuelve ESE registro aunque su id se repita en la traza (relanzamientos).
export const getTrazaDetalle = (id: string, indice?: number | null) =>
  pedir(`/api/traza/${encodeURIComponent(id)}${indice != null ? `?indice=${indice}` : ""}`, DetalleSchema)
export const getVerificacion = () => pedir("/api/verificar", VerificacionSchema)
export const getMetricas = () => pedir("/api/metricas", MetricasSchema)

export async function aprobar(id: string, respuesta: string, paso?: number | null): Promise<boolean> {
  try {
    const r = await fetch(BASE + "/api/aprobar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      // sin paso (escaladas de la ruta bloqueante) no se manda y el backend no lo comprueba
      body: JSON.stringify({ id, respuesta, ...(paso != null ? { paso } : {}) }),
    })
    return r.ok            // 200 -> true; 409 (pendiente caduca) -> false, no lanza
  } catch {
    return false
  }
}

export function controlesDePendiente(p: Pendiente): { etiqueta: string; respuesta: string; variante: "aprobar" | "rechazar" }[] {
  return p.tipo === "escalada"
    ? [{ etiqueta: "Aprobar", respuesta: "s", variante: "aprobar" }, { etiqueta: "Rechazar", respuesta: "", variante: "rechazar" }]
    : [{ etiqueta: "Aprobar (1)", respuesta: "1", variante: "aprobar" }, { etiqueta: "Rechazar (2)", respuesta: "2", variante: "rechazar" }]
}

export type Opcion = { n: string; etiqueta: string }
export type PendienteVista = {
  incidente?: string; info: string[]; consecuencia?: string; titulo?: string; opciones: Opcion[]
  cascada: string[]   // activos que dependen del bloqueado y caerían al aprobar
}

// Convierte las líneas capturadas del prompt de la terminal en algo presentable: separa la info del
// incidente de las opciones del menú (que se vuelven botones), y descarta lo redundante (el título
// "¿Qué hacer…" y la línea "Elige [1-N]:"). Reinicia las opciones en cada título para que el submenú
// de reclasificación muestre SOLO las clases, no también el menú de veredicto anterior.
export function parsearPendiente(p: Pendiente): PendienteVista {
  const texto = p.lineas.length ? p.lineas.join("\n") : p.prompt
  const info: string[] = []
  let opciones: Opcion[] = []
  let incidente: string | undefined, consecuencia: string | undefined, titulo: string | undefined
  for (const raw of texto.split("\n")) {
    const t = raw.trim()
    if (!t) continue
    if (t.startsWith("¿Qué hacer") || t.startsWith("Nueva clase")) { titulo = t; opciones = []; continue }
    const op = t.match(/^(\d+)\)\s*(.+)$/)
    if (op) { opciones.push({ n: op[1], etiqueta: op[2] }); continue }
    if (/^⚠?\s*Incidente:/.test(t)) { incidente = t.replace(/^⚠\s*/, ""); continue }
    if (t.startsWith("──") || /^Elige \[/.test(t)) continue
    if (t.startsWith("Consecuencia:")) { consecuencia = t.slice("Consecuencia:".length).trim(); continue }
    info.push(t)
  }
  // impacto._motivo añade « · en cascada: a, b, c» cuando la hay; en una escalada le sigue « · en
  // <cortafuegos>: …», que no son activos que caen: la lista acaba en el siguiente « · ».
  const m = consecuencia?.match(/en cascada:\s*(.+?)(?:\s+·\s+|$)/)
  const cascada = m ? m[1].split(",").map((s) => s.trim()).filter(Boolean) : []
  return { incidente, info, consecuencia, titulo, opciones, cascada }
}

export function useSondeo<T>(fn: () => Promise<T>, ms = 2000): T | undefined {
  const [v, setV] = useState<T>()
  useEffect(() => {
    let vivo = true
    const tick = async () => {
      const r = await fn()
      if (!vivo) return
      // Solo re-renderiza si los datos cambiaron: devolver la misma referencia hace que React
      // descarte el render. Sin esto, cada sondeo (2 s) re-renderiza toda la app y los gráficos
      // Recharts, y esas ráfagas se "comen" los clics del usuario.
      setV((prev) => (JSON.stringify(prev) === JSON.stringify(r) ? prev : r))
    }
    tick()
    const id = setInterval(tick, ms)
    return () => { vivo = false; clearInterval(id) }
  }, [])
  return v
}
