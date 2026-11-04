import type { KeyboardEvent } from "react"
import type { Red } from "@/api"
import { disposicion, cascadaDe, resumenRama, DIM, type Origen } from "@/red"
import { cn } from "@/lib/utils"

// Estado del nodo -> texto (se anuncia y se lee), icono y color. Nunca solo el color.
export const ESTADO_VISUAL: Record<string, { texto: string; icono: string; relleno: string; borde: string }> = {
  atacado:       { texto: "atacado", icono: "⚠", relleno: "fill-critico/25", borde: "stroke-critico" },
  pendiente:     { texto: "espera tu decisión", icono: "⏸", relleno: "fill-aviso/25", borde: "stroke-aviso" },
  contenido:     { texto: "contenido", icono: "✓", relleno: "fill-ok/20", borde: "stroke-ok" },
  en_cascada:    { texto: "caería en cascada", icono: "⚠", relleno: "fill-aviso/20", borde: "stroke-aviso" },
  origen:        { texto: "origen de ataques", icono: "↗", relleno: "fill-info/20", borde: "stroke-info" },
  caido:         { texto: "caído", icono: "✕", relleno: "fill-enrutado/30", borde: "stroke-enrutado" },
  sin_actividad: { texto: "sin actividad", icono: "", relleno: "fill-card", borde: "stroke-border" },
}

const grosor = (n: number) => (n >= 10 ? 3 : n >= 3 ? 2 : 1.2)
const PILDORA = { w: 150, h: 20, hueco: 10 }

