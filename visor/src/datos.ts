import type { Decision, Detalle } from "@/api"

// Filtro de la lista de decisiones/trazas: texto libre (activo, IP, id, clase, acción) + clase exacta.
export type Filtro = { texto: string; clase: string }

export function filtrarDecisiones(ds: Decision[], f: Filtro): Decision[] {
  const t = f.texto.trim().toLowerCase()
  return ds.filter((d) => {
    if (f.clase && d.clase !== f.clase) return false
    if (!t) return true
    return [d.activo, d.origen_ip, d.id_decision, d.clase, d.accion_final]
      .some((v) => (v ?? "").toLowerCase().includes(t))
  })
}

export function clasesDe(ds: Decision[]): string[] {
  return [...new Set(ds.map((d) => d.clase).filter((c): c is string => !!c))].sort()
}

// Desenlace de la contención de una decisión, a partir de su registro de traza.
export type EstadoContencion = "contenida" | "fallida" | "retenida" | "cancelada" | "degradada" | "sin_accion"
export type Contencion = {
  estado: EstadoContencion
  ejecutada?: boolean      // la orden se aplicó en el activo (código 0)
  verificada?: boolean     // la verificación posterior confirmó el bloqueo en el activo
  escalada: boolean        // hubo que subir a otro dispositivo (el activo no respondió)
  dispositivo?: string     // dónde quedó contenida
  desde?: string           // activo desde el que se escaló
  accion?: string
  comando?: string
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
  if (!orden) {
    const v = det.veredicto_humano
    return { estado: v === "rechazar" || v === "reclasificar" ? "retenida" : "sin_accion", escalada: false }
  }
  const base = { accion: orden.accion_id ?? undefined, comando: det.ejecucion?.comando_ejecutado ?? undefined,
    ejecutada: !!det.ejecucion?.exito, verificada: !!det.verificacion?.verificado }
  if (base.ejecutada && base.verificada)
    return { ...base, estado: "contenida", escalada: false, dispositivo: orden.nodo_objetivo ?? undefined }
  const esc = det.escalada                                 // el activo no respondió: ¿contuvo el perímetro?
  if (esc)
    return { ...base, estado: ESTADO_PLAN[esc.resultado ?? ""] ?? "fallida", escalada: !!esc.escalado,
      dispositivo: esc.dispositivo_ejecutor ?? undefined, desde: orden.nodo_objetivo ?? undefined }
  return { ...base, estado: "fallida", escalada: false }  // sin topología a la que escalar
}

// Cómo trató el filtro del perfil la acción propuesta (mismas frases que validacion.filtro_legible
// en la terminal del daemon). El «por qué» fino (veto de gestión, cascada…) está en el motivo del impacto.
export function filtroLegible(d: {
  resultado_filtro?: string | null; accion_final?: string | null; requiere_humano?: boolean | null
}): string | null {
  switch (d.resultado_filtro) {
    case "veta":
      return d.accion_final ? "retenida — espera tu aprobación" : "vetada — no se puede ejecutar"
    case "degrada":
      return `degradada — se sustituye por ${d.accion_final ?? "—"}` + (d.requiere_humano ? "; espera tu aprobación" : "")
    case "permite":
      return d.requiere_humano ? "permitida — espera tu aprobación" : "automática"
    case "sin_accion":
      return "sin acción"
    default:
      return d.resultado_filtro ?? null
  }
}
