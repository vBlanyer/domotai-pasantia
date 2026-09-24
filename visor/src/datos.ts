import type { Decision } from "@/api"

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
