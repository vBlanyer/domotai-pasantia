import { useEffect, useState, type ReactNode } from "react"
import { useSondeo, getTrazas, getContenciones, operadorActual, type Decision } from "@/api"
import { Cargando, SinConexion, Vacio, Prioridad } from "@/components/bits"
import { eventosDeEntidad, claveIncidenteDe, paginar, TAM_PAGINA } from "@/datos"
import { Paginador } from "@/components/Paginador"
import { LineaTiempo } from "@/components/LineaTiempo"
import { PanelCaso, ESTADO_CASO } from "@/components/PanelCaso"
import { edadTexto } from "@/alertas"
import {
  incidentesDe, resumenIncidentes, pasaFiltroIncidente, ordenarIncidentes, historiaDe, duracion,
  FILTROS_INCIDENTE, ORDENES_INCIDENTE, type FiltroIncidente, type OrdenIncidente, type IncidenteVista,
} from "@/incidentes"
import { cn } from "@/lib/utils"

// Vista «Incidentes»: gestión de casos. Cada incidente es una campaña de origen /24 (las IPs rotadas
// de un mismo atacante = una sola historia) con su caso (estado, responsable, notas). La lista arranca
// en los abiertos; el caso se abre a la derecha, sin navegar a otra página.

const TONO_SEV = ["bg-muted-foreground/40", "bg-info", "bg-aviso", "bg-critico"]
const iniciales = (n: string) => n.split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase()
const MAX_CRONO = 6

function Avatar({ nombre }: { nombre: string | null }) {
  return nombre
    ? <span className="inline-flex items-center gap-1.5 text-[11.5px]"><span className="grid size-[18px] place-items-center rounded-full bg-primary/20 text-[10px] font-semibold text-primary">{iniciales(nombre)}</span>{nombre}</span>
    : <span className="inline-flex items-center gap-1.5 text-[11.5px] text-muted-foreground"><span className="grid size-[18px] place-items-center rounded-full border border-dashed border-border bg-muted text-[10px]">?</span>sin asignar</span>
}

function Vivo() {
  return <span title="activo ahora: atacó en la última hora" className="inline-block size-2 shrink-0 rounded-full bg-critico motion-safe:animate-pulse" />
}

function Seccion({ titulo, extra, children }: { titulo: string; extra?: ReactNode; children: ReactNode }) {
  return (
    <div className="border-b border-border px-4 py-3 last:border-b-0">
      <h4 className="mb-2 flex items-center justify-between gap-2 text-[11px] font-medium text-muted-foreground"><span>{titulo}</span>{extra}</h4>
      {children}
    </div>
  )
}

function Cifra({ k, v, sub, cls }: { k: string; v: number; sub?: string; cls?: string }) {
  return (
    <div className="border-r border-border px-3.5 py-2 last:border-r-0">
      <div className="text-[11px] text-muted-foreground">{k}</div>
      <div className={cn("text-lg font-semibold tabular-nums", cls)}>{v} {sub && <small className="text-xs font-normal text-muted-foreground">{sub}</small>}</div>
    </div>
  )
}

