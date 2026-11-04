import { useEffect, useState, type ReactNode } from "react"
import { paginar, TAM_PAGINA, etiquetaClase } from "@/datos"
import { Paginador } from "@/components/Paginador"
import { useSondeo, getContenciones, getPausa, getTrazas, setPausa, revertirTodo, revertirUna, watchlistAgregar, type Decision } from "@/api"
import { AlertDialog } from "@/components/ui/alert-dialog"
import { useToast } from "@/components/ui/use-toast"
import { Cargando, SinConexion, Vacio } from "./bits"
import { OrigenBadges } from "./OrigenBadges"
import { edadTexto } from "@/alertas"
import {
  UMBRAL_VIEJA_MS, enriquecer, resumenContenciones, ordenarContenciones, agruparContenciones, serieIntentos,
  ORDENES_CONTENCION, AGRUPACIONES_CONTENCION, type ContencionVista, type OrdenContencion, type AgrupacionContencion,
} from "@/contenciones"
import { cn } from "@/lib/utils"

// #8 kill switch: contenciones activas (reconstruidas de la traza) + los dos interruptores de
// seguridad — pausa global de la automatización y retirada de contenciones. Cada contención se cruza
// con la traza para responder si está sirviendo (intentos parados después) y qué pasa si se quita.

const DIAS_VIEJA = Math.round(UMBRAL_VIEJA_MS / 86_400_000)
const COLOR_ACCION = ["bg-primary", "bg-violeta", "bg-aviso", "bg-enrutado", "bg-critico", "bg-ok"]
const tiempo = (msEdad: number) => (msEdad < 60_000 ? "hace un momento" : edadTexto(msEdad))
const fecha = (iso?: string | null) => {
  const t = iso ? new Date(iso) : null
  return t && !isNaN(t.getTime()) ? t.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—"
}
// Qué se contiene: la IP, cuenta o servicio; una acción sin parámetro (AISLAR_NODO) contiene el equipo entero.
const objetivoDe = (e: ContencionVista) => e.c.objetivo ?? e.c.ip ?? (e.c.nodo ? `${e.c.nodo} (equipo entero)` : "—")
// Qué vuelve a pasar si se revierte, según lo que contiene la acción.
function consecuencia(e: ContencionVista): string {
  const c = e.c, a = c.accion_id
  if (a.includes("AISLAR")) return `${c.nodo ?? c.activo ?? "el equipo"} vuelve a estar conectado a la red`
  if (a.includes("DESTINO")) return `la red vuelve a poder enviar tráfico a ${c.ip ?? objetivoDe(e)}`
  if (a.includes("BANDA")) return `el enlace de ${c.nodo ?? c.activo ?? "el equipo"} vuelve a su ancho de banda normal`
  if (c.usuario) return `la cuenta ${c.usuario} vuelve a poder entrar${c.activo ? ` en ${c.activo}` : ""}`
  if (c.servicio) return `el servicio ${c.servicio} vuelve a arrancarse${c.nodo ? ` en ${c.nodo}` : ""}`
  if (c.ip) return `${c.ip} vuelve a poder llegar${c.activo ? ` a ${c.activo}` : ""}`
  return `se deshace ${accionLegible(a).toLowerCase()} en ${c.nodo ?? "el equipo"}`
}

// «BLOQUEAR_IP» → «Bloquear IP»: el nombre del catálogo, legible.
const accionLegible = (a: string) => a.toLowerCase().split("_").map((w, i) => (["ip", "fw"].includes(w) ? w.toUpperCase() : i === 0 ? w[0].toUpperCase() + w.slice(1) : w)).join(" ")

function Boton({ children, tono = "normal", ...p }: { children: ReactNode; tono?: "pri" | "dan" | "normal" } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" {...p}
      className={cn("inline-flex h-8 items-center gap-1.5 rounded-[8px] border px-3 text-[13px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-45",
        tono === "pri" ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
          : tono === "dan" ? "border-critico/45 bg-card text-critico hover:bg-critico/10"
          : "border-border bg-card hover:bg-muted", p.className)}>
      {children}
    </button>
  )
}

