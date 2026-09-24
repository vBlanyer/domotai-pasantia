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

// CSV de las decisiones (para exportar lo que se ve). Comillas escapadas (RFC 4180).
export function aCSV(ds: Decision[]): string {
  const cols = ["id_decision", "timestamp", "activo", "origen_ip", "clase",
    "confianza", "accion_final", "requiere_humano", "cascada"]
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`
  const filas = ds.map((d) => cols.map((c) => esc((d as Record<string, unknown>)[c])).join(","))
  return [cols.join(","), ...filas].join("\n")
}

// Descarga un contenido como fichero (sin dependencias): Blob + <a download>.
export function descargar(nombre: string, contenido: string, tipo = "text/csv;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }))
  const a = document.createElement("a")
  a.href = url
  a.download = nombre
  a.click()
  URL.revokeObjectURL(url)
}
