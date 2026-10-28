import { useState } from "react"
import { useSondeo, getTrazas, type Decision } from "@/api"
import { Prioridad, Cargando, SinConexion, Vacio } from "@/components/bits"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ubicacionesDe, type MetricaUbicacion } from "@/datos"
import { TIERRA_PATHS } from "@/worldmap"

// Las tres vistas del mapa: en curso (recibidos no contenidos), total (recibidos) y mitigados
// (contenidos). total = en curso + mitigados. El filtro elige cuál dimensiona y numera los puntos.
const METRICAS: { clave: MetricaUbicacion; etiqueta: string; color: string }[] = [
  { clave: "enCurso",   etiqueta: "En curso",  color: "fill-rose-500/70 stroke-rose-600" },
  { clave: "n",         etiqueta: "Total",     color: "fill-amber-500/70 stroke-amber-600" },
  { clave: "mitigados", etiqueta: "Mitigados", color: "fill-emerald-500/70 stroke-emerald-600" },
]

// Vista «Ubicaciones»: origen de los ataques por ubicación. La geo es OFFLINE y aproximada (tabla de
// muestra, sin egreso); las IPs de laboratorio/documentación e internas no geolocalizan y van en la
// tabla. Mapamundi inline: siluetas de tierra (Natural Earth 110m, dominio público) + marcadores,
// ambos en la misma proyección equirectangular (x=lon+180, y=90-lat). Sin dependencias ni egreso.
type Ubi = ReturnType<typeof ubicacionesDe>[number]

