import { useMemo, useState, type ReactNode } from "react"
import { getRed, getTrazas, getWatchlist, useSondeo, type Red as RedDatos, type WatchEntrada, type Decision } from "@/api"
import { Cargando, SinConexion } from "@/components/bits"
import { MapaRed, ESTADO_VISUAL } from "@/components/MapaRed"
import { PanelEquipo } from "@/components/PanelEquipo"
import { origenesDe, cascadaDe } from "@/red"
import { cn } from "@/lib/utils"

type Capa = "ataques" | "cascada" | "dependencias"
const CAPAS: { id: Capa; nombre: string; cls: string }[] = [
  { id: "ataques", nombre: "ataques", cls: "border-critico" },
  { id: "cascada", nombre: "cascada", cls: "border-aviso border-dashed" },
  { id: "dependencias", nombre: "dependencias", cls: "border-violeta border-dashed" },
]

function Kpi({ v, k, cls }: { v: ReactNode; k: string; cls?: string }) {
  return (
    <div className="border-r border-border px-1.5 py-2 text-center last:border-r-0">
      <div className={cn("text-lg font-semibold leading-tight tabular-nums", cls)}>{v}</div>
      <div className="text-[10px] text-muted-foreground">{k}</div>
    </div>
  )
}

// El panel derecho cuando no hay equipo elegido: el resumen de la red, no un hueco.
function ResumenRed({ red, nOrigenes, onVerAprobaciones, onVerSalud }: {
  red: RedDatos; nOrigenes: number; onVerAprobaciones?: () => void; onVerSalud?: () => void
}) {
  const internos = red.nodos.filter((n) => n.tipo !== "externo")
  const atacados = internos.filter((n) => n.actividad.estado === "atacado")
  const esperan = internos.filter((n) => n.actividad.pendientes > 0)
  const caidos = internos.filter((n) => n.actividad.estado === "caido")
  const masAtacados = [...internos].filter((n) => n.actividad.objetivo > 0).sort((a, b) => b.actividad.objetivo - a.actividad.objetivo).slice(0, 3)
  const max = masAtacados[0]?.actividad.objetivo ?? 1
  const arrastra = new Map<string, string[]>()
  for (const [c, n] of cascadaDe(red)) arrastra.set(c, [...(arrastra.get(c) ?? []), n])
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card text-sm">
      <div className="border-b border-border px-4 py-3">
        <div className="font-heading text-base font-semibold">Red del cliente</div>
        <div className="text-xs text-muted-foreground">{internos.length} equipos en {red.zonas.length} {red.zonas.length === 1 ? "zona" : "zonas"}. Pulsa un equipo para ver su ficha.</div>
      </div>
      <div className="grid grid-cols-4 border-b border-border">
        <Kpi v={atacados.length} k="atacados" cls={atacados.length ? "text-critico" : undefined} />
        <Kpi v={esperan.length} k="esperan" cls={esperan.length ? "text-aviso" : undefined} />
        <Kpi v={caidos.length} k={caidos.length === 1 ? "caído" : "caídos"} />
        <Kpi v={nOrigenes} k="orígenes" />
      </div>
      {masAtacados.length > 0 && (
        <div className="border-b border-border px-4 py-3">
          <div className="mb-1.5 text-[11px] text-muted-foreground">Más atacados</div>
          <ul className="space-y-1.5">
            {masAtacados.map((n) => (
              <li key={n.nombre} className="grid grid-cols-[96px_1fr_32px] items-center gap-2 text-xs">
                <span className="truncate text-muted-foreground">{n.nombre}</span>
                <span className="h-2 rounded-sm bg-muted"><span className="block h-full rounded-r-sm bg-critico" style={{ width: `${Math.round((n.actividad.objetivo / max) * 100)}%` }} /></span>
                <span className="text-right font-medium tabular-nums">{n.actividad.objetivo}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="px-4 py-3">
        <div className="mb-1.5 text-[11px] text-muted-foreground">Lo que exige atención</div>
        {esperan.length === 0 && caidos.length === 0
          ? <p className="text-xs text-muted-foreground">Nada esperando ni caído ahora mismo.</p>
          : (
            <ul className="space-y-1.5 text-xs">
              {esperan.map((n) => (
                <li key={`e-${n.nombre}`} className="flex items-center gap-2">
                  <span className="font-mono text-aviso">⏸</span>
                  <span className="flex-1"><b className="font-medium">{n.nombre}</b> · {n.actividad.pendientes} {n.actividad.pendientes === 1 ? "decisión espera" : "decisiones esperan"}</span>
                  {onVerAprobaciones && <button onClick={onVerAprobaciones} className="font-medium text-info hover:underline">aprobar</button>}
                </li>
              ))}
              {caidos.map((n) => (
                <li key={`c-${n.nombre}`} className="flex items-center gap-2">
                  <span className="font-mono text-critico">✕</span>
                  <span className="flex-1"><b className="font-medium">{n.nombre}</b> caído{arrastra.get(n.nombre)?.length ? ` · arrastra a ${arrastra.get(n.nombre)!.join(", ")}` : ""}</span>
                  {onVerSalud && <button onClick={onVerSalud} className="font-medium text-info hover:underline">ver estado</button>}
                </li>
              ))}
            </ul>
          )}
      </div>
    </div>
  )
}

export function Red({ onVerDecisiones, onVerAtacante, onVerAprobaciones, onVerSalud }: {
  onVerDecisiones: (equipo: string | null, texto?: string) => void
  onVerAtacante?: (ip: string) => void
  onVerAprobaciones?: () => void
  onVerSalud?: () => void
}) {
  const red = useSondeo(getRed)
  const trazas = useSondeo(getTrazas)
  const wl = useSondeo(getWatchlist)
  const watchlist: WatchEntrada[] = Array.isArray(wl) ? wl : []
  const [sel, setSel] = useState<string | null>(null)
  const [capas, setCapas] = useState<Record<Capa, boolean>>({ ataques: true, cascada: true, dependencias: true })
  const [soloActividad, setSoloActividad] = useState(false)
  const [plegadas, setPlegadas] = useState<Set<string>>(new Set())
  const [busca, setBusca] = useState("")
  const trazasArr: Decision[] = Array.isArray(trazas) ? trazas : []
  const origenes = useMemo(() => origenesDe(Array.isArray(trazas) ? trazas : [], 4), [trazas])
  if (!red) return <Cargando />
  if ("error" in red) return <SinConexion />
  const nodo = red.nodos.find((n) => n.nombre === sel)
  // La ventana filtrada completa (hasta 500) para que las gráficas por dispositivo no queden
  // truncadas; la lista de eventos del panel ya acota su propio render.
  const eventos = nodo ? trazasArr.filter((d) => d.relaciones?.[nodo.nombre]).slice().reverse() : []
  const avisos = red.avisos ?? []
  // «solo con actividad» pliega las ramas en las que no ha pasado nada, además de las plegadas a mano.
  const quietas = soloActividad
    ? red.zonas.filter((z) => z.nodos.every((n) => red.nodos.find((x) => x.nombre === n)?.actividad.estado === "sin_actividad")).map((z) => z.nombre)
    : []
  const plegadasEfectivas = new Set([...plegadas, ...quietas])
  const plegar = (z: string) => setPlegadas((p) => { const q = new Set(p); if (q.has(z)) q.delete(z); else q.add(z); return q })
  // Buscar: con un único equipo que case por nombre o IP, se selecciona solo; Enter coge el primero.
  const coincide = (t: string) => red.nodos.filter((n) => t && (n.nombre.toLowerCase().includes(t) || (n.ip ?? "").includes(t)))
  const buscar = (t: string) => {
    setBusca(t)
    const c = coincide(t.trim().toLowerCase())
    if (c.length === 1) setSel(c[0].nombre)
  }
  return (
    <div className="space-y-3">
      {avisos.length > 0 && (
        <div role="status" className="rounded-md border border-aviso/40 bg-aviso/10 px-3 py-2 text-xs text-aviso">
          <p>El perfil tiene {avisos.length} {avisos.length === 1 ? "aviso" : "avisos"} en la sección red:</p>
          <ul className="list-disc pl-5">{avisos.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted-foreground">
        <input value={busca} onChange={(e) => buscar(e.target.value)} placeholder="Buscar equipo o IP…" aria-label="Buscar equipo o IP"
          onKeyDown={(e) => { if (e.key === "Enter") { const c = coincide(busca.trim().toLowerCase()); if (c[0]) setSel(c[0].nombre) } }}
          className="h-8 w-44 rounded-md border border-border bg-card px-2.5 text-xs text-foreground outline-none focus:border-ring" />
        <div role="group" aria-label="Capas del mapa" className="flex gap-1">
          {CAPAS.map((c) => (
            <button key={c.id} aria-pressed={capas[c.id]} onClick={() => setCapas((k) => ({ ...k, [c.id]: !k[c.id] }))}
              className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 transition-colors",
                capas[c.id] ? "border-primary/45 bg-primary/12 font-medium text-foreground" : "border-border hover:text-foreground")}>
              <span className={cn("inline-block w-3.5 border-t-2", c.cls)} />{c.nombre}
            </button>
          ))}
          <button aria-pressed={soloActividad} onClick={() => setSoloActividad((v) => !v)}
            className={cn("rounded-full border px-2.5 py-0.5 transition-colors", soloActividad ? "border-primary/45 bg-primary/12 font-medium text-foreground" : "border-border hover:text-foreground")}>
            solo con actividad
          </button>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-3">
          {Object.entries(ESTADO_VISUAL).map(([k, v]) => <span key={k}>{v.icono || "○"} {v.texto}</span>)}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="rounded-lg border border-border bg-card p-3">
          <MapaRed red={red} seleccionado={sel} onSeleccionar={setSel} dependencias={capas.dependencias} ataques={capas.ataques} cascada={capas.cascada}
            origenes={origenes} plegadas={plegadasEfectivas} onPlegar={plegar} onVerOrigen={onVerAtacante} />
        </div>
        {nodo
          ? <PanelEquipo nodo={nodo} eventos={eventos} todos={trazasArr} watchlist={watchlist}
              onVerDecisiones={() => onVerDecisiones(nodo.nombre)}
              onVerOrigen={(texto) => onVerDecisiones(null, texto)}
              onVerAtacante={onVerAtacante} />
          : <ResumenRed red={red} nOrigenes={origenes.total} onVerAprobaciones={onVerAprobaciones} onVerSalud={onVerSalud} />}
      </div>
    </div>
  )
}
