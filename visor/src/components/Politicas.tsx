import { useState } from "react"
import {
  useSondeo, getPolitica, actualizarPolitica,
  type PoliticaEstado, type PoliticaFamilia, type ZonaPolitica, type DispositivoPolitica, type CambioPolitica,
} from "@/api"
import { Cargando, SinConexion, Vacio } from "@/components/bits"
import { etiquetaClase, pasosRunbook } from "@/datos"

type Valor = CambioPolitica["automatizacion"]
type Pestana = "familias" | "zonas"

const AUTO = "automatica_si_confianza"
const HUMANO = "humano_siempre"

// Control segmentado accesible: cada opción es un botón con nombre «<sujeto> <opción>».
function Segmento({ sujeto, opciones, actual, deshabilitado, onElegir }: {
  sujeto: string; opciones: { etq: string; valor: Valor }[]; actual: Valor
  deshabilitado?: boolean; onElegir: (v: Valor) => void
}) {
  return (
    <span role="group" aria-label={sujeto} className="inline-flex overflow-hidden rounded border border-border">
      {opciones.map((o) => {
        const activo = o.valor === actual
        return (
          <button key={o.etq} type="button" disabled={deshabilitado} aria-pressed={activo}
            aria-label={`${sujeto} ${o.etq}`} onClick={() => onElegir(o.valor)}
            className={`px-2 py-0.5 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50 ${
              activo ? "bg-primary text-primary-foreground" : "bg-card text-muted-foreground hover:bg-muted"}`}>
            {o.etq}
          </button>
        )
      })}
    </span>
  )
}

const AUTO_HUMANO = [{ etq: "AUTO", valor: AUTO as Valor }, { etq: "HUMANO", valor: HUMANO as Valor }]
const HEREDA = [{ etq: "HEREDA", valor: null as Valor }, ...AUTO_HUMANO]

function aValor(a?: string | null): Valor {
  return a === HUMANO || a === "requiere_humano" ? HUMANO : a === AUTO || a === "automatica_si_confianza" ? AUTO : null
}

type Sel = { tipo: "familia"; f: PoliticaFamilia } | { tipo: "activo"; d: DispositivoPolitica; zona: string }

function Detalle({ sel }: { sel: Sel }) {
  if (sel.tipo === "familia") {
    const f = sel.f
    const pasos = pasosRunbook(f.clase_tipica)
    return (
      <div className="space-y-1 text-xs">
        <div className="font-medium">Detalle · {f.familia} <span className="font-normal text-muted-foreground">({etiquetaClase(f.clase_tipica)})</span></div>
        <div>Acción: <span className="font-mono">{f.accion ?? "—"}</span></div>
        <div>Impacto: <span className="font-mono">{f.impacto ?? "—"}</span></div>
        {f.nivel === "triar_y_enrutar" && <div>Se tría y enruta a {f.ruta ?? "—"} (no contiene).</div>}
        {f.recomendacion?.respuesta && <div>Respuesta recomendada: {f.recomendacion.respuesta}{f.recomendacion.nota ? ` — ${f.recomendacion.nota}` : ""}</div>}
        {f.vetos.length > 0 && <ul className="list-disc pl-4 text-muted-foreground">{f.vetos.map((v, i) => <li key={i}>{v}</li>)}</ul>}
        {pasos.length > 0 && <ol className="list-decimal pl-4">{pasos.map((p, i) => <li key={i}>{p}</li>)}</ol>}
      </div>
    )
  }
  const d = sel.d
  return (
    <div className="space-y-1 text-xs">
      <div className="font-medium">Detalle · {d.activo} <span className="font-normal text-muted-foreground">(zona {sel.zona})</span></div>
      <div>Criticidad: {d.criticidad ?? "—"} · radio de impacto: {d.radio}</div>
      <div>Postura efectiva: {d.postura_efectiva ?? "—"}</div>
      <div>Cascada (depende de este activo): {d.cascada.length ? d.cascada.join(", ") : "ninguno"}
        {d.cascada_posiblemente_incompleta && " (posiblemente incompleta)"}</div>
    </div>
  )
}

