import type { Decision, Detalle } from "@/api"

// Etiquetas legibles de las clases del motor — ÚNICA fuente (A1: vivían triplicadas en Dashboard,
// Métricas y Aprobaciones, y dos copias no conocían exfiltración/malware). El orden es canónico y
// fijo: también ancla el color de cada clase en las donas (colorClase).
export const ETIQUETA_CLASE: Record<string, string> = {
  vp_intento_acceso: "Intento de acceso",
  vp_reconocimiento: "Reconocimiento",
  vp_integridad: "Integridad de fichero",
  vp_denegacion_servicio: "Denegación de servicio",
  vp_abuso_cuenta: "Abuso de cuenta",
  vp_acceso_consumado: "Acceso consumado",
  vp_exfiltracion: "Exfiltración / C2",
  vp_malware: "Malware",
  fp_actividad_legitima: "Falso positivo (legítimo)",
  fp_exposicion_inexistente: "Falso positivo (exposición)",
  no_soportada: "No soportada",
  amenaza_enrutada: "Enrutada a un equipo",
  otra: "Otra",
}
const CLASES_CANONICAS = Object.keys(ETIQUETA_CLASE)

export function etiquetaClase(clase: string): string {
  return ETIQUETA_CLASE[clase] ?? clase
}

// Color por IDENTIDAD de la clase, no por posición (A10): una clase nueva en vivo no desplaza el
// color de las demás a mitad de sesión. Una clase fuera del canon recibe un color estable por hash.
export function colorClase(clase: string, paleta: string[]): string {
  const i = CLASES_CANONICAS.indexOf(clase)
  if (i >= 0) return paleta[i % paleta.length]
  let h = 0
  for (const ch of clase) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return paleta[h % paleta.length]
}

// Vista «Consola»: clasificación PURA de cada línea del feed del daemon, por los prefijos reales
// que emiten stream._resumen_incidente / _linea_* (los filtros de la vista agrupan por esto).
export type TipoLinea = "incidente" | "decision" | "supresion" | "error" | "propia" | "aviso" | "ejecucion" | "detalle" | "otro"
export type LineaConsola = { n: number; t: string; linea: string }

export function clasificarLinea(linea: string): TipoLinea {
  if (linea.startsWith("⚠")) return "incidente"
  if (linea.startsWith("  Clase:") || linea.startsWith("⏸")) return "decision"
  if (linea.startsWith("↩")) return "supresion"
  // ✗ es ambiguo: la verificación fallida es narración de la RESPUESTA; el resto, error de proceso
  if (/^✗ \S+ NO verificada/.test(linea)) return "ejecucion"
  if (linea.startsWith("✗")) return "error"
  if (linea.startsWith("↺")) return "propia"
  if (linea.startsWith("[aviso]") || linea.startsWith("[red]")) return "aviso"
  // narración de la caja negra: ▶ orden ejecutada, ✔/⇪ verificación/escalada, ↶ reversión, · detalle
  if (/^[▶✔⇪↶]/.test(linea)) return "ejecucion"
  // diario del operador: ✓/✋/↻ veredicto humano (↻ no es ↺, la actividad propia), ☰ ciclo de caso,
  // ⏻ kill switch y [inicio] el contexto del arranque
  if (/^[✓✋↻]/.test(linea)) return "decision"
  if (linea.startsWith("☰")) return "detalle"
  if (linea.startsWith("⏻") || linea.startsWith("[inicio]")) return "aviso"
  if (linea.startsWith("· ")) return "detalle"
  return "otro"
}

// Grupos de los chips de filtro -> tipos que incluyen. «todo» no filtra.
const GRUPOS_CONSOLA: Record<string, TipoLinea[]> = {
  decisiones: ["decision", "supresion", "detalle"],
  incidentes: ["incidente"],
  ejecucion: ["ejecucion"],
  avisos: ["aviso", "error"],
}

export function filtrarConsola(lineas: LineaConsola[], grupo: string, texto: string): LineaConsola[] {
  const tipos = GRUPOS_CONSOLA[grupo]
  const q = texto.trim().toLowerCase()
  return lineas.filter((l) =>
    (!tipos || tipos.includes(clasificarLinea(l.linea))) &&
    (!q || l.linea.toLowerCase().includes(q)))
}

// Filtro de la lista de decisiones/trazas: texto libre (activo, IP, id, clase, acción) + clase exacta.
export type Filtro = { texto: string; clase: string; equipo?: string | null }

