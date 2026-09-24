import { useSondeo, getEquipos, getTrazas, type Equipo, type Decision } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Punto, Cargando, SinConexion, Vacio, Dato } from "./bits"

// Categorías en orden de presentación (las que el backend emite desde el perfil).
const CATS: { id: string; nombre: string }[] = [
  { id: "servidor", nombre: "Servidores" },
  { id: "endpoint", nombre: "Endpoints" },
  { id: "gestion", nombre: "Gestión / SIEM" },
  { id: "cortafuegos", nombre: "Cortafuegos" },
]

const CRIT: Record<string, string> = {
  critica: "bg-rose-500/15 text-rose-600 dark:text-rose-400",
  alta: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  media: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  baja: "bg-slate-500/15 text-slate-600 dark:text-slate-400",
}

function Criticidad({ v }: { v?: string | null }) {
  if (!v) return <span className="text-muted-foreground">—</span>
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${CRIT[v] ?? CRIT.baja}`}>{v}</span>
}

function Estado({ v }: { v?: string | null }) {
  if (v === "ok")
    return <span className="inline-flex items-center gap-1.5"><Punto estado="ok" /><span className="text-emerald-600 dark:text-emerald-400">operativo</span></span>
  if (v === "caido")
    return <span className="inline-flex items-center gap-1.5"><Punto estado="caido" /><span className="text-rose-600 dark:text-rose-400">caído</span></span>
  return <span className="text-xs text-muted-foreground">sin monitor</span>
}

type Postura = { recibidos: number; amenazas: number; originados: number; bloqueado: boolean }

function posturaDe(equipos: Equipo[], trazas: Decision[]) {
  const decisiones = trazas.filter((d) => d.tipo !== "actividad_suprimida")
  const porActivo = new Map<string, { recibidos: number; amenazas: number }>()
  const porOrigen = new Map<string, number>()
  const bloqueada = new Set<string>()
  for (const d of decisiones) {
    const a = d.activo ?? ""
    const r = porActivo.get(a) ?? { recibidos: 0, amenazas: 0 }
    r.recibidos += 1
    if ((d.clase ?? "").startsWith("vp_")) r.amenazas += 1
    porActivo.set(a, r)
    const ip = d.origen_ip ?? ""
    if (ip) {
      porOrigen.set(ip, (porOrigen.get(ip) ?? 0) + 1)
      if ((d.accion_final ?? "").includes("BLOQUEAR")) bloqueada.add(ip)
    }
  }
  const m = new Map<string, Postura>()
  for (const e of equipos) {
    const rec = porActivo.get(e.nombre) ?? { recibidos: 0, amenazas: 0 }
    m.set(e.nombre, {
      recibidos: rec.recibidos, amenazas: rec.amenazas,
      originados: (e.ip && porOrigen.get(e.ip)) || 0,
      bloqueado: !!e.ip && bloqueada.has(e.ip),
    })
  }
  return m
}

function Seguridad({ p }: { p: Postura }) {
  if (p.amenazas === 0 && p.originados === 0)
    return <span className="text-muted-foreground">sin actividad</span>
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      {p.amenazas > 0 && (
        <span className="rounded bg-rose-500/15 px-1.5 py-0.5 text-rose-600 dark:text-rose-400">
          {p.amenazas} amenaza(s) recibida(s)
        </span>
      )}
      {p.recibidos > p.amenazas && (
        <span className="text-muted-foreground">{p.recibidos - p.amenazas} sin acción</span>
      )}
      {p.originados > 0 && (
        <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-amber-600 dark:text-amber-400">
          originó {p.originados} ataque(s){p.bloqueado ? " · bloqueado" : ""}
        </span>
      )}
    </div>
  )
}

function Mini({ valor, etiqueta, tono = "" }: { valor: number; etiqueta: string; tono?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className={`font-heading text-2xl font-semibold tabular-nums ${tono}`}>{valor}</div>
      <div className="mt-0.5 text-xs text-muted-foreground">{etiqueta}</div>
    </div>
  )
}

function Grupo({ nombre, equipos, postura }: { nombre: string; equipos: Equipo[]; postura: Map<string, Postura> }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-sm font-medium">{nombre}</span>
        <span className="text-xs text-muted-foreground">{equipos.length}</span>
      </div>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Equipo</TableHead><TableHead>Criticidad</TableHead><TableHead>IP</TableHead>
            <TableHead>Estado</TableHead><TableHead>Seguridad</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {equipos.map((e) => (
            <TableRow key={e.nombre}>
              <TableCell>
                <div className="font-medium">{e.nombre}</div>
                {e.funcion && <div className="text-xs text-muted-foreground">{e.funcion}</div>}
              </TableCell>
              <TableCell><Criticidad v={e.criticidad} /></TableCell>
              <TableCell><Dato>{e.ip}</Dato></TableCell>
              <TableCell><Estado v={e.estado} /></TableCell>
              <TableCell><Seguridad p={postura.get(e.nombre) ?? { recibidos: 0, amenazas: 0, originados: 0, bloqueado: false }} /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export function Equipos() {
  const eq = useSondeo(getEquipos)
  const tz = useSondeo(getTrazas)
  if (!eq) return <Cargando />
  if (!Array.isArray(eq)) return <SinConexion />
  if (eq.length === 0) return <Vacio>El perfil no declara equipos.</Vacio>

  const trazas: Decision[] = Array.isArray(tz) ? tz : []
  const postura = posturaDe(eq, trazas)
  const criticos = eq.filter((e) => e.criticidad === "critica").length
  const conAmenaza = eq.filter((e) => { const p = postura.get(e.nombre); return p && (p.amenazas > 0 || p.originados > 0) }).length

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <Mini valor={eq.length} etiqueta="equipos en el inventario" />
        <Mini valor={criticos} etiqueta="de criticidad crítica" />
        <Mini valor={conAmenaza} etiqueta="con actividad de amenaza" tono={conAmenaza ? "text-rose-600 dark:text-rose-400" : ""} />
      </div>
      {(CATS.map((c) => ({ ...c, items: eq.filter((e) => e.categoria === c.id) }))
        .filter((c) => c.items.length > 0) as { id: string; nombre: string; items: Equipo[] }[])
        .map((c) => <Grupo key={c.id} nombre={c.nombre} equipos={c.items} postura={postura} />)}
      {/* categorías no previstas, por si el perfil añade otras */}
      {(() => {
        const otras = eq.filter((e) => !CATS.some((c) => c.id === e.categoria))
        return otras.length > 0 ? <Grupo nombre="Otros" equipos={otras} postura={postura} /> : null
      })()}
    </div>
  )
}
