import { useState } from "react"
import { getRed, getTrazas, useSondeo } from "@/api"
import { Cargando, SinConexion } from "@/components/bits"
import { MapaRed, ESTADO_VISUAL } from "@/components/MapaRed"
import { PanelEquipo } from "@/components/PanelEquipo"

export function Red({ onVerDecisiones, onVerAtacante }: {
  onVerDecisiones: (equipo: string | null, texto?: string) => void
  onVerAtacante?: (ip: string) => void
}) {
  const red = useSondeo(getRed)
  const trazas = useSondeo(getTrazas)
  const [sel, setSel] = useState<string | null>(null)
  const [deps, setDeps] = useState(true)
  if (!red) return <Cargando />
  if ("error" in red) return <SinConexion />
  const nodo = red.nodos.find((n) => n.nombre === sel)
  // La ventana filtrada completa (hasta 500) para que las gráficas por dispositivo no queden
  // truncadas; la lista de eventos del panel ya acota su propio render.
  const eventos = nodo && Array.isArray(trazas)
    ? trazas.filter((d) => d.relaciones?.[nodo.nombre]).slice().reverse() : []
  const avisos = red.avisos ?? []
  return (
    <div className="space-y-3">
      {avisos.length > 0 && (
        <div role="status" className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-600 dark:text-amber-400">
          <p>El perfil tiene {avisos.length} {avisos.length === 1 ? "aviso" : "avisos"} en la sección red:</p>
          <ul className="list-disc pl-5">{avisos.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        {Object.entries(ESTADO_VISUAL).map(([k, v]) => <span key={k}>{v.icono || "○"} {v.texto}</span>)}
        <label className="ml-auto flex items-center gap-1.5">
          <input type="checkbox" checked={deps} onChange={(e) => setDeps(e.target.checked)} /> dependencias
        </label>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="rounded-lg border border-border bg-card p-3">
          <MapaRed red={red} seleccionado={sel} onSeleccionar={setSel} dependencias={deps} />
        </div>
        {nodo
          ? <PanelEquipo nodo={nodo} eventos={eventos} todos={Array.isArray(trazas) ? trazas : []}
              onVerDecisiones={() => onVerDecisiones(nodo.nombre)}
              onVerOrigen={(texto) => onVerDecisiones(null, texto)}
              onVerAtacante={onVerAtacante} />
          : <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
              Pulsa un equipo para ver sus eventos.</div>}
      </div>
    </div>
  )
}
