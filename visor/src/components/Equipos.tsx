import { useSondeo, getTrazas, type Decision } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Punto, Cargando, SinConexion, Vacio, Dato } from "./bits"

// Un equipo es un activo del cliente visto desde los incidentes: agregamos la traza por `activo`.
// Es la lente centrada en activos, complementaria a «Estado de servicios» (salud de los servicios).
type Equipo = {
  nombre: string
  incidentes: number
  amenazas: number
  falsos: number
  enrutadas: number
  ultimaAccion: string | null
  ultimaHora: string | null
}

type Riesgo = { texto: string; punto: "ok" | "pendiente" | "caido"; clase: string }

function riesgoDe(e: Equipo): Riesgo {
  if (e.amenazas > 0) return { texto: "amenaza activa", punto: "caido", clase: "text-rose-600 dark:text-rose-400" }
  if (e.enrutadas > 0) return { texto: "enrutado a revisión", punto: "pendiente", clase: "text-amber-600 dark:text-amber-400" }
  return { texto: "sin amenazas", punto: "ok", clase: "text-emerald-600 dark:text-emerald-400" }
}

function agregar(regs: Decision[]): Equipo[] {
  const m = new Map<string, Equipo>()
  for (const d of regs) {
    if (d.tipo === "actividad_suprimida") continue
    const nombre = d.activo ?? "—"
    const e = m.get(nombre) ?? { nombre, incidentes: 0, amenazas: 0, falsos: 0, enrutadas: 0, ultimaAccion: null, ultimaHora: null }
    e.incidentes += 1
    const c = d.clase ?? ""
    if (c.startsWith("vp_")) e.amenazas += 1
    else if (c === "amenaza_enrutada") e.enrutadas += 1
    else if (c.startsWith("fp_")) e.falsos += 1
    const ts = d.timestamp ?? ""
    if (ts && (!e.ultimaHora || ts > e.ultimaHora)) {
      e.ultimaHora = ts
      e.ultimaAccion = d.accion_final ?? null
    }
    m.set(nombre, e)
  }
  // Orden: primero los que tienen amenazas, luego por número de incidentes.
  return [...m.values()].sort((a, b) => b.amenazas - a.amenazas || b.incidentes - a.incidentes)
}

function Mini({ valor, etiqueta, tono = "" }: { valor: number; etiqueta: string; tono?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className={`font-heading text-2xl font-semibold tabular-nums ${tono}`}>{valor}</div>
      <div className="mt-0.5 text-xs text-muted-foreground">{etiqueta}</div>
    </div>
  )
}

export function Equipos() {
  const t = useSondeo(getTrazas)
  if (!t) return <Cargando />
  if (!Array.isArray(t)) return <SinConexion />
  const equipos = agregar(t)
  if (equipos.length === 0) return <Vacio>Aún no hay actividad sobre ningún equipo.</Vacio>

  const conAmenaza = equipos.filter((e) => e.amenazas > 0).length
  const incidentes = equipos.reduce((a, e) => a + e.incidentes, 0)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <Mini valor={equipos.length} etiqueta="equipos con actividad" />
        <Mini valor={conAmenaza} etiqueta="con amenaza activa" tono={conAmenaza ? "text-rose-600 dark:text-rose-400" : ""} />
        <Mini valor={incidentes} etiqueta="incidentes totales" />
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <div className="border-b border-border px-4 py-3 text-sm font-medium">Equipos monitoreados</div>
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Equipo</TableHead>
              <TableHead>Riesgo</TableHead>
              <TableHead className="text-right">Incidentes</TableHead>
              <TableHead className="text-right">Amenazas</TableHead>
              <TableHead className="text-right">Falsos +</TableHead>
              <TableHead>Última acción</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {equipos.map((e) => {
              const r = riesgoDe(e)
              return (
                <TableRow key={e.nombre}>
                  <TableCell className="font-medium">{e.nombre}</TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-2">
                      <Punto estado={r.punto} />
                      <span className={r.clase}>{r.texto}</span>
                    </span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{e.incidentes}</TableCell>
                  <TableCell className="text-right tabular-nums">{e.amenazas || <span className="text-muted-foreground">0</span>}</TableCell>
                  <TableCell className="text-right tabular-nums">{e.falsos || <span className="text-muted-foreground">0</span>}</TableCell>
                  <TableCell><Dato>{e.ultimaAccion ?? "—"}</Dato></TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
