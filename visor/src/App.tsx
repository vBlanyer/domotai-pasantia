import { useState, useEffect, useMemo, useRef, useCallback, type ComponentType } from "react"
import {
  Moon, Sun, Menu, Bell, BellOff, Pause, PanelLeftClose, PanelLeftOpen,
  LayoutDashboard, SquareTerminal, ListChecks, Shield, List, TriangleAlert, Network, MapPin, Eye, ScrollText,
  ChartBar, SlidersHorizontal, Activity, KeyRound,
} from "lucide-react"
import {
  useSondeo, getSalud, getPendientes, getPausa, getContenciones, getTrazas, tokenActual, listaConocida, comprobarSesion,
  iniciarSesion, cerrarSesion, sesionActual, operadorActual, EVENTO_NO_AUTORIZADO, type Pendiente, type Sesion, type ModoSesion,
} from "@/api"
import { Acceso, Reautenticar, ChipSesion, BandaAbierta, type Motivo, type Entrada as EntradaSesion } from "@/components/Acceso"
import { campanasDe, estadoDeCasos, claveDeCampana } from "@/datos"
import { cn } from "@/lib/utils"
import { tituloConPendientes, nuevosPendientes, textoAviso } from "@/alertas"
import { useTema } from "@/tema"
import { Dashboard } from "@/components/Dashboard"
import { Metricas } from "@/components/Metricas"
import { Salud } from "@/components/Salud"
import { Red } from "@/components/Red"
import { Ubicaciones } from "@/components/Ubicaciones"
import { PerfilAtacante } from "@/components/PerfilAtacante"
import { Watchlist } from "@/components/Watchlist"
import { Decisiones } from "@/components/Decisiones"
import { Aprobaciones } from "@/components/Aprobaciones"
import { Consola } from "@/components/Consola"
import { Trazas } from "@/components/Trazas"
import { Contenciones } from "@/components/Contenciones"
import { Politicas } from "@/components/Politicas"
import { Conectividad } from "@/components/Conectividad"
import { Incidentes } from "@/components/Incidentes"
import { VistaIncidente } from "@/components/VistaIncidente"
import { Punto } from "@/components/bits"
import type { Decision } from "@/api"

type Vista = "panel" | "metricas" | "salud" | "red" | "ubicaciones" | "incidentes" | "decisiones" | "aprobaciones" | "consola" | "trazas" | "contenciones" | "watchlist" | "politicas" | "conectividad" | "incidente" | "atacante"

// Un pitido corto (WebAudio, sin fichero) cuando entra una decisión nueva. Best-effort: si el
// navegador no lo permite, se ignora en silencio.
function pitido() {
  try {
    const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AC) return
    const ctx = new AC()
    const o = ctx.createOscillator(), g = ctx.createGain()
    o.connect(g); g.connect(ctx.destination)
    o.frequency.value = 880; g.gain.value = 0.04
    o.start(); o.stop(ctx.currentTime + 0.15)
    o.onended = () => ctx.close()
  } catch { /* sin audio: no pasa nada */ }
}

function leerAvisos(): boolean {
  try { return localStorage.getItem("mdr.avisos") === "1" } catch { return false }
}

// Alterna el aviso al analista; al activarlo pide permiso de notificación del navegador (gesto del
// usuario). Todo local: la notificación la emite el SO del analista, no sale nada a ningún servidor.
async function alternarAvisos(actual: boolean, set: (b: boolean) => void) {
  const nuevo = !actual
  if (nuevo && typeof Notification !== "undefined" && Notification.permission === "default") {
    try { await Notification.requestPermission() } catch { /* ignore */ }
  }
  try { localStorage.setItem("mdr.avisos", nuevo ? "1" : "0") } catch { /* ignore */ }
  set(nuevo)
}

