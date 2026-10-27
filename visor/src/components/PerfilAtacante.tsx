import { useSondeo, getTrazas, type Decision } from "@/api"
import { Prioridad, RiesgoBadge, Cargando, SinConexion } from "@/components/bits"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { OrigenBadges } from "@/components/OrigenBadges"
import { Tendencia } from "@/components/charts"
import { perfilAtacante, riesgoAtacante } from "@/datos"

const hora = (ts?: string | null) => {
  if (!ts) return "—"
  const t = new Date(ts)
  return isNaN(t.getTime()) ? ts : new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(t)
}

function Kpi({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2">
      <div className="text-xs text-muted-foreground">{etiqueta}</div>
      <div className="mt-0.5 text-sm font-medium">{children}</div>
    </div>
  )
}

// Página de entidad del atacante: una IP de origen → todo lo suyo (equipos atacados, ventana,
// enriquecimiento y tendencia), con pivote a sus decisiones. Drill-down (no en el menú).
export function PerfilAtacante({ ip, onVolver, onVerDecisiones }: {
  ip: string; onVolver: () => void; onVerDecisiones: (ip: string) => void
}) {
  const t = useSondeo(getTrazas)
  if (!t) return <Cargando />
  const fallo = "error" in t ? t : null
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />
  const regs: Decision[] = fallo ? (fallo.datos ?? []) : (t as Decision[])
  const p = perfilAtacante(regs, ip)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" variant="secondary" onClick={onVolver}>← Volver</Button>
        <div className="font-heading text-base font-semibold font-mono">{ip}</div>
        <RiesgoBadge r={riesgoAtacante(p)} />
        <OrigenBadges e={p.enriquecimiento} />
        <Button size="sm" className="ml-auto" onClick={() => onVerDecisiones(ip)}>Ver sus decisiones →</Button>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Kpi etiqueta="Ataques">{p.n}</Kpi>
        <Kpi etiqueta="Equipos atacados">{p.equipos.length}</Kpi>
        <Kpi etiqueta="Gravedad"><Prioridad n={p.prioridad || null} /></Kpi>
        <Kpi etiqueta="Ventana">{hora(p.primera)} → {hora(p.ultima)}</Kpi>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-2 text-sm font-medium">Equipos atacados</div>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Equipo</TableHead><TableHead>Ataques</TableHead><TableHead>Última</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {p.equipos.length === 0
                ? <TableRow><TableCell colSpan={3} className="text-muted-foreground">Sin ataques de esta IP en la ventana.</TableCell></TableRow>
                : p.equipos.map((e) => (
                  <TableRow key={e.equipo}>
                    <TableCell>{e.equipo}</TableCell>
                    <TableCell className="tabular-nums">×{e.n}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{hora(e.ultima)}</TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </div>
        <div className="rounded-lg border border-border bg-card p-3">
          <div className="mb-1 text-xs text-muted-foreground">Actividad por día</div>
          <Tendencia data={p.porDia} />
        </div>
      </div>
    </div>
  )
}
