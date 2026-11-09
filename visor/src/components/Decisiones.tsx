import { Fragment, useEffect, useState, type ReactNode } from "react"
import { TriangleAlert } from "lucide-react"
import { useSondeo, getDecisiones, getTrazaDetalle, operadorActual, type Decision, type Detalle, type Pasaje } from "@/api"
import { Cargando, SinConexion, Vacio, Prioridad, BarraFiltros, DatosCongelados, LineaCausa } from "./bits"
import { filtrarDecisiones, clasesDe, claveDe, contencionDe, ventanaDe, paginar, pasosRunbook, estadoDeCasos, etiquetaClase, TAM_PAGINA, type Contencion, type EstadoContencion, type Filtro, quienDecidio } from "@/datos"
import { desenlaceDe, resumenDecisiones, pasaFiltro, pasosDe, FILTROS_DECISION, type FiltroDecision, type Paso, type Tono } from "@/decisiones"
import { claveDia, etiquetaDia, horaLocal } from "@/trazas"
import { Paginador } from "./Paginador"
import { OrigenBadges } from "./OrigenBadges"
import { cn } from "@/lib/utils"

// Vista «Decisiones»: cómo razonó el motor en cada caso y en qué acabó. Aprobaciones es lo que espera a
// un humano; Trazas, la integridad del registro. Aquí cada decisión se lee como un recorrido de seis
// pasos: alerta → clasificación → propuesta → política del cliente → analista → ejecución.

const PILDORA: Record<Tono, string> = {
  ok: "bg-ok/15 text-ok", aviso: "bg-aviso/15 text-aviso", critico: "bg-critico/15 text-critico",
  neutro: "bg-enrutado/15 text-enrutado", violeta: "bg-violeta/15 text-violeta",
}
const PASO: Record<Paso["estado"], string> = {
  ok: "border-ok text-ok", aviso: "border-aviso text-aviso", critico: "border-critico text-critico",
  neutro: "border-border text-muted-foreground", violeta: "border-violeta text-violeta", humano: "border-aviso bg-aviso text-aviso-foreground",
}

// De dónde viene la justificación: plantilla (baseline, sin modelo) o el LLM.
const esLLM = (v?: string | null) => !!v && !v.startsWith("plantilla")

function Seccion({ titulo, extra, children }: { titulo: string; extra?: ReactNode; children: ReactNode }) {
  return (
    <div className="border-b border-border px-4 py-3 last:border-b-0">
      <h4 className="mb-2 flex items-center justify-between gap-2 text-[11px] font-medium text-muted-foreground"><span>{titulo}</span>{extra}</h4>
      {children}
    </div>
  )
}

// Qué pasó con la contención, en una frase (paso 6).
const FRASE: Record<EstadoContencion, (c: Contencion) => string> = {
  contenida: (c) => `Contenida en ${c.dispositivo ?? "—"}` + (c.escalada && c.desde ? ` · escaló desde ${c.desde}` : ""),
  fallida: (c) => c.desde ? "No se pudo contener: ni el activo ni la escalada lo lograron"
    : "No se pudo contener en el activo (no hay a dónde escalar)",
  retenida: () => "Retenida por el analista: no se ejecutó ninguna acción",
  cancelada: () => "Escalada cancelada por el analista",
  degradada: () => "El agente no respondió: se degradó al motor determinista",
  enrutada: (c) => `Enrutada a ${c.destino ?? "—"}: se deriva al equipo, sin contención (por diseño)`,
  sin_accion: () => "Sin acción de contención",
}

function Pasajes({ pasajes, consulta }: { pasajes: Pasaje[]; consulta?: string | null }) {
  if (pasajes.length === 0)
    return <p className="text-xs text-muted-foreground">Esta decisión no consultó el RAG (la recuperación de conocimiento se activa en los accesos a credenciales y requiere el daemon con <code className="rounded bg-foreground/10 px-1 font-mono">--con-llm</code>).</p>
  return (
    <div className="space-y-1.5">
      {consulta && <p className="font-mono text-[11px] text-muted-foreground">consulta: {consulta}</p>}
      {pasajes.map((p, i) => (
        <blockquote key={i} className="rounded-r-md border-l-[3px] border-border bg-muted px-2.5 py-1.5 text-xs">
          {p.titulo && <b className="font-medium">{p.titulo}</b>}{p.titulo && " — "}<span className="text-muted-foreground">{p.texto}</span>
        </blockquote>
      ))}
    </div>
  )
}