// Mantiene el título de la pestaña con el nº de pendientes (visible aunque el analista esté en otra
// pestaña) y, si están habilitados los avisos, notifica + pita SOLO cuando entra una decisión nueva
// (no al abrir la consola con cola ya existente, ni en cada refresco). RNF-01: todo en el navegador.
function useAvisoPendientes(pend: Pendiente[] | null, habilitado: boolean) {
  const vistos = useRef<Set<string>>(new Set())
  const primera = useRef(true)
  useEffect(() => {
    // null = el sondeo falló SIN datos previos: no se toca ni el título ni lo visto — si se vaciara
    // `vistos`, un parpadeo de red re-notificaría (y re-pitaría) todo lo que el analista ya vio.
    if (pend === null) return
    document.title = tituloConPendientes(pend.length)
    const nuevos = nuevosPendientes(vistos.current, pend)
    if (!primera.current && habilitado && nuevos.length) {
      const a = textoAviso(nuevos)
      if (a && typeof Notification !== "undefined" && Notification.permission === "granted") {
        try { new Notification(a.titulo, { body: a.cuerpo }) } catch { /* ignore */ }
        pitido()
      }
    }
    vistos.current = new Set(pend.map((p) => p.id))
    primera.current = false
  }, [pend, habilitado])
}

// Menú agrupado por lo que está haciendo el analista: Panel como inicio; Operar = lo que mira durante
// un ataque; Investigar = lo que mira después, para entender; Informar = lo que enseña a otros;
// Configurar = lo que toca de vez en cuando.
type Entrada = { id: Vista; nombre: string; icono: ComponentType<{ className?: string }> }
const NAV: { grupo: string | null; vistas: Entrada[] }[] = [
  { grupo: null, vistas: [{ id: "panel", nombre: "Panel", icono: LayoutDashboard }] },
  { grupo: "Operar", vistas: [
    { id: "consola", nombre: "Consola", icono: SquareTerminal },
    { id: "aprobaciones", nombre: "Aprobaciones", icono: ListChecks },
    { id: "contenciones", nombre: "Contenciones activas", icono: Shield },
    { id: "decisiones", nombre: "Decisiones", icono: List },
  ] },
  { grupo: "Investigar", vistas: [
    { id: "incidentes", nombre: "Incidentes", icono: TriangleAlert },
    { id: "red", nombre: "Red", icono: Network },
    { id: "ubicaciones", nombre: "Ubicaciones", icono: MapPin },
    { id: "watchlist", nombre: "Watchlist", icono: Eye },
    { id: "trazas", nombre: "Trazas", icono: ScrollText },
  ] },
  { grupo: "Informar", vistas: [
    { id: "metricas", nombre: "Informe", icono: ChartBar },
  ] },
  { grupo: "Configurar", vistas: [
    { id: "politicas", nombre: "Políticas de respuesta", icono: SlidersHorizontal },
    { id: "conectividad", nombre: "Conectividad", icono: KeyRound },
    { id: "salud", nombre: "Estado de servicios", icono: Activity },
  ] },
]
const VISTAS: Entrada[] = NAV.flatMap((g) => g.vistas)

// Menú plegado (56 px, solo iconos) en escritorio; se recuerda en el navegador. El drawer móvil va siempre completo.
function leerPlegado(): boolean {
  try { return localStorage.getItem("mdr.menu") === "plegado" } catch { return false }
}

// Incidentes (campañas /24) cuyo caso no está resuelto: el contador del menú.
function incidentesAbiertos(regs: Decision[]): number {
  const casos = estadoDeCasos(regs)
  return campanasDe(regs).filter((c) => (casos[claveDeCampana(c.prefijo)]?.estado ?? "nuevo") !== "resuelto").length
}
const getTrazasVentana = () => getTrazas()

// Contador neutro de estado (contenciones activas, incidentes abiertos): informa, no urge. El ámbar
// queda para lo que exige acción (Aprobaciones).
function Contador({ n, compacto }: { n: number; compacto: boolean }) {
  return (
    <span className={cn("rounded bg-sidebar-foreground/12 px-1.5 text-xs font-medium tabular-nums text-sidebar-foreground",
      compacto && "absolute right-1 top-0.5 px-1 text-[10px] leading-[14px]")}>{n}</span>
  )
}