function Seccion({ titulo, extra, children }: { titulo: string; extra?: ReactNode; children: ReactNode }) {
  return (
    <div className="border-b border-border px-4 py-3 last:border-b-0">
      <h4 className="mb-2 flex items-center justify-between gap-2 text-[11px] font-medium text-muted-foreground"><span>{titulo}</span>{extra}</h4>
      {children}
    </div>
  )
}

function Cifra({ k, children }: { k: string; children: ReactNode }) {
  return <div className="border-r border-border px-4 py-2"><div className="text-[11px] text-muted-foreground">{k}</div><div className="text-lg font-semibold tabular-nums">{children}</div></div>
}

function Decidio({ e }: { e: ContencionVista }) {
  const cls = e.decidio === "automática" ? "bg-ok/15 text-ok" : e.decidio === "vía escalada" ? "bg-violeta/15 text-violeta"
    : e.decidio === "—" ? "bg-muted text-muted-foreground" : "bg-aviso/15 text-aviso"
  return <span className={cn("shrink-0 rounded px-1.5 text-[11px] font-medium", cls)}>{e.decidio}</span>
}

// «¿Está sirviendo?»: intentos por hora del mismo origen, antes y después del bloqueo.
function Serie({ datos }: { datos: { n: number; despues: boolean }[] }) {
  if (!datos.some((d) => d.n > 0)) return null
  const max = Math.max(1, ...datos.map((d) => d.n))
  const w = 300 / datos.length
  const corte = datos.findIndex((d) => d.despues)
  return (
    <svg viewBox="0 0 300 44" className="mt-2 h-11 w-full" role="img" aria-label="Intentos por hora antes y después del bloqueo">
      {datos.map((d, i) => {
        const h = d.n ? Math.max(3, (d.n / max) * 34) : 0
        return <rect key={i} x={i * w + 3} y={38 - h} width={w - 6} height={h} rx={2} className={cn("fill-critico", d.despues ? "opacity-35" : "opacity-75")} />
      })}
      {corte > 0 && <><line x1={corte * w} y1={0} x2={corte * w} y2={40} className="stroke-primary" strokeDasharray="3 2" strokeWidth={1.5} />
        <text x={corte * w + 4} y={8} className="fill-muted-foreground text-[8px]">bloqueo</text></>}
    </svg>
  )
}

