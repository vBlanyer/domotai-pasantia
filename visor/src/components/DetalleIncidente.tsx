import { ArrowLeft } from "lucide-react"
import { useSondeo, getTrazas, type Decision } from "@/api"
import { Cargando, SinConexion, Prioridad } from "@/components/bits"
import { Button } from "@/components/ui/button"
import { campanasDe, eventosDeEntidad, claveIncidenteDe } from "@/datos"
import { LineaTiempo } from "@/components/LineaTiempo"
import { PanelCaso } from "@/components/PanelCaso"

const hora = (ts?: string | null) => {
  if (!ts) return "—"
  const t = new Date(ts)
  return isNaN(t.getTime()) ? ts : new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(t)
}

function Kpi({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2">
      <div className="text-xs text-muted-foreground">{etiqueta}</div>
      <div className="mt-0.5 text-sm font-medium">{children}</div>
    </div>
  )
}

// Detalle de un INCIDENTE (campaña /24): sus decisiones en una línea de tiempo (detección + respuesta)
// y el caso a NIVEL INCIDENTE (estado/responsable/notas), reutilizando `PanelCaso` con la clave
// `inc:<prefijo>`. Drill-down (no en el menú). Cero backend: reusa /api/trazas y /api/caso.
// `onVerDecisiones` recibe el prefijo del bloque ("203.0.113.") para abrir Decisiones filtradas por él (lo
// que antes hacía la vista «Campañas», fundida aquí: un incidente ES una campaña /24).
export function DetalleIncidente({ clave, cidr, onVolver, onVerDecisiones }: { clave: string; cidr: string; onVolver: () => void; onVerDecisiones?: (prefijo: string) => void }) {
  const t = useSondeo(getTrazas)
  if (!t) return <Cargando />
  const fallo = "error" in t ? t : null
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />
  const regs: Decision[] = fallo ? (fallo.datos ?? []) : (t as Decision[])
  const camp = campanasDe(regs).find((c) => "inc:" + c.prefijo.replace(/\.$/, "") === clave)
  const eventos = eventosDeEntidad(regs, (d) => claveIncidenteDe(d.origen_ip) === clave)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" variant="secondary" onClick={onVolver}><ArrowLeft className="size-4" /> Volver</Button>
        <div className="font-heading text-base font-semibold font-mono">{cidr}</div>
        {camp && <Prioridad n={camp.prioridad || null} />}
        {camp?.alcance && <span className="text-xs text-muted-foreground">· {camp.alcance}</span>}
        {camp && onVerDecisiones && (
          <button onClick={() => onVerDecisiones(camp.prefijo)} className="ml-auto text-xs font-medium text-info hover:underline">Ver las decisiones del bloque →</button>
        )}
      </div>
      {camp && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Kpi etiqueta="Decisiones">{camp.n}</Kpi>
          <Kpi etiqueta="IPs de origen">{camp.ips}</Kpi>
          <Kpi etiqueta="Objetivos">{camp.objetivos.length}</Kpi>
          <Kpi etiqueta="Ventana">{hora(camp.primera)} → {hora(camp.ultima)}</Kpi>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="mb-2 text-sm font-medium">Línea de tiempo</div>
          <LineaTiempo regs={eventos} />
        </div>
        <PanelCaso idDecision={clave} />
      </div>
    </div>
  )
}
