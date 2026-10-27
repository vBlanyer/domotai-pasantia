import { useSondeo, getTrazas, type Decision } from "@/api"
import { Prioridad, Cargando, SinConexion, Vacio } from "@/components/bits"
import { campanasDe } from "@/datos"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

const hora = (ts?: string | null) => {
  if (!ts) return "—"
  const t = new Date(ts)
  return isNaN(t.getTime()) ? ts : new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(t)
}

// Vista «Campañas» (attack story): los ataques agrupados por bloque de origen /24 a través de todos
// los equipos. Una campaña que rota IPs contra varios activos = una fila. Al pulsar un bloque se
// pivota a Decisiones filtradas por ese prefijo.
export function Campanas({ onVerOrigen }: { onVerOrigen: (prefijo: string) => void }) {
  const t = useSondeo(getTrazas)
  if (!t) return <Cargando />
  const fallo = "error" in t ? t : null
  const regs: Decision[] = fallo ? (fallo.datos ?? []) : (t as Decision[])
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />
  const campanas = campanasDe(regs)
  if (campanas.length === 0) return <Vacio>Sin campañas: no hay ataques agrupables por bloque de origen todavía.</Vacio>
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Ataques agrupados por <strong>bloque de origen /24</strong> a través de todos los equipos: una campaña
        que rota IPs contra varios activos aparece como una sola fila. Pulsa un bloque para ver sus decisiones.
      </p>
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Bloque de origen</TableHead><TableHead>Gravedad</TableHead>
              <TableHead>IPs</TableHead><TableHead>Ataques</TableHead>
              <TableHead>Objetivos</TableHead><TableHead>Ventana</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {campanas.map((c) => (
              <TableRow key={c.cidr}>
                <TableCell>
                  <button onClick={() => onVerOrigen(c.prefijo)}
                    className="font-mono text-xs underline-offset-2 hover:underline" title="Ver las decisiones del bloque">{c.cidr}</button>
                  {c.alcance && <span className="ml-1 text-xs text-muted-foreground">· {c.alcance}</span>}
                </TableCell>
                <TableCell><Prioridad n={c.prioridad || null} /></TableCell>
                <TableCell className="tabular-nums whitespace-nowrap">{c.ips} IP{c.ips === 1 ? "" : "s"}</TableCell>
                <TableCell className="tabular-nums">×{c.n}</TableCell>
                <TableCell className="text-xs">
                  <span title={c.objetivos.map((o) => `${o.equipo} ×${o.n}`).join(", ")}>
                    {c.objetivos.slice(0, 2).map((o) => `${o.equipo} ×${o.n}`).join(", ")}
                    {c.objetivos.length > 2 ? ` +${c.objetivos.length - 2}` : ""}
                  </span>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{hora(c.primera)} → {hora(c.ultima)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
