import type { Decision, Detalle } from "@/api"

// Filtro de la lista de decisiones/trazas: texto libre (activo, IP, id, clase, acción) + clase exacta.
export type Filtro = { texto: string; clase: string; equipo?: string | null }

export function filtrarDecisiones(ds: Decision[], f: Filtro): Decision[] {
  const t = f.texto.trim().toLowerCase()
  return ds.filter((d) => {
    if (f.clase && d.clase !== f.clase) return false
    if (f.equipo && !d.relaciones?.[f.equipo]) return false
    if (!t) return true
    return [d.activo, d.origen_ip, d.id_decision, d.clase, d.accion_final]
      .some((v) => (v ?? "").toLowerCase().includes(t))
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
const NO_DECISIONES = new Set(["actividad_suprimida", "actividad_propia", "reversion", "error"])
export function esDecision(d: Decision): boolean {
  return !NO_DECISIONES.has(d.tipo ?? "")
}