function Recorrido({ pasos, extras }: { pasos: Paso[]; extras: (ReactNode | null)[] }) {
  return (
    <ol aria-label="Cómo se decidió" className="space-y-0">
      {pasos.map((p, i) => (
        <li key={p.titulo} className="relative grid grid-cols-[22px_1fr] gap-2.5 pb-3 last:pb-0">
          {i < pasos.length - 1 && <span aria-hidden className="absolute left-[10px] top-5 bottom-0 w-0.5 bg-border" />}
          <span className={cn("z-10 grid size-[22px] place-items-center rounded-full border-2 bg-card text-[11px] font-semibold", PASO[p.estado])}>{i + 1}</span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5 text-[13px] font-semibold">{p.titulo}
              {p.etiqueta && <span className="text-[11.5px] font-normal text-muted-foreground">{p.etiqueta}</span>}
            </div>
            {p.texto && <div className="text-[12.5px] text-muted-foreground [overflow-wrap:anywhere]">{p.texto}</div>}
            {extras[i]}
          </div>
        </li>
      ))}
    </ol>
  )
}

export function InspectorDecision({ d, onVerIncidente, onVerTrazas, onVerAtacante, onVerContenciones }: {
  d: Decision; onVerIncidente?: (d: Decision) => void; onVerTrazas?: () => void
  onVerAtacante?: (ip: string) => void; onVerContenciones?: () => void
}) {
  const [det, setDet] = useState<Detalle | { error: string }>()
  useEffect(() => {
    let vivo = true
    if (d.id_decision) getTrazaDetalle(d.id_decision, d.indice).then((x) => { if (vivo) setDet(x) })
    return () => { vivo = false }
  }, [d.id_decision, d.indice])
  const detalle = det && !("error" in det) ? det : null
  const pasos = pasosDe(d, detalle)
  const des = desenlaceDe(d)
  const c = detalle ? contencionDe(detalle) : null
  const ev = (detalle?.justificacion_estructurada?.evidencia ?? {}) as Record<string, unknown>
  // Si la contención escaló, el impacto es el del dispositivo que contuvo, no el del activo.
  const efectivo = detalle?.escalada?.resultado === "mitigado" ? detalle.escalada.impacto_efectivo?.motivo : null
  const motivo = efectivo ?? detalle?.impacto_determinado?.motivo
  const cascada = detalle?.impacto_determinado?.activos_afectados_en_cascada ?? []
  const propuesta = detalle?.accion_propuesta, final = detalle?.accion_final
  const runbook = pasosRunbook(d.clase)
  const pequeno = "mt-1 text-xs text-muted-foreground"
  const extras: (ReactNode | null)[] = [
    Object.keys(ev).length ? (
      <ul key="ev" className="mt-1 space-y-0.5 text-xs">{Object.entries(ev).map(([k, v]) => <li key={k}><span className="text-muted-foreground">{k}:</span> <span className="font-mono">{String(v)}</span></li>)}</ul>
    ) : null,
    null,
    motivo ? <p key="motivo" className={pequeno}>{motivo}</p> : null,
    detalle ? (
      <Fragment key="politica">
        {propuesta && propuesta !== final && <p className="mt-1 font-mono text-xs">{`${propuesta} → ${final ?? "ninguna"}`}</p>}
        {detalle.veredicto_escalada && <p className={pequeno}>{`escalada ${detalle.veredicto_escalada === "aprobar" ? "aprobada" : "rechazada"} por el analista`}</p>}
      </Fragment>
    ) : null,
    null,
    c ? (
      <div key="ejecucion" className="mt-1 space-y-0.5 text-xs">
        <p className={cn("font-medium", c.estado === "contenida" ? "text-ok" : c.estado === "fallida" ? "text-critico" : "text-muted-foreground")}>{FRASE[c.estado](c)}</p>
        {c.accion && (
          <p className="flex flex-wrap gap-x-3 text-muted-foreground"><span>{c.accion}</span><span>ejecutada: {c.ejecutada ? "sí" : "no"}</span><span>verificada: {c.verificada ? "sí" : "no"}</span></p>
        )}
        {c.comando && <p className="font-mono text-muted-foreground [overflow-wrap:anywhere]">{c.comando}</p>}
        {c.causa && <LineaCausa causa={c.causa} equipo={c.intento?.nodo ?? detalle?.orden?.nodo_objetivo} prefijo={c.intento ? "intento en" : undefined} />}
        {!c.causa && c.intento && <p className="text-muted-foreground">{`intento en ${c.intento.nodo ?? "el activo"}: ${c.intento.ejecutada ? "se ejecutó pero no se verificó" : "no respondió"}`}</p>}
        {c.respaldo && <p className="rounded border border-aviso/40 bg-aviso/10 px-2 py-1 text-foreground">Salto de respaldo: {c.respaldo}. Corrige el perfil.</p>}
        {c.fallosEscalada?.map((f, i) => <LineaCausa key={`${f.dispositivo}-${i}`} causa={f.causa} equipo={f.dispositivo} prefijo="escalada en" />)}
      </div>
    ) : null,
  ]
  return (
    <section aria-label="Decisión" className="overflow-hidden rounded-lg border border-border bg-card text-sm lg:sticky lg:top-3">
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-base font-semibold">
          <span>{d.activo ?? "—"} · {d.clase ? etiquetaClase(d.clase) : "—"} → {d.accion_final ?? "ninguna"}</span>
          <span className={cn("rounded px-1.5 text-[11px] font-medium", PILDORA[des.tono])}>{des.texto}</span>
        </div>
        <div className="text-xs text-muted-foreground">
          {[`decisión ${d.id_decision ?? "—"}`, d.timestamp ? `${new Date(d.timestamp).toLocaleDateString(undefined, { day: "numeric", month: "short" })}, ${horaLocal(d.timestamp)}` : null, d.origen_ip, d.enriquecimiento_origen?.geo?.pais].filter(Boolean).join(" · ")}
        </div>
      </div>

      {cascada.length > 0 && (
        <div className="border-b border-border px-4 py-3">
          <div className="rounded-md border border-critico/40 bg-critico/10 px-3 py-2 text-[13px]">
            <div className="flex items-center gap-1.5 font-semibold text-critico"><TriangleAlert className="size-4 shrink-0" /> Riesgo de cascada</div>
            <p className="mt-0.5">Contener aquí aísla un activo del que otros dependen: caerían en cascada <b className="font-medium">{cascada.join(", ")}</b>.</p>
          </div>
        </div>
      )}

      <Seccion titulo="Cómo se decidió" extra={<span>6 pasos</span>}>
        {!det ? <p className="mb-2 text-xs text-muted-foreground">cargando detalle…</p>
          : "error" in det ? <p className="mb-2 text-xs text-muted-foreground">no se pudo cargar el detalle de esta decisión; se enseña lo que trae la lista.</p> : null}
        <Recorrido pasos={pasos} extras={extras} />
      </Seccion>

      {detalle && (
        <Seccion titulo="Justificación" extra={<span className={cn("rounded px-1.5 py-px text-[10.5px] font-medium", esLLM(detalle.version_justificador) ? "bg-violeta/15 text-violeta" : "bg-enrutado/15 text-enrutado")}>
          {esLLM(detalle.version_justificador) ? (d.con_rag || (detalle.pasajes ?? []).length ? "LLM + RAG" : "LLM") : "plantilla"}</span>}>
          <p className="text-[13px] leading-relaxed">{detalle.justificacion ?? "—"}</p>
          {detalle.justificacion_descartada && (
            <div className="mt-2 rounded-md border border-dashed border-border p-2 text-xs text-muted-foreground">
              <p>El modelo respondió, pero su texto se descartó: {detalle.justificacion_descartada.motivo}</p>
              {detalle.justificacion_descartada.texto && <p className="mt-1 italic">«{detalle.justificacion_descartada.texto}»</p>}
            </div>
          )}
          <div className="mt-2"><div className="mb-1 text-[11px] text-muted-foreground">Conocimiento recuperado (RAG)</div>
            <Pasajes pasajes={detalle.pasajes ?? []} consulta={detalle.consulta_rag} /></div>
        </Seccion>
      )}

      {d.enriquecimiento_origen && (
        <Seccion titulo="Origen">
          <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs">{d.origen_ip ?? "—"}</span><OrigenBadges e={d.enriquecimiento_origen} /></div>
        </Seccion>
      )}

      {(runbook.length > 0 || detalle?.recomendacion?.respuesta) && (
        <Seccion titulo="Qué hacer después">
          {detalle?.recomendacion?.respuesta && (
            <div className="mb-2 text-[13px]">
              <span className="text-muted-foreground">Recomendación: </span>
              {detalle.recomendacion.respuesta === "endurecer_servicio" && detalle.recomendacion.servicio
                ? `Endurecer el servicio ${detalle.recomendacion.servicio}` : detalle.recomendacion.respuesta}
              {detalle.recomendacion.ruta ? ` → ${detalle.recomendacion.ruta}` : ""}
              {detalle.recomendacion.nota && <div className="text-xs text-muted-foreground">{detalle.recomendacion.nota}</div>}
            </div>
          )}
          {runbook.length > 0 && (
            <div><div className="mb-1 text-[11px] text-muted-foreground">Respuesta recomendada (runbook)</div>
              <ol className="list-decimal space-y-0.5 pl-4 text-xs text-muted-foreground">{runbook.map((p, i) => <li key={i}>{p}</li>)}</ol></div>
          )}
        </Seccion>
      )}

      <div className="flex flex-wrap gap-3 bg-muted px-4 py-3 text-xs font-medium">
        {onVerIncidente && <button onClick={() => onVerIncidente(d)} className="text-info hover:underline">Ver el grafo del incidente</button>}
        {onVerTrazas && <button onClick={onVerTrazas} className="text-info hover:underline">Ver en Trazas (prueba de integridad)</button>}
        {onVerAtacante && d.origen_ip && <button onClick={() => onVerAtacante(d.origen_ip!)} className="text-info hover:underline">Perfil del atacante</button>}
        {onVerContenciones && d.contencion === "contenida" && <button onClick={onVerContenciones} className="text-info hover:underline">Ver la contención</button>}
      </div>
    </section>
  )
}

