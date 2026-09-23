import { useSondeo, getSalud } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

export function Salud() {
  const s = useSondeo(getSalud)
  if (!s) return <p>cargando…</p>
  if ("error" in s) return <p className="text-red-600">sin conexión con el daemon</p>
  if ("sin_datos" in s) return <p>sin datos del monitor (¿banco levantado?)</p>
  return (
    <div>
      <p className="mb-2">{s.caidos} de {s.total} servicios caídos</p>
      <Table>
        <TableHeader><TableRow><TableHead>Servicio</TableHead><TableHead>Estado</TableHead><TableHead>Depende de</TableHead></TableRow></TableHeader>
        <TableBody>{s.servicios.map((x) => (
          <TableRow key={x.nombre}>
            <TableCell>{x.nombre}</TableCell>
            <TableCell><Badge variant={x.estado === "ok" ? "default" : "destructive"}>{x.estado === "ok" ? "OK" : "CAÍDO"}</Badge></TableCell>
            <TableCell>{x.depende_de.join(", ") || "—"}</TableCell>
          </TableRow>))}
        </TableBody>
      </Table>
    </div>
  )
}
