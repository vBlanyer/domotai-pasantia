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
// Recomendación de respuesta dirigida (asesora): no es la acción que se ejecuta, es lo que el
// triaje sugiere valorar (contener origen / endurecer servicio / enrutar / observar).
export const RecomendacionSchema = z.object({
  respuesta: z.string().nullable().optional(), accion_sugerida: z.string().nullable().optional(),
  ruta: z.string().nullable().optional(), servicio: z.string().nullable().optional(),
  nota: z.string().nullable().optional(),
}).passthrough()
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
  recomendacion: RecomendacionSchema.nullable().optional(),
  aviso: z.string().nullable().optional(),               // señal de vigilancia 'low-and-slow' (asesora)
  resultado_filtro: z.string().nullable().optional(), veredicto_humano: z.string().nullable().optional(),
  veredicto_por: z.string().nullable().optional(),       // no repudio: quién aprobó
  clase_reclasificada: z.string().nullable().optional(),
  // posición en la cadena completa: identidad de la fila (los id_decision se repiten)
  indice: z.number().nullable().optional(),
  // registro de reversión (qué deshizo, dónde, si se aplicó) y de error (por qué no se procesó)
  id_decision_revertida: z.string().nullable().optional(), indice_revertido: z.number().nullable().optional(),
  exito: z.boolean().nullable().optional(), accion_id: z.string().nullable().optional(),
  nodo: z.string().nullable().optional(), error: z.string().nullable().optional(),
  // relaciones evento-equipo en la red y dispositivo de contención
  relaciones: z.record(z.string(), z.array(z.string())).nullable().optional(), contencion: z.string().nullable().optional(), dispositivo: z.string().nullable().optional(),
  // ciclo de vida del caso (registro `actualizacion_caso`): estado/asignado/nota + quién y cuándo
  estado: z.string().nullable().optional(), asignado: z.string().nullable().optional(),
  nota: z.string().nullable().optional(), operador: z.string().nullable().optional(),
  decidido_en: z.string().nullable().optional(),
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
  // lo que respondió el modelo y por qué no pasó el anclaje (se muestra la plantilla en su lugar)
  justificacion_descartada: z.object({
    motivo: z.string().nullable().optional(), texto: z.string().nullable().optional(),
  }).passthrough().nullable().optional(),
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
  recomendacion: RecomendacionSchema.nullable().optional(),
}).passthrough()
const NodoRedSchema = z.object({
  nombre: z.string(), ip: z.string().nullable().optional(), tipo: z.string(),
  zona: z.string().nullable().optional(), funcion: z.string().nullable().optional(),
  criticidad: z.string().nullable().optional(),
  servicios_prestados: z.array(z.union([z.number(), z.string()])).optional(),
  depende_de: z.array(z.string()).optional(), salud: z.string().nullable().optional(),
  actividad: z.object({
    objetivo: z.number(), origen: z.number(), contuvo_aqui: z.number(), pendientes: z.number(),
    estado: z.string(), ultima: z.string().nullable().optional(),
  }),
})
export const RedSchema = z.object({
  nodos: z.array(NodoRedSchema),
  enlaces: z.array(z.tuple([z.string(), z.string()])),
  dependencias: z.array(z.tuple([z.string(), z.string()])),
  zonas: z.array(z.object({ nombre: z.string(), nodos: z.array(z.string()) })),
  avisos: z.array(z.string()).optional(),
})
export const ContencionSchema = z.object({
  id_decision: z.string(), objetivo: z.string().nullable(),           // IP, cuenta o servicio bloqueado
  ip: z.string().nullable().optional(), usuario: z.string().nullable().optional(),
  servicio: z.string().nullable().optional(), activo: z.string().nullable(),
  nodo: z.string().nullable(), accion_id: z.string(), ts: z.string().nullable(),
  via_escalada: z.boolean().optional(),
})
export type Contencion = z.infer<typeof ContencionSchema>
export const PendienteSchema = z.object({
  id: z.string(), tipo: z.string(), prompt: z.string(), lineas: z.array(z.string()),
  // cola no bloqueante: orden por severidad y cuántas repeticiones llegaron mientras espera.
  severidad: z.number().nullable().optional(), suprimidas: z.number().nullable().optional(),
  // menú que se está mostrando: se reenvía al responder para que el backend descarte una
  // respuesta a un menú ya superado (p. ej. «Aprobar» justo después de «Reclasificar»).
  paso: z.number().nullable().optional(),
  // null = vetada sin sustituta: aprobarla no ejecuta nada (ausente en daemons antiguos)
  accion_final: z.string().nullable().optional(),
  // estado activo y origen de la amenaza
  activo: z.string().nullable().optional(), origen_ip: z.string().nullable().optional(),
  // hora de encolado (ISO, del servidor): el SLA del analista en el visor («lleva esperando X»)
  encolado_en: z.string().nullable().optional(),
})
export const VerificacionSchema = z.object({
  ok: z.boolean(), roto_en: z.number().nullable().optional(), motivo: z.string().optional(),
})
export const MetricasSchema = z.object({
  total: z.number(), fp: z.number(), tasa_fp: z.number(),
  auto: z.number(), pct_auto: z.number(), suprimidas: z.number(),
  // valor: carga que va al humano y con qué frecuencia el analista corrige al motor
  escalado_humano: z.number().optional(), pct_humano: z.number().optional(),
  resueltos_humano: z.number().optional(), override: z.number().optional(),
  tasa_override: z.number().optional(),
  mttr_seg: z.number().nullable(),
  por_clase: z.record(z.string(), z.number()), veredictos: z.record(z.string(), z.number()),
  por_dia: z.array(z.object({ dia: z.string(), n: z.number() })),
  top_activos: z.array(z.object({ nombre: z.string(), n: z.number() })),
  mitre: z.array(z.object({ tecnica: z.string(), n: z.number() })),
  // periodo del informe (null = todo el histórico)
  desde: z.string().nullable().optional(), hasta: z.string().nullable().optional(),
})

