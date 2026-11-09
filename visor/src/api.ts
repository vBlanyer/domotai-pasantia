import { z } from "zod"
import { useEffect, useState } from "react"

// Base de la API: relativa (mismo origen) en el build que sirve el daemon --web (funciona en
// cualquier puerto); en desarrollo (Vite en :5173) apunta al daemon en :8787; VITE_API lo sobreescribe.
export function baseApi(env: { VITE_API?: string; DEV?: boolean }): string {
  return env.VITE_API ?? (env.DEV ? "http://127.0.0.1:8787" : "")
}
const BASE = baseApi(import.meta.env)

export const ServicioSchema = z.object({ nombre: z.string(), estado: z.string(), depende_de: z.array(z.string()) })
// Salud del PROPIO daemon (/healthz, #5; fuera de /api/, sin token): lazo vivo, silencio de la ingesta
// y alertas procesadas. `desde` falta cuando el daemon corre sin latido.
export const LatidoSchema = z.object({
  ok: z.boolean(), desde: z.string().nullable().optional(),
  lazo_quietud_s: z.number(), ingesta_silencio_s: z.number().nullable(), alertas: z.number(),
})
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
// Enriquecimiento de la IP de origen (backend: actores.enriquecer_origen): alcance interno/externo,
// clasificación de la IP, tercero de confianza, legitimidad, geolocalización (offline) y ASN. Compartido
// por las decisiones del feed y por los pendientes de la cola de aprobación.
export const EnriquecimientoOrigenSchema = z.object({
  alcance: z.string(), inventariado: z.boolean(), por: z.string().nullable().optional(),
  clasificacion_ip: z.string(), tercero_confiable: z.boolean(), legitimo: z.boolean(),
  geolocalizable: z.boolean(),
  geo: z.object({ pais: z.string().nullable().optional(), ciudad: z.string().nullable().optional(),
    codigo: z.string().nullable().optional(), lat: z.number().nullable().optional(), lon: z.number().nullable().optional() }).nullable().optional(),
  asn: z.object({ asn: z.string(), org: z.string() }).nullable().optional(),
})
// Por qué no quedó contenida (prototipo/accion/fallos.py): F1..F10, qué hacer y si puede ser un ataque.
export const CausaSchema = z.object({
  clase: z.string(), descripcion: z.string().nullable().optional(), accion: z.string().nullable().optional(),
  posible_ataque: z.boolean().nullable().optional(), regresion: z.boolean().nullable().optional(),
  evidencia: z.string().nullable().optional(),
  dispositivo: z.string().nullable().optional(),          // en el resumen: dónde falló (activo o salto)
}).passthrough()
export type CausaFallo = z.infer<typeof CausaSchema>
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
  espera_humana_s: z.number().nullable().optional(),     // segundos en cola hasta el veredicto
  clase_reclasificada: z.string().nullable().optional(),
  // posición en la cadena completa: identidad de la fila (los id_decision se repiten)
  indice: z.number().nullable().optional(),
  // registro de reversión (qué deshizo, dónde, si se aplicó) y de error (por qué no se procesó)
  id_decision_revertida: z.string().nullable().optional(), indice_revertido: z.number().nullable().optional(),
  exito: z.boolean().nullable().optional(), accion_id: z.string().nullable().optional(),
  nodo: z.string().nullable().optional(), error: z.string().nullable().optional(),
  // relaciones evento-equipo en la red y dispositivo de contención
  relaciones: z.record(z.string(), z.array(z.string())).nullable().optional(), contencion: z.string().nullable().optional(), dispositivo: z.string().nullable().optional(),
  causa: CausaSchema.nullable().optional(),               // por qué falló la contención (lo más grave primero)
  enriquecimiento_origen: EnriquecimientoOrigenSchema.nullable().optional(),
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
  // cada salto (acción o verificación) y, si falló, por qué
  pasos: z.array(z.object({
    tipo: z.string().nullable().optional(), dispositivo: z.string().nullable().optional(),
    causa: CausaSchema.nullable().optional(),
  }).passthrough()).nullable().optional(),
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
  causa_fallo: CausaSchema.nullable().optional(),          // por qué no quedó contenida en el activo
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
  id_decision: z.string(), indice: z.number().nullable().optional(),  // índice de traza: identifica la contención a revertir
  objetivo: z.string().nullable(),                                    // IP, cuenta o servicio bloqueado
  ip: z.string().nullable().optional(), usuario: z.string().nullable().optional(),
  servicio: z.string().nullable().optional(), activo: z.string().nullable(),
  nodo: z.string().nullable(), accion_id: z.string(), ts: z.string().nullable(),
  via_escalada: z.boolean().optional(),
  // la regla aplicada y la que la quita, del catálogo con sus parámetros (se enseñan antes de revertir)
  regla: z.string().nullable().optional(), reversion_cmd: z.string().nullable().optional(),
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
  // ubicación/alcance del origen (mismo enriquecimiento que el feed), para mostrarlo y filtrar por país
  enriquecimiento_origen: EnriquecimientoOrigenSchema.nullable().optional(),
  // hora de encolado (ISO, del servidor): el SLA del analista en el visor («lleva esperando X»)
  encolado_en: z.string().nullable().optional(),
  // resumen de la decisión (por qué lo propone el motor) e id para anotar el caso con la nota del analista
  id_decision: z.string().nullable().optional(), clase: z.string().nullable().optional(),
  confianza: z.number().nullable().optional(), tecnica_mitre: z.array(z.string()).nullable().optional(),
  motivo: z.string().nullable().optional(),
})
export const VerificacionSchema = z.object({
  ok: z.boolean(), roto_en: z.number().nullable().optional(), motivo: z.string().optional(),
})
// Decisiones humanas por analista (analista null = sin nombre registrado, al final).
export const FilaAnalistaSchema = z.object({
  analista: z.string().nullable(), aprobar: z.number(), rechazar: z.number(), reclasificar: z.number(),
  total: z.number(), mediana_seg: z.number().nullable(), fuera_sla: z.number(),
})
export type FilaAnalista = z.infer<typeof FilaAnalistaSchema>
export const MetricasSchema = z.object({
  total: z.number(), fp: z.number(), tasa_fp: z.number(),
  auto: z.number(), pct_auto: z.number(), suprimidas: z.number(),
  // valor: carga que va al humano y con qué frecuencia el analista corrige al motor
  escalado_humano: z.number().optional(), pct_humano: z.number().optional(),
  resueltos_humano: z.number().optional(), override: z.number().optional(),
  tasa_override: z.number().optional(),
  mttr_seg: z.number().nullable(),
  // tiempos de respuesta / SLA (cola humana): mediana + % dentro del umbral e incumplidos
  mttr_mediano_seg: z.number().nullable().optional(), sla_umbral_seg: z.number().optional(),
  sla_resueltos: z.number().optional(), sla_dentro: z.number().optional(),
  sla_incumplidos: z.number().optional(), sla_pct: z.number().nullable().optional(),
  por_clase: z.record(z.string(), z.number()), veredictos: z.record(z.string(), z.number()),
  por_dia: z.array(z.object({ dia: z.string(), n: z.number() })),
  top_activos: z.array(z.object({ nombre: z.string(), n: z.number() })),
  mitre: z.array(z.object({ tecnica: z.string(), n: z.number() })),
  // ranking por familia de amenaza y por país de origen (resumen ejecutivo; opcionales: daemons viejos no los traen)
  por_familia: z.array(z.object({ familia: z.string(), n: z.number() })).optional(),
  por_pais: z.array(z.object({ pais: z.string(), n: z.number() })).optional(),
  por_analista: z.array(FilaAnalistaSchema).optional(),
  // periodo del informe (null = todo el histórico)
  desde: z.string().nullable().optional(), hasta: z.string().nullable().optional(),
})

