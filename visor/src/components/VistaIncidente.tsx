import { useEffect, useState } from "react"
import { ArrowLeft } from "lucide-react"
import { useSondeo, getRed, getTrazaDetalle, type Decision, type Detalle } from "@/api"
import { MapaRed, ESTADO_VISUAL } from "@/components/MapaRed"
import { Cargando, SinConexion, ClaseBadge, Prioridad } from "@/components/bits"
import { estadosDelIncidente } from "@/incidente"

const LEYENDA = ["origen", "atacado", "contenido", "en_cascada", "sin_actividad"] as const

function Campo({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{etiqueta}</div>
      <div className="mt-0.5">{children}</div>
    </div>
  )
}

// El grafo de UN incidente superpuesto en la topología (reutiliza MapaRed) + su detalle. No es un
// árbol de procesos (eso es EDR): es el recorrido por la red y la evidencia de la decisión.
export function VistaIncidente({ decision, onVolver }: { decision: Decision; onVolver: () => void }) {
  const red = useSondeo(getRed)
  const [det, setDet] = useState<Detalle | null>(null)
  useEffect(() => {
    let vivo = true
    getTrazaDetalle(decision.id_decision ?? "", decision.indice)
      .then((d) => { if (vivo && !("error" in d)) setDet(d) })
    return () => { vivo = false }
  }, [decision.id_decision, decision.indice])

  if (!red) return <Cargando />
  if ("error" in red) return <SinConexion />

  const redInc = estadosDelIncidente(decision, det, red)
  const cascada = [...new Set([
    ...(decision.cascada ?? []),
    ...(det?.impacto_determinado?.activos_afectados_en_cascada ?? []),
  ])]
  const pendiente = !!decision.requiere_humano && !decision.veredicto_humano
  const contuvo = det?.escalada?.dispositivo_ejecutor ?? (det?.ejecucion?.exito ? decision.activo : null)
  const mitre = decision.tecnica_mitre ?? det?.justificacion_estructurada?.tecnica_mitre ?? []
  const [desenlace, tono] = pendiente
    ? ["Pendiente de aprobación", "text-amber-600 dark:text-amber-400"]
    : contuvo
      ? [`Contenido en ${contuvo}`, "text-emerald-600 dark:text-emerald-400"]
      : decision.accion_final
        ? ["Contención sin verificar", "text-rose-600 dark:text-rose-400"]
        : ["Sin contención (clasificado)", "text-muted-foreground"]

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={onVolver}
          className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
          <ArrowLeft className="size-4" /> Volver
        </button>
        <div className="min-w-0">
          <h2 className="truncate font-heading text-base font-semibold">
            Incidente: <ClaseBadge clase={decision.clase} /> contra {decision.activo ?? "—"}
          </h2>
          <p className="text-xs text-muted-foreground">
            Grafo del incidente · origen <span className="font-mono">{decision.origen_ip ?? "desconocido"}</span>
          </p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="rounded-lg border border-border bg-card p-3">
          <MapaRed red={redInc} seleccionado={null} onSeleccionar={() => {}} dependencias={true} />
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {LEYENDA.map((k) => <span key={k}>{ESTADO_VISUAL[k].icono || "○"} {ESTADO_VISUAL[k].texto}</span>)}
          </div>
        </div>

        <div className="space-y-3.5 rounded-lg border border-border bg-card p-4 text-sm">
          <div className={`font-medium ${tono}`}>{desenlace}</div>

          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
            <dt className="text-muted-foreground">Severidad</dt><dd><Prioridad n={decision.prioridad} /></dd>
            <dt className="text-muted-foreground">Origen</dt><dd className="font-mono text-xs">{decision.origen_ip ?? "—"}</dd>
            <dt className="text-muted-foreground">Activo</dt><dd>{decision.activo ?? "—"}</dd>
            <dt className="text-muted-foreground">Acción</dt>
            <dd>{decision.accion_final ?? "—"}{decision.veredicto_humano ? ` (${decision.veredicto_humano})` : ""}</dd>
          </dl>

          {cascada.length > 0 && (
            <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
              <b className="text-amber-600 dark:text-amber-400">⚠ Conciencia de impacto.</b>{" "}
              Contener el origen dejaría sin servicio a {cascada.join(", ")} (dependen de él).
            </div>
          )}

          {det?.justificacion && (
            <Campo etiqueta="Descripción">
              <p className="text-xs leading-relaxed text-muted-foreground">{det.justificacion}</p>
            </Campo>
          )}

          {mitre.length > 0 && (
            <Campo etiqueta="MITRE ATT&CK">
              <div className="flex flex-wrap gap-1">
                {mitre.map((t) => (
                  <a key={t} href={`https://attack.mitre.org/techniques/${t.replace(".", "/")}/`}
                     target="_blank" rel="noopener"
                     className="rounded bg-sky-500/15 px-1.5 py-0.5 font-mono text-[10px] text-sky-600 hover:underline dark:text-sky-300">{t}</a>
                ))}
              </div>
            </Campo>
          )}

          {decision.hash && (
            <Campo etiqueta="Traza">
              <p className="break-all font-mono text-[10px] text-muted-foreground">sha256 {decision.hash}</p>
            </Campo>
          )}
        </div>
      </div>
    </div>
  )
}