// La consola, ya dentro: menú, cabecera con la sesión y las vistas.
function Interfaz({ sesion, onCerrarSesion, onCambiarNombre }: { sesion: Sesion; onCerrarSesion: () => void; onCambiarNombre: () => void }) {
  const [vista, setVista] = useState<Vista>("panel")
  const [equipo, setEquipo] = useState<string | null>(null)
  const [textoDec, setTextoDec] = useState("")        // filtro de Decisiones sembrado al pivotar (p. ej. una IP)
  const [atacanteIp, setAtacanteIp] = useState<string | null>(null)   // perfil de atacante (drill-down)
  const [paisAprob, setPaisAprob] = useState("")      // filtro de Aprobaciones por ubicación (desde Ubicaciones)
  const [aprobSel, setAprobSel] = useState<string | null>(null)   // pendiente abierta al llegar (desde el Panel)
  const [incidenteSel, setIncidenteSel] = useState<{ clave: string; cidr: string } | null>(null)   // detalle de incidente
  const [incidente, setIncidente] = useState<Decision | null>(null)
  const [menu, setMenu] = useState(false)             // drawer de navegación en móvil (< md)
  const [plegado, setPlegado] = useState(leerPlegado) // menú plegado a iconos (escritorio)
  const compacto = plegado && !menu                   // el drawer móvil nunca va plegado
  const alternarPlegado = () => {
    const nuevo = !plegado
    try { localStorage.setItem("mdr.menu", nuevo ? "plegado" : "abierto") } catch { /* sin persistencia */ }
    setPlegado(nuevo)
  }
  const { oscuro, alternar } = useTema()
  const salud = useSondeo(getSalud)
  const pend = useSondeo(getPendientes)
  const pausa = useSondeo(getPausa)
  // Contadores del menú: contenciones activas (lista corta) e incidentes abiertos (de la ventana de
  // trazas, más pesada: cada 10 s basta).
  const cont = useSondeo(getContenciones, 5000)
  const trazas = useSondeo(getTrazasVentana, 10000)
  const nCont = listaConocida(cont)?.length ?? 0
  const regs = listaConocida(trazas)
  const nInc = useMemo(() => (regs ? incidentesAbiertos(regs) : 0), [regs])
  const pausada = !!(pausa && !("error" in pausa) && pausa.pausada)
  const conectado = salud !== undefined && !("error" in salud)
  const pendConocidos = listaConocida(pend)   // en un fallo, los últimos buenos (no re-notificar todo)
  const nPend = pendConocidos?.length ?? 0
  const [avisos, setAvisos] = useState(leerAvisos)
  useAvisoPendientes(pendConocidos, avisos)
  const titulo = vista === "incidente" ? "Incidente"
    : vista === "atacante" ? "Perfil de atacante"
    : VISTAS.find((n) => n.id === vista)!.nombre

  return (
    <div className="flex h-dvh overflow-hidden bg-background text-foreground print:h-auto print:overflow-visible print:bg-white">
      {/* Altura de pantalla exacta: el <main> es quien hace scroll, así los inspectores y barras «sticky» se quedan a la vista. */}
      {menu && (
        <div className="fixed inset-0 z-30 bg-black/40 md:hidden print:hidden" onClick={() => setMenu(false)} />
      )}
      {/* `dark`: la barra lateral es siempre oscura (paleta oscura de la consola, también en tema claro).
          `compacto`: plegada a 56 px (solo iconos, nombre en tooltip, grupos como separadores). */}
      <aside className={`${menu ? "flex" : "hidden"} dark fixed inset-y-0 left-0 z-40 w-56 shrink-0 flex-col bg-sidebar text-sidebar-foreground/80 md:static md:flex print:hidden ${compacto ? "md:w-14" : ""}`}>
        <div className={`flex items-center gap-2.5 py-5 ${compacto ? "justify-center px-2" : "px-5"}`}>
          <div className="grid size-8 shrink-0 place-items-center rounded-md bg-sidebar-primary/20 text-sm font-bold text-sidebar-primary">M</div>
          {!compacto && (
            <div className="leading-tight">
              <div className="text-sm font-semibold text-sidebar-foreground">MDR</div>
              <div className="text-[11px] text-muted-foreground">consola de triaje</div>
            </div>
          )}
        </div>
        <nav className={`mt-1 flex-1 pb-2 ${compacto ? "px-2" : "overflow-y-auto px-3"}`}>
          {NAV.map((g) => (
            <div key={g.grupo ?? "inicio"} className={!g.grupo ? "" : compacto ? "mt-2 border-t border-sidebar-border pt-2" : "mt-4"}>
              {g.grupo && !compacto && <div className="mb-1 px-3 text-[11px] font-medium text-muted-foreground">{g.grupo}</div>}
              {g.vistas.map((n) => {
                const activo = vista === n.id
                const Icono = n.icono
                return (
                  <button
                    key={n.id}
                    onClick={() => { if (n.id === "aprobaciones") { setPaisAprob(""); setAprobSel(null) } if (n.id === "incidentes") setIncidenteSel(null); setVista(n.id); setMenu(false) }}
                    aria-label={compacto ? n.nombre : undefined}
                    data-tip={compacto ? n.nombre : undefined}
                    className={cn(
                      "relative mb-0.5 flex w-full items-center rounded-md text-sm transition-colors",
                      compacto ? "menu-tip justify-center py-1.5" : "gap-2.5 px-3 py-1.5",
                      activo
                        ? "bg-sidebar-primary/12 font-medium text-sidebar-foreground before:absolute before:top-1.5 before:bottom-1.5 before:w-0.5 before:rounded before:bg-sidebar-primary before:content-['']"
                        : "text-sidebar-foreground/80 hover:bg-white/5 hover:text-sidebar-foreground",
                      activo && (compacto ? "before:-left-2" : "before:-left-3"),
                    )}
                  >
                    <Icono className={cn("size-4 shrink-0", activo ? "text-sidebar-primary" : "text-muted-foreground")} />
                    {!compacto && <span className="flex-1 text-left">{n.nombre}</span>}
                    {n.id === "consola" && conectado && (
                      <span title="feed en vivo" className={cn("size-1.5 shrink-0 rounded-full bg-ok motion-safe:animate-pulse", compacto && "absolute right-2 top-1.5")} />
                    )}
                    {n.id === "aprobaciones" && nPend > 0 && (
                      <span className={cn("rounded bg-aviso px-1.5 text-xs font-semibold tabular-nums text-aviso-foreground",
                        compacto && "absolute right-1 top-0.5 px-1 text-[10px] leading-[14px]")}>{nPend}</span>
                    )}
                    {n.id === "contenciones" && nCont > 0 && <Contador n={nCont} compacto={compacto} />}
                    {n.id === "incidentes" && nInc > 0 && <Contador n={nInc} compacto={compacto} />}
                  </button>
                )
              })}
            </div>
          ))}
        </nav>
        {/* pie: estado global (conexión, cadencia, pausa de automatización) y el botón de plegar */}
        {compacto ? (
          <div className="flex flex-col items-center gap-3 border-t border-sidebar-border py-3">
            <Punto estado={conectado ? "ok" : "caido"} />
            {pausada && <Pause className="size-3.5 text-aviso" aria-label="Automatización en pausa" />}
            <button onClick={alternarPlegado} aria-label="Desplegar el menú" title="Desplegar el menú"
              className="grid size-6 place-items-center rounded border border-sidebar-border text-muted-foreground hover:text-sidebar-foreground">
              <PanelLeftOpen className="size-3.5" />
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-2 border-t border-sidebar-border px-5 py-3 text-xs">
            <div className="flex items-center gap-2">
              <Punto estado={conectado ? "ok" : "caido"} />
              <span className={conectado ? "text-ok" : "text-critico"}>{conectado ? "en vivo" : "sin conexión"}</span>
              {conectado && <span className="text-muted-foreground">· sondeo 2 s</span>}
              <button onClick={alternarPlegado} aria-label="Plegar el menú" title="Plegar el menú"
                className="ml-auto hidden size-6 place-items-center rounded border border-sidebar-border text-muted-foreground hover:text-sidebar-foreground md:grid">
                <PanelLeftClose className="size-3.5" />
              </button>
            </div>
            {pausada && <div className="flex items-center gap-1.5 text-aviso"><Pause className="size-3.5" />Automatización en pausa</div>}
          </div>
        )}
      </aside>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {sesion.modo === "abierta" && <BandaAbierta />}
        <header className="flex flex-wrap items-center justify-between gap-y-2 border-b border-border bg-card px-4 py-4 md:px-8 print:hidden">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setMenu(true)} aria-label="Abrir menú de navegación"
              className="grid size-9 place-items-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-muted md:hidden"
            >
              <Menu className="size-4" />
            </button>
            <h1 className="font-heading text-lg font-semibold">{titulo}</h1>
          </div>
          <div className="flex items-center gap-2 text-sm md:gap-4">
            <span className="flex items-center gap-2">
              <Punto estado={conectado ? "ok" : "caido"} />
              <span className="hidden text-muted-foreground sm:inline">{conectado ? "datos en vivo" : "sin conexión con el daemon"}</span>
            </span>
            <button
              onClick={() => alternarAvisos(avisos, setAvisos)}
              aria-label={avisos ? "Silenciar avisos de decisiones pendientes" : "Avisarme de decisiones pendientes"}
              title={avisos ? "Avisos activados (notificación del navegador al llegar una decisión)" : "Activar avisos de decisiones pendientes"}
              className={`relative grid size-9 place-items-center rounded-md border border-border transition-colors hover:bg-muted hover:text-foreground ${
                avisos ? "text-aviso" : "text-muted-foreground"
              }`}
            >
              {avisos ? <Bell className="size-4" /> : <BellOff className="size-4" />}
              {avisos && nPend > 0 && (
                <span className="absolute -right-1 -top-1 grid size-4 place-items-center rounded-full bg-aviso text-[10px] font-bold text-aviso-foreground">{nPend}</span>
              )}
            </button>
            <button
              onClick={alternar}
              aria-label={oscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
              title={oscuro ? "Tema claro" : "Tema oscuro"}
              className="grid size-9 place-items-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {oscuro ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
            <ChipSesion sesion={sesion} nombre={operadorActual()} onCerrar={onCerrarSesion} onCambiarNombre={onCambiarNombre} />
          </div>
        </header>
        <main className="flex-1 overflow-auto px-4 py-6 md:px-8 print:overflow-visible print:p-0">
          {pausada && (
            <div className="mb-4 flex items-center gap-2 rounded-md border border-critico/50 bg-critico/10 px-4 py-2.5 text-sm font-medium text-critico print:hidden">
              ⏸ Automatización en pausa — toda contención automática espera aprobación humana.
              {vista !== "contenciones" && (
                <button onClick={() => setVista("contenciones")} className="ml-auto underline underline-offset-2">Gestionar</button>
              )}
            </div>
          )}
          {vista === "panel" && <Dashboard conectado={conectado}
            onVerAprobaciones={(id) => { setPaisAprob(""); setAprobSel(id ?? null); setVista("aprobaciones") }}
            onVerIncidente={(clave, cidr) => { setIncidenteSel({ clave, cidr }); setVista("incidentes") }}
            onVerDecisiones={(texto) => { setEquipo(null); setTextoDec(texto); setVista("decisiones") }}
            onVerSalud={() => setVista("salud")} onVerInforme={() => setVista("metricas")} onVerRed={() => setVista("red")} />}
          {vista === "metricas" && <Metricas />}
          {vista === "salud" && <Salud onVerConectividad={() => setVista("conectividad")} />}
          {vista === "red" && <Red onVerDecisiones={(n, texto) => { setEquipo(n); setTextoDec(texto ?? ""); setVista("decisiones") }}
            onVerAtacante={(ip) => { setAtacanteIp(ip); setVista("atacante") }}
            onVerAprobaciones={() => { setPaisAprob(""); setAprobSel(null); setVista("aprobaciones") }} onVerSalud={() => setVista("salud")} />}
          {vista === "ubicaciones" && <Ubicaciones
            onVerPais={(pais) => { setEquipo(null); setTextoDec(pais); setVista("decisiones") }}
            onVerAprobaciones={(pais) => { setPaisAprob(pais); setAprobSel(null); setVista("aprobaciones") }} />}
          {vista === "atacante" && atacanteIp && (
            <PerfilAtacante ip={atacanteIp} onVolver={() => setVista("red")}
              onVerDecisiones={(ip) => { setEquipo(null); setTextoDec(ip); setVista("decisiones") }} />
          )}
          {vista === "decisiones" && (
            <Decisiones equipo={equipo} textoInicial={textoDec} onQuitarEquipo={() => setEquipo(null)}
              onVerIncidente={(d) => { setIncidente(d); setVista("incidente") }}
              onVerTrazas={() => setVista("trazas")} onVerAtacante={(ip) => { setAtacanteIp(ip); setVista("atacante") }}
              onVerContenciones={() => setVista("contenciones")} />
          )}
          {vista === "aprobaciones" && <Aprobaciones paisInicial={paisAprob} idInicial={aprobSel} onQuitarPais={() => setPaisAprob("")} />}
          {vista === "consola" && <Consola />}
          {vista === "trazas" && <Trazas onVerDecision={(id) => { setEquipo(null); setTextoDec(id); setVista("decisiones") }}
            onVerIncidente={(clave, cidr) => { setIncidenteSel({ clave, cidr }); setVista("incidentes") }} />}
          {vista === "contenciones" && <Contenciones />}
          {vista === "watchlist" && <Watchlist />}
          {vista === "politicas" && <Politicas />}
          {vista === "conectividad" && <Conectividad />}
          {vista === "incidentes" && <Incidentes claveInicial={incidenteSel?.clave ?? null}
            onVerDecisiones={(prefijo) => { setEquipo(null); setTextoDec(prefijo); setVista("decisiones") }}
            onVerRed={() => setVista("red")} onVerAtacante={(ip) => { setAtacanteIp(ip); setVista("atacante") }}
            onVerContenciones={() => setVista("contenciones")} />}
          {vista === "incidente" && incidente && (
            <VistaIncidente decision={incidente} onVolver={() => setVista("decisiones")} />
          )}
        </main>
      </div>
    </div>
  )
}