export function filtrarDecisiones(ds: Decision[], f: Filtro): Decision[] {
  const t = f.texto.trim().toLowerCase()
  return ds.filter((d) => {
    if (f.clase && d.clase !== f.clase) return false
    if (f.equipo && !d.relaciones?.[f.equipo]) return false
    if (!t) return true
    return [d.activo, d.origen_ip, d.id_decision, d.clase, d.accion_final, d.enriquecimiento_origen?.geo?.pais]
      .some((v) => (v ?? "").toLowerCase().includes(t))   // incluye el país (para pivotar desde Ubicaciones)
  })
}

// Identidad estable de una fila: la posición del registro en la cadena. No el id_decision (se repite
// en los resúmenes de supresión y al relanzar el daemon) ni el índice en pantalla (cambia al filtrar o
// al deslizarse la ventana de las últimas N).
export function claveDe(d: Decision, i: number): string {
  return d.indice != null ? `#${d.indice}` : `${i}:${d.id_decision ?? ""}`
}

export function clasesDe(ds: Decision[]): string[] {
  return [...new Set(ds.map((d) => d.clase).filter((c): c is string => !!c))].sort()
}

// Desenlace de la contención de una decisión, a partir de su registro de traza.
export type EstadoContencion =
  "contenida" | "fallida" | "retenida" | "cancelada" | "degradada" | "enrutada" | "sin_accion"
export type Contencion = {
  estado: EstadoContencion
  ejecutada?: boolean      // la orden se aplicó en el activo (código 0)
  verificada?: boolean     // la verificación posterior confirmó el bloqueo en el activo
  escalada: boolean        // hubo que subir a otro dispositivo (el activo no respondió)
  dispositivo?: string     // dónde quedó contenida
  desde?: string           // activo desde el que se escaló
  accion?: string
  comando?: string
  destino?: string         // amenaza enrutada: a qué cola/equipo
  // tras escalar: el intento en el activo, que no respondió (la orden efectiva va arriba)
  intento?: { nodo?: string; ejecutada: boolean; verificada: boolean }
}

const ESTADO_PLAN: Record<string, EstadoContencion> = {
  mitigado: "contenida", fallido: "fallida", cancelado_por_humano: "cancelada", degradado: "degradada",
}

export function contencionDe(det: Detalle): Contencion {
  const agente = det.mitigacion_agente
  if (agente) {                                            // modo --agente: el plan del agente manda
    return { estado: ESTADO_PLAN[agente.resultado ?? ""] ?? "fallida", escalada: !!agente.escalado,
      dispositivo: agente.dispositivo_ejecutor ?? undefined }
  }
  const orden = det.orden
  if (!orden && det.ruta)                                  // triar y enrutar: no se contiene, se deriva
    return { estado: "enrutada", escalada: false, destino: det.ruta }
  if (!orden) {
    const v = det.veredicto_humano
    return { estado: v === "rechazar" || v === "reclasificar" ? "retenida" : "sin_accion", escalada: false }
  }
  const base = { accion: orden.accion_id ?? undefined, comando: det.ejecucion?.comando_ejecutado ?? undefined,
    ejecutada: !!det.ejecucion?.exito, verificada: !!det.verificacion?.verificado }
  if (base.ejecutada && base.verificada)
    return { ...base, estado: "contenida", escalada: false, dispositivo: orden.nodo_objetivo ?? undefined }
  const esc = det.escalada                                 // el activo no respondió: ¿contuvo el perímetro?
  if (esc) {
    const estado = ESTADO_PLAN[esc.resultado ?? ""] ?? "fallida"
    const efectiva = esc.orden_efectiva
    const intento = { nodo: orden.nodo_objetivo ?? undefined, ejecutada: base.ejecutada, verificada: base.verificada }
    // Contenida al escalar: arriba va la orden que contuvo; el intento fallido en el activo, aparte.
    const arriba = estado === "contenida" && efectiva
      ? { accion: efectiva.accion_id ?? undefined, comando: undefined, ejecutada: true, verificada: true }
      : base
    return { ...arriba, estado, escalada: !!esc.escalado, intento,
      dispositivo: esc.dispositivo_ejecutor ?? undefined, desde: orden.nodo_objetivo ?? undefined }
  }
  return { ...base, estado: "fallida", escalada: false }  // sin topología a la que escalar
}

// Cómo trató el filtro del perfil la acción propuesta. Mientras espera, con las frases de
// validacion.filtro_legible en la terminal del daemon (más «permitida — espera…» cuando otra regla pide
// humano, que la terminal no distingue); ya resuelta, en pasado y con lo que decidió el analista.
// El «por qué» fino (veto de gestión, cascada…) está en el motivo del impacto.
const DESENLACE_HUMANO: Record<string, string> = { aprobar: "aprobada", rechazar: "rechazada", reclasificar: "reclasificada" }