export type Salud = z.infer<typeof SaludSchema>
export type Servicio = z.infer<typeof ServicioSchema>
export type Latido = z.infer<typeof LatidoSchema>
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
    if (r.status === 401 || r.status === 429) avisarNoAutorizado()   // la consola pide volver a entrar
    if (r.status === 401 || r.status === 403 || r.status === 429) return { error: `HTTP ${r.status}`, causa: "auth" }
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
export const getLatido = () => pedir("/healthz", LatidoSchema)
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
// Para el Panel: las métricas del día (UTC, como compara el daemon) y una ventana de trazas amplia
// para la actividad de 24 h y la comparación con ayer (sin ese margen, la ventana corta no llega).
export const LIMITE_TRAZAS_PANEL = 2000
export const getTrazasPanel = () => getTrazas(LIMITE_TRAZAS_PANEL)
export const getMetricasHoy = () => {
  const d = new Date(ahoraServidor()).toISOString().slice(0, 10)
  return getMetricas({ desde: d, hasta: d })
}
export const getRed = () => pedir("/api/red", RedSchema)
export const getContenciones = () => pedir("/api/contenciones", z.array(ContencionSchema))

// Playbook estático por familia (solo lectura, GET /api/politica): clase típica → acción →
// automatización + vetos, derivado del catálogo + el perfil. Para la vista «Políticas».
export const PoliticaFamiliaSchema = z.object({
  familia: z.string(), clase_tipica: z.string(),
  accion: z.string().nullable().optional(), impacto: z.string().nullable().optional(),
  automatizacion: z.string(), mitre: z.array(z.string()),
  nivel: z.string().nullable().optional(), ruta: z.string().nullable().optional(),
  vetos: z.array(z.string()),
  recomendacion: z.object({ respuesta: z.string(), accion_sugerida: z.string().nullable().optional(),
    ruta: z.string().nullable().optional(), servicio: z.string().nullable().optional(),
    nota: z.string().nullable().optional() }).nullable().optional(),
  postura_familia: z.string().nullable().optional(),
  automatizacion_efectiva: z.string(),
})
export type PoliticaFamilia = z.infer<typeof PoliticaFamiliaSchema>
export const DispositivoPoliticaSchema = z.object({
  activo: z.string(), criticidad: z.string().nullable().optional(), override: z.string().nullable().optional(),
  postura_efectiva: z.string().nullable().optional(), cascada: z.array(z.string()), radio: z.number(),
  cascada_posiblemente_incompleta: z.boolean(),
})
export type DispositivoPolitica = z.infer<typeof DispositivoPoliticaSchema>
export const ZonaPoliticaSchema = z.object({
  zona: z.string(), automatizacion: z.string(), protegida: z.boolean(),
  dispositivos: z.array(DispositivoPoliticaSchema),
})
export type ZonaPolitica = z.infer<typeof ZonaPoliticaSchema>
export const PoliticaEstadoSchema = z.object({
  familias: z.array(PoliticaFamiliaSchema), zonas: z.array(ZonaPoliticaSchema),
})
export type PoliticaEstado = z.infer<typeof PoliticaEstadoSchema>
export const getPolitica = () => pedir("/api/politica", PoliticaEstadoSchema)

