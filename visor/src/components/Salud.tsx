import { useSondeo, getSalud } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Punto, Cargando, SinConexion, Vacio, Dato } from "./bits"

export function Salud() {
  const s = useSondeo(getSalud)
  if (!s) return <Cargando />
  if ("error" in s) return <SinConexion />
  if ("sin_datos" in s) return <Vacio>Sin datos del monitor. ¿Está levantado el banco?</Vacio>
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-sm font-medium">
          {s.caidos === 0
            ? <span className="text-emerald-600">Todos los servicios sanos</span>
            : <span className="text-rose-600">{s.caidos} de {s.total} servicios caídos</span>}
        </span>
        <Dato>{s.t}</Dato>
      </div>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Servicio</TableHead><TableHead>Estado</TableHead><TableHead>Depende de</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {s.servicios.map((x) => (
            <TableRow key={x.nombre}>
              <TableCell className="font-medium">{x.nombre}</TableCell>
              <TableCell>
                <span className="inline-flex items-center gap-2">
                  <Punto estado={x.estado === "ok" ? "ok" : "caido"} />
                  <span className={x.estado === "ok" ? "text-emerald-600" : "text-rose-600"}>
                    {x.estado === "ok" ? "operativo" : "caído"}
                  </span>
                </span>
              </TableCell>
              <TableCell className="text-muted-foreground">{x.depende_de.join(", ") || "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
