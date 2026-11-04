import { useState } from "react"
import type { Decision, NodoRed, WatchEntrada } from "@/api"
import { ESTADO_VISUAL } from "@/components/MapaRed"
import { Prioridad, RiesgoBadge } from "@/components/bits"
import { Tendencia, type Segmento } from "./charts"
import { etiquetaClase, colorClase, agruparPorDia, atacantesDe, agruparPorSubred, riesgoEquipo, enWatchlist } from "@/datos"
import { CATEGORICO_LIGHT, CATEGORICO_DARK } from "@/theme"
import { useTema } from "@/tema"

const TOP_ATACANTES = 8

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

export function PanelEquipo({ nodo, eventos, todos = [], watchlist = [], onVerDecisiones, onVerOrigen, onVerAtacante }: {
  nodo: NodoRed; eventos: Decision[]; todos?: Decision[]; watchlist?: WatchEntrada[]; onVerDecisiones: () => void
  onVerOrigen?: (texto: string) => void        // bloque/subred → Decisiones filtradas
  onVerAtacante?: (ip: string) => void          // una IP → su perfil de atacante
}) {
  const a = nodo.actividad
  const v = ESTADO_VISUAL[a.estado] ?? ESTADO_VISUAL.sin_actividad
  const CAT = useTema().oscuro ? CATEGORICO_DARK : CATEGORICO_LIGHT
  const atacantes = atacantesDe(eventos, nodo.nombre, todos)
  // Con muchos orígenes (p. ej. una campaña que rota IPs del mismo /24) se agrupa por subred por
  // defecto: una campaña = una fila. Con pocos, por IP. El conmutador deja alternar.
  const [modo, setModo] = useState<"ip" | "subred">(atacantes.length > TOP_ATACANTES ? "subred" : "ip")
  const subredes = agruparPorSubred(atacantes)
  // Gráficas derivadas de la ventana de eventos del equipo (los conteos ya los da `nodo.actividad`).
  const total = eventos.length
  const porClase = eventos.reduce<Record<string, number>>((m, d) => {
    if (d.clase) m[d.clase] = (m[d.clase] ?? 0) + 1
    return m
  }, {})
  const segClase: Segmento[] = Object.keys(porClase).sort()
    .map((c) => ({ name: etiquetaClase(c), value: porClase[c], fill: colorClase(c, CAT) }))
    .sort((x, y) => y.value - x.value)   // barras: la clase más frecuente arriba
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
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
          <span>{v.icono} {v.texto}</span>
          <RiesgoBadge r={riesgoEquipo(nodo, eventos)} />
        </div>
      </div>
      {/* las cifras del equipo, en una fila que se lee de un vistazo (los conteos los da `actividad`) */}
      <dl className="grid grid-cols-4 overflow-hidden rounded-md border border-border">
        {([["recibidos", a.objetivo, a.objetivo ? "text-critico" : ""], ["originados", a.origen, ""],
           ["contenidos aquí", a.contuvo_aqui, a.contuvo_aqui ? "text-ok" : ""], ["pendientes", a.pendientes, a.pendientes ? "text-aviso" : ""]] as const).map(([k, v, cls]) => (
          <div key={k} className="border-r border-border px-1 py-1.5 text-center last:border-r-0">
            <dd className={`text-lg font-semibold leading-tight tabular-nums ${cls}`}>{v}</dd>
            <dt className="text-[10px] text-muted-foreground">{k}</dt>
          </div>
        ))}
      </dl>
      <div className="text-xs text-muted-foreground">último: {hora(a.ultima)}</div>
      {total > 0 && (
        <div className="space-y-3 border-t border-border pt-2">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="mb-1 text-xs text-muted-foreground">Por clase · {totalClasificado} eventos</div>
              {/* barras con cifra: se leen en 360 px mejor que una dona */}
              <ul aria-label="Por clase" className="space-y-1">
                {segClase.map((s) => (
                  <li key={s.name} className="grid grid-cols-[10px_1fr_28px] items-center gap-1.5 text-[11px]">
                    <span className="size-2.5 rounded-[3px]" style={{ background: s.fill }} />
                    <span className="flex items-center gap-1.5"><span className="truncate text-muted-foreground">{s.name}</span>
                      <span className="h-1.5 flex-1 rounded-sm bg-muted"><span className="block h-full rounded-r-sm" style={{ width: `${Math.round((s.value / (segClase[0]?.value || 1)) * 100)}%`, background: s.fill }} /></span></span>
                    <span className="text-right font-medium tabular-nums">{s.value}</span>
                  </li>
                ))}
              </ul>
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
          <div className="flex items-center justify-between gap-2">
            <div className="font-heading text-xs font-semibold">Atacantes de este equipo (correlación)</div>
            <div className="flex gap-1.5 text-xs">
              <button onClick={() => setModo("ip")}
                className={modo === "ip" ? "font-semibold" : "text-muted-foreground hover:underline"}>por IP</button>
              <span className="text-muted-foreground">·</span>
              <button onClick={() => setModo("subred")}
                className={modo === "subred" ? "font-semibold" : "text-muted-foreground hover:underline"}>por subred</button>
            </div>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="font-normal">{modo === "subred" ? "Bloque de origen" : "Origen"}</th>
                <th className="font-normal">Gravedad</th><th className="font-normal">Ataques</th>
                <th className="font-normal">También en</th>
              </tr>
            </thead>
            <tbody>
              {modo === "subred"
                ? subredes.slice(0, TOP_ATACANTES).map((s) => (
                  <tr key={s.cidr}>
                    <td className="py-0.5">
                      {onVerOrigen
                        ? <button onClick={() => onVerOrigen(s.prefijo)}
                            className="font-mono underline-offset-2 hover:underline" title="Ver las decisiones del bloque">{s.cidr}</button>
                        : <span className="font-mono">{s.cidr}</span>}
                      <span className="ml-1 text-muted-foreground">· {s.ips} IP{s.ips === 1 ? "" : "s"}{s.alcance ? ` · ${s.alcance}` : ""}</span>
                    </td>
                    <td><Prioridad n={s.prioridad || null} /></td>
                    <td className="tabular-nums">×{s.n}</td>
                    <td className="text-muted-foreground">
                      {s.otrosEquipos.length ? <span title={s.otrosEquipos.join(", ")}>{s.otrosEquipos.length} equipo(s)</span> : "—"}
                    </td>
                  </tr>
                ))
                : atacantes.slice(0, TOP_ATACANTES).map((at) => (
                  <tr key={at.ip}>
                    <td className="py-0.5">
                      {enWatchlist(at.ip, watchlist) && <span title={enWatchlist(at.ip, watchlist)?.nota ?? "en la watchlist"}>⚑ </span>}
                      {(onVerAtacante ?? onVerOrigen)
                        ? <button onClick={() => (onVerAtacante ?? onVerOrigen)!(at.ip)}
                            className="font-mono underline-offset-2 hover:underline" title="Ver el perfil del atacante">{at.ip}</button>
                        : <span className="font-mono">{at.ip}</span>}
                      {at.alcance && <span className="ml-1 text-muted-foreground">· {at.alcance}</span>}
                    </td>
                    <td><Prioridad n={at.prioridad || null} /></td>
                    <td className="tabular-nums">×{at.n}</td>
                    <td className="text-muted-foreground">
                      {at.otrosEquipos.length ? <span title={at.otrosEquipos.join(", ")}>{at.otrosEquipos.length} equipo(s)</span> : "—"}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          {atacantes.length > TOP_ATACANTES && (
            <button onClick={onVerDecisiones} className="text-xs text-info hover:underline">
              Ver los {atacantes.length} orígenes en Decisiones →
            </button>
          )}
        </div>
      )}
      <details className="border-t border-border pt-2">
        <summary className="cursor-pointer font-heading text-xs font-semibold text-muted-foreground">
          Eventos recientes ({eventos.length})
        </summary>
        <ul className="mt-2 space-y-2">
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
      </details>
      <button onClick={onVerDecisiones} className="text-sm text-info hover:underline">Ver en Decisiones →</button>
    </div>
  )
}