export function filtroLegible(d: {
  resultado_filtro?: string | null; accion_final?: string | null; requiere_humano?: boolean | null
  veredicto_humano?: string | null
}): string | null {
  const v = d.veredicto_humano
  const humano = v ? ` · requirió aprobación · ${DESENLACE_HUMANO[v] ?? v}` : "; espera tu aprobación"
  switch (d.resultado_filtro) {
    case "veta":
      if (!d.accion_final) return "vetada — no se puede ejecutar"
      return v ? `retenida — requirió aprobación · ${DESENLACE_HUMANO[v] ?? v}` : "retenida — espera tu aprobación"
    case "degrada":
      return v ? `degradada — se sustituyó por ${d.accion_final ?? "—"}` + humano
        : `degradada — se sustituye por ${d.accion_final ?? "—"}` + (d.requiere_humano ? humano : "")
    case "permite":
      if (!d.requiere_humano) return "automática"
      return v ? `permitida — requirió aprobación · ${DESENLACE_HUMANO[v] ?? v}` : "permitida — espera tu aprobación"
    case "sin_accion":
      return "sin acción"
    case "revisar":
      // no_soportada de severidad alta: sin acción automática, pero escalada para que un humano la mire.
      return v ? `revisar — alerta no soportada de severidad alta · ${DESENLACE_HUMANO[v] ?? v}`
        : "revisar — alerta no soportada de severidad alta, sin acción automática"
    default:
      return d.resultado_filtro ?? null
  }
}

// Gravedad de una decisión en la escala del motor (analisis._priorizar: 1..4). Rótulo con texto,
// nunca solo color. 0 es el valor por defecto de la cola cuando no hay prioridad: no se rotula.
const NIVELES = ["baja", "media", "alta", "crítica"]
export function nivelPrioridad(p?: number | null): { n: number; etiqueta: string } | null {
  if (!p || p < 1) return null
  const n = Math.min(4, Math.round(p))
  return { n, etiqueta: `P${n} · ${NIVELES[n - 1]}` }
}

// /api/trazas sirve la cola del fichero (los últimos N): si el primer registro no es el 0 de la
// cadena, lo que se ve es parcial. El total sale del último índice + 1, sin pedir nada más.
export function ventanaDe(regs: Decision[]): { mostrados: number; total: number; desde: number } | null {
  const desde = regs[0]?.indice
  const ultimo = regs[regs.length - 1]?.indice
  if (desde == null || ultimo == null || desde === 0) return null
  return { mostrados: regs.length, total: ultimo + 1, desde }
}

// Qué registros de la traza son decisiones: no los resúmenes de supresión («el ataque sigue, ya
// decidido»), el eco del login del propio MDR al contener («actividad propia»), la reversión de
// una contención ni el fallo al procesar un incidente.
const NO_DECISIONES = new Set(["actividad_suprimida", "actividad_propia", "reversion", "error", "actualizacion_caso"])
export function esDecision(d: Decision): boolean {
  return !NO_DECISIONES.has(d.tipo ?? "")
}

// Ciclo de vida del caso: pliega los registros `actualizacion_caso` de la traza en el estado actual
// por id_decision (espejo de prototipo/servicio/casos.estado_de_casos). Una decisión sin ninguna actualización
// no aparece aquí (su estado implícito es 'nuevo').
export type CasoNota = { texto: string; operador?: string | null; decidido_en?: string | null }
export type CasoEstado = { estado: string; asignado: string | null; notas: CasoNota[]; actualizado_en?: string | null }

export function estadoDeCasos(regs: Decision[]): Record<string, CasoEstado> {
  const casos: Record<string, CasoEstado> = {}
  for (const r of regs) {
    if (r.tipo !== "actualizacion_caso" || !r.id_decision) continue
    const c = casos[r.id_decision] ?? (casos[r.id_decision] = { estado: "nuevo", asignado: null, notas: [] })
    if (r.estado) c.estado = r.estado
    if (r.asignado) c.asignado = r.asignado
    if (r.nota) c.notas.push({ texto: r.nota, operador: r.operador, decidido_en: r.decidido_en })
    c.actualizado_en = r.decidido_en
  }
  return casos
}

// Paginación en cliente de las listas largas (Trazas, Decisiones). El feed ya llega acotado con
// `indice` global estable (claveDe), así que basta cortar en cliente; la página vive en el
// componente y sobrevive al sondeo. `tam` por defecto TAM_PAGINA.
export const TAMANOS = [10, 20, 50] as const        // tamaños de página ofrecidos en el selector
export const TAM_PAGINA = 20                         // por defecto (uno de TAMANOS)