// Vista «Políticas»: editor del playbook. Dos pestañas (por familia / por zona y dispositivo). Los
// cambios se envían a POST /api/politica (fail-closed en el servidor; exige token de operador) y las
// acciones destructivas quedan bloqueadas por el freno duro del catálogo. El sondeo refresca el estado.
export function Politicas() {
  const t = useSondeo(getPolitica)
  const [pestana, setPestana] = useState<Pestana>("familias")
  const [sel, setSel] = useState<Sel | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  // Valor elegido localmente hasta que el sondeo lo confirme (clave dimension:clave).
  const [local, setLocal] = useState<Record<string, Valor>>({})

  if (!t) return <Cargando />
  const fallo = "error" in t ? t : null
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />
  const est: PoliticaEstado | undefined = fallo ? undefined : (t as PoliticaEstado)
  if (!est || (est.familias.length === 0 && est.zonas.length === 0)) return <Vacio>Sin políticas que mostrar.</Vacio>

  async function cambiar(c: CambioPolitica) {
    setAviso(null)
    try {
      await actualizarPolitica(c)
      setLocal((l) => ({ ...l, [`${c.dimension}:${c.clave}`]: c.automatizacion }))
    } catch (e) {
      const m = e instanceof Error ? e.message : ""
      setAviso(m.includes("403") || m.includes("401")
        ? "No se pudo guardar: editar requiere token de operador."
        : `No se pudo guardar el cambio (${m || "error de red"}).`)
    }
  }
  const val = (dim: string, clave: string, base: Valor): Valor => {
    const k = `${dim}:${clave}`
    return k in local ? local[k] : base
  }

  return (
    <div className="space-y-3">
      <div role="tablist" className="flex gap-1 border-b border-border">
        {([["familias", "Por tipo de ataque"], ["zonas", "Por zona y dispositivo"]] as const).map(([id, n]) => (
          <button key={id} role="tab" aria-selected={pestana === id} onClick={() => { setPestana(id); setSel(null) }}
            className={`px-3 py-1.5 text-sm ${pestana === id ? "border-b-2 border-primary font-medium" : "text-muted-foreground hover:text-foreground"}`}>
            {n}
          </button>
        ))}
      </div>
      <p className="rounded border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
        {pestana === "familias"
          ? <>La decisión efectiva <strong>también depende de la zona</strong> del activo afectado: una zona o un dispositivo en HUMANO prevalece sobre AUTO aquí.</>
          : <>La decisión efectiva <strong>también depende de la familia</strong> de ataque: una familia en HUMANO o «nunca automática» prevalece sobre AUTO aquí.</>}
      </p>
      {aviso && <p role="alert" className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">{aviso}</p>}

      {pestana === "familias" ? (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {est.familias.map((f) => {
            const nunca = f.automatizacion === "nunca_automatica" || f.automatizacion_efectiva === "nunca_automatica"
            const sinAccion = f.accion == null
            const bloqueada = nunca || sinAccion
            return (
              <li key={f.familia} className="flex flex-wrap items-center gap-3 px-3 py-2">
                <span className="min-w-40 font-medium">{f.familia}</span>
                <span className="font-mono text-xs text-muted-foreground">{f.accion ?? "—"}</span>
                <Segmento sujeto={f.familia} opciones={AUTO_HUMANO} deshabilitado={bloqueada}
                  actual={val("familia", f.familia, aValor(f.automatizacion_efectiva ?? f.automatizacion))}
                  onElegir={(v) => cambiar({ dimension: "familia", clave: f.familia, automatizacion: v })} />
                {nunca && <span className="text-xs text-rose-700 dark:text-rose-300">freno duro / nunca automática</span>}
                {!nunca && sinAccion && <span className="text-xs text-muted-foreground">se tría y enruta</span>}
                <button type="button" aria-label={`Detalle ${f.familia}`} onClick={() => setSel({ tipo: "familia", f })}
                  className="ml-auto text-xs text-muted-foreground hover:underline">detalle</button>
              </li>
            )
          })}
        </ul>
      ) : (
        <div className="space-y-3">
          {est.zonas.map((z: ZonaPolitica) => (
            <div key={z.zona} className="rounded-lg border border-border bg-card">
              <div className="flex flex-wrap items-center gap-3 px-3 py-2">
                <span className="font-medium">{z.zona}</span>
                {z.protegida
                  ? <span className="text-xs text-muted-foreground">protegido · no_cortar_gestion</span>
                  : <Segmento sujeto={`zona ${z.zona}`} opciones={AUTO_HUMANO}
                      actual={val("zona", z.zona, aValor(z.automatizacion))}
                      onElegir={(v) => cambiar({ dimension: "zona", clave: z.zona, automatizacion: v })} />}
              </div>
              {z.dispositivos.length > 0 && (
                <ul className="divide-y divide-border border-t border-border">
                  {z.dispositivos.map((d) => (
                    <li key={d.activo} className="flex flex-wrap items-center gap-3 px-3 py-1.5 pl-6">
                      <span className="min-w-32 text-sm">{d.activo}</span>
                      <span className="text-xs text-muted-foreground">criticidad {d.criticidad ?? "—"} · radio {d.radio}
                        {d.cascada.length > 0 && ` · cascada: ${d.cascada.join(", ")}`}</span>
                      <Segmento sujeto={d.activo} opciones={HEREDA}
                        actual={val("activo", d.activo, aValor(d.override))}
                        onElegir={(v) => cambiar({ dimension: "activo", clave: d.activo, automatizacion: v })} />
                      <button type="button" aria-label={`Detalle ${d.activo}`} onClick={() => setSel({ tipo: "activo", d, zona: z.zona })}
                        className="ml-auto text-xs text-muted-foreground hover:underline">detalle</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
      {sel && <div className="rounded-lg border border-border bg-card p-3"><Detalle sel={sel} /></div>}
    </div>
  )
}
