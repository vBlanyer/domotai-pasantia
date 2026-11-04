import { useRef, useState, useEffect, type ReactNode } from "react"
import { TriangleAlert, Clock, ChevronDown, ChevronRight } from "lucide-react"
import { useSondeo, getPendientes, getTrazas, aprobar, actualizarCaso, parsearPendiente, operadorActual, operadorVerificado, ahoraServidor, type Pendiente, type Opcion, type Decision } from "@/api"
import { edadTexto, msDesde } from "@/alertas"
import { etiquetaClase, ubicacionLabelDe, nivelPrioridad, paginar, TAM_PAGINA } from "@/datos"
import { SLA_MS, ordenarPor, agruparPor, ORDENES, AGRUPACIONES, type Orden, type Agrupacion, saludCola, siguienteTras, historialOrigen, resueltasHoyPor, efectoAprobar } from "@/aprobaciones"
import { cn } from "@/lib/utils"
import { Paginador } from "@/components/Paginador"
import { useToast } from "@/components/ui/use-toast"
import { AlertDialog } from "@/components/ui/alert-dialog"
import { Cargando, SinConexion, Vacio, Prioridad, DatosCongelados } from "./bits"
import { OrigenBadges } from "./OrigenBadges"

// Lo que el aviso confirma tras un veredicto aplicado (mismo vocabulario que el menú del daemon).
const HECHO: Record<string, string> = {
  Aprobar: "Aprobada: se ejecuta la acción propuesta",
  Rechazar: "Rechazada: se retiene sin ejecutar",
}

// enviando: el POST está en vuelo · clases: «Reclasificar» aceptado, a la espera del submenú ·
// hecho: veredicto aplicado, la tarjeta sale de la cola en el próximo refresco.
type Estado = "listo" | "enviando" | "clases" | "hecho"
const MENSAJE: Record<Exclude<Estado, "listo">, string> = {
  enviando: "Enviando…",
  clases: "Cargando las clases…",
  hecho: "Aplicado. Sale de la cola en el próximo refresco.",
}

// Botón a partir de una opción del menú: veredicto (aprobar/rechazar/reclasificar) o una clase.
function boton(op: Opcion): { etiqueta: string; variante: "default" | "destructive" | "outline" } {
  const base = op.etiqueta.split("—")[0].trim().toLowerCase()
  if (base === "aprobar") return { etiqueta: "Aprobar", variante: "default" }
  if (base === "rechazar") return { etiqueta: "Rechazar", variante: "destructive" }
  if (base === "reclasificar") return { etiqueta: "Reclasificar", variante: "outline" }
  // submenú de clases: etiqueta legible de la fuente única (@/datos); desconocida -> la del menú
  const legible = etiquetaClase(base)
  return { etiqueta: legible !== base ? legible : op.etiqueta, variante: "outline" }
}

// La `respuesta` que espera el daemon para un veredicto, según el tipo de pendiente (para el bloque).
function respuestaPara(p: Pendiente, veredicto: "aprobar" | "rechazar"): string {
  if (p.tipo === "escalada") return veredicto === "aprobar" ? "s" : ""
  const op = parsearPendiente(p).opciones.find((o) => boton(o).etiqueta === (veredicto === "aprobar" ? "Aprobar" : "Rechazar"))
  return op ? op.n : veredicto === "aprobar" ? "1" : "2"
}

function LineaInfo({ t }: { t: string }) {
  const i = t.indexOf(": ")
  if (i === -1) return <div className="text-sm">{t}</div>
  return (
    <div className="text-sm">
      <span className="text-muted-foreground">{t.slice(0, i)}:</span> {t.slice(i + 2)}
    </div>
  )
}

// Reloj que avanza cada segundo, para que el «lleva esperando X» de la cola sea en vivo (el sondeo
// no re-renderiza si los datos no cambian). La edad sale de `encolado_en` del servidor y se compara
// contra la hora del DAEMON (ahoraServidor, anclada a la cabecera Date): el drift del reloj del
// navegador (A3, habitual en WSL2/VMs) ya no infla ni congela el SLA.
function useAhora(ms = 1000): number {
  const [ahora, setAhora] = useState(() => ahoraServidor())
  useEffect(() => {
    const t = setInterval(() => setAhora(ahoraServidor()), ms)
    return () => clearInterval(t)
  }, [ms])
  return ahora
}

function leerPreferencia<T extends string>(k: string, validos: T[], defecto: T): T {
  try { const v = localStorage.getItem(k) as T | null; return v && validos.includes(v) ? v : defecto } catch { return defecto }
}
function guardarPreferencia(k: string, v: string) {
  try { localStorage.setItem(k, v) } catch { /* sin persistencia */ }
}

type Chip = "todas" | "sla" | "criticas" | "cascada" | "ataca"
const clave = (p: Pendiente) => `${p.id}:${p.paso ?? 0}`
const pct = (edadMs: number) => Math.min(100, Math.round((edadMs / SLA_MS) * 100))
const tonoSla = (edadMs: number) => (edadMs >= SLA_MS ? "bg-critico" : edadMs >= SLA_MS * 0.5 ? "bg-aviso" : "bg-primary")
const TONO_SEV = ["bg-enrutado", "bg-info", "bg-aviso", "bg-critico"]
const TONO_PILDORA = ["bg-enrutado/15 text-enrutado", "bg-info/15 text-info", "bg-aviso/15 text-aviso", "bg-critico/15 text-critico"]