export function paginar<T>(xs: T[], pagina: number, tam: number = TAM_PAGINA): {
  filas: T[]; pagina: number; paginas: number; total: number; desde: number
} {
  const total = xs.length
  const paginas = Math.max(1, Math.ceil(total / tam))
  const p = Math.min(Math.max(1, Math.floor(pagina) || 1), paginas)   // clampa a [1, paginas]
  const desde = (p - 1) * tam                        // desplazamiento absoluto (para claves estables)
  return { filas: xs.slice(desde, desde + tam), pagina: p, paginas, total, desde }
}

// Cuenta eventos por día (YYYY-MM-DD del timestamp ISO), para la gráfica de tendencia por equipo.
// Ignora los registros sin timestamp; ordena cronológicamente.
export function agruparPorDia(ds: Decision[]): { dia: string; n: number }[] {
  const cuenta = new Map<string, number>()
  for (const d of ds) {
    if (!d.timestamp) continue
    const dia = d.timestamp.slice(0, 10)               // día del ISO, determinista y sin depender de Date
    cuenta.set(dia, (cuenta.get(dia) ?? 0) + 1)
  }
  return [...cuenta.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([dia, n]) => ({ dia, n }))
}

// Cronología de un incidente/atacante (attack story): eventos ordenados por tiempo, mezclando la
// DETECCIÓN (decisiones) con la RESPUESTA (reversión de contención, hitos del ciclo de caso). Ignora
// el ruido (supresión, eco propio, error). Puro: ordena comparando el string ISO (como agruparPorDia),
// sin `Date`; los eventos sin hora van al final de forma estable.
export type EventoCronologia = {
  clave: string; ts: string | null; tipo: "decision" | "reversion" | "caso"
  clase?: string | null; prioridad?: number | null; origen_ip?: string | null; activo?: string | null
  accion?: string | null; veredicto_humano?: string | null; nota?: string | null; operador?: string | null
}

export function cronologiaDe(regs: Decision[]): EventoCronologia[] {
  const eventos: EventoCronologia[] = []
  regs.forEach((d, i) => {
    const clave = claveDe(d, i)
    const tipo = d.tipo ?? "decision"
    if (tipo === "reversion") {
      eventos.push({ clave, ts: d.decidido_en ?? d.timestamp ?? null, tipo: "reversion",
        activo: d.nodo, accion: d.accion_id, operador: d.operador })
    } else if (tipo === "actualizacion_caso") {
      eventos.push({ clave, ts: d.decidido_en ?? d.timestamp ?? null, tipo: "caso",
        activo: d.activo, nota: d.nota, operador: d.operador })
    } else if (esDecision(d)) {
      eventos.push({ clave, ts: d.timestamp ?? null, tipo: "decision",
        clase: d.clase, prioridad: d.prioridad, origen_ip: d.origen_ip, activo: d.activo,
        accion: d.accion_final ?? d.contencion, veredicto_humano: d.veredicto_humano })
    }
    // actividad_suprimida / actividad_propia / error -> ruido, se ignoran
  })
  const orden = (e: EventoCronologia) => e.ts ?? "￿"   // sin hora -> al final
  return eventos.sort((a, b) => (orden(a) < orden(b) ? -1 : orden(a) > orden(b) ? 1 : 0))
}

// Todos los eventos (detección + RESPUESTA) de una entidad definida por un predicado sobre sus
// decisiones: sus decisiones + las reversiones/hitos de caso que las referencian (por `id_decision`).
// Necesario porque reversión/caso no llevan `origen_ip`: sin correlacionar, la línea de tiempo del
// atacante/incidente solo mostraría detecciones. Reutilizable por el perfil de atacante y el detalle
// de incidente para alimentar `cronologiaDe`/`LineaTiempo`.
export function eventosDeEntidad(todos: Decision[], pertenece: (d: Decision) => boolean): Decision[] {
  const decisiones = todos.filter((d) => esDecision(d) && pertenece(d))
  const ids = new Set(decisiones.map((d) => d.id_decision).filter(Boolean))
  const respuestas = todos.filter((d) =>
    (d.tipo === "reversion" && ids.has(d.id_decision_revertida ?? "")) ||
    (d.tipo === "actualizacion_caso" && ids.has(d.id_decision ?? "")))
  return [...decisiones, ...respuestas]
}