// Cifra de la franja de resultados: pulsarla filtra la lista por ese desenlace (y otra vez, lo quita).
function Cifra({ k, v, sub, cls, f, actual, elegir }: {
  k: string; v: number; sub?: string; cls?: string; f: FiltroDecision; actual: FiltroDecision; elegir: (f: FiltroDecision) => void
}) {
  return (
    <button type="button" onClick={() => elegir(actual === f ? "todas" : f)} aria-pressed={actual === f}
      className={cn("border-r border-border px-3.5 py-2 text-left last:border-r-0 hover:bg-muted/50", actual === f && f !== "todas" && "bg-primary/10")}>
      <div className="text-[11px] text-muted-foreground">{k}</div>
      <div className={cn("text-lg font-semibold tabular-nums", cls)}>{v} {sub && <small className="text-xs font-normal text-muted-foreground">{sub}</small>}</div>
    </button>
  )
}

// Línea de un registro que no es una decisión (supresión, reversión, error, actividad propia).
function LineaSistema({ d }: { d: Decision }) {
  const texto = d.tipo === "actividad_propia" ? `↺ actividad propia del MDR en ${d.activo}: login de gestión al aplicar o verificar una contención (no es un ataque)`
    : d.tipo === "reversion" ? `↶ reversión de ${d.id_decision_revertida ?? "—"} en ${d.nodo ?? "—"}: ${d.exito ? "aplicada" : "falló"}${d.accion_id ? ` (${d.accion_id})` : ""}`
    : d.tipo === "error" ? `✗ ${d.id_decision}: error al procesar el incidente de ${d.origen_ip ?? "—"} → ${d.activo ?? "—"}: ${d.error}`
    : d.tipo === "actividad_suprimida" ? `↩ el ataque continúa · ${d.alertas_suprimidas} alerta(s) suprimida(s) (ya decidido)`
    : `${d.tipo}`
  return (
    <div data-sistema className={cn("grid grid-cols-[86px_1fr] gap-2.5 border-b border-border px-3.5 py-1.5 text-xs [overflow-wrap:anywhere]", d.tipo === "error" ? "text-critico" : "italic text-muted-foreground")}>
      <span className="whitespace-nowrap font-mono not-italic">{horaLocal(d.timestamp)}</span><span>{texto}</span>
    </div>
  )
}

