import { useSondeo, getDecisiones, type Decision } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export function FilaDecision({ d }: { d: Decision }) {
  if (d.tipo === "actividad_suprimida")
    return <TableRow className="opacity-60"><TableCell colSpan={4}>↩ actividad suprimida (+{d.alertas_suprimidas})</TableCell></TableRow>
  return (
    <TableRow>
      <TableCell>{d.timestamp}</TableCell><TableCell>{d.activo}</TableCell>
      <TableCell>{d.clase}</TableCell><TableCell>{d.accion_final ?? "—"}</TableCell>
    </TableRow>
  )
}

export function Decisiones() {
  const d = useSondeo(getDecisiones)
  if (!d || "error" in d) return <p>{d && "error" in d ? "sin conexión" : "cargando…"}</p>
  if (d.length === 0) return <p>sin decisiones todavía</p>
  return (
    <Table>
      <TableHeader><TableRow><TableHead>Cuándo</TableHead><TableHead>Activo</TableHead><TableHead>Clase</TableHead><TableHead>Acción</TableHead></TableRow></TableHeader>
      <TableBody>{d.map((x, i) => <FilaDecision key={i} d={x} />)}</TableBody>
    </Table>
  )
}