// Correlación de atacantes por dispositivo: los orígenes que ATACARON `equipo` (relación objetivo),
// con cuántas veces, su alcance (del enriquecimiento) y en qué OTROS equipos pegó la misma IP
// (correlación entre dispositivos, al estilo de los MDR comerciales). `todos` = el feed completo.
export function atacantesDe(eventos: Decision[], equipo: string, todos: Decision[] = []):
  { ip: string; n: number; prioridad: number; ultima: string | null; alcance?: string; otrosEquipos: string[] }[] {
  const spread = new Map<string, Set<string>>()          // ip -> equipos que atacó (objetivo)
  for (const d of todos) {
    if (!d.origen_ip) continue
    for (const [eq, etqs] of Object.entries(d.relaciones ?? {})) {
      if ((etqs ?? []).includes("objetivo")) (spread.get(d.origen_ip) ?? spread.set(d.origen_ip, new Set()).get(d.origen_ip)!).add(eq)
    }
  }
  const acc = new Map<string, { ip: string; n: number; prioridad: number; ultima: string | null; alcance?: string }>()
  for (const d of eventos) {
    if (!d.origen_ip || !(d.relaciones?.[equipo] ?? []).includes("objetivo")) continue   // solo ataques RECIBIDOS
    const a = acc.get(d.origen_ip) ?? { ip: d.origen_ip, n: 0, prioridad: 0, ultima: null, alcance: d.enriquecimiento_origen?.alcance ?? undefined }
    a.n += 1
    a.prioridad = Math.max(a.prioridad, d.prioridad ?? 0)   // la gravedad del peor de sus ataques
    if (d.timestamp && (!a.ultima || d.timestamp > a.ultima)) a.ultima = d.timestamp
    if (!a.alcance && d.enriquecimiento_origen?.alcance) a.alcance = d.enriquecimiento_origen.alcance
    acc.set(d.origen_ip, a)
  }
  return [...acc.values()]
    .map((a) => ({ ...a, otrosEquipos: [...(spread.get(a.ip) ?? new Set<string>())].filter((e) => e !== equipo).sort() }))
    // rankea por GRAVEDAD (el peor primero), luego por nº de ataques, luego IP para estabilidad
    .sort((x, y) => y.prioridad - x.prioridad || y.n - x.n || (x.ip < y.ip ? -1 : 1))
}

// Agrupa los atacantes (salida de atacantesDe) por subred /24 (bloque de origen): una campaña que
// rota IPs del mismo bloque se colapsa en UNA fila, que es la correlación útil cuando hay muchos
// orígenes singleton. Las IPs que no son IPv4 quedan como su propia clave.
export function agruparPorSubred(
  atacantes: { ip: string; n: number; prioridad: number; ultima: string | null; alcance?: string; otrosEquipos: string[] }[],
): { cidr: string; prefijo: string; ips: number; n: number; prioridad: number; ultima: string | null; alcance?: string; otrosEquipos: string[] }[] {
  const acc = new Map<string, { cidr: string; prefijo: string; ips: number; n: number; prioridad: number; ultima: string | null; alcance?: string; otros: Set<string> }>()
  for (const at of atacantes) {
    const m = /^(\d+)\.(\d+)\.(\d+)\.\d+$/.exec(at.ip)
    const cidr = m ? `${m[1]}.${m[2]}.${m[3]}.0/24` : at.ip
    const prefijo = m ? `${m[1]}.${m[2]}.${m[3]}.` : at.ip
    const g = acc.get(cidr) ?? { cidr, prefijo, ips: 0, n: 0, prioridad: 0, ultima: null, alcance: at.alcance, otros: new Set<string>() }
    g.ips += 1
    g.n += at.n
    g.prioridad = Math.max(g.prioridad, at.prioridad)
    if (at.ultima && (!g.ultima || at.ultima > g.ultima)) g.ultima = at.ultima
    if (!g.alcance && at.alcance) g.alcance = at.alcance
    for (const e of at.otrosEquipos) g.otros.add(e)
    acc.set(cidr, g)
  }
  return [...acc.values()]
    .map((g) => ({ cidr: g.cidr, prefijo: g.prefijo, ips: g.ips, n: g.n, prioridad: g.prioridad, ultima: g.ultima, alcance: g.alcance, otrosEquipos: [...g.otros].sort() }))
    .sort((x, y) => y.prioridad - x.prioridad || y.n - x.n || (x.cidr < y.cidr ? -1 : 1))
}

