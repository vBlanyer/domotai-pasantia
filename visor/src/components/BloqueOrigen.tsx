// El origen de un ataque, igual en Aprobaciones y en Decisiones: IP, equipo atacado, alcance y
// clasificación (OrigenBadges), ubicación y lo que ya pasó con ese origen.
import type { Decision } from "@/api"
import { ubicacionLabelDe } from "@/datos"
import { historialOrigen } from "@/aprobaciones"
import { OrigenBadges } from "./OrigenBadges"

type ConOrigen = Pick<Decision, "origen_ip" | "activo" | "enriquecimiento_origen">

export type Vigilancia = { indicador: string; nota?: string | null; agregado_en?: string | null }

export function BloqueOrigen({ d, trazas, onUbicacion, vigilancia }: {
  d: ConOrigen
  trazas: Decision[]                    // de donde sale el historial (sin el propio registro)
  onUbicacion?: (u: string) => void     // con él, la ubicación filtra (Aprobaciones)
  vigilancia?: Vigilancia | null        // el origen está en la watchlist («Revertir y vigilar»)
}) {
  if (!d.origen_ip && !d.enriquecimiento_origen) return null
  const ubic = d.enriquecimiento_origen ? ubicacionLabelDe(d) : null
  const historia = historialOrigen(trazas, d.origen_ip)
  return (
    <section aria-label="Origen" className="border-b border-border px-4 py-3 last:border-b-0">
      <h4 className="mb-2 text-[11px] font-medium text-muted-foreground">Origen</h4>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {d.origen_ip && <b className="font-mono text-sm font-semibold">{d.origen_ip}</b>}
        {d.activo && <span className="text-muted-foreground">→ {d.activo}</span>}
        <OrigenBadges e={d.enriquecimiento_origen} />
        {ubic && (onUbicacion
          ? <button onClick={() => onUbicacion(ubic)} title={`Filtrar la cola por ${ubic}`}
              className="rounded bg-muted px-1.5 py-0.5 hover:underline">📍 {ubic} · filtrar</button>
          : <span className="rounded bg-muted px-1.5 py-0.5">📍 {ubic}</span>)}
        {vigilancia && <span className="rounded bg-aviso/15 px-1.5 py-0.5 font-medium text-aviso">⚑ en vigilancia</span>}
      </div>
      {vigilancia && (vigilancia.nota || vigilancia.agregado_en) && (
        <p className="mt-1.5 text-xs text-muted-foreground">
          {vigilancia.nota}{vigilancia.agregado_en ? `${vigilancia.nota ? " · " : ""}desde ${new Date(vigilancia.agregado_en).toLocaleString()}` : ""}
          {vigilancia.indicador !== d.origen_ip && ` · por ${vigilancia.indicador}`}
        </p>
      )}
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
    </section>
  )
}
