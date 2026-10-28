import { useSondeo, getTrazas, type Decision } from "@/api"
import { Prioridad, Cargando, SinConexion, Vacio } from "@/components/bits"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ubicacionesDe } from "@/datos"
import { TIERRA_PATHS } from "@/worldmap"

// Vista «Ubicaciones»: origen de los ataques por ubicación. La geo es OFFLINE y aproximada (tabla de
// muestra, sin egreso); las IPs de laboratorio/documentación e internas no geolocalizan y van en la
// tabla. Mapamundi inline: siluetas de tierra (Natural Earth 110m, dominio público) + marcadores,
// ambos en la misma proyección equirectangular (x=lon+180, y=90-lat). Sin dependencias ni egreso.
export function Ubicaciones() {
  const t = useSondeo(getTrazas)
  if (!t) return <Cargando />
  const fallo = "error" in t ? t : null
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />
  const regs: Decision[] = fallo ? (fallo.datos ?? []) : (t as Decision[])
  const ubis = ubicacionesDe(regs)
  if (ubis.length === 0) return <Vacio>Sin orígenes de ataque todavía.</Vacio>
  const paises = ubis.filter((u) => u.lat != null && u.lon != null)
  const maxN = Math.max(1, ...paises.map((p) => p.n))
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Origen de los ataques por ubicación. La geolocalización es <b>offline y aproximada</b> (tabla de muestra,
        sin egreso); las IPs de <b>laboratorio/documentación</b> e <b>internas</b> no se geolocalizan y van en la tabla.
      </p>
      <div className="rounded-lg border border-border bg-card p-3">
        <div className="mb-1 text-xs text-muted-foreground">Mapamundi (equirectangular aproximado)</div>
        {paises.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            Sin orígenes geolocalizables (todos son de laboratorio o internos).
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
            {paises.map((p) => {
              const cx = p.lon! + 180, cy = 90 - p.lat!
              const r = 3 + 6 * (Math.log(p.n + 1) / Math.log(maxN + 1))
              return (
                <g key={p.clave}>
                  <circle cx={cx} cy={cy} r={r} className="fill-rose-500/60 stroke-rose-600" strokeWidth="0.5">
                    <title>{p.nombre}: {p.n} ataque(s), {p.ips} IP(s)</title>
                  </circle>
                  <text x={cx} y={cy - r - 1} textAnchor="middle" className="fill-muted-foreground" fontSize="6">{p.codigo ?? p.nombre}</text>
                </g>
              )
            })}
          </svg>
        )}
      </div>
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Ubicación</TableHead><TableHead>Ataques</TableHead><TableHead>IPs</TableHead><TableHead>Gravedad</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ubis.map((u) => (
              <TableRow key={u.clave}>
                <TableCell>{u.codigo ? `${u.nombre} (${u.codigo})` : u.nombre}</TableCell>
                <TableCell className="tabular-nums">×{u.n}</TableCell>
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