// Campañas (attack story): agrupa TODOS los ataques recibidos (relación objetivo) por bloque de
// origen /24, a través de todos los equipos. Una campaña que rota IPs contra varios activos se ve
// como una sola fila: nº de IPs, ataques, a qué equipos pegó (con cuántas veces), gravedad y ventana.
export function campanasDe(todos: Decision[]): {
  cidr: string; prefijo: string; ips: number; n: number; prioridad: number
  primera: string | null; ultima: string | null; alcance?: string; objetivos: { equipo: string; n: number }[]
}[] {
  const acc = new Map<string, { cidr: string; prefijo: string; ips: Set<string>; n: number; prioridad: number; primera: string | null; ultima: string | null; alcance?: string; objetivos: Map<string, number> }>()
  for (const d of todos) {
    if (!d.origen_ip) continue
    const objetivos = Object.entries(d.relaciones ?? {}).filter(([, e]) => (e ?? []).includes("objetivo")).map(([eq]) => eq)
    if (!objetivos.length) continue
    const m = /^(\d+)\.(\d+)\.(\d+)\.\d+$/.exec(d.origen_ip)
    const cidr = m ? `${m[1]}.${m[2]}.${m[3]}.0/24` : d.origen_ip
    const prefijo = m ? `${m[1]}.${m[2]}.${m[3]}.` : d.origen_ip
    const g = acc.get(cidr) ?? { cidr, prefijo, ips: new Set<string>(), n: 0, prioridad: 0, primera: null, ultima: null, alcance: d.enriquecimiento_origen?.alcance, objetivos: new Map<string, number>() }
    g.ips.add(d.origen_ip)
    g.n += 1
    g.prioridad = Math.max(g.prioridad, d.prioridad ?? 0)
    if (d.timestamp) {
      if (!g.primera || d.timestamp < g.primera) g.primera = d.timestamp
      if (!g.ultima || d.timestamp > g.ultima) g.ultima = d.timestamp
    }
    if (!g.alcance && d.enriquecimiento_origen?.alcance) g.alcance = d.enriquecimiento_origen.alcance
    for (const t of objetivos) g.objetivos.set(t, (g.objetivos.get(t) ?? 0) + 1)
    acc.set(cidr, g)
  }
  return [...acc.values()]
    .map((g) => ({ cidr: g.cidr, prefijo: g.prefijo, ips: g.ips.size, n: g.n, prioridad: g.prioridad, primera: g.primera, ultima: g.ultima, alcance: g.alcance, objetivos: [...g.objetivos.entries()].map(([equipo, n]) => ({ equipo, n })).sort((a, b) => b.n - a.n) }))
    .sort((x, y) => y.prioridad - x.prioridad || y.n - x.n || (x.cidr < y.cidr ? -1 : 1))
}

// Perfil de atacante (página de entidad): resume una IP de origen — nº de ataques, a qué equipos
// pegó (con cuántas veces y la última), gravedad máxima, ventana temporal, el enriquecimiento (de
// cualquiera de sus decisiones) y su actividad por día. Todo de los ataques RECIBIDOS (objetivo).
export function perfilAtacante(todos: Decision[], ip: string): {
  ip: string; n: number; prioridad: number; primera: string | null; ultima: string | null
  enriquecimiento?: Decision["enriquecimiento_origen"]; equipos: { equipo: string; n: number; ultima: string | null }[]
  porDia: { dia: string; n: number }[]
} {
  const suyas = todos.filter((d) => d.origen_ip === ip &&
    Object.values(d.relaciones ?? {}).some((e) => (e ?? []).includes("objetivo")))
  const eq = new Map<string, { n: number; ultima: string | null }>()
  let n = 0, prioridad = 0, primera: string | null = null, ultima: string | null = null
  let enr: Decision["enriquecimiento_origen"] | undefined
  for (const d of suyas) {
    n += 1
    prioridad = Math.max(prioridad, d.prioridad ?? 0)
    if (d.timestamp) {
      if (!primera || d.timestamp < primera) primera = d.timestamp
      if (!ultima || d.timestamp > ultima) ultima = d.timestamp
    }
    if (!enr && d.enriquecimiento_origen) enr = d.enriquecimiento_origen
    for (const [e, etqs] of Object.entries(d.relaciones ?? {})) {
      if (!(etqs ?? []).includes("objetivo")) continue
      const g = eq.get(e) ?? { n: 0, ultima: null }
      g.n += 1
      if (d.timestamp && (!g.ultima || d.timestamp > g.ultima)) g.ultima = d.timestamp
      eq.set(e, g)
    }
  }
  const equipos = [...eq.entries()].map(([equipo, g]) => ({ equipo, n: g.n, ultima: g.ultima })).sort((a, b) => b.n - a.n)
  return { ip, n, prioridad, primera, ultima, enriquecimiento: enr, equipos, porDia: agruparPorDia(suyas) }
}

