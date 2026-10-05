import type { Decision, NodoRed } from "@/api"
import { ESTADO_VISUAL } from "@/components/MapaRed"

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

export function PanelEquipo({ nodo, eventos, onVerDecisiones }: {
  nodo: NodoRed; eventos: Decision[]; onVerDecisiones: () => void
}) {
  const a = nodo.actividad
  const v = ESTADO_VISUAL[a.estado] ?? ESTADO_VISUAL.sin_actividad
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
      <ul className="space-y-2 border-t border-border pt-2">
        {eventos.length === 0 && <li className="text-muted-foreground">Sin eventos en la traza reciente.</li>}
        {eventos.map((d) => (
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