export type Salud = z.infer<typeof SaludSchema>
export type Decision = z.infer<typeof DecisionSchema>
export type Detalle = z.infer<typeof DetalleSchema>
export type Pasaje = z.infer<typeof PasajeSchema>
export type Pendiente = z.infer<typeof PendienteSchema>
export type Verificacion = z.infer<typeof VerificacionSchema>
export type Metricas = z.infer<typeof MetricasSchema>
export type Red = z.infer<typeof RedSchema>
export type NodoRed = z.infer<typeof NodoRedSchema>

// A2 de la auditoría 20/10: «daemon caído», «token rechazado» y «respuesta que no valida» son fallos
// DISTINTOS. `causa` los separa para que SinConexion no mande a arrancar un daemon que está vivo.
export type Causa = "auth" | "red" | "http" | "datos"
export type Fallo = { error: string; causa?: Causa }
// Al fallar el sondeo se conservan los últimos datos buenos (y cuándo llegaron): la vista no se vacía.
export type FalloCon<T> = Fallo & { datos?: T; desde?: number }

// Desfase reloj-servidor − reloj-navegador, de la cabecera `Date` de cada respuesta: el SLA de la cola
// («pendiente hace X») compara contra la hora del DAEMON, no la del navegador (A3: drift en WSL2/VMs).
let desfaseServidorMs = 0
export function ahoraServidor(): number {
  return Date.now() + desfaseServidorMs
}

async function pedirCrudo(ruta: string): Promise<{ json: unknown } | Fallo> {
  try {
    const r = await fetch(BASE + ruta, { headers: cabeceras() })
    const fecha = r.headers?.get?.("date")
    if (fecha) {
      const t = Date.parse(fecha)
      // Solo se mueve el ancla si el desfase medido cambió de verdad (> 2 s): la cabecera tiene
      // resolución de 1 s y la latencia de cada respuesta metería jitter en el «hace X» de la cola.
      if (!Number.isNaN(t) && Math.abs(t - Date.now() - desfaseServidorMs) > 2000) {
        desfaseServidorMs = t - Date.now()
      }
    }
    if (r.status === 401 || r.status === 403) return { error: `HTTP ${r.status}`, causa: "auth" }
    if (!r.ok) return { error: `HTTP ${r.status}`, causa: "http" }   // 404 del detalle, 500…
    return { json: await r.json() }
  } catch (e) {
    return { error: String(e), causa: "red" }
  }
}

async function pedir<T>(ruta: string, esquema: z.ZodType<T>): Promise<T | Fallo> {
  const r = await pedirCrudo(ruta)
  if ("error" in r) return r
  const p = esquema.safeParse(r.json)
  return p.success ? p.data : { error: p.error.issues[0]?.message ?? "respuesta inválida", causa: "datos" }
}

// Lista tolerante: UN registro malformado se descarta (un daemon más nuevo, un registro raro en la
// traza), no tira la vista entera. Solo si ninguno valida es un fallo de datos de verdad.
async function pedirLista<T>(ruta: string, elemento: z.ZodType<T>): Promise<T[] | Fallo> {
  const r = await pedirCrudo(ruta)
  if ("error" in r) return r
  if (!Array.isArray(r.json)) return { error: "se esperaba una lista", causa: "datos" }
  const buenos = r.json.map((x) => elemento.safeParse(x)).filter((p) => p.success).map((p) => p.data)
  if (r.json.length > 0 && buenos.length === 0) return { error: "ningún registro valida", causa: "datos" }
  if (buenos.length < r.json.length) {
    // Residual asumido: el descarte es silencioso para el analista (la alternativa — tirar la lista
    // entera — es peor); al menos queda rastro en la consola del navegador para diagnosticar.
    console.warn(`[visor] ${r.json.length - buenos.length} registro(s) de ${ruta} no validan y se descartan`)
  }
  return buenos
}

