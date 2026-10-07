import { useSondeo, getContenciones } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Cargando, SinConexion, Vacio, Dato } from "./bits"

// #4: contenciones que siguen activas, reconstruidas de la traza. El daemon «recuerda» qué tiene
// bloqueado aunque se reinicie; esto responde a «¿qué estoy conteniendo ahora mismo?».
export function Contenciones() {
  const c = useSondeo(getContenciones)
  if (!c) return <Cargando />
  if ("error" in c) return <SinConexion />
  if (!c.length) return <Vacio>No hay contenciones activas. Nada bloqueado ahora mismo.</Vacio>
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-sm font-medium">
          {c.length} {c.length === 1 ? "contención activa" : "contenciones activas"}
        </span>
        <Dato>reconstruidas de la traza</Dato>
      </div>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Objetivo bloqueado</TableHead><TableHead>Activo</TableHead>
            <TableHead>Dónde</TableHead><TableHead>Acción</TableHead><TableHead>Decisión</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {c.map((x) => (
            <TableRow key={`${x.id_decision}:${x.objetivo}:${x.nodo}`}>
              <TableCell className="font-mono text-xs">{x.objetivo ?? x.ip ?? "—"}</TableCell>
              <TableCell>{x.activo ?? "—"}</TableCell>
              <TableCell className="text-muted-foreground">
                {x.nodo ?? "—"}{x.via_escalada ? " (escalada)" : ""}
              </TableCell>
              <TableCell className="font-mono text-xs">{x.accion_id}</TableCell>
              <TableCell className="text-muted-foreground">{x.id_decision}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