// ---- puerta de acceso ----------------------------------------------------------------------------
// Al arrancar se pregunta a /api/sesion con el token de la pestaña (si lo hay). Nada de la consola se
// monta (ni sondea) hasta entrar. Dentro, un 401 de cualquier sondeo abre «volver a entrar» encima de la
// vista, sin desmontarla.
type Fase =
  | { f: "comprobando" }
  | { f: "acceso"; motivo?: Motivo; segundos?: number }
  | { f: "nombre"; modo: Exclude<ModoSesion, "identificado"> }
  | { f: "dentro" }

export default function App() {
  const [fase, setFase] = useState<Fase>({ f: "comprobando" })
  const [reentrar, setReentrar] = useState(false)
  const [generacion, setGeneracion] = useState(0)     // remonta la consola si cambia quién firma
  const dentro = fase.f === "dentro"

  const entrar = useCallback(({ modo, operador }: EntradaSesion) => {
    const antes = sesionActual()?.operador
    iniciarSesion(modo, operador)
    setReentrar(false)
    if (antes !== undefined && antes !== (sesionActual()?.operador ?? "")) setGeneracion((g) => g + 1)
    setFase(modo !== "identificado" && !operadorActual().trim() ? { f: "nombre", modo } : { f: "dentro" })
  }, [])

  useEffect(() => {
    let vivo = true
    const token = tokenActual()
    comprobarSesion(token).then((r) => {
      if (!vivo) return
      if (r.tipo === "ok") return entrar({ modo: !r.requiereToken ? "abierta" : r.operador ? "identificado" : "compartido", operador: r.operador })
      if (r.tipo === "rechazado") return setFase({ f: "acceso", motivo: token ? "caducado" : undefined })
      if (r.tipo === "bloqueado") return setFase({ f: "acceso", motivo: "bloqueado", segundos: r.segundos })
      setFase({ f: "acceso", motivo: "sin_red" })
    })
    return () => { vivo = false }
  }, [entrar])

  useEffect(() => {
    if (!dentro) return
    const pedir = () => setReentrar(true)
    window.addEventListener(EVENTO_NO_AUTORIZADO, pedir)
    return () => window.removeEventListener(EVENTO_NO_AUTORIZADO, pedir)
  }, [dentro])

  const salir = () => { cerrarSesion(); setReentrar(false); setFase({ f: "acceso" }) }
  const sesion = sesionActual()

  if (fase.f === "comprobando") return <div className="h-dvh bg-[#0d1117]" aria-busy="true" />
  if (fase.f === "acceso") return <Acceso motivo={fase.motivo} segundos={fase.segundos} onEntrar={entrar} />
  if (fase.f === "nombre") return <Acceso pedirNombre={fase.modo} onEntrar={entrar} onNombre={() => { setGeneracion((g) => g + 1); setFase({ f: "dentro" }) }} />
  if (!sesion) return <Acceso onEntrar={entrar} />
  return (
    <>
      <Interfaz key={generacion} sesion={sesion} onCerrarSesion={salir}
        onCambiarNombre={() => setFase({ f: "nombre", modo: sesion.modo === "compartido" ? "compartido" : "abierta" })} />
      {reentrar && <Reautenticar onEntrar={entrar} onSalir={salir} />}
    </>
  )
}
