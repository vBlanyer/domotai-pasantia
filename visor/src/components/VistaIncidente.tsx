import { useCallback, useEffect, useState } from "react"
import { ArrowLeft } from "lucide-react"
import { useSondeo, getRed, getCaso, getTrazaDetalle, actualizarCaso, type Decision, type Detalle, type Caso } from "@/api"
import { MapaRed, ESTADO_VISUAL } from "@/components/MapaRed"
import { Cargando, SinConexion, ClaseBadge, Prioridad } from "@/components/bits"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
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

const ESTADO_CASO: Record<string, { texto: string; clase: string }> = {
  nuevo: { texto: "Nuevo", clase: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  en_revision: { texto: "En revisión", clase: "bg-sky-500/15 text-sky-700 dark:text-sky-300" },
  resuelto: { texto: "Resuelto", clase: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
}

// Ciclo de vida del caso de una decisión: estado, responsable y notas del analista. Cada cambio se
// añade a la traza como registro `actualizacion_caso` encadenado (no muta la decisión); el estado
// actual se pliega de ellos (estadoDeCasos). El `operador` lo sella el backend (del token, no repudio).
function PanelCaso({ idDecision }: { idDecision: string }) {
  // El caso llega YA plegado del servidor (GET /api/caso/<id>, sobre el fichero completo): no
  // «rejuvenece» al salir de la ventana de /api/trazas ni descarga la traza entera (A4). Se recarga
  // al guardar, para que el analista vea su cambio al instante, y cada 10 s por si otro lo cambia.
  const [caso, setCaso] = useState<Caso | null>(null)
  const recargar = useCallback(async () => {
    const r = await getCaso(idDecision)
    if (!("error" in r)) setCaso(r)
  }, [idDecision])
  useEffect(() => {
    setCaso(null)
    recargar()
    const t = setInterval(recargar, 10000)
    return () => clearInterval(t)
  }, [recargar])
  const estadoActual = caso?.estado ?? "nuevo"
  const [estado, setEstado] = useState("")
  const [asignado, setAsignado] = useState("")
  const [nota, setNota] = useState("")
  const [guardando, setGuardando] = useState(false)
  const toast = useToast()
  const hayCambio = !!estado || !!asignado.trim() || !!nota.trim()

  async function guardar() {
    if (!hayCambio || guardando) return
    setGuardando(true)
    const ok = await actualizarCaso(idDecision, {
      ...(estado ? { estado } : {}),
      ...(asignado.trim() ? { asignado: asignado.trim() } : {}),
      ...(nota.trim() ? { nota: nota.trim() } : {}),
    })
    setGuardando(false)
    if (ok) {
      setEstado(""); setAsignado(""); setNota("")
      recargar()   // el panel refleja el cambio al instante (sin esperar al sondeo: parecería fallido)
      toast({ type: "success", title: "Caso actualizado", description: "Queda anotado en la traza." })
    }
    else toast({ type: "error", title: "No se pudo actualizar el caso", description: "Revisa la conexión o el token de la consola." })
  }

  const badge = ESTADO_CASO[estadoActual] ?? ESTADO_CASO.nuevo
  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-heading text-sm font-semibold">Caso</span>
        <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${badge.clase}`}>{badge.texto}</span>
        {caso?.asignado && <span className="text-xs text-muted-foreground">· asignado a {caso.asignado}</span>}
      </div>

      {!!caso?.notas?.length && (
        <ul className="space-y-1.5">
          {caso.notas.map((n, i) => (
            <li key={i} className="rounded-md border border-border bg-muted px-2.5 py-1.5 text-xs">
              <span className="text-muted-foreground">{n.operador || "—"}{n.decidido_en ? ` · ${n.decidido_en.slice(0, 16).replace("T", " ")}` : ""}:</span>{" "}
              {n.texto}
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2 border-t border-border pt-3">
        <div className="flex flex-wrap items-center gap-2">
          <select value={estado} onChange={(e) => setEstado(e.target.value)}
            className="rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground"
            aria-label="Cambiar estado del caso">
            <option value="">— estado —</option>
            <option value="en_revision">En revisión</option>
            <option value="resuelto">Resuelto</option>
            <option value="nuevo">Reabrir (nuevo)</option>
          </select>
          <input value={asignado} onChange={(e) => setAsignado(e.target.value)} placeholder="asignar a…"
            className="w-36 rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground"
            aria-label="Asignar el caso a un analista" />
        </div>
        <textarea value={nota} onChange={(e) => setNota(e.target.value)} rows={2} placeholder="Añadir una nota…"
          className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground"
          aria-label="Nota del analista" />
        <Button onClick={guardar} disabled={!hayCambio || guardando}>
          {guardando ? "Guardando…" : "Guardar en el caso"}
        </Button>
      </div>
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
  if ("error" in red) return <SinConexion causa={red.causa} />

  const redInc = estadosDelIncidente(decision, det, red)
  const cascada = [...new Set([
    ...(decision.cascada ?? []),
    ...(det?.impacto_determinado?.activos_afectados_en_cascada ?? []),
  ])]
  const pendiente = !!decision.requiere_humano && !decision.veredicto_humano
  const contuvo = det?.escalada?.dispositivo_ejecutor ?? (det?.ejecucion?.exito ? decision.activo : null)
  const origenNodo = decision.origen_ip
    ? (red.nodos.find((n) => n.ip === decision.origen_ip)?.nombre ?? null) : null
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
          <MapaRed red={redInc} seleccionado={null} onSeleccionar={() => {}} dependencias={false}
            incidente={{ origen: origenNodo, activo: decision.activo, cascada }} />
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

      {decision.id_decision && <PanelCaso idDecision={decision.id_decision} />}
    </div>
  )
}