// Runbook por familia: los pasos de respuesta recomendados para el analista, aflorados en la tarjeta
// de decisión (complementa la `recomendacion` del motor). Clave = clase del motor; FP/desconocida → [].
const RUNBOOK: Record<string, string[]> = {
  vp_intento_acceso: [
    "Confirma el bloqueo del origen en el borde (contención aplicada y verificada).",
    "Revisa si tras la fuerza bruta hubo un login exitoso: sería acceso consumado (corta la sesión).",
    "Si el origen es legítimo (mantenimiento, escáner autorizado), reclasifica y decláralo de confianza.",
  ],
  vp_reconocimiento: [
    "Verifica el bloqueo del escáner en el borde.",
    "Comprueba si el reconocimiento precede a un intento de acceso contra el mismo activo.",
    "Si es un escáner autorizado, reclasifica.",
  ],
  vp_abuso_cuenta: [
    "Bloquea/deshabilita la cuenta implicada (acción humana incondicional).",
    "Fuerza el cambio de credenciales y revisa los accesos recientes de esa cuenta.",
    "Comprueba si la cuenta se creó sin autorización (backdoor).",
  ],
  vp_integridad: [
    "Aísla el host en cuarentena en el borde (contención aprobada).",
    "Identifica qué fichero crítico cambió y compáralo con el respaldo.",
    "Planifica la restauración y la causa raíz antes de reconectar.",
  ],
  vp_denegacion_servicio: [
    "Acota la banda del enlace de la víctima (contención gradual).",
    "Si el flujo es entrante, la contención en la víctima es parcial: escala al borde si hace falta.",
    "Vigila la salud del servicio durante la mitigación.",
  ],
  vp_acceso_consumado: [
    "Corta la sesión viva del atacante en el activo (MATAR_CONEXION).",
    "Revisa qué hizo durante la sesión (persistencia, movimiento lateral).",
    "Rota credenciales y revisa cuentas y servicios tocados.",
  ],
  vp_exfiltracion: [
    "Bloquea el destino malicioso en el cortafuegos de borde (egreso).",
    "Identifica qué datos salieron y por qué canal.",
    "Busca el implante/C2 en el host de origen.",
  ],
  vp_malware: [
    "Aísla el host en cuarentena en el borde.",
    "Recoge la muestra y su veredicto; busca otros hosts con el mismo indicador.",
    "Limpia o reimagina el host antes de reconectarlo.",
  ],
  amenaza_enrutada: [
    "No hay contención automática: se enruta a la cola especializada (p. ej. AppSec).",
    "Traslada el caso al equipo destinatario con el contexto del incidente.",
  ],
  no_soportada: [
    "Frontera honesta del alcance: revisa la alerta manualmente.",
    "Si es un patrón recurrente, valora ampliar el catálogo de familias.",
  ],
}

export function pasosRunbook(clase?: string | null): string[] {
  return (clase && RUNBOOK[clase]) || []
}

// Riesgo por entidad (ASESOR y EXPLICABLE, no un número mágico): un nivel bajo/medio/alto/crítico
// con los factores que lo elevaron. Fórmula transparente sobre señales objetivas (gravedad del peor
// ataque, volumen, decisiones pendientes, contención sin confirmar, criticidad del activo).
export type Riesgo = { nivel: "bajo" | "medio" | "alto" | "critico"; etiqueta: string; puntuacion: number; factores: string[] }

function nivelDeRiesgo(p: number, factores: string[]): Riesgo {
  const n = p >= 90 ? "critico" : p >= 60 ? "alto" : p >= 30 ? "medio" : "bajo"
  return { nivel: n, etiqueta: n === "critico" ? "crítico" : n, puntuacion: p, factores }
}

export function riesgoEquipo(
  nodo: { nombre: string; criticidad?: string | null; actividad?: { pendientes?: number } },
  eventos: Decision[],
): Riesgo {
  const recibidos = eventos.filter((d) => (d.relaciones?.[nodo.nombre] ?? []).includes("objetivo"))
  if (recibidos.length === 0) return nivelDeRiesgo(0, ["sin ataques recibidos"])
  const f: string[] = []
  let p = 0
  const maxPrio = Math.max(0, ...recibidos.map((d) => d.prioridad ?? 0))
  p += maxPrio * 20
  if (maxPrio) f.push(`ataque de prioridad ${maxPrio}`)
  if (recibidos.length >= 10) { p += 15; f.push(`${recibidos.length} ataques recibidos`) }
  else if (recibidos.length >= 3) { p += 8; f.push(`${recibidos.length} ataques recibidos`) }
  const pend = nodo.actividad?.pendientes ?? 0
  if (pend > 0) { p += 15; f.push(`${pend} decisión(es) pendiente(s)`) }
  const expuestos = recibidos.filter((d) => d.contencion === "fallida").length
  if (expuestos) { p += 15; f.push(`${expuestos} contención(es) sin confirmar`) }
  const crit = (nodo.criticidad ?? "").toLowerCase()
  if (crit === "alta" || crit === "critica" || crit === "crítica") { p += 10; f.push(`activo ${nodo.criticidad}`) }
  return nivelDeRiesgo(Math.min(100, p), f)
}