function Caso({ e, regs, ahora, bloqueos, onVerDecisiones, onVerRed, onVerAtacante, onVerContenciones }: {
  e: IncidenteVista; regs: Decision[]; ahora: number; bloqueos: number
  onVerDecisiones?: (prefijo: string) => void; onVerRed?: () => void; onVerAtacante?: (ip: string) => void; onVerContenciones?: () => void
}) {
  const [todo, setTodo] = useState(false)
  // decisiones del /24 + sus reversiones y notas de caso por decisión + las del caso del INCIDENTE
  const eventos = [...eventosDeEntidad(regs, (d) => claveIncidenteDe(d.origen_ip) === e.clave),
                   ...regs.filter((d) => d.tipo === "actualizacion_caso" && d.id_decision === e.clave)]
  const ipEjemplo = regs.find((d) => claveIncidenteDe(d.origen_ip) === e.clave && d.origen_ip)?.origen_ip
  const max = Math.max(1, ...e.objetivos.map((o) => o.n))
  const estado = ESTADO_CASO[e.caso.estado] ?? ESTADO_CASO.nuevo
  return (
    <section aria-label="Incidente" className="overflow-hidden rounded-lg border border-border bg-card text-sm lg:sticky lg:top-3">
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-base font-semibold">
          <span className="font-mono">{e.cidr}</span>
          <Prioridad n={e.prioridad || null} />
          <span className={cn("rounded px-1.5 text-[11px] font-medium", estado.clase)}>{estado.texto}</span>
          {e.activo && <Vivo />}
        </div>
        <div className="text-xs text-muted-foreground">
          {[e.pais, e.alcance, e.caso.asignado ? `lo lleva ${e.caso.asignado}` : "sin asignar"].filter(Boolean).join(" · ")}
        </div>
      </div>

      <Seccion titulo="Historia del ataque">
        <p className="text-[13.5px] leading-relaxed">{historiaDe(e, ahora)}</p>
        <div className="mt-2.5 grid grid-cols-4 overflow-hidden rounded-md border border-border text-center">
          {([["IPs", e.ips, ""], ["Decisiones", e.n, ""], ["Contenidas", e.contenidas, "text-ok"], ["Bloqueos activos", bloqueos, ""]] as const).map(([k, v, cls]) => (
            <div key={k} className="border-r border-border px-1.5 py-1.5 last:border-r-0">
              <div className="text-[10.5px] text-muted-foreground">{k}</div><div className={cn("text-base font-semibold tabular-nums", cls)}>{v}</div>
            </div>
          ))}
        </div>
      </Seccion>

      {e.objetivos.length > 0 && (
        <Seccion titulo="Contra qué equipos" extra={<span>contenido / sin contener</span>}>
          <ul aria-label="Equipos atacados" className="space-y-1.5">
            {e.objetivos.map((o) => (
              <li key={o.equipo} className="grid grid-cols-[100px_1fr_30px] items-center gap-2 text-[11.5px]">
                <span className="truncate text-muted-foreground">{o.equipo}</span>
                <span className="flex h-2 overflow-hidden rounded-sm bg-muted">
                  <span className="h-full bg-ok" style={{ width: `${(o.contenidas / max) * 100}%` }} />
                  <span className="h-full bg-critico" style={{ width: `${((o.n - o.contenidas) / max) * 100}%` }} />
                </span>
                <span className="text-right font-medium tabular-nums">{o.n}</span>
              </li>
            ))}
          </ul>
        </Seccion>
      )}

      <Seccion titulo="Cronología" extra={eventos.length > MAX_CRONO
        ? <button onClick={() => setTodo((v) => !v)} className="font-medium text-info hover:underline">{todo ? "ver solo las últimas" : `ver toda (${eventos.length})`}</button>
        : null}>
        <LineaTiempo regs={eventos} max={todo ? undefined : MAX_CRONO} />
      </Seccion>

      <Seccion titulo="Gestión" extra={<span>cada cambio queda en la traza</span>}>
        <PanelCaso key={e.clave} idDecision={e.clave} sinMarco />
      </Seccion>

      <div className="flex flex-wrap gap-3 bg-muted px-4 py-3 text-xs font-medium">
        {onVerDecisiones && <button onClick={() => onVerDecisiones(e.prefijo)} className="text-info hover:underline">Ver las decisiones del bloque</button>}
        {onVerRed && <button onClick={onVerRed} className="text-info hover:underline">Ver en Red</button>}
        {onVerAtacante && ipEjemplo && <button onClick={() => onVerAtacante(ipEjemplo)} className="text-info hover:underline">Perfil del atacante</button>}
        {onVerContenciones && bloqueos > 0 && <button onClick={onVerContenciones} className="text-info hover:underline">Sus contenciones</button>}
      </div>
    </section>
  )
}