export type CambioPolitica = {
  dimension: "familia" | "zona" | "activo"; clave: string
  automatizacion: "automatica_si_confianza" | "humano_siempre" | null
}
// POST /api/politica (fail-closed en el servidor). Lanza si el servidor rechaza o no hay red.
export async function actualizarPolitica(cambio: CambioPolitica, token?: string): Promise<void> {
  const base = { "Content-Type": "application/json" }
  const r = await fetch(BASE + "/api/politica", {
    method: "POST",
    headers: token ? { ...base, Authorization: `Bearer ${token}` } : cabeceras(base),
    body: JSON.stringify(cambio),
  })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
}
export const getPausa = () => pedir("/api/pausa", z.object({ pausada: z.boolean() }))

// ---- sesión de la consola ---------------------------------------------------------------------
// Tres modos, según lo que diga /api/sesion al entrar:
//  · identificado: token por persona (TRIAJE_CONSOLA_OPERADORES); el nombre lo da el daemon y firma.
//  · compartido: token común (TRIAJE_CONSOLA_TOKEN); el nombre lo escribe el analista, sin verificar.
//  · abierta: el daemon no exige token (laboratorio); nombre escrito, sin verificar.
export type ModoSesion = "abierta" | "identificado" | "compartido"
export type Sesion = { modo: ModoSesion; operador: string; desde: number }
let sesion: Sesion | null = null
export const sesionActual = () => sesion
export function iniciarSesion(modo: ModoSesion, operadorDelToken?: string | null): void {
  sesion = { modo, operador: modo === "identificado" ? (operadorDelToken ?? "") : "", desde: Date.now() }
}
export function cerrarSesion(): void { sesion = null; fijarToken("", false) }
export const operadorVerificado = () => sesion?.modo === "identificado" && !!sesion.operador