export function riesgoAtacante(perfil: { n: number; prioridad: number; equipos: { equipo: string }[] }): Riesgo {
  const f: string[] = []
  let p = (perfil.prioridad ?? 0) * 20
  if (perfil.prioridad) f.push(`ataque de prioridad ${perfil.prioridad}`)
  if (perfil.n >= 10) { p += 15; f.push(`${perfil.n} ataques`) }
  else if (perfil.n >= 3) { p += 8; f.push(`${perfil.n} ataques`) }
  const eq = perfil.equipos.length
  if (eq >= 3) { p += 20; f.push(`${eq} equipos atacados`) }
  else if (eq >= 2) { p += 10; f.push(`${eq} equipos atacados`) }
  if (!f.length) f.push("actividad baja")
  return nivelDeRiesgo(Math.min(100, p), f)
}

// ¿Está `ip` en la watchlist? Coincidencia por IP exacta o por /24 (soporte simple, sin lib CIDR).
export function enWatchlist(
  ip: string | null | undefined,
  lista: { indicador: string; nota?: string | null }[],
): { indicador: string; nota?: string | null } | null {
  if (!ip) return null
  for (const e of lista) {
    if (e.indicador === ip) return e
    const m = /^(\d+\.\d+\.\d+)\.0\/24$/.exec(e.indicador)
    if (m && ip.startsWith(m[1] + ".")) return e
  }
  return null
}

// Ubicación de origen de cada ataque recibido, para la vista «Ubicaciones»: país real (si la IP
// pública geolocaliza), o un cubo honesto —red interna, laboratorio/documentación, pública sin geo—.
type ConOrigen = { enriquecimiento_origen?: Decision["enriquecimiento_origen"] }

// La etiqueta de ubicación de un registro (decisión o pendiente): país real o el cubo (red interna /
// laboratorio / loopback / pública sin geo / desconocida). Compartida por el mapa y el filtro de Aprobaciones.
export function ubicacionLabelDe(d: ConOrigen): string {
  return ubicacionDe(d).nombre
}

function ubicacionDe(d: ConOrigen): { clave: string; nombre: string; lat?: number | null; lon?: number | null; codigo?: string | null } {
  const e = d.enriquecimiento_origen
  if (e?.geo?.pais) return { clave: e.geo.codigo ?? e.geo.pais, nombre: e.geo.pais, lat: (e.geo as { lat?: number }).lat, lon: (e.geo as { lon?: number }).lon, codigo: e.geo.codigo }
  switch (e?.clasificacion_ip) {
    case "privada": return { clave: "interna", nombre: "Red interna" }
    case "documentacion": return { clave: "lab", nombre: "Laboratorio / documentación" }
    case "loopback": return { clave: "loopback", nombre: "Loopback" }
    case "publica": return { clave: "sin-geo", nombre: "Pública (sin geolocalizar)" }
    default: return { clave: "desconocida", nombre: "Desconocida" }
  }
}

// Las tres métricas por ubicación: total (recibidos), mitigados (contención «contenida») y en curso
// (recibidos aún NO contenidos = total − mitigados; partición limpia: total = mitigados + enCurso).
export type MetricaUbicacion = "enCurso" | "n" | "mitigados"

export function ubicacionesDe(todos: Decision[]): {
  clave: string; nombre: string; lat?: number | null; lon?: number | null; codigo?: string | null
  n: number; mitigados: number; enCurso: number; ips: number; prioridad: number
}[] {
  const acc = new Map<string, { clave: string; nombre: string; lat?: number | null; lon?: number | null; codigo?: string | null; n: number; mitigados: number; ips: Set<string>; prioridad: number }>()
  for (const d of todos) {
    if (!d.origen_ip || !Object.values(d.relaciones ?? {}).some((e) => (e ?? []).includes("objetivo"))) continue
    const u = ubicacionDe(d)
    const g = acc.get(u.clave) ?? { ...u, n: 0, mitigados: 0, ips: new Set<string>(), prioridad: 0 }
    g.n += 1
    if (d.contencion === "contenida") g.mitigados += 1   // mitigado = contención efectiva y verificada
    g.ips.add(d.origen_ip)
    g.prioridad = Math.max(g.prioridad, d.prioridad ?? 0)
    acc.set(u.clave, g)
  }
  return [...acc.values()].map((g) => ({ clave: g.clave, nombre: g.nombre, lat: g.lat, lon: g.lon, codigo: g.codigo,
    n: g.n, mitigados: g.mitigados, enCurso: g.n - g.mitigados, ips: g.ips.size, prioridad: g.prioridad }))
    .sort((a, b) => b.n - a.n || (a.nombre < b.nombre ? -1 : 1))
}