export function Incidentes({ claveInicial = null, onVerDecisiones, onVerRed, onVerAtacante, onVerContenciones }: {
  claveInicial?: string | null; onVerDecisiones?: (prefijo: string) => void; onVerRed?: () => void
  onVerAtacante?: (ip: string) => void; onVerContenciones?: () => void
} = {}) {
  const t = useSondeo(getTrazas)
  const c = useSondeo(getContenciones, 10000)
  // Llegando desde otra vista se abre ese incidente: cada salto vuelve a montar la vista, así que basta
  // con el valor inicial.
  const [actual, setActual] = useState<string | null>(claveInicial)
  const [filtro, setFiltro] = useState<FiltroIncidente>("abiertos")
  const [mios, setMios] = useState(false)
  const [orden, setOrden] = useState<OrdenIncidente>("reciente")
  const [busca, setBusca] = useState("")
  const [ahora, setAhora] = useState(() => Date.now())
  useEffect(() => { const id = setInterval(() => setAhora(Date.now()), 30000); return () => clearInterval(id) }, [])
  const [pagina, setPagina] = useState(1)
  const [tam, setTam] = useState(TAM_PAGINA)
  const elegirTam = (n: number) => { setTam(n); setPagina(1) }
  if (!t) return <Cargando />
  const fallo = "error" in t ? t : null
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />
  const regs: Decision[] = fallo ? (fallo.datos ?? []) : (t as Decision[])
  const todos = incidentesDe(regs, ahora)
  if (todos.length === 0) return <Vacio>Sin incidentes: no hay ataques agrupables por campaña todavía.</Vacio>
  const yo = operadorActual().trim()
  const r = resumenIncidentes(todos, yo)
  const q = busca.trim().toLowerCase()
  const coincide = (e: IncidenteVista) => !q || e.cidr.includes(q) || (e.pais ?? "").toLowerCase().includes(q)
    || e.objetivos.some((o) => o.equipo.toLowerCase().includes(q))
    || regs.some((d) => d.origen_ip?.includes(q) && claveIncidenteDe(d.origen_ip) === e.clave)
  // Con un incidente pedido desde otra vista, se muestra aunque el filtro por defecto lo ocultara.
  const visibles = ordenarIncidentes(todos.filter((e) => (pasaFiltroIncidente(e, filtro, mios ? yo : "") && coincide(e)) || e.clave === claveInicial), orden)
  const pag = paginar(visibles, pagina, tam)
  const elegido = visibles.find((e) => e.clave === actual) ?? visibles[0] ?? null
  const contenciones = Array.isArray(c) ? c : []
  const bloqueosDe = (e: IncidenteVista) => contenciones.filter((x) => (x.ip ?? "").startsWith(e.prefijo)).length
  const cuenta: Record<FiltroIncidente, number> = { abiertos: r.abiertos, nuevos: r.nuevos, en_revision: r.enRevision, resueltos: r.resueltos, todos: r.total }
  const cambiar = (f: () => void) => { f(); setPagina(1) }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-border bg-card sm:grid-cols-5">
        <Cifra k="Abiertos" v={r.abiertos} sub={`de ${r.total}`} />
        <Cifra k="Sin asignar" v={r.sinAsignar} sub="nadie los lleva" cls={r.sinAsignar ? "text-aviso" : undefined} />
        <Cifra k="Activos ahora" v={r.activos} sub="atacaron en la última hora" cls={r.activos ? "text-critico" : undefined} />
        <Cifra k="En revisión" v={r.enRevision} sub={yo ? `${r.mios} tuyos` : undefined} />
        <Cifra k="Resueltos" v={r.resueltos} sub="en la ventana" cls={r.resueltos ? "text-ok" : undefined} />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <input value={busca} onChange={(x) => cambiar(() => setBusca(x.target.value))} placeholder="Buscar bloque, IP, equipo…" aria-label="Buscar incidentes"
          className="h-8 w-48 rounded-md border border-border bg-card px-2.5 text-xs outline-none focus:border-ring" />
        <div role="group" aria-label="Filtrar por estado del caso" className="flex flex-wrap gap-1">
          {FILTROS_INCIDENTE.map((f) => (
            <button key={f.id} aria-pressed={filtro === f.id} onClick={() => cambiar(() => setFiltro(f.id))}
              className={cn("rounded-full border px-2.5 py-0.5 transition-colors", filtro === f.id ? "border-primary/45 bg-primary/12 font-medium text-foreground" : "border-border text-muted-foreground hover:text-foreground")}>
              {f.nombre} <span className="tabular-nums">{cuenta[f.id]}</span>
            </button>
          ))}
          <button aria-pressed={mios} disabled={!yo} onClick={() => cambiar(() => setMios((v) => !v))}
            title={yo ? undefined : "Escribe tu nombre de operador (en Aprobaciones o Decisiones) para activarlo"}
            className={cn("rounded-full border px-2.5 py-0.5 transition-colors disabled:opacity-45", mios ? "border-primary/45 bg-primary/12 font-medium text-foreground" : "border-border text-muted-foreground hover:text-foreground")}>
            Solo míos
          </button>
        </div>
        <label className="ml-auto flex items-center gap-1.5 text-muted-foreground">Ordenar
          <select aria-label="Ordenar incidentes" value={orden} onChange={(x) => cambiar(() => setOrden(x.target.value as OrdenIncidente))}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground">
            {ORDENES_INCIDENTE.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}
          </select>
        </label>
      </div>

      <div className="grid items-start gap-3.5 lg:grid-cols-[minmax(0,1.2fr)_minmax(390px,1fr)]">
        <div className="space-y-3">
          <ul aria-label="Incidentes" className="overflow-hidden rounded-lg border border-border bg-card">
            {visibles.length === 0 && <li className="px-4 py-6 text-sm text-muted-foreground">Ningún incidente con este filtro.</li>}
            {pag.filas.map((e) => {
              const est = ESTADO_CASO[e.caso.estado] ?? ESTADO_CASO.nuevo
              const ultimaNota = e.caso.estado === "resuelto" ? e.caso.notas[e.caso.notas.length - 1]?.texto : null
              const activa = elegido?.clave === e.clave
              return (
                <li key={e.clave} data-incidente={e.clave}>
                  <button type="button" onClick={() => setActual(e.clave)} aria-current={activa}
                    className={cn("grid w-full grid-cols-[4px_minmax(0,1fr)_auto] items-center gap-3 border-b border-border py-2.5 pl-2.5 pr-3.5 text-left text-[13px] hover:bg-muted/50",
                      activa && "bg-primary/10 shadow-[inset_3px_0_0_var(--primary)]", e.caso.estado === "resuelto" && !activa && "opacity-60")}>
                    <span className={cn("self-stretch rounded-sm", TONO_SEV[Math.max(0, Math.min(3, e.prioridad - 1))])} />
                    <span className="min-w-0">
                      <span className="flex items-center gap-1.5 overflow-hidden whitespace-nowrap">
                        {e.activo && <Vivo />}
                        <b className="font-mono font-semibold">{e.cidr}</b>
                        {(e.pais ?? e.alcance) && <span className="text-muted-foreground">{e.pais ?? e.alcance}</span>}
                        <span className={cn("shrink-0 rounded px-1.5 text-[11px] font-medium", est.clase)}>{est.texto}</span>
                      </span>
                      <span className="block truncate text-[11.5px] text-muted-foreground">
                        {ultimaNota ? `cerrado: «${ultimaNota}»`
                          : `${e.ips} ${e.ips === 1 ? "IP" : "IPs"} · ${e.n} ${e.n === 1 ? "decisión" : "decisiones"} · ${e.objetivos.slice(0, 3).map((o) => o.equipo).join(", ")}${e.objetivos.length > 3 ? ` +${e.objetivos.length - 3}` : ""} · durante ${duracion(e)}`}
                      </span>
                    </span>
                    <span className="flex flex-col items-end gap-1 text-[11px]">
                      <Avatar nombre={e.caso.asignado} />
                      <span className={e.activo ? "font-medium text-critico" : "text-muted-foreground"}>{e.ultima ? edadTexto(ahora - Date.parse(e.ultima)) : "—"}</span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
          <Paginador pagina={pag.pagina} paginas={pag.paginas} total={pag.total} tam={tam} onPagina={setPagina} onTam={elegirTam} />
        </div>
        {elegido
          ? <Caso key={elegido.clave} e={elegido} regs={regs} ahora={ahora} bloqueos={bloqueosDe(elegido)}
              onVerDecisiones={onVerDecisiones} onVerRed={onVerRed} onVerAtacante={onVerAtacante} onVerContenciones={onVerContenciones} />
          : <div className="rounded-lg border border-dashed border-border bg-card px-4 py-5 text-sm text-muted-foreground">Ningún incidente con este filtro.</div>}
      </div>
    </div>
  )
}
