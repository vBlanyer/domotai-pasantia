import { useEffect, useState } from "react"
import {
  useSondeo, getPolitica, actualizarPolitica,
  type PoliticaEstado, type PoliticaFamilia, type ZonaPolitica, type DispositivoPolitica, type CambioPolitica,
} from "@/api"
import { Cargando, SinConexion, Vacio } from "@/components/bits"
import { etiquetaClase, pasosRunbook } from "@/datos"
import "./Politicas.css"

type Valor = CambioPolitica["automatizacion"]
type Pestana = "familias" | "zonas"

const AUTO = "automatica_si_confianza"
const HUMANO = "humano_siempre"

const ICON_LOCK = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
    <rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </svg>
)

function variantDe(v: Valor) { return v === AUTO ? "auto" : v === HUMANO ? "humano" : "hereda" }

// Control segmentado accesible: cada opción es un botón con nombre «<sujeto> <opción>».
function Segmento({ sujeto, opciones, actual, deshabilitado, onElegir }: {
  sujeto: string; opciones: { etq: string; valor: Valor }[]; actual: Valor
  deshabilitado?: boolean; onElegir: (v: Valor) => void
}) {
  return (
    <span role="group" aria-label={sujeto} className="pol-seg">
      {opciones.map((o) => {
        const activo = o.valor === actual
        return (
          <button key={o.etq} type="button" disabled={deshabilitado} aria-pressed={activo}
            aria-label={`${sujeto} ${o.etq}`} onClick={() => onElegir(o.valor)}
            className={`pol-seg-btn ${activo ? `is-active v-${variantDe(o.valor)}` : ""}`}>
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
function radioClase(n: number) { return n === 0 ? "z0" : n <= 2 ? "z1" : "z2" }

type Sel = { tipo: "familia"; f: PoliticaFamilia } | { tipo: "activo"; d: DispositivoPolitica; zona: string }

function Detalle({ sel }: { sel: Sel }) {
  if (sel.tipo === "familia") {
    const f = sel.f
    const pasos = pasosRunbook(f.clase_tipica)
    const enrutada = f.nivel === "triar_y_enrutar"
    return (
      <div className="pol-detail">
        <div className="pol-detail-head">
          <div className="dk">familia · {etiquetaClase(f.clase_tipica)}</div>
          <div className="dt">{f.accion ?? "— sin contención —"}</div>
        </div>
        <div className="pol-detail-body">
          <div className="row"><span className="k">Familia</span><span>{f.familia}</span></div>
          <div className="row"><span className="k">Impacto</span><span className="mono">{f.impacto ?? "—"}</span></div>
          {enrutada && <div className="pol-block routed"><span className="bl">Enrutada</span>Se tría y enruta a {f.ruta ?? "—"} (no contiene automáticamente).</div>}
          {f.recomendacion?.respuesta && (
            <div className="row"><span className="k">Recomendación</span><span>{f.recomendacion.respuesta}{f.recomendacion.nota ? ` — ${f.recomendacion.nota}` : ""}</span></div>
          )}
          {f.vetos.length > 0 && <div className="pol-block crit"><span className="bl">Vetos / condiciones</span><ul>{f.vetos.map((v, i) => <li key={i}>{v}</li>)}</ul></div>}
          {pasos.length > 0 && <div><div className="k" style={{ marginBottom: 6 }}>Runbook</div><ol>{pasos.map((p, i) => <li key={i}>{p}</li>)}</ol></div>}
        </div>
      </div>
    )
  }
  const d = sel.d
  const n = d.cascada.length
  return (
    <div className="pol-detail">
      <div className="pol-detail-head">
        <div className="dk">zona {sel.zona} <span className={`pol-sev ${d.criticidad ?? "na"}`}>{d.criticidad ?? "—"}</span></div>
        <div className="dt">{d.activo}</div>
      </div>
      <div className="pol-detail-body">
        <div className="row"><span className="k">Postura efectiva</span><span className="mono">{d.postura_efectiva ?? "hereda"}</span></div>
        <div className="row"><span className="k">Radio</span><span className="mono num">{d.radio}</span></div>
        {n > 0 ? (
          <div className="pol-block crit"><span className="bl">Si lo aíslas, caen {n}</span>{d.cascada.join(", ")}
            {d.cascada_posiblemente_incompleta && " · cascada posiblemente incompleta"}</div>
        ) : (
          <div className="pol-block"><span className="bl">Radio de impacto</span>Según el inventario, aislarlo no arrastra otros activos.
            {d.cascada_posiblemente_incompleta && " (cascada posiblemente incompleta — dependencias sin declarar)"}</div>
        )}
      </div>
    </div>
  )
}

// Vista «Políticas»: editor del playbook, con el tema de consola del mockup (Politicas.css, scopeado a
// .pol). Dos pestañas (por familia / por zona y dispositivo). Los cambios van a POST /api/politica
// (fail-closed; exige token de operador) y las acciones destructivas quedan bloqueadas por el freno
// duro del catálogo. El sondeo refresca el estado y poda el valor optimista al confirmarlo.
export function Politicas() {
  const t = useSondeo(getPolitica)
  const [pestana, setPestana] = useState<Pestana>("familias")
  const [sel, setSel] = useState<Sel | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  // Valor elegido localmente hasta que el sondeo lo confirme (clave dimension:clave).
  const [local, setLocal] = useState<Record<string, Valor>>({})

  // Poda el valor optimista cuando el sondeo ya lo confirma (el servidor vuelve a mandar).
  useEffect(() => {
    if (!t || "error" in t) return
    const e = t as PoliticaEstado
    const base: Record<string, Valor> = {}
    for (const f of e.familias) base[`familia:${f.familia}`] = aValor(f.automatizacion_efectiva ?? f.automatizacion)
    for (const z of e.zonas) {
      base[`zona:${z.zona}`] = aValor(z.automatizacion)
      for (const d of z.dispositivos) base[`activo:${d.activo}`] = aValor(d.override)
    }
    setLocal((l) => {
      const ks = Object.keys(l).filter((k) => k in base && base[k] === l[k])
      if (ks.length === 0) return l
      const n = { ...l }
      for (const k of ks) delete n[k]
      return n
    })
  }, [t])

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

  // Resumen dinámico (como el mockup): por familias auto/humano/enrutadas; por zonas zonas/overrides/críticos.
  let resumen
  if (pestana === "familias") {
    let a = 0, hu = 0, r = 0
    for (const f of est.familias) {
      if (f.accion == null) r++
      else if (val("familia", f.familia, aValor(f.automatizacion_efectiva ?? f.automatizacion)) === AUTO
        && f.automatizacion !== "nunca_automatica" && f.automatizacion_efectiva !== "nunca_automatica") a++
      else hu++
    }
    resumen = (
      <div className="pol-summary">
        <span className="pol-s"><span className="pol-dot ok" /><b className="num">{a}</b> automáticas</span>
        <span className="pol-s"><span className="pol-dot warn" /><b className="num">{hu}</b> requieren humano</span>
        <span className="pol-s"><span className="pol-dot routed" /><b className="num">{r}</b> enrutadas</span>
      </div>
    )
  } else {
    const devs = est.zonas.flatMap((z) => z.dispositivos)
    const ov = devs.filter((d) => val("activo", d.activo, aValor(d.override)) !== null).length
    const cr = devs.filter((d) => d.criticidad === "critica").length
    resumen = (
      <div className="pol-summary">
        <span className="pol-s"><b className="num">{est.zonas.length}</b> zonas</span>
        <span className="pol-s"><span className="pol-dot warn" /><b className="num">{ov}</b> overrides</span>
        <span className="pol-s"><span className="pol-dot crit" /><b className="num">{cr}</b> críticos</span>
      </div>
    )
  }

  return (
    <div className="pol">
      {/* Sin título propio (la cabecera de la app ya dice «Políticas de respuesta») ni caja alrededor:
          la primera fila son las pestañas con el resumen a la derecha, como una barra de herramientas. */}
      <div className="pol-tabs">
        <div role="tablist" className="pol-tablist">
          {([["familias", "Por tipo de ataque"], ["zonas", "Por zona y dispositivo"]] as const).map(([id, n]) => (
            <button key={id} role="tab" aria-selected={pestana === id} onClick={() => { setPestana(id); setSel(null) }} className="pol-tab">
              {n}
            </button>
          ))}
        </div>
        {resumen}
      </div>

      {aviso && <p role="alert" className="pol-alert">{aviso}</p>}

      <div className="pol-grid">
        <section aria-label="Lista">

          {pestana === "familias" ? (
            <ul className="pol-rows">
              {est.familias.map((f) => {
                const nunca = f.automatizacion === "nunca_automatica" || f.automatizacion_efectiva === "nunca_automatica"
                const sinAccion = f.accion == null
                const bloqueada = nunca || sinAccion
                const ef = val("familia", f.familia, aValor(f.automatizacion_efectiva ?? f.automatizacion))
                const stripe = sinAccion ? "routed" : nunca ? "crit" : ef === AUTO ? "ok" : "warn"
                return (
                  <li key={f.familia} className="pol-row">
                    <span className={`pol-stripe ${stripe}`} />
                    <div className="pol-main">
                      <div className="pol-fam">{f.familia}</div>
                      <div className="pol-sub">{etiquetaClase(f.clase_tipica)} <span className="arw">→</span> {f.accion ?? "—"}</div>
                      <div className="pol-chips">
                        {f.impacto === "localizado" && <span className="pol-chip loc">localizado</span>}
                        {f.impacto === "alcanza_servicio" && <span className="pol-chip serv">alcanza servicio</span>}
                      </div>
                    </div>
                    <div className="pol-ctl">
                      {sinAccion
                        ? <span className="pol-tag-routed">se tría y enruta</span>
                        : <Segmento sujeto={f.familia} opciones={AUTO_HUMANO} deshabilitado={bloqueada} actual={ef}
                            onElegir={(v) => cambiar({ dimension: "familia", clave: f.familia, automatizacion: v })} />}
                      {nunca && <span className="pol-lock">{ICON_LOCK} freno duro / nunca automática</span>}
                      <button type="button" aria-label={`Detalle ${f.familia}`} className="pol-detalle-btn" onClick={() => setSel({ tipo: "familia", f })}>detalle</button>
                    </div>
                  </li>
                )
              })}
            </ul>
          ) : (
            <div>
              {est.zonas.map((z: ZonaPolitica) => (
                <div key={z.zona} className="pol-zone">
                  <div className="pol-zone-head">
                    <span className="zn">{z.zona}</span>
                    <span className="zc">{z.dispositivos.length} dispositivo{z.dispositivos.length === 1 ? "" : "s"}</span>
                    <span className="zctl">
                      {z.protegida
                        ? <span className="pol-tag-routed">protegido · no_cortar_gestion</span>
                        : <><span className="zl">postura de zona</span>
                            <Segmento sujeto={`zona ${z.zona}`} opciones={AUTO_HUMANO} actual={val("zona", z.zona, aValor(z.automatizacion))}
                              onElegir={(v) => cambiar({ dimension: "zona", clave: z.zona, automatizacion: v })} /></>}
                    </span>
                  </div>
                  {z.dispositivos.length > 0 && (
                    <div className="pol-zone-devs">
                      <ul className="pol-rows">
                        {z.dispositivos.map((d) => {
                          const n = d.cascada.length
                          const stripe = z.protegida ? "routed" : n === 0 ? "ok" : n >= 3 ? "crit" : "warn"
                          return (
                            <li key={d.activo} className="pol-row">
                              <span className={`pol-stripe ${stripe}`} />
                              <div className="pol-main">
                                <div className="pol-fam">{d.activo} <span className={`pol-sev ${d.criticidad ?? "na"}`}>{d.criticidad ?? "—"}</span></div>
                                <div className="pol-sub">radio {d.radio}{d.cascada.length > 0 && <> <span className="arw">·</span> cascada: {d.cascada.join(", ")}</>}</div>
                              </div>
                              <div className="pol-ctl">
                                {!z.protegida && <Segmento sujeto={d.activo} opciones={HEREDA} actual={val("activo", d.activo, aValor(d.override))}
                                  onElegir={(v) => cambiar({ dimension: "activo", clave: d.activo, automatizacion: v })} />}
                                {n > 0
                                  ? <span className={`pol-radio ${radioClase(n)}`}>{n}<span className="pol-radio-lbl"> en cascada</span></span>
                                  : null}
                                <button type="button" aria-label={`Detalle ${d.activo}`} className="pol-detalle-btn" onClick={() => setSel({ tipo: "activo", d, zona: z.zona })}>detalle</button>
                              </div>
                            </li>
                          )
                        })}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {sel
          ? <div className="pol-detail-col"><Detalle sel={sel} /></div>
          : (
            // La explicación de la interferencia entre pestañas vive aquí, en el hueco del detalle: se ve
            // mientras hay sitio y desaparece cuando el analista ya está mirando una fila.
            <div className="pol-detail-col pol-detail-empty">
              <p>Selecciona una fila para ver su detalle.</p>
              <p>
                {pestana === "familias"
                  ? <>La decisión efectiva <strong>también depende de la zona</strong> del activo afectado: una zona o un dispositivo en HUMANO prevalece sobre AUTO aquí.</>
                  : <>La decisión efectiva <strong>también depende de la familia</strong> de ataque: una familia en HUMANO o «nunca automática» prevalece sobre AUTO aquí.</>}
              </p>
            </div>
          )}
      </div>
    </div>
  )
}
