import { useEffect, useState } from "react"
import { Printer } from "lucide-react"
import { getMetricas, type Metricas as Datos, type Fallo } from "@/api"
import { Donut, Barras } from "./charts"
import { MatrizAttack } from "./MatrizAttack"
import { ESTADO } from "@/theme"
import { Cargando, SinConexion, Kpi, Tarjeta } from "./bits"
import { rangoDe, etiquetaPeriodo, type Preset } from "@/informe"

type Seleccion = Preset | "rango"
const pct = (x: number) => `${Math.round(x * 100)}%`
const mmss = (s?: number | null) => (s == null ? "—" : s >= 60 ? `${Math.round(s / 60)} min` : `${Math.round(s)} s`)

// Vista «Resumen ejecutivo»: una página para dirección, SIEMPRE por periodo (getMetricas{desde,hasta},
// coherente; no mezcla con la ventana viva). Titulares de negocio + top amenazas por familia + top
// ubicaciones + acciones tomadas + cobertura ATT&CK. Exportable a PDF (window.print). Reusa KPIs/charts.
export function ResumenEjecutivo() {
  const [sel, setSel] = useState<Seleccion>("mes")
  const [rango, setRango] = useState(() => rangoDe("mes", new Date()))
  const [m, setM] = useState<Datos | Fallo | undefined>()

  useEffect(() => {
    let vivo = true
    getMetricas({ desde: rango.desde, hasta: rango.hasta })
      .then((r) => { if (vivo) setM(r) })
    return () => { vivo = false }
  }, [rango.desde, rango.hasta])

  const elegir = (s: Seleccion) => {
    setM(undefined); setSel(s)
    if (s !== "rango") setRango(rangoDe(s, new Date()))
  }
  const fijarRango = (parte: "desde" | "hasta", valor: string) => { setM(undefined); setRango((r) => ({ ...r, [parte]: valor })) }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3 print:hidden">
        <div className="flex gap-1 rounded-lg border border-border bg-muted/40 p-1">
          {([["mes", "Este mes"], ["año", "Este año"], ["rango", "Rango…"]] as const).map(([s, t]) => (
            <button key={s} onClick={() => elegir(s)}
              className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                sel === s ? "bg-card font-medium text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}>
              {t}
            </button>
          ))}
        </div>
        {sel === "rango" && (
          <div className="flex items-center gap-2 text-sm">
            <input type="date" value={rango.desde} aria-label="desde" onChange={(e) => fijarRango("desde", e.target.value)}
              className="rounded-md border border-border bg-card px-2 py-1" />
            <span className="text-muted-foreground">a</span>
            <input type="date" value={rango.hasta} aria-label="hasta" onChange={(e) => fijarRango("hasta", e.target.value)}
              className="rounded-md border border-border bg-card px-2 py-1" />
          </div>
        )}
        <button onClick={() => window.print()}
          className="ml-auto flex items-center gap-2 rounded-lg bg-[color:#1f6fd6] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[color:#1a5fba]">
          <Printer className="size-4" /> Guardar PDF
        </button>
      </div>

      {!m ? <Cargando /> : "error" in m ? <SinConexion causa={m.causa} /> : (
        <article className="space-y-5">
          <header className="flex flex-wrap items-start justify-between gap-4 border-b-2 border-foreground pb-4">
            <div>
              <h1 className="font-heading text-xl font-semibold">Resumen ejecutivo · MDR</h1>
              <p className="text-sm text-muted-foreground">Detección gestionada · refinamiento de alertas del SIEM</p>
            </div>
            <div className="text-right text-sm text-muted-foreground">
              <div className="text-base font-semibold text-foreground">{etiquetaPeriodo(rango.desde, rango.hasta)}</div>
              <div>{new Date().toLocaleDateString()}</div>
            </div>
          </header>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6 print:grid-cols-6">
            <Kpi valor={String(m.total)} etiqueta="Amenazas tratadas" />
            <Kpi valor={pct(m.tasa_fp)} etiqueta="Falsos positivos" />
            <Kpi valor={pct(m.pct_auto)} etiqueta="Contenidas en automático" />
            <Kpi valor={pct(m.pct_humano ?? 0)} etiqueta="A revisión humana" />
            <Kpi valor={mmss(m.mttr_mediano_seg)} etiqueta="MTTR mediano" />
            <Kpi valor={m.sla_pct == null ? "—" : pct(m.sla_pct)} etiqueta="Dentro de SLA" aviso={(m.sla_incumplidos ?? 0) > 0} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2 print:grid-cols-2">
            <Tarjeta titulo="Amenazas por familia">
              <Barras data={(m.por_familia ?? []).map((f) => ({ nombre: f.familia, n: f.n }))} />
            </Tarjeta>
            <Tarjeta titulo="Orígenes por ubicación">
              <Barras data={(m.por_pais ?? []).map((p) => ({ nombre: p.pais, n: p.n }))} />
            </Tarjeta>
            <Tarjeta titulo="Acciones tomadas">
              <Donut unidad="decisiones" total={m.total}
                data={[{ name: "Contenidas en automático", value: m.auto, fill: ESTADO.good },
                       { name: "A revisión humana", value: m.escalado_humano ?? (m.total - m.auto), fill: ESTADO.warning }]} />
            </Tarjeta>
            <Tarjeta titulo="Cobertura ATT&CK">
              <MatrizAttack tecnicas={m.mitre} />
            </Tarjeta>
          </div>
        </article>
      )}
    </div>
  )
}
