import type { KeyboardEvent } from "react"
import type { Red } from "@/api"
import { disposicion, DIM } from "@/red"

// Estado del nodo -> texto (se anuncia y se lee), icono y color. Nunca solo el color.
export const ESTADO_VISUAL: Record<string, { texto: string; icono: string; relleno: string; borde: string }> = {
  atacado:       { texto: "atacado", icono: "⚠", relleno: "fill-rose-500/25", borde: "stroke-rose-500" },
  pendiente:     { texto: "espera tu decisión", icono: "⏸", relleno: "fill-amber-400/25", borde: "stroke-amber-500" },
  contenido:     { texto: "contenido", icono: "✓", relleno: "fill-emerald-500/20", borde: "stroke-emerald-500" },
  origen:        { texto: "origen de ataques", icono: "↗", relleno: "fill-sky-500/20", borde: "stroke-sky-500" },
  caido:         { texto: "caído", icono: "✕", relleno: "fill-slate-500/30", borde: "stroke-slate-400" },
  sin_actividad: { texto: "sin actividad", icono: "", relleno: "fill-card", borde: "stroke-border" },
}

export function MapaRed({ red, seleccionado, onSeleccionar, dependencias }: {
  red: Red; seleccionado: string | null; onSeleccionar: (n: string) => void; dependencias: boolean
}) {
  const d = disposicion(red)
  const zonaDe = new Map(red.zonas.flatMap((z) => z.nodos.map((n) => [n, z.nombre] as const)))
  const cajaZona = new Map(d.zonas.map((z) => [z.nombre, z]))
  // Si todos los nodos de una zona cuelgan del mismo equipo de fuera, una sola línea hasta la caja.
  const lineas: { x1: number; y1: number; x2: number; y2: number; clave: string }[] = []
  const zonasUnidas = new Set<string>()
  for (const z of red.zonas) {
    const padres = new Set(z.nodos.map((n) => red.enlaces.find(([h]) => h === n)?.[1]))
    const [p] = [...padres]
    if (padres.size === 1 && p && !z.nodos.includes(p) && d.nodos[p]) {
      const caja = cajaZona.get(z.nombre)!
      lineas.push({ x1: d.nodos[p].x, y1: d.nodos[p].y + DIM.nodoAlto / 2, x2: caja.x + caja.w / 2, y2: caja.y, clave: `z-${z.nombre}` })
      zonasUnidas.add(z.nombre)
    }
  }
  for (const [h, p] of red.enlaces) {
    if (!d.nodos[h] || !d.nodos[p] || zonasUnidas.has(zonaDe.get(h) ?? "")) continue
    lineas.push({ x1: d.nodos[p].x, y1: d.nodos[p].y + DIM.nodoAlto / 2, x2: d.nodos[h].x, y2: d.nodos[h].y - DIM.nodoAlto / 2, clave: `${h}-${p}` })
  }
  const teclado = (n: string) => (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSeleccionar(n) }
  }
  return (
    <svg viewBox={`0 0 ${d.ancho} ${d.alto}`} className="h-auto w-full" role="group" aria-label="Mapa de la red">
      {d.zonas.map((z) => (
        <g key={z.nombre}>
          <rect x={z.x} y={z.y} width={z.w} height={z.h} rx={8} className="fill-none stroke-border" strokeDasharray="4 3" />
          <text x={z.x + 8} y={z.y + 14} className="fill-muted-foreground text-[10px]">{z.nombre}</text>
        </g>
      ))}
      {lineas.map(({ clave, ...l }) => <line key={clave} {...l} className="stroke-muted-foreground/60" strokeWidth={1.2} />)}
      {dependencias && red.dependencias.map(([n, dep]) => d.nodos[n] && d.nodos[dep] && (
        <line key={`dep-${n}-${dep}`} data-dependencia x1={d.nodos[n].x + DIM.nodoAncho / 2} y1={d.nodos[n].y}
          x2={d.nodos[dep].x - DIM.nodoAncho / 2} y2={d.nodos[dep].y} className="stroke-violet-400" strokeDasharray="4 3" strokeWidth={1.2} />
      ))}
      {red.nodos.map((n) => {
        const p = d.nodos[n.nombre]
        if (!p) return null
        const v = ESTADO_VISUAL[n.actividad.estado] ?? ESTADO_VISUAL.sin_actividad
        const sel = seleccionado === n.nombre
        return (
          <g key={n.nombre} role="button" tabIndex={0} aria-pressed={sel} aria-label={`${n.nombre}, ${v.texto}`}
            onClick={() => onSeleccionar(n.nombre)} onKeyDown={teclado(n.nombre)} className="cursor-pointer outline-none focus-visible:[&>rect]:stroke-ring">
            <rect x={p.x - DIM.nodoAncho / 2} y={p.y - DIM.nodoAlto / 2} width={DIM.nodoAncho} height={DIM.nodoAlto}
              rx={n.tipo === "externo" ? DIM.nodoAlto / 2 : 5} className={`${v.relleno} ${v.borde}`} strokeWidth={sel ? 3 : 1.4} />
            <text x={p.x} y={p.y + 4} textAnchor="middle" className="fill-foreground text-[11px]">
              {v.icono ? `${v.icono} ` : ""}{n.nombre}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
