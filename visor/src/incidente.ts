import type { Decision, Detalle, Red } from "@/api"

// Estados de nodo para UN incidente, superpuestos sobre la topología (los pinta MapaRed vía
// `nodo.actividad.estado`). El feed (Decision) trae activo/origen/cascada; el detalle (Detalle,
// opcional mientras carga) añade dónde contuvo la escalada y si se verificó en el activo.
//
// Precedencia (gana el último que aplica): sin_actividad < en_cascada < origen < (activo) < contenido.
export function estadosDelIncidente(d: Decision, det: Detalle | null, red: Red): Red {
  const activo = d.activo
  const contenidoEn = det?.escalada?.dispositivo_ejecutor ?? null       // escaló: contuvo en otro dispositivo
  const contenidoEnActivo = !det?.escalada && !!det?.ejecucion?.exito   // contuvo en el propio activo
  const pendiente = !!d.requiere_humano && !d.veredicto_humano
  const cascada = new Set<string>([
    ...(d.cascada ?? []),
    ...(det?.impacto_determinado?.activos_afectados_en_cascada ?? []),
  ])
  const nodos = red.nodos.map((n) => {
    let estado = "sin_actividad"
    if (cascada.has(n.nombre)) estado = "en_cascada"
    if (d.origen_ip && n.ip === d.origen_ip) estado = "origen"
    if (activo && n.nombre === activo)
      estado = pendiente ? "pendiente" : contenidoEnActivo ? "contenido" : "atacado"
    if (contenidoEn && n.nombre === contenidoEn) estado = "contenido"
    return { ...n, actividad: { ...n.actividad, estado } }
  })
  return { ...red, nodos }
}
