import type { ReactNode } from "react"
import { useSondeo, getMetricas } from "@/api"
import { Donut, Tendencia, Barras, type Segmento } from "./charts"
import { CATEGORICO_LIGHT, CATEGORICO_DARK, ESTADO } from "@/theme"
import { useTema } from "@/tema"
import { Cargando, SinConexion, Vacio } from "./bits"

const ETIQUETA_CLASE: Record<string, string> = {
  vp_intento_acceso: "Intento de acceso",
  vp_acceso_consumado: "Acceso consumado",
  fp_actividad_legitima: "Falso positivo (legítimo)",
  fp_exposicion_inexistente: "Falso positivo (exposición)",
  no_soportada: "No soportada",
  amenaza_enrutada: "Enrutada a un equipo",
  otra: "Otra",
}
const VEREDICTO = {
  aprobar: { nombre: "Aprobadas", fill: ESTADO.good },
  rechazar: { nombre: "Rechazadas", fill: ESTADO.critical },
  reclasificar: { nombre: "Reclasificadas", fill: ESTADO.warning },
} as const

function Kpi({ valor, etiqueta, tono = "" }: { valor: string; etiqueta: string; tono?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card px-5 py-4 shadow-sm">
      <div className={`font-heading text-3xl font-semibold tabular-nums ${tono}`}>{valor}</div>
      <div className="mt-1 text-sm text-muted-foreground">{etiqueta}</div>
    </div>
  )
}

function Tarjeta({ titulo, children, className = "" }: { titulo: string; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-xl border border-border bg-card p-5 shadow-sm ${className}`}>
      <h2 className="mb-4 text-sm font-medium text-muted-foreground">{titulo}</h2>
      {children}
    </section>
  )
}

const pct = (x: number) => `${Math.round(x * 100)}%`

export function Metricas() {
  const m = useSondeo(getMetricas)
  const CAT = useTema().oscuro ? CATEGORICO_DARK : CATEGORICO_LIGHT
  if (!m) return <Cargando />
  if ("error" in m) return <SinConexion />
  if (m.total === 0) return <Vacio>Aún no hay decisiones para medir. Lanza algún ataque y vuelve.</Vacio>

  // Donut por clase: color estable por clase (orden alfabético), nunca por rango.
  const clases = Object.keys(m.por_clase).sort()
  const porClase: Segmento[] = clases.map((c, i) => ({
    name: ETIQUETA_CLASE[c] ?? c, value: m.por_clase[c], fill: CAT[i % CAT.length],
  }))
  const veredictos: Segmento[] = (Object.keys(VEREDICTO) as (keyof typeof VEREDICTO)[])
    .filter((v) => m.veredictos[v])
    .map((v) => ({ name: VEREDICTO[v].nombre, value: m.veredictos[v], fill: VEREDICTO[v].fill }))
  const nHumano = m.total - m.auto

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi valor={pct(m.tasa_fp)} etiqueta="tasa de falsos positivos" tono={m.tasa_fp > 0 ? "text-[color:#eda100]" : ""} />
        <Kpi valor={pct(m.pct_auto)} etiqueta="resuelto sin humano (automatizado)" />
        <Kpi valor={m.mttr_seg != null ? `${m.mttr_seg}s` : "—"} etiqueta="tiempo medio de respuesta (MTTR)" />
        <Kpi valor={String(m.suprimidas)} etiqueta="alertas de ruido evitadas" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Tarjeta titulo="Decisiones por clase">
          <Donut data={porClase} total={m.total} unidad="decisiones" />
        </Tarjeta>
        <Tarjeta titulo="Veredictos humanos">
          {nHumano > 0
            ? <Donut data={veredictos} total={nHumano} unidad="a humano" />
            : <p className="py-14 text-center text-sm text-muted-foreground">todo se resolvió automáticamente</p>}
        </Tarjeta>
        <Tarjeta titulo="Decisiones por día">
          {m.por_dia.length
            ? <Tendencia data={m.por_dia.map((d) => ({ dia: d.dia, n: d.n }))} />
            : <p className="py-16 text-center text-sm text-muted-foreground">sin histórico todavía</p>}
        </Tarjeta>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Tarjeta titulo="Activos más atacados">
          {m.top_activos.length
            ? <Barras data={m.top_activos.map((a) => ({ nombre: a.nombre, n: a.n }))} />
            : <p className="py-10 text-center text-sm text-muted-foreground">sin datos</p>}
        </Tarjeta>
        <Tarjeta titulo="Cobertura MITRE ATT&CK">
          {m.mitre.length
            ? <Barras data={m.mitre.map((t) => ({ nombre: t.tecnica, n: t.n }))} />
            : <p className="py-10 text-center text-sm text-muted-foreground">sin técnicas registradas</p>}
        </Tarjeta>
      </div>
    </div>
  )
}