// Nombre del operador que firma (no repudio). Con token por persona manda el del daemon; si no, el que
// escribió el analista (se recuerda por navegador) y viaja en el cuerpo de cada acción.
const OPERADOR_KEY = "mdr.operador"
export function operadorActual(): string {
  if (operadorVerificado()) return sesion!.operador
  try { return localStorage.getItem(OPERADOR_KEY) || "" } catch { return "" }
}
export function fijarOperador(nombre: string): void {
  try { localStorage.setItem(OPERADOR_KEY, nombre) } catch { /* modo privado: solo esta sesión */ }
}

// Token de la consola (#6/#8): viaja como 'Authorization: Bearer <token>'. Por defecto se guarda en la
// pestaña (sessionStorage: se borra al cerrarla); sin «mantener la sesión» vive solo en memoria y una
// recarga vuelve a pedirlo. Nunca va a localStorage ni al disco.
const TOKEN_KEY = "mdr.token"
let tokenMemoria = ""
export function tokenActual(): string {
  try { return sessionStorage.getItem(TOKEN_KEY) || tokenMemoria } catch { return tokenMemoria }
}
export function fijarToken(t: string, recordar = true): void {
  tokenMemoria = t
  try {
    if (t && recordar) sessionStorage.setItem(TOKEN_KEY, t)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch { /* modo privado: queda en memoria */ }
}

// Un 401/429 de cualquier sondeo avisa a la consola (una vez por tanda) para que pida volver a entrar.
export const EVENTO_NO_AUTORIZADO = "mdr:no-autorizado"
function avisarNoAutorizado(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(EVENTO_NO_AUTORIZADO))
}

export type ResultadoSesion =
  | { tipo: "ok"; requiereToken: boolean; operador: string | null }
  | { tipo: "rechazado" } | { tipo: "bloqueado"; segundos: number } | { tipo: "sin_red" }