export const getSalud = () => pedir("/api/salud", SaludSchema)
export const getDecisiones = () => pedirLista("/api/decisiones", DecisionSchema)
export const getPendientes = () => pedirLista("/api/pendientes", PendienteSchema)
export const getTrazas = (limite?: number) =>
  pedirLista(`/api/trazas${limite ? `?limite=${limite}` : ""}`, DecisionSchema)

// Ciclo de caso plegado en el SERVIDOR sobre el fichero completo (A4): el caso no «rejuvenece»
// cuando sus actualizaciones salen de la ventana de /api/trazas, y el panel no descarga la traza.
export const CasoSchema = z.object({
  estado: z.string(), asignado: z.string().nullable().optional(),
  notas: z.array(z.object({
    texto: z.string(), operador: z.string().nullable().optional(),
    decidido_en: z.string().nullable().optional(),
  })),
  actualizado_en: z.string().nullable().optional(),
}).passthrough()
export type Caso = z.infer<typeof CasoSchema>
export const getCaso = (id: string) => pedir(`/api/caso/${encodeURIComponent(id)}`, CasoSchema)

// Feed vivo del daemon para la vista «Consola» (incremental: solo líneas con n > desde).
export const ConsolaSchema = z.object({
  hasta: z.number(),
  lineas: z.array(z.object({ n: z.number(), t: z.string(), linea: z.string() })),
})
export type Consola = z.infer<typeof ConsolaSchema>
export const getConsola = (desde = 0) => pedir(`/api/consola?desde=${desde}`, ConsolaSchema)

// La lista utilizable de un resultado del sondeo: la buena, la congelada de un fallo, o null.
// (El aviso de pendientes la usa para NO olvidar lo visto ni re-notificar tras un parpadeo de red.)
export function listaConocida<T>(r: T[] | FalloCon<T[]> | undefined): T[] | null {
  if (Array.isArray(r)) return r
  if (r && "error" in r && r.datos) return r.datos
  return null
}
// Con `indice` el backend devuelve ESE registro aunque su id se repita en la traza (relanzamientos).
export const getTrazaDetalle = (id: string, indice?: number | null) =>
  pedir(`/api/traza/${encodeURIComponent(id)}${indice != null ? `?indice=${indice}` : ""}`, DetalleSchema)
export const getVerificacion = () => pedir("/api/verificar", VerificacionSchema)
export const getMetricas = (p?: { desde?: string; hasta?: string }) => {
  const q = new URLSearchParams()
  if (p?.desde) q.set("desde", p.desde)
  if (p?.hasta) q.set("hasta", p.hasta)
  const qs = q.toString()
  return pedir(`/api/metricas${qs ? `?${qs}` : ""}`, MetricasSchema)
}
export const getRed = () => pedir("/api/red", RedSchema)
export const getContenciones = () => pedir("/api/contenciones", z.array(ContencionSchema))
export const getPausa = () => pedir("/api/pausa", z.object({ pausada: z.boolean() }))

// Nombre del operador que aprueba (no repudio): se guarda por navegador y viaja en /api/aprobar.
const OPERADOR_KEY = "mdr.operador"
export function operadorActual(): string {
  try { return localStorage.getItem(OPERADOR_KEY) || "" } catch { return "" }
}
export function fijarOperador(nombre: string): void {
  try { localStorage.setItem(OPERADOR_KEY, nombre) } catch { /* modo privado: solo esta sesión */ }
}

// Token opcional de la consola (#6): si el daemon arranca con TRIAJE_CONSOLA_TOKEN, la API exige
// 'Authorization: Bearer <token>'. Se guarda por sesión (más sensible que el nombre del operador).
// Sin token guardado no se manda cabecera y una consola abierta funciona igual que siempre.
const TOKEN_KEY = "mdr.token"
export function tokenActual(): string {
  try { return sessionStorage.getItem(TOKEN_KEY) || "" } catch { return "" }
}
export function fijarToken(t: string): void {
  try { sessionStorage.setItem(TOKEN_KEY, t) } catch { /* modo privado */ }
}
function cabeceras(base: Record<string, string> = {}): Record<string, string> {
  const t = tokenActual()
  return t ? { ...base, Authorization: `Bearer ${t}` } : base
}

