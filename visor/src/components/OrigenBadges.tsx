import type { Decision } from "@/api"

// Enriquecimiento de la IP de origen (backend: actores.enriquecer_origen), compacto, para el
// incidente y el detalle de una decisión. Capa de presentación: no recalcula nada.
type Enr = NonNullable<Decision["enriquecimiento_origen"]>

const ALCANCE: Record<string, { txt: string; cls: string }> = {
  interno: { txt: "interno", cls: "bg-amber-400/20" },
  externo: { txt: "externo", cls: "bg-rose-500/15" },
  gestion: { txt: "gestión MDR", cls: "bg-slate-500/15" },
  dispositivo_red: { txt: "dispositivo de red", cls: "bg-slate-500/15" },
}
const CLASE_IP: Record<string, string> = {
  publica: "IP pública", privada: "IP privada", documentacion: "IP de documentación",
  loopback: "loopback", invalida: "IP inválida",
}

export function OrigenBadges({ e }: { e?: Enr | null }) {
  if (!e) return null
  const al = ALCANCE[e.alcance] ?? { txt: e.alcance, cls: "bg-muted" }
  const lugar = [e.geo?.ciudad, e.geo?.pais].filter(Boolean).join(", ")
  const geo = lugar || (e.geolocalizable ? "sin base GeoIP cargada" : "sin geolocalización")
  return (
    <span className="inline-flex flex-wrap items-center gap-1 text-xs">
      <span className={`rounded px-1.5 py-0.5 ${al.cls}`}>{al.txt}</span>
      <span className="rounded bg-muted px-1.5 py-0.5">{CLASE_IP[e.clasificacion_ip] ?? e.clasificacion_ip}</span>
      {e.inventariado && <span className="rounded bg-muted px-1.5 py-0.5">inventariado</span>}
      {e.tercero_confiable && <span className="rounded bg-sky-500/15 px-1.5 py-0.5">tercero de confianza</span>}
      {e.legitimo && <span className="rounded bg-emerald-500/15 px-1.5 py-0.5">origen legítimo</span>}
      {e.asn && (
        <span className="rounded bg-violet-500/15 px-1.5 py-0.5" title={e.asn.asn}>{e.asn.org}</span>
      )}
      <span className="text-muted-foreground">· {geo}</span>
    </span>
  )
}
