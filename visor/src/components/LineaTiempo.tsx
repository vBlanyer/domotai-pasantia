import { cronologiaDe, etiquetaClase, type EventoCronologia } from "@/datos"
import { Prioridad } from "@/components/bits"
import type { Decision } from "@/api"

const hora = (ts?: string | null) => {
  if (!ts) return "—"
  const t = new Date(ts)
  return isNaN(t.getTime()) ? ts : new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "medium" }).format(t)
}

// Marcador por tipo de evento (detección vs respuesta).
const ICONO: Record<EventoCronologia["tipo"], { s: string; cls: string }> = {
  decision: { s: "●", cls: "text-rose-500" },
  reversion: { s: "↩", cls: "text-sky-500" },
  caso: { s: "☰", cls: "text-slate-400" },
}

// Línea de tiempo (attack story): la cronología de un incidente/atacante, mezclando la detección
// (decisiones) con la respuesta (reversión de contención, hitos del ciclo de caso). Deriva del feed
// (`cronologiaDe`), sin backend.
export function LineaTiempo({ regs }: { regs: Decision[] }) {
  const eventos = cronologiaDe(regs)
  if (eventos.length === 0) {
    return <div className="py-4 text-center text-sm text-muted-foreground">Sin eventos en la ventana.</div>
  }
  return (
    <ol className="relative space-y-3 border-l border-border pl-5">
      {eventos.map((e) => {
        const ic = ICONO[e.tipo]
        return (
          <li key={e.clave} className="relative">
            <span className={`absolute -left-[1.6rem] top-0 ${ic.cls}`} aria-hidden>{ic.s}</span>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
              <span className="font-mono text-muted-foreground">{hora(e.ts)}</span>
              {e.tipo === "decision" && (
                <>
                  {e.prioridad != null && <Prioridad n={e.prioridad} />}
                  <span>{etiquetaClase(e.clase ?? "")}</span>
                  {e.origen_ip && <span className="text-muted-foreground">{e.origen_ip} → {e.activo ?? "—"}</span>}
                  {e.accion && <span className="rounded bg-muted px-1.5 py-0.5 font-mono">{e.accion}</span>}
                  {e.veredicto_humano && <span className="text-muted-foreground">· {e.veredicto_humano}</span>}
                </>
              )}
              {e.tipo === "reversion" && (
                <span>reversión de contención{e.activo ? ` en ${e.activo}` : ""}{e.operador ? ` · por ${e.operador}` : ""}</span>
              )}
              {e.tipo === "caso" && (
                <span>caso{e.nota ? `: ${e.nota}` : ""}{e.operador ? ` · ${e.operador}` : ""}</span>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