// Prueba un token contra /api/sesion SIN guardarlo: la pantalla de acceso solo lo guarda si vale.
export async function comprobarSesion(token: string): Promise<ResultadoSesion> {
  try {
    const r = await fetch(BASE + "/api/sesion", { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (r.status === 429) {
      let seg = Number(r.headers?.get?.("retry-after"))
      if (!seg) { try { seg = Number((await r.json()).reintentar_en) } catch { seg = 0 } }
      return { tipo: "bloqueado", segundos: Math.max(1, Math.round(seg || 30)) }
    }
    if (r.status === 401 || r.status === 403) return { tipo: "rechazado" }
    // un daemon anterior sin /api/sesion responde 404 DESPUÉS de pasar la auth: el token vale
    if (r.status === 404) return { tipo: "ok", requiereToken: !!token, operador: null }
    if (!r.ok) return { tipo: "sin_red" }
    const j = await r.json()
    return { tipo: "ok", requiereToken: !!j?.requiere_token, operador: typeof j?.operador === "string" && j.operador ? j.operador : null }
  } catch {
    return { tipo: "sin_red" }
  }
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

// Conectividad del conector con cada equipo (vista «Conectividad»). La clave privada no viaja nunca:
// solo su huella y la clave pública. Editar exige operador identificado (403 si no).
const PruebaSchema = z.object({
  ok: z.boolean(), estado: z.string(), en: z.string().nullable().optional(),
  puerto: z.number().nullable().optional(), usuario: z.string().nullable().optional(), por: z.string().nullable().optional(),
  pasos: z.array(z.object({ paso: z.string(), ok: z.boolean(), detalle: z.string() })),
  // deriva del sudoers: lo que sudo permite de verdad frente a lo que espera el papel del equipo
  reglas: z.object({ estado: z.string(), sobran: z.array(z.string()), faltan: z.array(z.string()) }).nullable().optional(),
})
const RotacionSchema = z.object({
  iniciada_por: z.string().nullable().optional(), en: z.string().nullable().optional(), huella_nueva: z.string().nullable().optional(),
  equipos: z.record(z.string(), z.object({
    anadida: z.boolean().optional(), probada: z.boolean().optional(), retirada: z.boolean().optional(), error: z.string().nullable().optional(),
  })),
})
export const ConectividadSchema = z.object({
  modo: z.string(), nodo_gestion: z.string().nullable().optional(),
  editable: z.boolean(), motivo_no_editable: z.string().nullable().optional(),
  usuario_defecto: z.string().nullable().optional(), usuario_entorno: z.string(),
  ruta_clave: z.string(), known_hosts: z.string(),
  clave: z.object({ huella: z.string(), tipo: z.string().nullable().optional(), publica: z.string().nullable().optional() }).nullable(),
  equipos: z.array(z.object({
    nombre: z.string(), ip: z.string(), zona: z.string().nullable().optional(), tipo: z.string().nullable().optional(),
    funcion: z.string().nullable().optional(), protegido: z.boolean(), puerto: z.number(), usuario: z.string(),
    ajustado: z.boolean(), huella_fijada: z.string().nullable().optional(), ultima_prueba: PruebaSchema.nullable().optional(),
    // la última contención real en este equipo falló (fase 3 del plan de fallos): resta confianza
    operativo: z.object({
      clase: z.string(), descripcion: z.string().nullable().optional(), accion: z.string().nullable().optional(),
      posible_ataque: z.boolean().nullable().optional(), regresion: z.boolean().nullable().optional(), en: z.string().nullable().optional(),
    }).nullable().optional(),
    // memoria de fallos (fase 5): el MDR perdió el acceso; las contenciones escalan directo y se reprueba
    sin_acceso: z.object({
      clase: z.string(), desde: z.string(), fallos: z.number().nullable().optional(),
      regresion: z.boolean().nullable().optional(), ultimo_sondeo: z.string().nullable().optional(),
    }).nullable().optional(),
    // inventario operativo: papel y reglas del equipo, y si es un alta pendiente o hecha desde la consola
    papel: z.string().nullable().optional(), acciones: z.array(z.string()).nullable().optional(),
    servicios: z.array(z.string()).optional(), cuentas: z.array(z.string()).optional(), cuentas_cualquiera: z.boolean().optional(),
    alta: z.string().nullable().optional(), criticidad: z.string().nullable().optional(),
    depende_de: z.array(z.string()).optional(), interfaz: z.string().nullable().optional(),
  })),
  permisos: z.object({ probar: z.boolean(), editar: z.boolean(), motivo: z.string().nullable().optional(),
    generar_clave: z.boolean().optional() }).optional(),
  falta_clave: z.boolean().optional(),
  papeles: z.array(z.object({ id: z.string(), nombre: z.string(), descripcion: z.string(), acciones: z.array(z.string()) })).optional(),
  acciones: z.array(z.object({ id: z.string(), comando: z.string(), nunca_automatica: z.boolean(), lista: z.string().nullable().optional() })).optional(),
  zonas: z.array(z.string()).optional(), activos: z.array(z.string()).optional(), criticidades: z.array(z.string()).optional(),
  rotacion: RotacionSchema.nullable().optional(),
  cambios: z.array(z.object({
    operador: z.string().nullable().optional(), dimension: z.string(), clave: z.string(),
    antes: z.unknown().optional(), despues: z.unknown().optional(), timestamp: z.string(),
  })),
})
export type Conectividad = z.infer<typeof ConectividadSchema>
export type EquipoConectividad = Conectividad["equipos"][number]
export type PruebaConexion = z.infer<typeof PruebaSchema>
export const getConectividad = () => pedir("/api/conectividad", ConectividadSchema)

// POST de conectividad: devuelve el código y el cuerpo (409 lleva la prueba que impidió guardar).
async function postConectividad(ruta: string, cuerpo: object): Promise<{ status: number; datos: Record<string, unknown> }> {
  try {
    const operador = operadorActual()
    const r = await fetch(BASE + ruta, {
      method: "POST", headers: cabeceras({ "Content-Type": "application/json" }),
      body: JSON.stringify({ ...cuerpo, ...(operador ? { operador } : {}) }),
    })
    let datos: Record<string, unknown> = {}
    try { datos = await r.json() } catch { /* cuerpo vacío */ }
    return { status: r.status, datos }
  } catch {
    return { status: 0, datos: { error: "sin conexión con el daemon" } }
  }
}
export const probarConexion = (equipo: string, ajuste: { puerto?: number | null; usuario?: string | null } = {}) =>
  postConectividad("/api/conectividad/probar", { equipo, ...ajuste })
export const guardarConexion = (equipo: string, ajuste: { puerto?: number | null; usuario?: string | null }) =>
  postConectividad("/api/conectividad", { equipo, ...ajuste })
export const guardarUsuarioDefecto = (usuario_defecto: string | null) => postConectividad("/api/conectividad", { usuario_defecto })
export const leerClaveHost = (equipo: string) => postConectividad("/api/conectividad/leer-clave-host", { equipo })
export const aceptarClaveHost = (equipo: string, huella: string) => postConectividad("/api/conectividad/clave-host", { equipo, huella })
// Inventario operativo: alta de un equipo nuevo (queda pendiente) o papel y reglas de uno existente.
export type DatosInventario = {
  nombre: string; ip?: string; zona?: string; funcion?: string; criticidad?: string; depende_de?: string[]; interfaz?: string | null
  papel: string; acciones: string[]; servicios: string[]; cuentas: string[]; cuentas_cualquiera?: boolean
}
// Genera el par de claves del conector cuando aún no hay ninguno (despliegue nuevo, sin el script).
export const generarClaveConector = (tipo: "ed25519" | "rsa") => postConectividad("/api/conectividad/clave-conector", { tipo })
// Probar con los ajustes guardados del equipo (sin proponer otros): «Probar todos».
export const probarEquipo = (equipo: string) => postConectividad("/api/conectividad/probar", { equipo })
export const guardarInventario = (datos: DatosInventario) => postConectividad("/api/conectividad/inventario", datos)
export const quitarInventario = (nombre: string) => postConectividad("/api/conectividad/inventario/quitar", { nombre })
export const darDeAlta = (equipo: string, huella: string) => postConectividad("/api/conectividad/alta", { equipo, huella })
export const rotarClave = (accion: "iniciar" | "preparar" | "retirar" | "finalizar" | "cancelar") =>
  postConectividad("/api/conectividad/rotacion", { accion })
export type FormatoPaquete = "script" | "ansible" | "sudoers"
export const getPaquete = (equipo: string, formato: FormatoPaquete) =>
  pedir(`/api/conectividad/paquete?equipo=${encodeURIComponent(equipo)}&formato=${formato}`,
    z.object({ nombre: z.string(), contenido: z.string(), formato: z.string() }))

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

export async function revertirUna(indice: number): Promise<{ revertida: boolean } | null> {
  try {
    const operador = operadorActual()
    const r = await fetch(BASE + "/api/revertir", {
      method: "POST", headers: cabeceras({ "Content-Type": "application/json" }),
      // confirmar: mismo gesto explícito que el des-bloqueo en masa (el diálogo de la fila es el gesto).
      body: JSON.stringify({ indice, confirmar: true, ...(operador ? { operador } : {}) }),
    })
    if (!r.ok) return null
    return await r.json()
  } catch { return null }
}

export const WatchEntradaSchema = z.object({
  indicador: z.string(), nota: z.string().nullable().optional(),
  operador: z.string().nullable().optional(), agregado_en: z.string().nullable().optional(),
})
export type WatchEntrada = z.infer<typeof WatchEntradaSchema>
export const getWatchlist = () => pedir("/api/watchlist", z.array(WatchEntradaSchema))

async function _postWatchlist(cuerpo: Record<string, unknown>): Promise<WatchEntrada[] | null> {
  try {
    const operador = operadorActual()
    const r = await fetch(BASE + "/api/watchlist", {
      method: "POST", headers: cabeceras({ "Content-Type": "application/json" }),
      body: JSON.stringify({ ...cuerpo, ...(operador ? { operador } : {}) }),
    })
    if (!r.ok) return null
    return await r.json()
  } catch { return null }
}
export const watchlistAgregar = (indicador: string, nota = "") => _postWatchlist({ indicador, nota })
export const watchlistQuitar = (indicador: string) => _postWatchlist({ quitar: indicador })

// rDNS (DNS inverso) de una IP pública. Opt-in en el backend (TRIAJE_RDNS): apagado por defecto
// devuelve null sin tocar la red (RNF-01). Bajo demanda desde el perfil del atacante, nunca en el sondeo.
export const RdnsSchema = z.object({ ip: z.string(), rdns: z.string().nullable().optional() })
export const getRdns = (ip: string) => pedir(`/api/rdns?ip=${encodeURIComponent(ip)}`, RdnsSchema)

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
