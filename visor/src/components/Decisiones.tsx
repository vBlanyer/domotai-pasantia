import { useSondeo, getDecisiones, type Decision } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Cargando, SinConexion, Vacio, ClaseBadge, Dato } from "./bits"

export function FilaDecision({ d }: { d: Decision }) {
  if (d.tipo === "actividad_suprimida")
    return (
      <TableRow className="text-muted-foreground">
        <TableCell colSpan={5} className="italic">
          ↩ el ataque continúa · {d.alertas_suprimidas} alerta(s) suprimida(s) (ya decidido)
        </TableCell>
      </TableRow>
    )
  return (
    <TableRow>
      <TableCell><Dato>{d.timestamp}</Dato></TableCell>
      <TableCell className="font-medium">{d.activo}</TableCell>
      <TableCell><ClaseBadge clase={d.clase} /></TableCell>
      <TableCell>{d.accion_final ?? <span className="text-muted-foreground">—</span>}</TableCell>
      <TableCell>
        {d.requiere_humano
          ? <span className="text-amber-400">humano</span>
          : <span className="text-muted-foreground">auto</span>}
      </TableCell>
    </TableRow>
  )
}

export function Decisiones() {
  const d = useSondeo(getDecisiones)
  if (!d) return <Cargando />
  if ("error" in d) return <SinConexion />
  if (d.length === 0) return <Vacio>Aún no hay decisiones. Lanza un ataque para verlas aquí.</Vacio>
  return (
    <div className="rounded-lg border border-border bg-card">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Cuándo</TableHead><TableHead>Activo</TableHead><TableHead>Clase</TableHead>
            <TableHead>Acción</TableHead><TableHead>Decisión</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>{d.map((x, i) => <FilaDecision key={i} d={x} />)}</TableBody>
      </Table>
    </div>
  )
}
