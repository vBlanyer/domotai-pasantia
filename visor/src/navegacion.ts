// La vista activa de la consola vive en la URL (`#/politicas`): sobrevive a recargar la página y los
// botones atrás/adelante del navegador recorren las vistas. Solo el nombre de la vista: el contexto de
// una vista de detalle (qué atacante, qué incidente) no viaja en la URL.
export const VISTAS = ["panel", "metricas", "salud", "red", "ubicaciones", "incidentes", "decisiones", "aprobaciones",
  "consola", "trazas", "contenciones", "watchlist", "politicas", "asistente", "conectividad", "incidente", "atacante"] as const
export type Vista = (typeof VISTAS)[number]

const PREFIJO = "#/"

export function vistaDeHash(hash: string): Vista {
  const v = hash.startsWith(PREFIJO) ? hash.slice(PREFIJO.length) : ""
  return (VISTAS as readonly string[]).includes(v) ? (v as Vista) : "panel"
}

export function hashDeVista(v: Vista): string {
  return PREFIJO + v
}

// Una vista de detalle necesita sus datos en memoria; tras recargar no los tiene y se muestra la vista
// de la que se sale (el perfil del atacante sale de Red; el grafo del incidente, de Decisiones).
export function vistaVisible(v: Vista, hay: { atacante: boolean; incidente: boolean }): Vista {
  if (v === "atacante" && !hay.atacante) return "red"
  if (v === "incidente" && !hay.incidente) return "decisiones"
  return v
}