// Mapa en árbol: carril de orígenes arriba, tronco (cortafuegos), bus, ramas (zonas) y hojas
// (equipos). Los nodos cuentan (ataques recibidos en rojo, pendientes en ámbar). Al seleccionar un
// equipo, lo que no le toca se atenúa. `incidente` superpone la HISTORIA de un incidente: la flecha
// del ataque (origen -> activo) y las aristas de cascada en ámbar.
export function MapaRed({ red, seleccionado, onSeleccionar, dependencias, ataques = true, cascada = true, origenes, plegadas, onPlegar, onVerOrigen, incidente }: {
  red: Red; seleccionado: string | null; onSeleccionar: (n: string) => void; dependencias: boolean
  ataques?: boolean; cascada?: boolean
  origenes?: { top: Origen[]; resto: number; total: number }
  plegadas?: Set<string>; onPlegar?: (zona: string) => void
  onVerOrigen?: (ip: string) => void
  incidente?: { origen?: string | null; activo?: string | null; cascada?: string[] }
}) {
  const d = disposicion(red, { plegadas, carril: !!origenes?.top.length })
  const porNombre = new Map(red.nodos.map((n) => [n.nombre, n]))
  const ramaDe = new Map(d.ramas.flatMap((r) => r.nodos.map((n) => [n, r] as const)))
  // Posición de un nodo; si su rama está plegada, la píldora de la rama.
  const pos = (n: string) => d.nodos[n] ?? (ramaDe.get(n)?.plegada ? { x: ramaDe.get(n)!.cx, y: ramaDe.get(n)!.y + DIM.ramaAlto / 2 } : undefined)
  const esHoja = (n: string) => ramaDe.has(n)
  const altoDe = (n: string) => (porNombre.get(n)?.tipo === "externo" ? DIM.nodoAlto : DIM.hojaAlto)
  const anchoDe = (n: string) => (porNombre.get(n)?.tipo === "externo" ? DIM.nodoAncho : DIM.hojaAncho)
  const haciaBorde = (desde: { x: number; y: number }, hasta: { x: number; y: number }, m: number) => {
    const dx = hasta.x - desde.x, dy = hasta.y - desde.y, len = Math.hypot(dx, dy) || 1
    return { x: hasta.x - (dx / len) * m, y: hasta.y - (dy / len) * m }
  }

  // carril: píldoras de los orígenes que más atacan, las que quepan; el resto se cuenta
  const externos = red.nodos.filter((n) => n.tipo === "externo" && d.nodos[n.nombre])
  const x0Pildoras = DIM.margen + 10 + externos.length * (DIM.nodoAncho + 10)
  const caben = Math.max(0, Math.floor((d.ancho - x0Pildoras - DIM.margen - 90) / (PILDORA.w + PILDORA.hueco)))
  const top = (origenes?.top ?? []).slice(0, caben)
  const resto = (origenes?.resto ?? 0) + Math.max(0, (origenes?.top.length ?? 0) - top.length)
  const pildora = (i: number) => ({ x: x0Pildoras + i * (PILDORA.w + PILDORA.hueco), y: (d.carril?.y ?? 0) + (DIM.carrilAlto - PILDORA.h) / 2 })

  // foco: con un equipo seleccionado, lo que no le toca se atenúa
  const foco = seleccionado != null
  const relacionados = new Set<string>(seleccionado ? [seleccionado] : [])
  if (seleccionado) {
    for (const [n, dep] of red.dependencias) { if (n === seleccionado) relacionados.add(dep); if (dep === seleccionado) relacionados.add(n) }
    for (const n of d.tronco) relacionados.add(n)
    for (const n of externos) relacionados.add(n.nombre)
  }
  const zonaSel = seleccionado ? ramaDe.get(seleccionado)?.nombre : undefined
  const dim = (relevante: boolean) => foco && !relevante && "opacity-30"

  const teclado = (f: () => void) => (e: KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); f() } }
  const cascadas = cascada ? cascadaDe(red) : []

  return (
    <svg viewBox={`0 0 ${d.ancho} ${d.alto}`} className="h-auto w-full" role="group" aria-label="Mapa de la red">
      <defs>
        <marker id="flecha-ataque" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L7,3 L0,6 Z" className="fill-critico" />
        </marker>
      </defs>

      {/* carril de orígenes */}
      {d.carril && (
        <g>
          <rect x={DIM.margen} y={d.carril.y} width={d.ancho - 2 * DIM.margen} height={d.carril.h} rx={8} className="fill-muted" />
          {origenes && origenes.total > 0 && (
            <text x={DIM.margen + 10} y={d.carril.y + 12} className="fill-muted-foreground text-[9px]">
              {origenes.total} {origenes.total === 1 ? "origen activo" : "orígenes activos"}{top.length < origenes.total ? ` · los ${top.length} que más atacan` : ""}
            </text>
          )}
          {top.map((o, i) => {
            const p = pildora(i)
            const relevante = !seleccionado || (o.objetivos[seleccionado] ?? 0) > 0
            return (
              <g key={o.ip} role={onVerOrigen ? "button" : undefined} tabIndex={onVerOrigen ? 0 : undefined}
                aria-label={`origen ${o.ip}, ${o.n} ${o.n === 1 ? "ataque" : "ataques"}${o.pais ? `, ${o.pais}` : ""}`}
                onClick={() => onVerOrigen?.(o.ip)} onKeyDown={teclado(() => onVerOrigen?.(o.ip))}
                className={cn("transition-opacity", onVerOrigen && "cursor-pointer outline-none focus-visible:[&>rect]:stroke-ring", dim(relevante))}>
                <rect x={p.x} y={p.y} width={PILDORA.w} height={PILDORA.h} rx={10} className="fill-info/15 stroke-info" strokeWidth={1.2} />
                <text x={p.x + 10} y={p.y + 14} className="fill-foreground font-mono text-[10px]">{o.ip}</text>
                <text x={p.x + PILDORA.w - 8} y={p.y + 14} textAnchor="end" className="fill-muted-foreground text-[9px]">{o.codigo ? `${o.codigo} · ` : ""}{o.n}</text>
              </g>
            )
          })}
          {resto > 0 && (() => {
            const p = pildora(top.length)
            return (
              <g className={cn("transition-opacity", dim(false))}>
                <rect x={p.x} y={p.y} width={80} height={PILDORA.h} rx={10} className="fill-card stroke-border" strokeDasharray="3 2" />
                <text x={p.x + 10} y={p.y + 14} className="fill-muted-foreground text-[9px]">+{resto} {resto === 1 ? "origen" : "orígenes"}</text>
              </g>
            )
          })()}
        </g>
      )}

      {/* tronco, bus y ramas: conectores en codo */}
      {d.tronco.map((n, i) => {
        const p = d.nodos[n]
        const anterior = i > 0 ? d.nodos[d.tronco[i - 1]] : null
        const y0 = anterior ? anterior.y + DIM.hojaAlto / 2 : d.carril ? d.carril.y + d.carril.h : null
        return y0 != null && <path key={`tr-${n}`} d={`M${anterior?.x ?? p.x},${y0} V${anterior ? (y0 + p.y - DIM.hojaAlto / 2) / 2 : p.y - DIM.hojaAlto / 2} H${p.x} V${p.y - DIM.hojaAlto / 2}`} className="fill-none stroke-border" strokeWidth={1.4} />
      })}
      {d.bus && (() => {
        const ultimo = d.nodos[d.tronco[d.tronco.length - 1]]
        return <path d={`M${ultimo.x},${ultimo.y + DIM.hojaAlto / 2} V${d.bus.y} M${d.bus.x1},${d.bus.y} H${d.bus.x2}`} className="fill-none stroke-border" strokeWidth={1.4} />
      })()}
      {d.ramas.map((r, i) => {
        const fila = Math.floor(i / DIM.porFila)
        const arriba = fila > 0 ? d.ramas[i - DIM.porFila] : null
        const yDesde = arriba ? arriba.y + arriba.h : d.bus ? d.bus.y : null
        const relevante = !zonaSel || zonaSel === r.nombre
        const res = resumenRama(r.nodos.map((n) => porNombre.get(n)!).filter(Boolean))
        return (
          <g key={`rama-${r.nombre}`} className={cn("transition-opacity", dim(relevante))}>
            {yDesde != null && <line x1={r.cx} y1={yDesde} x2={r.cx} y2={r.y} className="stroke-border" strokeWidth={1.4} />}
            {!r.plegada && r.hojas.length > 0 && (
              <path d={`M${r.espinaX},${r.y + DIM.ramaAlto} V${r.hojas[r.hojas.length - 1].y} ` + r.hojas.map((h) => `M${r.espinaX},${h.y} H${h.x - DIM.hojaAncho / 2}`).join(" ")}
                className="fill-none stroke-border" strokeWidth={1.4} />
            )}
            <g role="button" tabIndex={0} aria-expanded={!r.plegada} aria-label={`zona ${r.nombre}, ${res.texto}${r.plegada ? ", plegada" : ""}`}
              onClick={() => onPlegar?.(r.nombre)} onKeyDown={teclado(() => onPlegar?.(r.nombre))}
              className={cn(onPlegar && "cursor-pointer", "outline-none focus-visible:[&>rect]:stroke-ring")}>
              <rect x={r.cx - DIM.ramaAncho / 2} y={r.y} width={DIM.ramaAncho} height={DIM.ramaAlto} rx={13} className={cn("fill-muted", res.borde)} strokeWidth={1.2} />
              <text x={r.cx - DIM.ramaAncho / 2 + 10} y={r.y + 12} className="fill-foreground text-[10.5px] font-semibold">{r.nombre}</text>
              <text x={r.cx - DIM.ramaAncho / 2 + 10} y={r.y + 22} className="fill-muted-foreground text-[8.5px]">{res.texto}{r.plegada ? " · plegada" : ""}</text>
            </g>
          </g>
        )
      })}

      {/* capas: dependencias (violeta), cascada (ámbar) y ataques del carril (rojo, grosor = volumen) */}
      {dependencias && red.dependencias.map(([n, dep]) => {
        const a = pos(n), b = pos(dep)
        if (!a || !b) return null
        const relevante = n === seleccionado || dep === seleccionado
        const [ini, fin] = a.x <= b.x ? [{ x: a.x + anchoDe(n) / 2, y: a.y }, { x: b.x - anchoDe(dep) / 2, y: b.y }] : [{ x: a.x - anchoDe(n) / 2, y: a.y }, { x: b.x + anchoDe(dep) / 2, y: b.y }]
        const mx = (ini.x + fin.x) / 2
        return <path key={`dep-${n}-${dep}`} data-dependencia d={`M${ini.x},${ini.y} C${mx},${ini.y} ${mx},${fin.y} ${fin.x},${fin.y}`}
          className={cn("fill-none stroke-violeta transition-opacity", dim(relevante))} strokeDasharray="4 3" strokeWidth={1.2} />
      })}
      {cascadas.map(([c, n]) => {
        const a = pos(c), b = pos(n)
        if (!a || !b) return null
        const relevante = c === seleccionado || n === seleccionado
        const fin = haciaBorde(a, b, anchoDe(n) / 2 + 4)
        return <line key={`cas-${c}-${n}`} data-cascada x1={a.x} y1={a.y} x2={fin.x} y2={fin.y}
          className={cn("stroke-aviso transition-opacity", dim(relevante))} strokeDasharray="5 4" strokeWidth={1.6} />
      })}
      {ataques && d.carril && top.flatMap((o, i) => Object.entries(o.objetivos).map(([eq, n]) => {
        const b = pos(eq)
        if (!b) return null
        const p = pildora(i)
        const x1 = p.x + PILDORA.w / 2, y1 = p.y + PILDORA.h
        const y2 = b.y - altoDe(eq) / 2
        const relevante = eq === seleccionado
        return <path key={`atk-${o.ip}-${eq}`} data-ataque-origen d={`M${x1},${y1} C${x1},${(y1 + y2) / 2} ${b.x},${(y1 + y2) / 2} ${b.x},${y2}`}
          className={cn("fill-none stroke-critico transition-opacity", dim(relevante))} strokeWidth={grosor(n)} markerEnd="url(#flecha-ataque)" />
      }))}

      {/* superposición de un incidente: su flecha de ataque y su cascada */}
      {incidente && (() => {
        const o = incidente.origen ? pos(incidente.origen) : null
        const a = incidente.activo ? pos(incidente.activo) : null
        return (
          <g>
            {o && (incidente.cascada ?? []).map((c) => {
              const nc = pos(c); if (!nc) return null
              const fin = haciaBorde(o, nc, anchoDe(c) / 2 + 4)
              return <line key={`inc-casc-${c}`} data-cascada-incidente x1={o.x} y1={o.y} x2={fin.x} y2={fin.y} className="stroke-aviso" strokeDasharray="5 4" strokeWidth={1.8} />
            })}
            {o && a && (() => {
              const ini = haciaBorde(a, o, anchoDe(incidente.origen!) / 2 + 4), fin = haciaBorde(o, a, anchoDe(incidente.activo!) / 2 + 4)
              return <line data-ataque x1={ini.x} y1={ini.y} x2={fin.x} y2={fin.y} className="stroke-critico" strokeWidth={2.4} markerEnd="url(#flecha-ataque)" />
            })()}
          </g>
        )
      })()}

      {/* nodos: externos (carril), tronco y hojas visibles */}
      {red.nodos.map((n) => {
        const p = d.nodos[n.nombre]
        if (!p) return null
        const v = ESTADO_VISUAL[n.actividad.estado] ?? ESTADO_VISUAL.sin_actividad
        const sel = seleccionado === n.nombre
        const externo = n.tipo === "externo"
        const w = anchoDe(n.nombre), h = altoDe(n.nombre)
        const a = n.actividad
        const insignia = a.objetivo > 0 ? { n: a.objetivo, cls: "fill-critico" } : a.pendientes > 0 ? { n: a.pendientes, cls: "fill-aviso" } : null
        const relevante = relacionados.has(n.nombre) || (!esHoja(n.nombre) && !externo)
        const sub = [n.ip, n.criticidad, a.estado === "caido" ? "✕ caído" : null].filter(Boolean).join(" · ")
        return (
          <g key={n.nombre} role="button" tabIndex={0} aria-pressed={sel} aria-label={`${n.nombre}, ${v.texto}`}
            onClick={() => onSeleccionar(n.nombre)} onKeyDown={teclado(() => onSeleccionar(n.nombre))}
            className={cn("cursor-pointer outline-none transition-opacity focus-visible:[&>rect]:stroke-ring", dim(relevante))}>
            <rect x={p.x - w / 2} y={p.y - h / 2} width={w} height={h} rx={externo ? h / 2 : 5} className={`${v.relleno} ${v.borde}`} strokeWidth={sel ? 3 : 1.4} />
            {externo || !sub ? (
              <text x={p.x} y={p.y + 4} textAnchor="middle" className="fill-foreground text-[11px]">{externo && v.icono ? `${v.icono} ` : ""}{n.nombre}</text>
            ) : (
              <>
                <text x={p.x} y={p.y - 1} textAnchor="middle" className="fill-foreground text-[11px] font-medium">{n.nombre}</text>
                <text x={p.x} y={p.y + 10} textAnchor="middle" className="fill-muted-foreground font-mono text-[8px]">{sub}</text>
              </>
            )}
            {insignia && !externo && (
              <>
                <circle cx={p.x + w / 2 - 6} cy={p.y - h / 2 + 4} r={7} className={insignia.cls} />
                <text x={p.x + w / 2 - 6} y={p.y - h / 2 + 7} textAnchor="middle" className="fill-white text-[8.5px] font-semibold" style={{ fill: "var(--sobre-estado)" }}>{insignia.n}</text>
              </>
            )}
          </g>
        )
      })}
    </svg>
  )
}