function Kpi({ k, children, cls }: { k: string; children: ReactNode; cls?: string }) {
  return (
    <div className="border-b border-border px-4 py-2.5 sm:border-b-0 sm:border-r">
      <div className="text-[11px] text-muted-foreground">{k}</div>
      <div className={cn("text-lg font-semibold leading-tight tabular-nums", cls)}>{children}</div>
    </div>
  )
}

// Una línea de la bandeja: gravedad, activo · familia → acción, origen, edad y barra de SLA.
function Fila({ p, edadMs, activa, estado, seleccionada, onSeleccion, onAbrir }: {
  p: Pendiente; edadMs: number; activa: boolean; estado: Estado; seleccionada: boolean
  onSeleccion: (c: boolean) => void; onAbrir: () => void
}) {
  const v = parsearPendiente(p)
  const nivel = nivelPrioridad(p.severidad)
  const fuera = edadMs >= SLA_MS
  const cascada = efectoAprobar(p).cascada.length > 0
  const resumen = p.activo
    ? <><b className="font-semibold">{p.activo}</b>{p.clase && <><span className="text-muted-foreground"> · </span>{etiquetaClase(p.clase)}</>}{p.accion_final && <><span className="text-muted-foreground"> → </span><b className="font-semibold">{p.accion_final}</b></>}</>
    : <span>{v.incidente ?? `Pendiente ${p.id}`}</span>
  return (
    <li data-pendiente={p.id} className={cn("grid grid-cols-[16px_4px_minmax(0,1fr)] items-stretch gap-x-2.5 border-b border-border py-2 pl-3 pr-3.5 last:border-b-0",
      activa && "bg-primary/10 shadow-[inset_3px_0_0_var(--primary)]", estado === "hecho" && "opacity-50")}>
      <input type="checkbox" aria-label="Seleccionar" checked={seleccionada} onChange={(e) => onSeleccion(e.target.checked)}
        className="size-3.5 self-center accent-[var(--primary)]" />
      <span className={cn("rounded-sm", nivel ? TONO_SEV[nivel.n - 1] : "bg-border")} />
      <button onClick={onAbrir} aria-current={activa} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-left text-sm">
        <span className="min-w-0">
          <span className="flex items-center gap-1.5 overflow-hidden whitespace-nowrap">
            <span className="truncate">{resumen}</span>
            {nivel && <span className={cn("shrink-0 rounded px-1.5 text-[11px] font-medium", TONO_PILDORA[nivel.n - 1])}>P{nivel.n}</span>}
            {cascada && <span className="shrink-0 rounded bg-critico/15 px-1.5 text-[11px] font-medium text-critico">cascada</span>}
            {p.tipo === "escalada" && <span className="shrink-0 rounded bg-violeta/15 px-1.5 text-[11px] font-medium text-violeta">escalada</span>}
          </span>
          <span className="block truncate text-xs text-muted-foreground">
            {[p.origen_ip, p.enriquecimiento_origen?.geo?.pais].filter(Boolean).join(" · ") || "sin origen"}
            {!!p.suprimidas && <span className="font-medium text-critico"> · sigue atacando +{p.suprimidas}</span>}
            {estado === "hecho" && " · aplicada"}
          </span>
        </span>
        <span className="flex flex-col items-end gap-1">
          <span className={cn("text-[11px] tabular-nums", fuera ? "font-semibold text-critico" : "text-muted-foreground")}>{edadTexto(edadMs)}</span>
          <span className="h-1 w-16 overflow-hidden rounded-sm bg-muted"><span className={cn("block h-full", tonoSla(edadMs))} style={{ width: `${pct(edadMs)}%` }} /></span>
        </span>
      </button>
    </li>
  )
}

const ATAJO: Record<string, string> = { Aprobar: "A", Rechazar: "R", Reclasificar: "C" }

// Botón de veredicto con su atajo de teclado visible (el nombre accesible es solo la etiqueta).
function BotonDecision({ respuesta, etiqueta, variante, bloqueada, atajos, onPulsar }: {
  respuesta: string; etiqueta: string; variante: "default" | "destructive" | "outline"; bloqueada: boolean; atajos: boolean
  onPulsar: (respuesta: string, etiqueta: string) => void
}) {
  const tono = variante === "default" ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
    : variante === "destructive" ? "border-critico/45 bg-card text-critico hover:bg-critico/10"
    : "border-border bg-card text-foreground hover:bg-muted"
  return (
    <button type="button" aria-label={etiqueta} disabled={bloqueada} onClick={() => onPulsar(respuesta, etiqueta)}
      className={cn("inline-flex h-9 items-center gap-2 rounded-[8px] border px-3.5 text-[13.5px] font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50", tono)}>
      {etiqueta}{atajos && ATAJO[etiqueta] && <kbd aria-hidden className="rounded border border-current px-1 font-mono text-[10px] leading-4 opacity-75">{ATAJO[etiqueta]}</kbd>}
    </button>
  )
}

