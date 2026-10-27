import type { Decision, NodoRed } from "@/api"
import { ESTADO_VISUAL } from "@/components/MapaRed"
import { Donut, Tendencia, type Segmento } from "./charts"
import { etiquetaClase, colorClase, agruparPorDia, atacantesDe } from "@/datos"
import { CATEGORICO_LIGHT, CATEGORICO_DARK } from "@/theme"
import { useTema } from "@/tema"

const ETIQUETA: Record<string, string> = { objetivo: "objetivo", origen: "origen", contuvo_aqui: "contuvo aquí" }
const DESENLACE: Record<string, (d: Decision) => string> = {
  contenida: (d) => `✓ contenida en ${d.dispositivo ?? "—"}`,
  fallida: () => "✕ contención fallida",
  retenida: () => "retenida por el analista",
  cancelada: () => "escalada rechazada",
  degradada: () => "degradada",
  enrutada: (d) => `enrutada a ${d.dispositivo ?? "—"}`,
  sin_accion: () => "sin contención",
}
// Un timestamp que Date no sepa leer (p. ej. «+0000» en Safari) se muestra tal cual: format() lanzaría RangeError.
const hora = (ts?: string | null) => {
  if (!ts) return "—"
  const t = new Date(ts)
  return isNaN(t.getTime()) ? ts : new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(t)
}

export function PanelEquipo({ nodo, eventos, todos = [], onVerDecisiones }: {
  nodo: NodoRed; eventos: Decision[]; todos?: Decision[]; onVerDecisiones: () => void
}) {
  const a = nodo.actividad
  const v = ESTADO_VISUAL[a.estado] ?? ESTADO_VISUAL.sin_actividad
  const CAT = useTema().oscuro ? CATEGORICO_DARK : CATEGORICO_LIGHT
  const atacantes = atacantesDe(eventos, nodo.nombre, todos)
  // Resumen de la ventana de eventos del equipo (lo que ya llega del feed): conteos + gráficas.
  const total = eventos.length
  const auto = eventos.filter((d) => d.requiere_humano === false).length
  const retenido = eventos.filter((d) => d.contencion === "retenida").length
  const contenido = eventos.filter((d) => d.contencion === "contenida").length
  const porClase = eventos.reduce<Record<string, number>>((m, d) => {
    if (d.clase) m[d.clase] = (m[d.clase] ?? 0) + 1
    return m
  }, {})
  const segClase: Segmento[] = Object.keys(porClase).sort()
    .map((c) => ({ name: etiquetaClase(c), value: porClase[c], fill: colorClase(c, CAT) }))
  // El total del donut es la suma de sus porciones (eventos con clase), para que el centro cuadre
  // con las porciones aunque algún evento venga sin clase.
  const totalClasificado = segClase.reduce((s, x) => s + x.value, 0)
  const porDia = agruparPorDia(eventos)
  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4 text-sm">
      <div>
        <div className="font-heading text-base font-semibold">{nodo.nombre}
          <span className="ml-2 text-xs font-normal text-muted-foreground">{nodo.ip ?? ""}{nodo.zona ? ` · ${nodo.zona}` : ""}</span>
        </div>
        {nodo.funcion && <div className="text-muted-foreground">{nodo.funcion}</div>}
        <div className="text-xs text-muted-foreground">
          {nodo.criticidad ? `criticidad ${nodo.criticidad}` : ""}
          {nodo.servicios_prestados?.length ? ` · servicios ${nodo.servicios_prestados.join(", ")}` : ""}
          {nodo.depende_de?.length ? ` · depende de ${nodo.depende_de.join(", ")}` : ""}
        </div>
        <div className="mt-1 text-xs">{v.icono} {v.texto}</div>
      </div>
      <div className="flex flex-wrap gap-1.5 text-xs">
        <span className="rounded bg-rose-500/15 px-1.5 py-0.5">{a.objetivo} recibidos</span>
        <span className="rounded bg-slate-500/15 px-1.5 py-0.5">{a.origen} originados</span>
        <span className="rounded bg-emerald-500/15 px-1.5 py-0.5">{a.contuvo_aqui} contenidos aquí</span>
        <span className="rounded bg-amber-400/20 px-1.5 py-0.5">{a.pendientes} pendientes</span>
      </div>
      {total > 0 && (
        <div className="space-y-3 border-t border-border pt-2">
          <div className="flex flex-wrap gap-1.5 text-xs">
            <span className="rounded bg-muted px-1.5 py-0.5">{total} en la ventana</span>
            <span className="rounded bg-sky-500/15 px-1.5 py-0.5">{auto} automática(s)</span>
            <span className="rounded bg-amber-400/20 px-1.5 py-0.5">{retenido} retenida(s)</span>
            <span className="rounded bg-emerald-500/15 px-1.5 py-0.5">{contenido} contenida(s)</span>
            <span className="rounded px-1.5 py-0.5 text-muted-foreground">último: {hora(a.ultima)}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="mb-1 text-xs text-muted-foreground">Por clase</div>
              <Donut data={segClase} total={totalClasificado} unidad="eventos" />
            </div>
            <div>
              <div className="mb-1 text-xs text-muted-foreground">Actividad por día</div>
              <Tendencia data={porDia} />
            </div>
          </div>
        </div>
      )}
      {atacantes.length > 0 && (
        <div className="space-y-1 border-t border-border pt-2">
          <div className="text-xs text-muted-foreground">Atacantes de este equipo (correlación)</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="font-normal">Origen</th><th className="font-normal">Ataques</th>
                <th className="font-normal">Alcance</th><th className="font-normal">También en</th>
              </tr>
            </thead>
            <tbody>
              {atacantes.slice(0, 8).map((at) => (
                <tr key={at.ip}>
                  <td className="font-mono">{at.ip}</td>
                  <td className="tabular-nums">×{at.n}</td>
                  <td>{at.alcance ?? "—"}</td>
                  <td className="text-muted-foreground">
                    {at.otrosEquipos.length
                      ? <span title={at.otrosEquipos.join(", ")}>{at.otrosEquipos.length} equipo(s)</span>
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {atacantes.length > 8 && (
            <div className="text-xs text-muted-foreground">+{atacantes.length - 8} orígenes más</div>
          )}
        </div>
      )}
      <ul className="space-y-2 border-t border-border pt-2">
        {eventos.length === 0 && <li className="text-muted-foreground">Sin eventos en la traza reciente.</li>}
        {eventos.length > 30 && (
          <li className="text-xs text-muted-foreground">Mostrando los 30 más recientes de {eventos.length}.</li>
        )}
        {eventos.slice(0, 30).map((d) => (
          <li key={d.indice ?? d.id_decision} className="space-y-0.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-muted-foreground">{hora(d.timestamp)}</span>
              {(d.relaciones?.[nodo.nombre] ?? []).map((e) => (
                <span key={e} className="rounded bg-muted px-1.5 text-xs">{ETIQUETA[e] ?? e}</span>
              ))}
              <span className="font-mono text-xs">{d.origen_ip ?? "—"}</span>
              <span className="text-xs">{d.clase ?? "—"}</span>
            </div>
            <div className="text-xs text-muted-foreground">{(DESENLACE[d.contencion ?? ""] ?? (() => d.contencion ?? ""))(d)}</div>
          </li>
        ))}
      </ul>
      <button onClick={onVerDecisiones} className="text-sm text-sky-600 hover:underline dark:text-sky-400">Ver en Decisiones →</button>
    </div>
  )
}