function LineaDecision({ d, activa, onAbrir }: { d: Decision; activa: boolean; onAbrir: () => void }) {
  const des = desenlaceDe(d)
  const quien = quienDecidio(d) ?? (d.requiere_humano ? "espera a un analista" : "automática")
  return (
    <button type="button" onClick={onAbrir} aria-current={activa} aria-label={`ver detalle de ${d.activo ?? d.id_decision ?? "la decisión"}`}
      className={cn("grid w-full grid-cols-[86px_minmax(0,1fr)_auto] items-center gap-2.5 border-b border-border px-3.5 py-2 text-left text-[13px] hover:bg-muted/50",
        activa && "bg-primary/10 shadow-[inset_3px_0_0_var(--primary)]")}>
      <span className="whitespace-nowrap font-mono text-[11.5px] text-muted-foreground" title={d.timestamp ?? undefined}>{horaLocal(d.timestamp)}</span>
      <span className="min-w-0">
        <span className="flex items-center gap-1.5 overflow-hidden whitespace-nowrap">
          <b className="font-semibold">{d.activo ?? "—"}</b><span className="text-muted-foreground/60">·</span>
          <span>{d.clase ? etiquetaClase(d.clase) : "—"}</span><span className="text-muted-foreground/60">→</span>
          {d.accion_final ? <b className="font-semibold">{d.accion_final}</b>
            : d.resultado_filtro === "veta" && d.accion_propuesta ? <s className="text-muted-foreground">{d.accion_propuesta}</s>
            : <span className="text-muted-foreground">—</span>}
          <span className={cn("shrink-0 rounded px-1.5 text-[11px] font-medium", PILDORA[des.tono])}
            title={des.id === "degradada" ? `propuesta: ${d.accion_propuesta ?? "—"}` : undefined}>{des.texto}</span>
          {des.degradada && des.id !== "degradada" && <span className="shrink-0 rounded bg-aviso/15 px-1.5 text-[11px] font-medium text-aviso" title={`propuesta: ${d.accion_propuesta ?? "—"}`}>degradada</span>}
        </span>
        <span className="block truncate text-[11.5px] text-muted-foreground">
          {d.clase_reclasificada ? `reclasificada: ${d.clase} → ${d.clase_reclasificada}`
            : [d.origen_ip, d.enriquecimiento_origen?.geo?.pais, quien, d.cascada?.length ? `tumba en cascada: ${d.cascada.join(", ")}` : null].filter(Boolean).join(" · ")}
        </span>
      </span>
      <span className="flex flex-col items-end gap-1">
        <Prioridad n={d.prioridad} />
        {d.confianza != null && <span className="h-1 w-14 overflow-hidden rounded-sm bg-muted" title={`confianza ${d.confianza}`}><span className="block h-full bg-primary" style={{ width: `${Math.round(d.confianza * 100)}%` }} /></span>}
      </span>
    </button>
  )
}