// `onVerPais` pivota a Decisiones filtradas por ese país; `onVerAprobaciones` abre la cola. Según la
// métrica activa, al pulsar una fila de país: «En curso» → Aprobaciones (la cola a atender), «Total»/
// «Mitigados» → Decisiones del país.
export function Ubicaciones({ onVerPais, onVerAprobaciones }: {
  onVerPais?: (pais: string) => void; onVerAprobaciones?: (pais: string) => void
} = {}) {
  const t = useSondeo(getTrazas)
  const [metrica, setMetrica] = useState<MetricaUbicacion>("enCurso")
  const [hover, setHover] = useState<null | { x: number; y: number; p: Ubi }>(null)
  if (!t) return <Cargando />
  const fallo = "error" in t ? t : null
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />
  const regs: Decision[] = fallo ? (fallo.datos ?? []) : (t as Decision[])
  const ubis = ubicacionesDe(regs)
  if (ubis.length === 0) return <Vacio>Sin orígenes de ataque todavía.</Vacio>
  const paises = ubis.filter((u) => u.lat != null && u.lon != null)
  const activa = METRICAS.find((m) => m.clave === metrica)!
  // puntos del mapa: solo donde la métrica elegida > 0, dimensionados y numerados por ella
  const visibles = paises.map((p) => ({ ...p, v: p[metrica] })).filter((p) => p.v > 0)
  const maxV = Math.max(1, ...visibles.map((p) => p.v))
  const tot = (k: MetricaUbicacion) => ubis.reduce((s, u) => s + u[k], 0)
  // a dónde lleva pulsar una fila de país, según el filtro activo (solo clicable si existe su handler)
  const handlerActivo = metrica === "enCurso" ? onVerAprobaciones : onVerPais
  const esNavegable = (u: Ubi) => u.lat != null && !!handlerActivo
  const irA = (u: Ubi) => { if (metrica === "enCurso") onVerAprobaciones?.(u.nombre); else onVerPais?.(u.nombre) }
  const destino = metrica === "enCurso" ? "Aprobaciones" : "Decisiones"
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Origen de los ataques por ubicación. La geolocalización es <b>offline y aproximada</b> (tabla de muestra,
        sin egreso); las IPs de <b>laboratorio/documentación</b> e <b>internas</b> no se geolocalizan y van en la tabla.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {METRICAS.map((m) => (
          <Button key={m.clave} size="sm" variant={m.clave === metrica ? "default" : "secondary"}
            className="h-7 px-2.5 text-xs" onClick={() => setMetrica(m.clave)}>
            {m.etiqueta} <span className="ml-1 tabular-nums opacity-80">{tot(m.clave)}</span>
          </Button>
        ))}
        <span className="text-xs text-muted-foreground">· cifras <b>globales</b> (todas las ubicaciones, incl. las de la tabla);
          el mapa numera solo las <b>geolocalizadas</b> por «{activa.etiqueta.toLowerCase()}»
          {metrica === "enCurso" && " (recibidos aún no contenidos)"}</span>
      </div>
      <div className="rounded-lg border border-border bg-card p-3">
        {visibles.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            {paises.length === 0
              ? "Sin orígenes geolocalizables (todos son de laboratorio o internos)."
              : `Ningún país con ataques «${activa.etiqueta.toLowerCase()}» ahora mismo.`}
          </div>
        ) : (
          <svg viewBox="0 0 360 180" className="h-auto w-full rounded bg-sky-500/5" role="img" aria-label="Mapamundi de orígenes de ataque">
            {/* siluetas de tierra, al fondo */}
            <g className="fill-muted stroke-border" strokeWidth="0.2" strokeOpacity={0.5}>
              {TIERRA_PATHS.map((d, i) => <path key={i} d={d} />)}
            </g>
            <rect x="0.5" y="0.5" width="359" height="179" fill="none" className="stroke-border" strokeWidth="1" />
            {[90, 180, 270].map((x) => <line key={`v${x}`} x1={x} y1="0" x2={x} y2="180" className="stroke-border" strokeWidth="0.5" opacity="0.25" />)}
            {[45, 90, 135].map((y) => <line key={`h${y}`} x1="0" y1={y} x2="360" y2={y} className="stroke-border" strokeWidth="0.5" opacity="0.25" />)}
            {visibles.map((p) => {
              const cx = p.lon! + 180, cy = 90 - p.lat!
              const r = 5 + 7 * (Math.log(p.v + 1) / Math.log(maxV + 1))
              return (
                <g key={p.clave}>
                  <circle cx={cx} cy={cy} r={r} className={`${activa.color} cursor-help`} strokeWidth="0.5"
                    onMouseMove={(e) => setHover({ x: e.clientX, y: e.clientY, p })}
                    onMouseLeave={() => setHover(null)}>
                    <title>{p.nombre}: {p.v} {activa.etiqueta.toLowerCase()} · {p.n} total, {p.mitigados} mitigados, {p.ips} IP(s)</title>
                  </circle>
                  {/* la cantidad, ENCIMA del punto. pointer-events-none + select-none: el ratón pasa
                      al círculo (el hover no se interrumpe) y el número no se selecciona/copia como texto */}
                  <text x={cx} y={cy} dy="0.35em" textAnchor="middle" className="pointer-events-none select-none fill-white font-semibold"
                    fontSize={Math.min(r * 1.1, 8)}>{p.v}</text>
                  <text x={cx} y={cy - r - 1} textAnchor="middle" className="pointer-events-none select-none fill-muted-foreground" fontSize="6">{p.codigo ?? p.nombre}</text>
                </g>
              )
            })}
          </svg>
        )}
      </div>
      {/* hover sobre un punto: tarjeta que sigue al cursor con el desglose de las tres métricas */}
      {hover && (
        <div className="pointer-events-none fixed z-50 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs shadow-md"
          style={{ left: hover.x + 12, top: hover.y + 12 }}>
          <div className="font-medium">{hover.p.nombre}{hover.p.codigo ? ` (${hover.p.codigo})` : ""}</div>
          <div className="mt-0.5 space-x-1.5">
            <span className="text-rose-600 dark:text-rose-400">En curso {hover.p.enCurso}</span>
            <span className="text-muted-foreground">· Total {hover.p.n}</span>
            <span className="text-emerald-600 dark:text-emerald-400">· Mitigados {hover.p.mitigados}</span>
          </div>
          <div className="text-muted-foreground">{hover.p.ips} IP(s) distintas</div>
        </div>
      )}
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        {handlerActivo && (
          <div className="border-b border-border px-3 py-1.5 text-xs text-muted-foreground">
            Pulsa un país para ver sus ataques en <b>{destino}</b> (según el filtro «{activa.etiqueta.toLowerCase()}»).
          </div>
        )}
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Ubicación</TableHead>
              <TableHead className={metrica === "enCurso" ? "text-foreground" : ""}>En curso</TableHead>
              <TableHead className={metrica === "n" ? "text-foreground" : ""}>Total</TableHead>
              <TableHead className={metrica === "mitigados" ? "text-foreground" : ""}>Mitigados</TableHead>
              <TableHead>IPs</TableHead><TableHead>Gravedad</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ubis.map((u) => (
              <TableRow key={u.clave}
                className={esNavegable(u) ? "cursor-pointer" : "hover:bg-transparent"}
                onClick={esNavegable(u) ? () => irA(u) : undefined}
                title={esNavegable(u) ? `Ver en ${destino}` : undefined}>
                <TableCell>{u.codigo ? `${u.nombre} (${u.codigo})` : u.nombre}{esNavegable(u) && <span className="ml-1 text-muted-foreground">→</span>}</TableCell>
                <TableCell className={`tabular-nums ${metrica === "enCurso" ? "font-semibold" : "text-muted-foreground"}`}>{u.enCurso}</TableCell>
                <TableCell className={`tabular-nums ${metrica === "n" ? "font-semibold" : "text-muted-foreground"}`}>{u.n}</TableCell>
                <TableCell className={`tabular-nums ${metrica === "mitigados" ? "font-semibold" : "text-muted-foreground"}`}>{u.mitigados}</TableCell>
                <TableCell className="tabular-nums">{u.ips}</TableCell>
                <TableCell><Prioridad n={u.prioridad || null} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