function Seccion({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="border-b border-border px-4 py-3 last:border-b-0">
      <h4 className="mb-2 text-[11px] font-medium text-muted-foreground">{titulo}</h4>
      {children}
    </div>
  )
}

// El inspector de la pendiente elegida: «si apruebas» primero, luego el porqué, el origen con su
// historia, y la decisión (botones con atajo, nota opcional para la traza).
function Inspector({ p, edadMs, estado, trazas, nota, onNota, onPulsar, onUbicacion }: {
  p: Pendiente; edadMs: number; estado: Estado; trazas: Decision[]; nota: string; onNota: (t: string) => void
  onPulsar: (respuesta: string, etiqueta: string) => void; onUbicacion: (u: string) => void
}) {
  const v = parsearPendiente(p)
  const escalada = p.tipo === "escalada"
  const efecto = efectoAprobar(p)
  const conCascada = efecto.cascada.length > 0
  const clasificando = (v.titulo ?? "").startsWith("Nueva clase")
  const fuera = edadMs >= SLA_MS
  const ubic = p.enriquecimiento_origen ? ubicacionLabelDe(p) : null
  const historia = historialOrigen(trazas, p.origen_ip)
  const bloqueada = estado !== "listo"
  const comun = { bloqueada, atajos: !clasificando, onPulsar }
  return (
    <section aria-label="Decisión" className="overflow-hidden rounded-lg border border-border bg-card text-sm lg:sticky lg:top-3">
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          {!!p.severidad && <Prioridad n={p.severidad} />}
          <span className={cn("inline-flex items-center gap-1", fuera && "font-semibold text-critico")} title="Tiempo que lleva esperando tu decisión">
            <Clock className="size-3" />{fuera ? `fuera de SLA · ${edadTexto(edadMs).replace("hace ", "")} esperando` : `pendiente ${edadTexto(edadMs)}`}
          </span>
          {!!p.suprimidas && <span className="rounded bg-critico/15 px-1.5 py-0.5 font-medium text-critico">sigue atacando · +{p.suprimidas}</span>}
          {p.id_decision && <span>· decisión <span className="font-mono">{p.id_decision}</span></span>}
        </div>
        <div className="mt-1 text-base font-semibold">
          {p.activo ? <>{p.activo}{p.clase && ` · ${etiquetaClase(p.clase)}`}{p.accion_final && ` → ${p.accion_final}`}</> : (v.incidente ?? "Decisión pendiente")}
        </div>
        {p.activo && v.incidente && <div className="truncate text-xs text-muted-foreground">{v.incidente}</div>}
      </div>

      {!clasificando && (
        <Seccion titulo="Si apruebas">
          <div className={cn("rounded-md border px-3 py-2.5", conCascada ? "border-critico/40 bg-critico/10" : "border-border bg-muted")}>
            <div className={cn("flex items-start gap-2 font-semibold", conCascada && "text-critico")}>
              {conCascada && <TriangleAlert className="mt-0.5 size-4 shrink-0" />}
              <span>{efecto.titulo}{conCascada && `, y caen en cascada: ${efecto.cascada.join(", ")}`}.</span>
            </div>
            {efecto.detalle && <div className="mt-0.5 text-xs text-muted-foreground"><span className="font-medium">Consecuencia:</span> {efecto.detalle}</div>}
            {conCascada && <div className="mt-0.5 text-xs text-muted-foreground">Pedirá confirmación por la cascada. Reversible desde Contenciones activas.</div>}
          </div>
          <div className="mt-2 rounded-md border border-ok/30 bg-ok/5 px-3 py-2">
            <div className="font-semibold">Si rechazas, no se ejecuta nada</div>
            <div className="text-xs text-muted-foreground">La alerta queda registrada{p.suprimidas ? `; el origen sigue atacando (+${p.suprimidas} desde que entró en cola)` : ""}.</div>
          </div>
        </Seccion>
      )}

      <Seccion titulo="Por qué lo propone el motor">
        <div className="space-y-1">
          {(p.clase || p.confianza != null) && (
            <div className="text-sm"><span className="text-muted-foreground">Clase:</span> <span className="font-mono text-xs">{p.clase ?? "—"}</span>{p.confianza != null && <> · confianza <b className="font-semibold">{p.confianza}</b></>}</div>
          )}
          {p.motivo && <div className="text-sm"><span className="text-muted-foreground">Por qué humano:</span> {p.motivo}</div>}
          {!!p.tecnica_mitre?.length && (
            <div className="flex flex-wrap items-center gap-1 text-sm"><span className="text-muted-foreground">ATT&CK:</span>
              {p.tecnica_mitre.map((t) => <span key={t} className="rounded bg-muted px-1.5 font-mono text-[10px]">{t}</span>)}</div>
          )}
          {v.info.map((t, i) => <LineaInfo key={i} t={t} />)}
        </div>
      </Seccion>

      {(p.origen_ip || p.enriquecimiento_origen) && (
        <Seccion titulo="Origen">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {p.origen_ip && <b className="font-mono text-sm font-semibold">{p.origen_ip}</b>}
            {p.activo && <span className="text-muted-foreground">→ {p.activo}</span>}
            <OrigenBadges e={p.enriquecimiento_origen} />
            {ubic && (
              <button onClick={() => onUbicacion(ubic)} title={`Filtrar la cola por ${ubic}`}
                className="rounded bg-muted px-1.5 py-0.5 hover:underline">📍 {ubic} · filtrar</button>
            )}
          </div>
          {historia.length > 0 && (
            <>
              <h4 className="mb-1.5 mt-3 text-[11px] font-medium text-muted-foreground">Lo que ya pasó con este origen</h4>
              <ul className="space-y-1 text-xs">
                {historia.map((h, i) => (
                  <li key={i} className="grid grid-cols-[72px_1fr_auto] gap-2">
                    <span className="font-mono text-[11px] text-muted-foreground">{new Date(h.ts).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</span>
                    <span className="truncate">{h.texto} · {h.quien}</span>
                    <span className={h.desenlace === "contenida" ? "text-ok" : "text-muted-foreground"}>{h.desenlace ?? ""}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Seccion>
      )}

      <div className="space-y-2.5 bg-muted px-4 py-3">
        {p.id_decision && !clasificando && (
          <textarea value={nota} onChange={(e) => onNota(e.target.value)} rows={1} aria-label="Nota para la traza"
            placeholder="Nota para la traza (opcional): por qué decides esto"
            className="w-full resize-y rounded-md border border-border bg-card px-2.5 py-1.5 text-sm outline-none focus:border-ring" />
        )}
        {clasificando && <div className="text-sm font-medium">Elige la clase correcta:</div>}
        <div className="flex flex-wrap gap-2">
          {escalada ? (
            <><BotonDecision {...comun} respuesta="s" etiqueta="Aprobar" variante="default" /><BotonDecision {...comun} respuesta="" etiqueta="Rechazar" variante="destructive" /></>
          ) : v.opciones.length > 0 ? (
            v.opciones.map((op) => { const b = boton(op); return <BotonDecision {...comun} key={op.n} respuesta={op.n} etiqueta={b.etiqueta} variante={b.variante} /> })
          ) : (
            // fallback: el prompt no trajo el menú (p. ej. daemon sin la última versión)
            <><BotonDecision {...comun} respuesta="1" etiqueta="Aprobar" variante="default" /><BotonDecision {...comun} respuesta="2" etiqueta="Rechazar" variante="destructive" /></>
          )}
        </div>
        {estado !== "listo"
          ? <p aria-live="polite" className="text-xs text-muted-foreground">{MENSAJE[estado]}</p>
          : <p className="text-[11px] text-muted-foreground">J / K siguiente y anterior · X seleccionar · al decidir salta a la siguiente más urgente</p>}
      </div>
    </section>
  )
}

// Quién firma lo que se decide aquí: lo fija la sesión (token por persona, o el nombre dado al entrar).
function BarraOperador() {
  const yo = operadorActual().trim()
  return (
    <p className="text-sm text-muted-foreground">
      Firmas como <b className="font-medium text-foreground">{yo || "sin nombre"}</b>
      <span className="text-xs"> · {operadorVerificado() ? "verificado por tu token" : "nombre sin verificar"}</span>
    </p>
  )
}

export function Aprobaciones({ paisInicial = "", idInicial = null, onQuitarPais }: {
  // idInicial: la pendiente que se abre en el inspector al llegar (p. ej. «Revisar» desde el Panel)
  paisInicial?: string; idInicial?: string | null; onQuitarPais?: () => void
} = {}) {
  const p = useSondeo(getPendientes)
  const tr = useSondeo(getTrazas, 10000)          // memoria del origen y ritmo del operador
  const ahora = useAhora()   // hook incondicional (antes de cualquier return); 1 Hz para el SLA en vivo
  const [sel, setSel] = useState<Set<string>>(new Set())
  const [confirmarBloque, setConfirmarBloque] = useState(false)
  const [pagina, setPagina] = useState(1)
  const [tam, setTam] = useState(TAM_PAGINA)
  const [pais, setPais] = useState(paisInicial)       // filtro por ubicación, sembrado desde Ubicaciones
  useEffect(() => { setPais(paisInicial); setPagina(1) }, [paisInicial])
  const [chip, setChip] = useState<Chip>("todas")
  // Orden y agrupación elegibles; por defecto llega por tiempo (más reciente primero) y sin agrupar.
  // La elección se recuerda en este navegador.
  const [orden, setOrden] = useState<Orden>(() => leerPreferencia("mdr.aprob.orden", ORDENES.map((o) => o.id), "reciente"))
  const [agrupacion, setAgrupacion] = useState<Agrupacion>(() => leerPreferencia("mdr.aprob.agrupar", AGRUPACIONES.map((a) => a.id), "ninguno"))
  const elegirOrden = (o: Orden) => { setOrden(o); setPagina(1); guardarPreferencia("mdr.aprob.orden", o) }
  const elegirAgrupacion = (a: Agrupacion) => { setAgrupacion(a); setPagina(1); guardarPreferencia("mdr.aprob.agrupar", a) }
  const [actual, setActual] = useState<string | null>(idInicial)
  const [estados, setEstados] = useState<Record<string, Estado>>({})     // por id:paso (un menú nuevo = limpio)
  const [resueltas, setResueltas] = useState<Set<string>>(new Set())
  const [plegados, setPlegados] = useState<Set<string>>(new Set())
  const [notas, setNotas] = useState<Record<string, string>>({})
  const [confirmar, setConfirmar] = useState<{ p: Pendiente; respuesta: string; etiqueta: string } | null>(null)
  const enVuelo = useRef(new Set<string>())     // corta el doble clic antes de que llegue el re-render
  const teclas = useRef<(e: KeyboardEvent) => void>(() => {})
  const toast = useToast()
  const elegirTam = (t: number) => { setTam(t); setPagina(1) }
  // Cambiar un filtro vuelve a la primera página (en el mismo evento, no en un efecto).
  const filtrar = (v: string) => { setPais(v); setPagina(1) }
  const elegirChip = (c: Chip) => { setChip(c); setPagina(1) }

  // Con la conexión perdida pero datos previos, la cola se sigue mostrando (congelada) con aviso:
  // vaciarla en un parpadeo de red haría «desaparecer» decisiones que siguen esperando (C2).
  const todas = !p ? null : "error" in p ? (p.datos ?? null) : p
  const trazas: Decision[] = Array.isArray(tr) ? tr : []
  // filtro por ubicación (país real o cubo lab/interna…): el propio de la vista y el sembrado al pivotar
  // desde el mapa de Ubicaciones usan la MISMA etiqueta (ubicacionLabelDe).
  const porPais = todas && pais ? todas.filter((x) => ubicacionLabelDe(x) === pais) : todas
  const edad = (x: Pendiente) => msDesde(x.encolado_en, ahora)
  const PASA: Record<Chip, (x: Pendiente) => boolean> = {
    todas: () => true, sla: (x) => edad(x) >= SLA_MS, criticas: (x) => (x.severidad ?? 0) >= 4,
    cascada: (x) => efectoAprobar(x).cascada.length > 0, ataca: (x) => (x.suprimidas ?? 0) > 0,
  }
  const lista = porPais ? ordenarPor(porPais.filter(PASA[chip]), orden, ahora) : null
  const grupos = lista ? agruparPor(lista, agrupacion) : []
  const secuencia = grupos.flatMap((g) => g.items)                   // orden de lectura (grupos)
  // Se pagina por entradas: cada pendiente de un grupo desplegado, o el grupo plegado como una sola.
  type Entrada = { g: (typeof grupos)[number]; x: Pendiente | null }
  const entradas: Entrada[] = grupos.flatMap<Entrada>((g) => (g.cabecera && plegados.has(g.clave) ? [{ g, x: null }] : g.items.map((x) => ({ g, x }))))
  const pag = paginar(entradas, pagina, tam)
  const enPagina = pag.filas.flatMap((e) => (e.x ? [e.x] : []))
  const elegida = secuencia.find((x) => x.id === actual) ?? secuencia.find((x) => !resueltas.has(x.id)) ?? secuencia[0]
  // ubicaciones presentes en la cola, para el selector (incluye la filtrada aunque ya no haya tarjetas)
  const ubicaciones = [...new Set([...(todas ?? []).map(ubicacionLabelDe), ...(pais ? [pais] : [])])].sort()
  const fallo = p && "error" in p ? p : null
  const quitarPais = () => { filtrar(""); onQuitarPais?.() }
  const elegidas = (lista ?? []).filter((x) => sel.has(x.id))
  const fueraDePagina = elegidas.filter((x) => !enPagina.includes(x)).length
  const conCascadaSel = elegidas.filter((x) => efectoAprobar(x).cascada.length > 0).length
  const alternar = (id: string, c: boolean) => setSel((s) => { const n = new Set(s); if (c) n.add(id); else n.delete(id); return n })
  const salud = saludCola(porPais ?? [], ahora)
  const hoy = new Date(ahora).toISOString().slice(0, 10)
  const abrir = (id: string) => {
    setActual(id)
    const i = entradas.findIndex((e) => e.x?.id === id)
    if (i >= 0) setPagina(Math.floor(i / tam) + 1)
  }

  // Envía el veredicto con el `paso` del menú que se ve. Mientras vuela, la pendiente se bloquea; si
  // el backend lo rechaza (409: ya resuelta o menú superado) se avisa y se reactiva. Al aplicarse,
  // la nota (si hay) va al caso de la decisión y el inspector salta a la siguiente más urgente.
  async function responder(x: Pendiente, respuesta: string, etiqueta: string) {
    const k = clave(x)
    if (enVuelo.current.has(k)) return
    enVuelo.current.add(k)
    const v = parsearPendiente(x)
    const clasificando = (v.titulo ?? "").startsWith("Nueva clase")
    const sinAccion = x.tipo !== "escalada" && x.accion_final === null
    setEstados((e) => ({ ...e, [k]: "enviando" }))
    const r = await aprobar(x.id, respuesta, x.paso)
    if (r !== "ok") {
      enVuelo.current.delete(k)
      setEstados((e) => ({ ...e, [k]: "listo" }))
      toast({ type: "error", title: "No se aplicó el veredicto",
        description: r === "auth"
          ? "El daemon rechazó el token de la consola (401): revísalo arriba a la derecha."
          : "Ya no estaba vigente (la resolvió otro operador o cambió el menú) o se perdió la conexión con el daemon." })
      return
    }
    if (x.tipo !== "escalada" && !clasificando && etiqueta === "Reclasificar") {
      setEstados((e) => ({ ...e, [k]: "clases" }))   // sigue bloqueada hasta que llegue el submenú (paso nuevo)
      return
    }
    setEstados((e) => ({ ...e, [k]: "hecho" }))
    const nota = (notas[x.id] ?? "").trim()
    if (nota && x.id_decision) actualizarCaso(x.id_decision, { nota })
    const hechas = new Set(resueltas).add(x.id)
    setResueltas(hechas)
    const sig = siguienteTras(secuencia.map((y) => y.id), x.id, hechas)
    if (sig) abrir(sig)
    const titulo = clasificando ? `Reclasificada como «${etiqueta}»`
      : sinAccion && etiqueta === "Aprobar" ? "Aprobada: la acción está vetada, no se ejecuta nada"
      : HECHO[etiqueta] ?? etiqueta
    toast({ type: "success", description: v.incidente, title: titulo })
  }

  // Aprobar un bloqueo que deja activos sin servicio en cascada exige un gesto consciente; rechazar
  // o reclasificar no ejecutan nada y van directos.
  function pulsar(x: Pendiente, respuesta: string, etiqueta: string) {
    if (etiqueta === "Aprobar" && efectoAprobar(x).cascada.length > 0) setConfirmar({ p: x, respuesta, etiqueta })
    else responder(x, respuesta, etiqueta)
  }

  // Acciones en bloque: aplica el mismo veredicto a las seleccionadas (reusa el POST por decisión).
  async function enBloque(veredicto: "aprobar" | "rechazar") {
    setConfirmarBloque(false)
    let ok = 0, falladas = 0
    const hechas = new Set(resueltas)
    for (const x of elegidas) {
      const r = await aprobar(x.id, respuestaPara(x, veredicto), x.paso)
      if (r === "ok") { ok++; hechas.add(x.id) } else falladas++
    }
    setResueltas(hechas)
    setSel(new Set())
    toast({ type: falladas ? "error" : "success",
      title: `${ok} ${veredicto === "aprobar" ? "aprobada(s)" : "rechazada(s)"}${falladas ? ` · ${falladas} sin aplicar` : ""}` })
  }

  // Teclado: A/R/C deciden la pendiente del inspector, J/K (o flechas) se mueven, X la selecciona.
  // No actúa mientras se escribe en un campo ni con un diálogo abierto.
  useEffect(() => {
    teclas.current = (e: KeyboardEvent) => {
      const t = e.target instanceof Element ? e.target : null
      if (!elegida || confirmar || confirmarBloque || e.metaKey || e.ctrlKey || e.altKey) return
      if (t && (t.closest("input, textarea, select, [contenteditable=true]") || t.closest("[role=alertdialog]"))) return
      const tecla = e.key.toLowerCase()
      const i = secuencia.findIndex((x) => x.id === elegida.id)
      if (tecla === "j" || e.key === "ArrowDown") { const s = secuencia[i + 1]; if (s) { e.preventDefault(); abrir(s.id) } return }
      if (tecla === "k" || e.key === "ArrowUp") { const s = secuencia[i - 1]; if (s) { e.preventDefault(); abrir(s.id) } return }
      if (tecla === "x") { alternar(elegida.id, !sel.has(elegida.id)); return }
      const etiqueta = ({ a: "Aprobar", r: "Rechazar", c: "Reclasificar" } as Record<string, string>)[tecla]
      if (!etiqueta || (estados[clave(elegida)] ?? "listo") !== "listo") return
      const v = parsearPendiente(elegida)
      if ((v.titulo ?? "").startsWith("Nueva clase")) return
      if (elegida.tipo === "escalada") { if (etiqueta !== "Reclasificar") pulsar(elegida, etiqueta === "Aprobar" ? "s" : "", etiqueta); return }
      const op = v.opciones.find((o) => boton(o).etiqueta === etiqueta)
      const respuesta = op?.n ?? (etiqueta === "Aprobar" ? "1" : etiqueta === "Rechazar" ? "2" : null)
      if (respuesta) { e.preventDefault(); pulsar(elegida, respuesta, etiqueta) }
    }
  })
  useEffect(() => {
    const f = (e: KeyboardEvent) => teclas.current(e)
    window.addEventListener("keydown", f)
    return () => window.removeEventListener("keydown", f)
  }, [])

  const CHIPS: { id: Chip; nombre: string; n: number }[] = porPais ? [
    { id: "todas", nombre: "Todas", n: porPais.length }, { id: "sla", nombre: "Fuera de SLA", n: porPais.filter(PASA.sla).length },
    { id: "criticas", nombre: "Críticas", n: porPais.filter(PASA.criticas).length }, { id: "cascada", nombre: "Con cascada", n: porPais.filter(PASA.cascada).length },
    { id: "ataca", nombre: "Sigue atacando", n: porPais.filter(PASA.ataca).length },
  ] : []

  const cuerpo = !p ? <Cargando />
    : lista === null ? <SinConexion causa={fallo?.causa} />
    : (porPais ?? []).length === 0 ? <Vacio>{pais
        ? `Nada pendiente de ${pais} ahora mismo.`
        : "Nada que aprobar ahora mismo. Cuando una decisión necesite un humano, aparecerá aquí."}</Vacio>
    : (
      <div className="grid items-start gap-3.5 lg:grid-cols-[minmax(0,1.25fr)_minmax(360px,1fr)]">
        <div className="space-y-3">
          <div className="rounded-lg border border-border bg-card [&>*:first-child>div:first-child]:rounded-t-lg [&>*:last-child]:rounded-b-lg">
            {lista.length === 0 && <p className="px-4 py-6 text-sm text-muted-foreground">Ninguna pendiente con este filtro.</p>}
            {pag.filas.map((e, n) => {
              const g = e.g
              const nuevoGrupo = n === 0 || pag.filas[n - 1].g.clave !== g.clave
              const plegado = !e.x
              const todasSel = g.items.every((x) => sel.has(x.id))
              return (
                <div key={e.x ? clave(e.x) : `g-${g.clave}`}>
                  {nuevoGrupo && g.cabecera && (
                    <div className="flex items-center gap-2 border-b border-border bg-muted px-3.5 py-1.5 text-[11px] text-muted-foreground">
                      <button onClick={() => setPlegados((s) => { const m = new Set(s); if (m.has(g.clave)) m.delete(g.clave); else m.add(g.clave); return m })}
                        aria-expanded={!plegado} aria-label={`${plegado ? "Desplegar" : "Plegar"} ${g.etiqueta}`} className="hover:text-foreground">
                        {plegado ? <ChevronRight className="size-3.5" /> : <ChevronDown className="size-3.5" />}
                      </button>
                      <span className="flex-1 truncate">{g.etiqueta} · {g.items.length} {g.items.length === 1 ? "pendiente" : `pendientes${g.clave.startsWith("inc:") ? " de la misma campaña" : ""}`}{plegado && " · plegado"}</span>
                      {g.items.length > 1 && (
                        <button onClick={() => setSel((s) => { const m = new Set(s); for (const x of g.items) { if (todasSel) m.delete(x.id); else m.add(x.id) } return m })}
                          className="font-medium text-info hover:underline">{todasSel ? "quitar las" : "seleccionar las"} {g.items.length}</button>
                      )}
                    </div>
                  )}
                  {e.x && (
                    <ul>
                      <Fila p={e.x} edadMs={edad(e.x)} activa={elegida?.id === e.x.id} estado={estados[clave(e.x)] ?? "listo"}
                        seleccionada={sel.has(e.x.id)} onSeleccion={(c) => alternar(e.x!.id, c)} onAbrir={() => setActual(e.x!.id)} />
                    </ul>
                  )}
                </div>
              )
            })}
            {elegidas.length > 0 && (() => {
              const gs = [...new Set(elegidas.map((x) => grupos.find((g) => g.items.includes(x))?.etiqueta))]
              const deUno = gs.length === 1 && gs[0] ? `las ${elegidas.length} de ${gs[0].split(" · ")[0]}` : null
              return (
                // sticky: con una cola larga la barra queda a la vista al marcar, no al final de la lista
                <div role="region" aria-label="Selección" className="sticky bottom-0 z-10 flex flex-wrap items-center gap-2.5 border-t border-border bg-[color-mix(in_srgb,var(--primary)_7%,var(--card))] px-3.5 py-2.5 text-[12.5px]">
                  <b className="font-semibold">{elegidas.length} {elegidas.length === 1 ? "seleccionada" : "seleccionadas"}</b>
                  <span className="text-muted-foreground">
                    {[deUno, fueraDePagina ? `${fueraDePagina} fuera de esta página` : null,
                      conCascadaSel ? `${conCascadaSel} con cascada (pedirá confirmar)` : null].filter(Boolean).join(" · ")}
                  </span>
                  <span className="ml-auto flex items-center gap-2">
                    <button onClick={() => setConfirmarBloque(true)}
                      className="rounded-[7px] border border-primary bg-primary px-3 py-1 font-medium text-primary-foreground hover:bg-primary/90">Aprobar {elegidas.length === 1 ? "la seleccionada" : `las ${elegidas.length}`}</button>
                    <button onClick={() => enBloque("rechazar")}
                      className="rounded-[7px] border border-border bg-card px-3 py-1 font-medium hover:bg-muted">Rechazar {elegidas.length === 1 ? "la seleccionada" : `las ${elegidas.length}`}</button>
                    <button onClick={() => setSel(new Set())} className="text-muted-foreground hover:underline">quitar selección</button>
                  </span>
                </div>
              )
            })()}
          </div>
          <Paginador pagina={pag.pagina} paginas={pag.paginas} total={pag.total} tam={tam} onPagina={setPagina} onTam={elegirTam} />
        </div>
        {elegida
          ? <Inspector key={clave(elegida)} p={elegida} edadMs={edad(elegida)} estado={estados[clave(elegida)] ?? "listo"} trazas={trazas}
              nota={notas[elegida.id] ?? ""} onNota={(t) => setNotas((n) => ({ ...n, [elegida.id]: t }))}
              onPulsar={(respuesta, etiqueta) => pulsar(elegida, respuesta, etiqueta)} onUbicacion={filtrar} />
          : <div className="rounded-lg border border-dashed border-border bg-card px-4 py-5 text-sm text-muted-foreground">Selecciona una pendiente para decidir.</div>}
      </div>
    )

  return (
    <div className="space-y-3">
      {/* salud de la cola: siempre a la vista */}
      <div className="grid overflow-hidden rounded-lg border border-border bg-card sm:grid-cols-[repeat(4,minmax(0,1fr))_auto]">
        <Kpi k="En cola">{salud.total} <span className="text-xs font-normal text-muted-foreground">+{salud.ultimaHora} en la última hora</span></Kpi>
        <Kpi k="Fuera de SLA (15 min)" cls={salud.fueraSla ? "text-critico" : undefined}>
          {salud.fueraSla} {salud.fueraSla > 0 && <span className="text-xs font-normal text-muted-foreground">la más antigua, {edadTexto(salud.masAntiguaMs).replace("hace ", "")}</span>}
        </Kpi>
        <Kpi k="Críticas">{salud.criticas} {salud.criticasConCascada > 0 && <span className="text-xs font-normal text-muted-foreground">{salud.criticasConCascada} con cascada</span>}</Kpi>
        <Kpi k="Tu ritmo hoy">{resueltasHoyPor(trazas, operadorActual(), hoy)} <span className="text-xs font-normal text-muted-foreground">resueltas</span></Kpi>
        <div className="flex items-center px-4 py-2.5"><BarraOperador /></div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <div role="group" aria-label="Filtrar la cola" className="flex flex-wrap gap-1">
          {CHIPS.map((c) => (
            <button key={c.id} aria-pressed={chip === c.id} onClick={() => elegirChip(c.id)}
              className={cn("rounded-full border px-2.5 py-0.5 transition-colors",
                chip === c.id ? "border-primary/45 bg-primary/12 font-medium text-foreground" : "border-border text-muted-foreground hover:text-foreground")}>
              {c.nombre} <span className="tabular-nums">{c.n}</span>
            </button>
          ))}
        </div>
        <span className="ml-auto flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-muted-foreground">Ordenar
            <select aria-label="Ordenar la cola" value={orden} onChange={(e) => elegirOrden(e.target.value as Orden)}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground">
              {ORDENES.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-muted-foreground">Agrupar
            <select aria-label="Agrupar la cola" value={agrupacion} onChange={(e) => elegirAgrupacion(e.target.value as Agrupacion)}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground">
              {AGRUPACIONES.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
            </select>
          </label>
        </span>
        {(ubicaciones.length > 1 || pais) && (
          <span className="flex items-center gap-2">
            <label htmlFor="filtro-ubic" className="text-muted-foreground">Ubicación:</label>
            <select id="filtro-ubic" value={pais} aria-label="Filtrar por ubicación"
              onChange={(e) => { const v = e.target.value; filtrar(v); if (!v) onQuitarPais?.() }}
              className="rounded border border-border bg-background px-2 py-1 text-xs">
              <option value="">Todas las ubicaciones</option>
              {ubicaciones.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
            {pais && <button onClick={quitarPais} className="text-muted-foreground hover:underline">quitar ✕</button>}
          </span>
        )}
      </div>
      {fallo && lista !== null && <DatosCongelados fallo={fallo} />}
      {cuerpo}
      <AlertDialog open={confirmar !== null} onOpenChange={(o) => { if (!o) setConfirmar(null) }}
        title="¿Aprobar pese a la cascada?"
        description="El bloqueo deja sin servicio a los activos que dependen de este:"
        confirmLabel="Aprobar igualmente"
        onConfirm={() => { if (confirmar) responder(confirmar.p, confirmar.respuesta, confirmar.etiqueta) }}>
        <ul className="list-disc space-y-0.5 pl-5">{(confirmar ? efectoAprobar(confirmar.p).cascada : []).map((a) => <li key={a}>{a}</li>)}</ul>
      </AlertDialog>
      <AlertDialog open={confirmarBloque} onOpenChange={(o) => { if (!o) setConfirmarBloque(false) }}
        title={`¿Aprobar ${elegidas.length} decisión(es)?`}
        description={`Se ejecutará la acción propuesta de cada una (contención).${conCascadaSel ? ` ${conCascadaSel} deja(n) activos sin servicio en cascada.` : ""}${fueraDePagina ? ` ${fueraDePagina} no está(n) en esta página.` : ""} Revisa que es lo que quieres.`}
        confirmLabel="Aprobar todas" onConfirm={() => enBloque("aprobar")} />
    </div>
  )
}