// "ok" | "auth" (token rechazado: el aviso puede decirlo) | "fallo" (409 pendiente caduca, o red).
export async function aprobar(id: string, respuesta: string, paso?: number | null): Promise<"ok" | "auth" | "fallo"> {
  try {
    const operador = operadorActual()
    const r = await fetch(BASE + "/api/aprobar", {
      method: "POST", headers: cabeceras({ "Content-Type": "application/json" }),
      // sin paso (escaladas de la ruta bloqueante) no se manda y el backend no lo comprueba
      body: JSON.stringify({ id, respuesta, ...(paso != null ? { paso } : {}), ...(operador ? { operador } : {}) }),
    })
    return r.ok ? "ok" : r.status === 401 || r.status === 403 ? "auth" : "fallo"
  } catch {
    return "fallo"
  }
}

// Ciclo de vida del caso: anota estado/asignado/nota de una decisión. El daemon lo añade a la traza
// como registro `actualizacion_caso` encadenado (no muta la decisión). El operador sale del token
// (no repudio); si no hay token, se manda el nombre del operador local. true si se anotó.
export async function actualizarCaso(
  id: string, campos: { estado?: string; asignado?: string; nota?: string },
): Promise<boolean> {
  try {
    const operador = operadorActual()
    const r = await fetch(BASE + "/api/caso", {
      method: "POST", headers: cabeceras({ "Content-Type": "application/json" }),
      body: JSON.stringify({ id, ...campos, ...(operador ? { operador } : {}) }),
    })
    return r.ok            // 200 -> true; 400 (actualización vacía/estado inválido) o 409 -> false
  } catch {
    return false
  }
}

// Kill switch (#8): pausa global de la automatización y des-bloqueo en masa.
export async function setPausa(pausar: boolean): Promise<boolean> {
  try {
    const operador = operadorActual()
    const r = await fetch(BASE + "/api/pausa", {
      method: "POST", headers: cabeceras({ "Content-Type": "application/json" }),
      body: JSON.stringify({ pausar, ...(operador ? { operador } : {}) }),
    })
    return r.ok
  } catch { return false }
}

export async function revertirTodo(): Promise<{ revertidas: number; fallidas: number } | null> {
  try {
    const operador = operadorActual()
    const r = await fetch(BASE + "/api/revertir-todo", {
      method: "POST", headers: cabeceras({ "Content-Type": "application/json" }),
      // confirmar: el backend exige el gesto explícito (B2) — el diálogo de la vista es el gesto.
      body: JSON.stringify({ confirmar: true, ...(operador ? { operador } : {}) }),
    })
    if (!r.ok) return null
    return await r.json()
  } catch { return null }
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
    // «── Validación humana ── ACCION en DISPOSITIVO …» es la pregunta del agente (--agente): dice qué
    // se aprueba y dónde. Las demás líneas «──» son separadores de la terminal.
    const paso = t.match(/^── Validación humana ── (.+)$/)
    if (paso) { info.push(`Acción: ${paso[1]}`); continue }
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

// Un fallo que llega cuando YA hubo datos buenos se devuelve con esos datos adjuntos (C2): la vista
// puede seguir mostrando la última tabla con un aviso, en vez de vaciarse al primer parpadeo de red.
export function recordando<T>(r: T | Fallo, previo: { v: T; en: number } | undefined): T | FalloCon<T> {
  if (typeof r === "object" && r !== null && "error" in r && previo !== undefined) {
    return { ...(r as Fallo), datos: previo.v, desde: previo.en }
  }
  return r
}

export function useSondeo<T>(fn: () => Promise<T | Fallo>, ms = 2000): T | FalloCon<T> | undefined {
  const [v, setV] = useState<T | FalloCon<T>>()
  useEffect(() => {
    let vivo = true
    let seq = 0
    const bueno: { actual?: { v: T; en: number } } = {}
    const tick = async () => {
      const mio = ++seq
      const r = await fn()
      // `mio !== seq`: llegó ya una respuesta más nueva — esta, lenta, no la pisa (A6).
      if (!vivo || mio !== seq) return
      if (!(typeof r === "object" && r !== null && "error" in r)) bueno.actual = { v: r as T, en: Date.now() }
      const valor = recordando(r, bueno.actual)
      // Solo re-renderiza si los datos cambiaron: devolver la misma referencia hace que React
      // descarte el render. Sin esto, cada sondeo (2 s) re-renderiza toda la app y los gráficos
      // Recharts, y esas ráfagas se "comen" los clics del usuario.
      setV((prev) => (JSON.stringify(prev) === JSON.stringify(valor) ? prev : valor))
    }
    tick()
    const id = setInterval(tick, ms)
    return () => { vivo = false; clearInterval(id) }
  }, [])
  return v
}