function Inspector({ e, trazas, ahora, onRevertir }: {
  e: ContencionVista; trazas: Decision[]; ahora: number; onRevertir: (vigilar: boolean) => void
}) {
  const c = e.c
  const serie = c.ip && e.intentos != null ? serieIntentos(trazas, c.ip, c.ts, ahora) : []
  const sirve = e.intentos == null ? null : e.intentos > 0
  return (
    <section aria-label="Contención" className="overflow-hidden rounded-lg border border-border bg-card text-sm lg:sticky lg:top-3">
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-base font-semibold">
          <span className={c.ip ? "font-mono" : ""}>{objetivoDe(e)}</span>
          {sirve === true && <span className="rounded bg-ok/15 px-1.5 text-[11px] font-medium text-ok">surte efecto</span>}
          {e.vieja && <span className="rounded bg-aviso/15 px-1.5 text-[11px] font-medium text-aviso">más de {DIAS_VIEJA} días</span>}
        </div>
        <div className="text-xs text-muted-foreground">
          {c.accion_id} en {c.nodo ?? "—"} {tiempo(e.edadMs)} ({fecha(c.ts)}){c.activo && ` · protege ${c.activo}`}
        </div>
      </div>

      {e.intentos != null && (
        <Seccion titulo="¿Está sirviendo?" extra={<span>desde el bloqueo</span>}>
          <div className={cn("rounded-md border px-3 py-2 text-[13px]", sirve ? "border-ok/30 bg-ok/5" : "border-border bg-muted")}>
            {sirve
              ? <><b className="font-semibold">{e.intentos} {e.intentos === 1 ? "intento parado" : "intentos parados"}</b> del mismo origen después del bloqueo; el último {e.ultimoIntento ? tiempo(ahora - Date.parse(e.ultimoIntento)) : "—"}. Sin el bloqueo habrían llegado{c.activo ? ` a ${c.activo}` : ""}.</>
              : <>Ningún intento del mismo origen desde el bloqueo en la traza reciente.{e.vieja ? " Es candidata a retirarse." : ""}</>}
          </div>
          <Serie datos={serie} />
        </Seccion>
      )}

      <Seccion titulo="Qué se aplicó y cómo se quita">
        <div className="grid grid-cols-[100px_1fr] items-center gap-x-2.5 gap-y-1.5 text-[13px]">
          <span className="text-muted-foreground">Acción</span><span><b className="font-semibold">{c.accion_id}</b> en {c.nodo ?? "—"}{c.via_escalada ? " · vía escalada" : ""}</span>
          <span className="text-muted-foreground">Regla</span>
          {c.regla ? <code className="overflow-x-auto rounded-[7px] border border-border bg-muted px-2.5 py-1.5 font-mono text-[11.5px] whitespace-pre">{c.regla}</code> : <span className="text-muted-foreground">—</span>}
          <span className="text-muted-foreground">Para quitarla</span>
          {c.reversion_cmd ? <code className="overflow-x-auto rounded-[7px] border border-border bg-muted px-2.5 py-1.5 font-mono text-[11.5px] whitespace-pre">{c.reversion_cmd}</code> : <span className="text-muted-foreground">—</span>}
        </div>
      </Seccion>

      <Seccion titulo="Por qué está" extra={<span className="font-mono">decisión {c.id_decision}</span>}>
        <div className="grid grid-cols-[100px_1fr] items-center gap-x-2.5 gap-y-1.5 text-[13px]">
          <span className="text-muted-foreground">Decidió</span>
          <span>{e.decidio}{e.clase && ` · ${etiquetaClase(e.clase)}`}{e.confianza != null && ` · confianza ${e.confianza}`}</span>
          {e.decision?.enriquecimiento_origen && <><span className="text-muted-foreground">Origen</span><span><OrigenBadges e={e.decision.enriquecimiento_origen} /></span></>}
        </div>
        {!e.decision && <p className="mt-1 text-xs text-muted-foreground">La decisión ya no está en la ventana de trazas que carga el visor.</p>}
      </Seccion>

      <div className="space-y-2 bg-muted px-4 py-3">
        <div className="rounded-[7px] border border-aviso/35 bg-aviso/10 px-3 py-2 text-[12.5px]">
          <b className="font-semibold">Si la reviertes</b>, {consecuencia(e)}.
          {sirve && e.ultimoIntento && <> Sigue intentándolo: lo último fue {tiempo(ahora - Date.parse(e.ultimoIntento))}.</>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Boton tono="dan" onClick={() => onRevertir(false)} disabled={c.indice == null}>Revertir…</Boton>
          {c.ip && <Boton onClick={() => onRevertir(true)} disabled={c.indice == null}>Revertir y vigilar…</Boton>}
        </div>
        {c.ip && <p className="text-[11.5px] text-muted-foreground">«Revertir y vigilar» la quita y añade la IP a la watchlist para que cualquier alerta nueva salte a la vista.</p>}
      </div>
    </section>
  )
}

type Confirmacion =
  | { tipo: "una"; e: ContencionVista; vigilar: boolean }
  | { tipo: "varias"; es: ContencionVista[]; titulo: string }
  | { tipo: "todas" }

export function Contenciones() {
  const toast = useToast()
  const c = useSondeo(getContenciones)
  const p = useSondeo(getPausa)
  const tr = useSondeo(getTrazas, 10000)
  const pausadaServidor = !!(p && !("error" in p) && p.pausada)
  const [pausaLocal, setPausaLocal] = useState<boolean | null>(null)   // optimista hasta que el sondeo confirma
  const pausada = pausaLocal ?? pausadaServidor
  useEffect(() => { if (pausaLocal !== null && pausaLocal === pausadaServidor) setPausaLocal(null) },
    [pausaLocal, pausadaServidor])
  const [ahora, setAhora] = useState(() => Date.now())
  useEffect(() => { const id = setInterval(() => setAhora(Date.now()), 30000); return () => clearInterval(id) }, [])
  const [confirmar, setConfirmar] = useState<Confirmacion | null>(null)
  const [escrito, setEscrito] = useState("")
  const [trabajando, setTrabajando] = useState(false)
  const [sel, setSel] = useState<Set<number>>(new Set())
  const [actual, setActual] = useState<number | null>(null)
  const [filtro, setFiltro] = useState<string>("todas")
  const [orden, setOrden] = useState<OrdenContencion>("reciente")
  const [agrupacion, setAgrupacion] = useState<AgrupacionContencion>("donde")
  const [pagina, setPagina] = useState(1)
  const [tam, setTam] = useState(TAM_PAGINA)
  const elegirTam = (t: number) => { setTam(t); setPagina(1) }

  const activasCrudas = c && !("error" in c) ? c : []
  const trazas: Decision[] = Array.isArray(tr) ? tr : []
  const todas = enriquecer(activasCrudas, trazas, ahora)
  const r = resumenContenciones(todas)
  const filtradas = todas.filter((e) => filtro === "todas" || (filtro === "viejas" ? e.vieja : e.c.accion_id === filtro))
  const grupos = agruparContenciones(ordenarContenciones(filtradas, orden), agrupacion)
  type Entrada = { g: (typeof grupos)[number]; e: ContencionVista }
  const entradas = grupos.flatMap<Entrada>((g) => g.items.map((e) => ({ g, e })))
  const pag = paginar(entradas, pagina, tam)
  const elegida = filtradas.find((e) => e.c.indice === actual) ?? entradas[0]?.e ?? null
  const elegidas = filtradas.filter((e) => e.c.indice != null && sel.has(e.c.indice))
  const viejas = todas.filter((e) => e.vieja)
  const alternar = (i: number | null | undefined, v: boolean) => {
    if (i == null) return
    setSel((s) => { const n = new Set(s); if (v) n.add(i); else n.delete(i); return n })
  }

  const alternarPausa = async () => { const nuevo = !pausada; if (await setPausa(nuevo)) setPausaLocal(nuevo) }
  const abrir = (k: Confirmacion) => { setEscrito(""); setConfirmar(k) }

  async function revertirVarias(es: ContencionVista[]) {
    let ok = 0, mal = 0
    for (const e of es) {
      if (e.c.indice == null) { mal++; continue }
      const res = await revertirUna(e.c.indice)
      if (res?.revertida) ok++; else mal++
    }
    return { ok, mal }
  }
  async function ejecutar(k: Confirmacion) {
    setTrabajando(true)
    try {
      if (k.tipo === "todas") {
        const res = await revertirTodo()
        toast(res ? { type: res.fallidas ? "error" : "success", title: `Revertidas ${res.revertidas}${res.fallidas ? ` · ${res.fallidas} fallidas` : ""}` }
                  : { type: "error", title: "No se pudo revertir" })
      } else if (k.tipo === "varias") {
        const { ok, mal } = await revertirVarias(k.es)
        toast({ type: mal ? "error" : "success", title: `Revertidas ${ok}${mal ? ` · ${mal} sin revertir` : ""}` })
        setSel(new Set())
      } else {
        const res = k.e.c.indice != null ? await revertirUna(k.e.c.indice) : null
        if (!res?.revertida) { toast({ type: "error", title: "No se pudo revertir esa contención" }); return }
        if (k.vigilar && k.e.c.ip) await watchlistAgregar(k.e.c.ip, `revertida la contención ${k.e.c.accion_id} (${k.e.c.id_decision})`)
        toast({ type: "success", title: k.vigilar ? "Contención revertida y origen en vigilancia" : "Contención revertida" })
      }
    } finally {
      setTrabajando(false)
    }
  }

  if (!c) return <Cargando />
  if ("error" in c) return <SinConexion causa={c.causa} />

  const etiquetaFiltro = (id: string) => id === "todas" ? "Todas" : id === "viejas" ? `Más de ${DIAS_VIEJA} días` : accionLegible(id)
  const filtros: [string, number][] = [["todas", r.activas], ...r.porAccion, ...(r.viejas ? [["viejas", r.viejas] as [string, number]] : [])]
  const numeroPedido = confirmar?.tipo === "todas" ? String(r.activas) : confirmar?.tipo === "varias" ? String(confirmar.es.length) : null

  return (
    <div className="space-y-3">
      {/* panel de control: los dos interruptores de seguridad y el resumen */}
      <div className="overflow-hidden rounded-lg border border-border bg-card text-sm">
        <div className="grid lg:grid-cols-[1.2fr_1fr]">
          <div className="space-y-2 border-b border-border px-4 py-3.5 lg:border-b-0 lg:border-r">
            <div className="text-[11px] text-muted-foreground">Automatización</div>
            <div className="flex items-center gap-3">
              <button type="button" onClick={alternarPausa} aria-label={pausada ? "Reanudar automatización" : "Pausar automatización"}
                className={cn("relative h-6 w-[42px] shrink-0 rounded-full transition-colors", pausada ? "bg-critico" : "bg-ok")}>
                <span className={cn("absolute top-[3px] size-[18px] rounded-full bg-white transition-all", pausada ? "left-[3px]" : "left-[21px]")} />
              </button>
              <span>{pausada
                ? <><b className="font-semibold text-critico">En pausa</b> · toda contención nueva espera a un analista</>
                : <><b className="font-semibold">Activa</b> · el MDR contiene solo lo que la política permite en automático</>}</span>
            </div>
            <p className="text-xs text-muted-foreground">Pausarla no retira las contenciones que ya están puestas.</p>
          </div>
          <div className="space-y-2 px-4 py-3.5">
            <div className="text-[11px] text-muted-foreground">Retirar contenciones</div>
            <div className="flex flex-wrap gap-2">
              <Boton tono="dan" onClick={() => abrir({ tipo: "todas" })} disabled={!r.activas || trabajando}>Revertir todas ({r.activas})…</Boton>
              <Boton onClick={() => abrir({ tipo: "varias", es: viejas, titulo: `las de más de ${DIAS_VIEJA} días` })} disabled={!viejas.length || trabajando}>
                Revertir las de más de {DIAS_VIEJA} días ({viejas.length})…</Boton>
            </div>
            <p className="text-xs text-muted-foreground">{trabajando ? "Revirtiendo…" : "Pide escribir el número de contenciones para confirmar. Queda en la traza con tu operador."}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 border-t border-border sm:grid-cols-5">
          <Cifra k="Activas">{r.activas} <small className="text-xs font-normal text-muted-foreground">+{r.hoy} en 24 h</small></Cifra>
          <Cifra k="En el borde / en equipos">{r.enBorde} <small className="text-xs font-normal text-muted-foreground">/ {r.enEquipos}</small></Cifra>
          <Cifra k="Más antigua">{r.masAntigua ? <>{edadTexto(r.masAntigua.edadMs).replace("hace ", "")} <small className="text-xs font-normal text-muted-foreground">{r.masAntigua.activo}</small></> : "—"}</Cifra>
          <Cifra k="Siguen intentándolo"><span className={r.insisten ? "text-critico" : ""}>{r.insisten} <small className="text-xs font-normal text-muted-foreground">orígenes que insisten</small></span></Cifra>
          <div className="px-4 py-2">
            <div className="text-[11px] text-muted-foreground">Por acción</div>
            <div className="mt-1.5 flex h-1.5 gap-0.5 overflow-hidden rounded-sm" title={r.porAccion.map(([a, n]) => `${a} ${n}`).join(" · ")}>
              {r.porAccion.map(([a, n], i) => <span key={a} className={COLOR_ACCION[i % COLOR_ACCION.length]} style={{ width: `${(n / Math.max(1, r.activas)) * 100}%` }} />)}
            </div>
            <div className="mt-1 text-[11px] leading-tight text-muted-foreground">{r.porAccion.map(([a, n]) => `${accionLegible(a)} ${n}`).join(" · ") || "—"}</div>
          </div>
        </div>
      </div>

      {!r.activas ? <Vacio>No hay contenciones activas. Nada bloqueado ahora mismo.</Vacio> : (
        <>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <div role="group" aria-label="Filtrar contenciones" className="flex flex-wrap gap-1">
              {filtros.map(([id, n]) => (
                <button key={id} aria-pressed={filtro === id} onClick={() => { setFiltro(id); setPagina(1) }}
                  className={cn("rounded-full border px-2.5 py-0.5 transition-colors",
                    filtro === id ? "border-primary/45 bg-primary/12 font-medium text-foreground" : "border-border text-muted-foreground hover:text-foreground")}>
                  {etiquetaFiltro(id)} <span className="tabular-nums">{n}</span>
                </button>
              ))}
            </div>
            <span className="ml-auto flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-1.5 text-muted-foreground">Ordenar
                <select aria-label="Ordenar contenciones" value={orden} onChange={(x) => { setOrden(x.target.value as OrdenContencion); setPagina(1) }}
                  className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground">
                  {ORDENES_CONTENCION.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}
                </select>
              </label>
              <label className="flex items-center gap-1.5 text-muted-foreground">Agrupar
                <select aria-label="Agrupar contenciones" value={agrupacion} onChange={(x) => { setAgrupacion(x.target.value as AgrupacionContencion); setPagina(1) }}
                  className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground">
                  {AGRUPACIONES_CONTENCION.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
                </select>
              </label>
            </span>
          </div>

          <div className="grid items-start gap-3.5 lg:grid-cols-[minmax(0,1.3fr)_minmax(360px,1fr)]">
            <div className="space-y-3">
              <div className="rounded-lg border border-border bg-card [&>*:first-child>div:first-child]:rounded-t-lg [&>*:last-child]:rounded-b-lg">
                {pag.filas.map(({ g, e }, n) => {
                  const nuevo = n === 0 || pag.filas[n - 1].g.clave !== g.clave
                  const todasSel = g.items.every((x) => x.c.indice != null && sel.has(x.c.indice))
                  const activa = elegida?.c.indice === e.c.indice && elegida?.c.id_decision === e.c.id_decision
                  return (
                    <div key={`${e.c.id_decision}:${e.c.objetivo}:${e.c.nodo}:${e.c.indice}`}>
                      {nuevo && g.cabecera && (
                        <div className="flex items-center gap-2 border-b border-border bg-muted px-3.5 py-1.5 text-[11px] text-muted-foreground">
                          <span className="flex-1 truncate">{g.etiqueta} · {g.items.length} {g.items.length === 1 ? "contención" : "contenciones"}</span>
                          {g.items.length > 1 && (
                            <button onClick={() => setSel((s) => { const m = new Set(s); for (const x of g.items) if (x.c.indice != null) { if (todasSel) m.delete(x.c.indice); else m.add(x.c.indice) } return m })}
                              className="font-medium text-info hover:underline">{todasSel ? "quitar las" : "seleccionar las"} {g.items.length}</button>
                          )}
                        </div>
                      )}
                      <div data-contencion={e.c.indice ?? ""} className={cn("grid grid-cols-[14px_minmax(0,1fr)] items-center gap-x-2.5 border-b border-border py-2 pl-3 pr-3.5",
                        activa && "bg-primary/10 shadow-[inset_3px_0_0_var(--primary)]")}>
                        <input type="checkbox" aria-label="Seleccionar" checked={e.c.indice != null && sel.has(e.c.indice)} disabled={e.c.indice == null}
                          onChange={(x) => alternar(e.c.indice, x.target.checked)} className="size-3.5 accent-[var(--primary)]" />
                        <button type="button" onClick={() => setActual(e.c.indice ?? null)} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-left text-[13px]">
                          <span className="min-w-0">
                            <span className="flex items-center gap-1.5 overflow-hidden whitespace-nowrap">
                              <b className={cn("font-semibold", e.c.ip && "font-mono")}>{objetivoDe(e)}</b>
                              {e.pais && <span className="text-muted-foreground">{e.pais}</span>}
                              <span className="text-muted-foreground/60">·</span><span>{e.c.accion_id}</span>
                              {e.c.activo && <><span className="text-muted-foreground/60">·</span><span className="truncate text-muted-foreground">protege {e.c.activo}</span></>}
                              <Decidio e={e} />
                            </span>
                            <span className="block truncate text-[11.5px] text-muted-foreground">
                              {[e.clase ? etiquetaClase(e.clase) : null, `en ${e.c.nodo ?? "—"}`, `decisión ${e.c.id_decision}`].filter(Boolean).join(" · ")}
                            </span>
                          </span>
                          <span className="flex flex-col items-end gap-0.5 text-[11px] tabular-nums">
                            <span className={e.vieja ? "font-semibold text-aviso" : "text-muted-foreground"}>{tiempo(e.edadMs)}</span>
                            {e.intentos == null ? <span className="text-muted-foreground">—</span>
                              : e.intentos > 0 ? <span className="font-medium text-ok">{e.intentos} {e.intentos === 1 ? "intento parado" : "intentos parados"}</span>
                              : <span className="text-muted-foreground">sin intentos</span>}
                          </span>
                        </button>
                      </div>
                    </div>
                  )
                })}
                {elegidas.length > 0 && (
                  <div role="region" aria-label="Selección" className="sticky bottom-0 z-10 flex flex-wrap items-center gap-2.5 border-t border-border bg-[color-mix(in_srgb,var(--primary)_7%,var(--card))] px-3.5 py-2.5 text-[12.5px]">
                    <b className="font-semibold">{elegidas.length} {elegidas.length === 1 ? "seleccionada" : "seleccionadas"}</b>
                    <span className="ml-auto flex items-center gap-2">
                      <Boton tono="dan" className="h-7 text-xs" onClick={() => abrir({ tipo: "varias", es: elegidas, titulo: "las seleccionadas" })} disabled={trabajando}>
                        Revertir {elegidas.length === 1 ? "la seleccionada" : `las ${elegidas.length}`}…</Boton>
                      <button onClick={() => setSel(new Set())} className="text-muted-foreground hover:underline">quitar selección</button>
                    </span>
                  </div>
                )}
              </div>
              <Paginador pagina={pag.pagina} paginas={pag.paginas} total={pag.total} tam={tam} onPagina={setPagina} onTam={elegirTam} />
            </div>
            {elegida
              ? <Inspector key={`${elegida.c.id_decision}:${elegida.c.indice}`} e={elegida} trazas={trazas} ahora={ahora}
                  onRevertir={(vigilar) => abrir({ tipo: "una", e: elegida, vigilar })} />
              : <div className="rounded-lg border border-dashed border-border bg-card px-4 py-5 text-sm text-muted-foreground">Ninguna contención con este filtro.</div>}
          </div>
        </>
      )}

      <AlertDialog open={confirmar !== null} onOpenChange={(o) => { if (!o) setConfirmar(null) }}
        title={confirmar?.tipo === "todas" ? `¿Revertir las ${r.activas} contenciones activas?`
          : confirmar?.tipo === "varias" ? `¿Revertir ${confirmar.titulo} (${confirmar.es.length})?`
          : confirmar ? `¿Revertir la contención sobre ${objetivoDe(confirmar.e)}?` : ""}
        description={confirmar?.tipo === "una"
          ? `Se ejecuta la reversión en ${confirmar.e.c.nodo ?? "el equipo"}${confirmar.vigilar ? " y el origen pasa a la watchlist" : ""}.`
          : "Cada reversión se ejecuta en su equipo y queda en la traza con tu operador. Los orígenes que siguen intentándolo volverán a llegar."}
        confirmLabel={confirmar?.tipo === "todas" ? "Revertir todas" : confirmar?.tipo === "varias" ? "Revertir" : confirmar?.vigilar ? "Revertir y vigilar" : "Revertir"}
        confirmDisabled={numeroPedido !== null && escrito.trim() !== numeroPedido}
        onConfirm={() => { if (confirmar) ejecutar(confirmar) }}>
        {numeroPedido !== null && (
          <label className="block space-y-1">
            <span className="text-xs text-muted-foreground">Escribe <b className="text-foreground">{numeroPedido}</b> para confirmar</span>
            <input aria-label="Número de contenciones a revertir" value={escrito} onChange={(x) => setEscrito(x.target.value)} inputMode="numeric"
              className="h-8 w-28 rounded-[7px] border border-border bg-card px-2.5 text-sm outline-none focus:border-ring" />
          </label>
        )}
      </AlertDialog>
    </div>
  )
}