export function Decisiones({ equipo = null, textoInicial = "", onQuitarEquipo, onVerIncidente, onVerTrazas, onVerAtacante, onVerContenciones }: {
  equipo?: string | null; textoInicial?: string; onQuitarEquipo?: () => void; onVerIncidente?: (d: Decision) => void
  onVerTrazas?: () => void; onVerAtacante?: (ip: string) => void; onVerContenciones?: () => void
} = {}) {
  const r = useSondeo(getDecisiones)
  const [actual, setActual] = useState<string | null>(null)
  const [filtro, setFiltro] = useState<Filtro>({ texto: textoInicial, clase: "" })
  // Al pivotar desde otra vista (p. ej. clic en una IP atacante) se siembra el filtro de texto.
  useEffect(() => setFiltro((f) => ({ ...f, texto: textoInicial })), [textoInicial])
  const [desenlace, setDesenlace] = useState<FiltroDecision>("todas")
  const [pagina, setPagina] = useState(1)
  const [tam, setTam] = useState(TAM_PAGINA)
  const [soloMias, setSoloMias] = useState(false)    // «mi cola»: solo las asignadas al operador actual
  // Los registros de sistema (actividad propia, supresiones, reversiones, errores) tienen su sitio en
  // Trazas; aquí se ocultan por defecto para que se lean las decisiones.
  const [conSistema, setConSistema] = useState(false)
  // Al cambiar filtro, equipo, desenlace o «mías» la lista cambia de tamaño: se vuelve a la primera página.
  useEffect(() => setPagina(1), [filtro.texto, filtro.clase, equipo, soloMias, desenlace, conSistema])
  const elegirTam = (t: number) => { setTam(t); setPagina(1) }
  if (!r) return <Cargando />
  // C2: con la conexión perdida pero datos previos, se conserva la lista congelada con aviso.
  const fallo = "error" in r ? r : null
  const ds = "error" in r ? r.datos : r
  if (!ds) return <SinConexion causa={fallo?.causa} />
  if (ds.length === 0) return <Vacio>Aún no hay decisiones. Lanza un ataque para verlas aquí.</Vacio>
  const yo = operadorActual().trim()
  const casos = estadoDeCasos(ds)
  const base = filtrarDecisiones(ds, { ...filtro, equipo })
  const mias = soloMias && yo ? base.filter((x) => casos[x.id_decision ?? ""]?.asignado === yo) : base
  const filtradas = mias.filter((x) => pasaFiltro(x, desenlace, yo) && (conSistema || !x.tipo || x.tipo === "decision"))
  const decididasPorMi = yo ? base.filter((x) => pasaFiltro(x, "decididas_por_mi", yo)).length : 0
  const pag = paginar(filtradas, pagina, tam)
  const ventana = ventanaDe(ds)
  const res = resumenDecisiones(base)
  const decisionesVisibles = filtradas.map((x, i) => ({ x, clave: claveDe(x, i) })).filter(({ x }) => !x.tipo || x.tipo === "decision")
  const elegida = decisionesVisibles.find((e) => e.clave === actual) ?? decisionesVisibles[0] ?? null
  const pct = (n: number) => (res.total ? `${Math.round((n / res.total) * 100)} %` : "")
  return (
    <div className="space-y-3">
      {fallo && <DatosCongelados fallo={fallo} />}
      <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-border bg-card sm:grid-cols-3 lg:grid-cols-6">
        <Cifra actual={desenlace} elegir={setDesenlace} k="Decisiones" v={res.total} sub={ventana ? "ventana" : undefined} f="todas" />
        <Cifra actual={desenlace} elegir={setDesenlace} k="Contenidas en automático" v={res.autoContenidas} sub={pct(res.autoContenidas)} cls="text-ok" f="contenidas" />
        <Cifra actual={desenlace} elegir={setDesenlace} k="Pasaron por un analista" v={res.humano} sub={`${res.aprobadas} aprobadas`} f="pendientes" />
        <Cifra actual={desenlace} elegir={setDesenlace} k="Corregidas por el analista" v={res.corregidas} sub={`${res.rechazadas} rechaz. · ${res.reclasificadas} reclasif.`} cls={res.corregidas ? "text-aviso" : undefined} f="corregidas" />
        <Cifra actual={desenlace} elegir={setDesenlace} k="Frenadas por la política" v={res.frenadas} sub={`${res.degradadas} degrad. · ${res.vetadas} vetadas`} f="frenadas" />
        <Cifra actual={desenlace} elegir={setDesenlace} k="Contención fallida" v={res.fallidas} sub={res.fallidas ? "revisar" : undefined} cls={res.fallidas ? "text-critico" : undefined} f="fallidas" />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <BarraFiltros f={filtro} set={setFiltro} clases={clasesDe(ds)} cuenta={filtradas.length} equipo={equipo} onQuitarEquipo={onQuitarEquipo} />
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <div role="group" aria-label="Filtrar por desenlace" className="flex flex-wrap gap-1">
          {FILTROS_DECISION.filter((f) => f.id !== "decididas_por_mi" || yo).map((f) => (
            <button key={f.id} aria-pressed={desenlace === f.id} onClick={() => setDesenlace(f.id)}
              className={cn("rounded-full border px-2.5 py-0.5 transition-colors", desenlace === f.id ? "border-primary/45 bg-primary/12 font-medium text-foreground" : "border-border text-muted-foreground hover:text-foreground")}>
              {f.nombre}{f.id === "decididas_por_mi" ? ` · ${decididasPorMi}` : ""}
            </button>
          ))}
        </div>
        <span className="ml-auto flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-muted-foreground">
            <input type="checkbox" checked={conSistema} onChange={(e) => setConSistema(e.target.checked)} className="size-3.5 accent-[var(--primary)]" />
            Incluir registros del sistema
          </label>
          <label className={yo ? "flex items-center gap-1.5 text-foreground" : "flex items-center gap-1.5 text-muted-foreground"}>
            <input type="checkbox" checked={soloMias && !!yo} disabled={!yo} onChange={(e) => setSoloMias(e.target.checked)} className="size-3.5 accent-[var(--primary)]" />
            Solo mías{yo ? ` (asignadas a ${yo})` : ""}
          </label>
        </span>
      </div>
      {ventana && (
        // A7: el listado son los ÚLTIMOS registros, no el histórico — que el contador no lo sugiera.
        <p className="text-xs text-muted-foreground">mostrando las últimas {ventana.mostrados} de {ventana.total} decisiones; el histórico completo está en «Informe» y en «Trazas».</p>
      )}

      <div className="grid items-start gap-3.5 lg:grid-cols-[minmax(0,1.25fr)_minmax(380px,1fr)]">
        <div className="space-y-3">
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            {filtradas.length === 0 && <p className="px-4 py-6 text-sm text-muted-foreground">Ninguna decisión con este filtro.</p>}
            {pag.filas.map((x, i) => {
              const clave = claveDe(x, pag.desde + i)
              const dia = claveDia(x.timestamp)
              // el día de la fila anterior CON hora (las supresiones no la traen y repetían el separador)
              const anterior = pag.filas.slice(0, i).map((y) => claveDia(y.timestamp)).filter(Boolean).pop() ?? ""
              const cabecera = dia && dia !== anterior ? etiquetaDia(dia, claveDia(new Date().toISOString())) : null
              return (
                <div key={clave}>
                  {cabecera && <div className="border-b border-border bg-muted px-3.5 py-1 text-[11px] text-muted-foreground">{cabecera}</div>}
                  {x.tipo && x.tipo !== "decision"
                    ? <LineaSistema d={x} />
                    : <LineaDecision d={x} activa={elegida?.clave === clave} onAbrir={() => setActual(clave)} />}
                </div>
              )
            })}
          </div>
          <Paginador pagina={pag.pagina} paginas={pag.paginas} total={pag.total} tam={tam} onPagina={setPagina} onTam={elegirTam} />
        </div>
        {elegida
          ? <InspectorDecision key={elegida.clave} d={elegida.x} onVerIncidente={onVerIncidente} onVerTrazas={onVerTrazas} onVerAtacante={onVerAtacante} onVerContenciones={onVerContenciones} />
          : <div className="rounded-lg border border-dashed border-border bg-card px-4 py-5 text-sm text-muted-foreground">Selecciona una decisión para ver cómo se decidió.</div>}
      </div>
    </div>
  )
}
