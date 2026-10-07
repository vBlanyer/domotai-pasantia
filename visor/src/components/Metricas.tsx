import { useEffect, useState, type ReactNode } from "react"
import { Printer } from "lucide-react"
import { getMetricas, type Metricas as Datos } from "@/api"
import { Donut, Tendencia, Barras, type Segmento } from "./charts"
import { MatrizAttack } from "./MatrizAttack"
import { CATEGORICO_LIGHT, CATEGORICO_DARK, ESTADO } from "@/theme"
import { useTema } from "@/tema"
import { Cargando, SinConexion, Vacio } from "./bits"
import { rangoDe, etiquetaPeriodo, type Preset } from "@/informe"

const ETIQUETA_CLASE: Record<string, string> = {
  vp_intento_acceso: "Intento de acceso",
  vp_acceso_consumado: "Acceso consumado",
  vp_abuso_cuenta: "Abuso de cuenta",
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

// La vista une las antiguas «Métricas» (en vivo) e «Informe» (por periodo, exportable).
// Un único efecto decide la fuente: en vivo sondea cada 2 s sin periodo; un periodo hace una
// sola consulta (sin poll de fondo).
type Seleccion = "vivo" | Preset | "rango"

const pct = (x: number) => `${Math.round(x * 100)}%`

function Kpi({ valor, etiqueta, aviso = false }: { valor: string; etiqueta: string; aviso?: boolean }) {
  return (
    <div className="rounded-xl border border-border bg-card px-5 py-4 shadow-sm">
      <div className={`font-heading text-3xl font-semibold tabular-nums ${aviso ? "text-[color:#b5730b] dark:text-amber-400" : ""}`}>{valor}</div>
      <div className="mt-1 text-sm text-muted-foreground">{etiqueta}</div>
    </div>
  )
}

function Tarjeta({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="min-w-0 break-inside-avoid rounded-xl border border-border bg-card p-5 shadow-sm">
      <h2 className="mb-4 text-sm font-medium text-muted-foreground">{titulo}</h2>
      {children}
    </section>
  )
}

export function Metricas() {
  const oscuro = useTema().oscuro
  const [sel, setSel] = useState<Seleccion>("vivo")
  const [rango, setRango] = useState(() => rangoDe("mes", new Date()))
  const [m, setM] = useState<Datos | { error: string } | undefined>()

  useEffect(() => {
    let vivo = true
    const pedir = () =>
      getMetricas(sel === "vivo" ? undefined : { desde: rango.desde, hasta: rango.hasta })
        // Solo re-renderiza si cambió el dato (evita que el sondeo se coma los clics — ver useSondeo).
        .then((r) => { if (vivo) setM((prev) => (JSON.stringify(prev) === JSON.stringify(r) ? prev : r)) })
    pedir()
    if (sel !== "vivo") return () => { vivo = false }
    const id = setInterval(pedir, 2000)
    return () => { vivo = false; clearInterval(id) }
  }, [sel, rango.desde, rango.hasta])

  // El reset a «Cargando» va en el evento que cambia la fuente, no en el efecto (cascading renders).
  const elegir = (s: Seleccion) => {
    if (s !== sel) setM(undefined)
    setSel(s)
    if (s !== "vivo" && s !== "rango") setRango(rangoDe(s, new Date()))
  }
  const fijarRango = (parte: "desde" | "hasta", valor: string) => {
    setM(undefined)
    setRango((r) => ({ ...r, [parte]: valor }))
  }

  const enVivo = sel === "vivo"
  const CAT = oscuro ? CATEGORICO_DARK : CATEGORICO_LIGHT

  return (
    <div className="space-y-5">
      {/* barra de control — no se imprime */}
      <div className="flex flex-wrap items-center gap-3 print:hidden">
        <div className="flex gap-1 rounded-lg border border-border bg-muted/40 p-1">
          {([["vivo", "En vivo"], ["mes", "Este mes"], ["año", "Este año"], ["rango", "Rango…"]] as const).map(([s, t]) => (
            <button key={s} onClick={() => elegir(s)}
              className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                sel === s ? "bg-card font-medium text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}>
              {t}
            </button>
          ))}
        </div>
        {sel === "rango" && (
          <div className="flex items-center gap-2 text-sm">
            <input type="date" value={rango.desde} aria-label="desde"
              onChange={(e) => fijarRango("desde", e.target.value)}
              className="rounded-md border border-border bg-card px-2 py-1" />
            <span className="text-muted-foreground">a</span>
            <input type="date" value={rango.hasta} aria-label="hasta"
              onChange={(e) => fijarRango("hasta", e.target.value)}
              className="rounded-md border border-border bg-card px-2 py-1" />
          </div>
        )}
        <button onClick={() => window.print()}
          className="ml-auto flex items-center gap-2 rounded-lg bg-[color:#1f6fd6] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[color:#1a5fba]">
          <Printer className="size-4" /> Guardar PDF
        </button>
      </div>

      {!m ? <Cargando /> : "error" in m ? <SinConexion /> : (
        <article className="space-y-5">
          <header className="flex flex-wrap items-start justify-between gap-4 border-b-2 border-foreground pb-4">
            <div>
              <h1 className="font-heading text-xl font-semibold">Informe de triaje MDR</h1>
              <p className="text-sm text-muted-foreground">Detección gestionada · refinamiento de alertas del SIEM</p>
            </div>
            <div className="text-right text-sm text-muted-foreground">
              <div className="text-base font-semibold text-foreground">
                {enVivo ? "En vivo · sesión actual" : etiquetaPeriodo(m.desde, m.hasta)}
              </div>
              <div className="font-mono text-xs">
                {enVivo ? `${m.total} decisiones · sesión actual` : `${m.total} decisiones en el periodo`}
              </div>
            </div>
          </header>

          {m.total === 0 ? (
            <Vacio>{enVivo
              ? "Aún no hay decisiones para medir. Lanza algún ataque y vuelve."
              : "No hay decisiones en este periodo. Prueba otro rango."}</Vacio>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
                <Kpi valor={pct(m.tasa_fp)} etiqueta="tasa de falsos positivos" aviso={m.tasa_fp > 0} />
                <Kpi valor={pct(m.pct_auto)} etiqueta="resuelto sin humano (automatizado)" />
                <Kpi valor={pct(m.pct_humano ?? 0)} etiqueta="escalado a decisión humana" />
                <Kpi valor={m.mttr_seg != null ? `${m.mttr_seg}s` : "—"} etiqueta="tiempo medio de respuesta (MTTR)" />
                <Kpi valor={String(m.suprimidas)} etiqueta="alertas de ruido evitadas" />
                <Kpi valor={pct(m.tasa_override ?? 0)} etiqueta="corrección del analista (override)" aviso={(m.tasa_override ?? 0) > 0} />
              </div>

              <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                <Tarjeta titulo="Decisiones por clase">
                  <Donut unidad="decisiones" total={m.total}
                    data={Object.keys(m.por_clase).sort().map((c, i): Segmento =>
                      ({ name: ETIQUETA_CLASE[c] ?? c, value: m.por_clase[c], fill: CAT[i % CAT.length] }))} />
                </Tarjeta>
                <Tarjeta titulo="Veredictos humanos">
                  {m.total - m.auto > 0
                    ? <Donut total={m.total - m.auto} unidad="a humano"
                        data={(Object.keys(VEREDICTO) as (keyof typeof VEREDICTO)[])
                          .filter((v) => m.veredictos[v])
                          .map((v) => ({ name: VEREDICTO[v].nombre, value: m.veredictos[v], fill: VEREDICTO[v].fill }))} />
                    : <p className="py-14 text-center text-sm text-muted-foreground">todo se resolvió automáticamente</p>}
                </Tarjeta>
                <Tarjeta titulo="Decisiones por día">
                  {m.por_dia.length
                    ? <Tendencia data={m.por_dia.map((d) => ({ dia: d.dia, n: d.n }))} />
                    : <p className="py-16 text-center text-sm text-muted-foreground">sin histórico todavía</p>}
                </Tarjeta>
              </div>

              <Tarjeta titulo="Activos más atacados">
                {m.top_activos.length
                  ? <Barras data={m.top_activos.map((a) => ({ nombre: a.nombre, n: a.n }))} />
                  : <p className="py-10 text-center text-sm text-muted-foreground">sin datos</p>}
              </Tarjeta>
              <Tarjeta titulo="Cobertura MITRE ATT&CK">
                {m.mitre.length
                  ? <MatrizAttack tecnicas={m.mitre} />
                  : <p className="py-10 text-center text-sm text-muted-foreground">sin técnicas registradas</p>}
              </Tarjeta>

              <div className="break-inside-avoid rounded-lg border border-border border-l-4 border-l-[color:#1f6fd6] bg-muted/40 p-4 text-sm">
                <h2 className="mb-1.5 text-sm font-medium text-muted-foreground">Resumen</h2>
                <p>
                  {enVivo ? "En la sesión actual" : "En el periodo"} el MDR procesó <b>{m.total} decisiones</b> refinando
                  las alertas del SIEM: resolvió el <b>{pct(m.pct_auto)}</b> en automático y escaló el{" "}
                  <b>{pct(m.pct_humano ?? 0)}</b> a un analista. La tasa de falsos positivos fue del{" "}
                  <b>{pct(m.tasa_fp)}</b> y se evitaron <b>{m.suprimidas}</b> alertas de ruido. El analista corrigió
                  al motor el <b>{pct(m.tasa_override ?? 0)}</b> de las veces.
                </p>
              </div>

              <footer className="flex flex-wrap justify-between gap-2 border-t border-border pt-3 text-xs text-muted-foreground">
                <span>Cadena de traza encadenada (SHA-256) · {m.total} registros {enVivo ? "en la sesión" : "en el periodo"}</span>
                <span className="font-mono">prototipo MDR · perfil bancario</span>
              </footer>
            </>
          )}
        </article>
      )}
    </div>
  )
}
