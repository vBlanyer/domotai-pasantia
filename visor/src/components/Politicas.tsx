import { useEffect, useState } from "react"
import {
  useSondeo, getPolitica, actualizarPolitica, getPoliticaExplicar, getPoliticaPropuesta,
  type PoliticaEstado, type PoliticaFamilia, type ZonaPolitica, type DispositivoPolitica, type CambioPolitica,
  type DiferenciaPolitica,
} from "@/api"
import { Cargando, SinConexion, Vacio } from "@/components/bits"
import { etiquetaClase, pasosRunbook } from "@/datos"
import "./Politicas.css"

type Valor = CambioPolitica["automatizacion"]
type Pestana = "resumen" | "familias" | "zonas" | "confianza" | "intocables"
const PESTANAS: [Pestana, string][] = [["resumen", "Resumen"], ["familias", "Por tipo de ataque"],
  ["zonas", "Por zona y dispositivo"], ["confianza", "Confianza"], ["intocables", "Intocables"]]

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

// De dónde sale cada valor (plan de la política de la empresa): el código manda, luego politica.yml,
// y la consola solo endurece por encima.
function origenTexto(origen: string | undefined, version: unknown) {
  if (origen === "codigo") return "código"
  if (origen === "consola") return "consola"
  if (origen === "fichero") return version != null ? `política v${version}` : "política"
  if (origen === "perfil") return "perfil"
  return "por defecto"
}
function Origen({ sujeto, origen, version }: { sujeto: string; origen?: string; version?: unknown }) {
  if (!origen) return null                          // servicio anterior: no lo informa
  const t = origenTexto(origen, version)
  return <span className={`pol-origen o-${origen}`} aria-label={`${sujeto}: origen ${t}`}>{t}</span>
}
const VALOR_LEGIBLE: Record<string, string> = {
  automatica_si_confianza: "si hay certeza", humano_siempre: "con analista", por_defecto: "por defecto",
}
function hora(iso?: string | null) {
  if (!iso) return ""
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("es", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
}

function descargar(nombre: string, texto: string) {
  const url = URL.createObjectURL(new Blob([texto], { type: "application/x-yaml" }))
  const a = document.createElement("a")
  a.href = url; a.download = nombre
  document.body.appendChild(a); a.click(); a.remove()
  URL.revokeObjectURL(url)
}

// «Resumen»: la política efectiva contada en frases (GET /api/politica/explicar), lo que firma Seguridad.
function Explicacion() {
  const [frases, setFrases] = useState<string[] | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  useEffect(() => {
    let vivo = true
    getPoliticaExplicar().then((r) => {
      if (!vivo) return
      if ("error" in r) setFallo(r.error)
      else setFrases(r.frases)
    })
    return () => { vivo = false }
  }, [])
  if (fallo) return <p role="alert" className="pol-alert">No se pudo leer la explicación ({fallo}).</p>
  if (!frases) return <Cargando />
  return (
    <div className="pol-panel">
      <p className="pol-panel-nota">Lo mismo que imprime <span className="mono">mdr explicar-politica</span>; es lo que aprueba Seguridad.</p>
      <ul className="pol-frases">{frases.map((f, i) => <li key={i}>{f}</li>)}</ul>
    </div>
  )
}

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
  const [pestana, setPestana] = useState<Pestana>("resumen")
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

  const cab = est.politica
  const version = cab?.version
  const difs: DiferenciaPolitica[] = est.diferencias ?? []
  async function exportar() {
    setAviso(null)
    const r = await getPoliticaPropuesta()
    if ("error" in r) { setAviso(`No se pudo preparar la propuesta (${r.error}).`); return }
    descargar(`politica-v${r.version}.yml`, r.yaml)
  }
  const siguiente = typeof version === "number" ? version + 1 : 1

  return (
    <div className="pol">
      {/* La política vigente: de dónde salen las reglas y la propuesta de la versión siguiente. */}
      <section aria-label="Política vigente" className="pol-banner">
        <div className="pol-banner-txt">
          {cab
            ? <><b>Política de la empresa · versión {String(version ?? "?")}</b>
                <span> · aprobada por {cab.aprobada_por ?? "(sin indicar)"}{cab.fecha ? ` · ${cab.fecha}` : ""}</span>
                <span className="mono"> · {cab.ruta}{cab.huella ? ` · huella ${cab.huella.slice(0, 12)}…` : ""}</span></>
            : <><b>Sin politica.yml</b><span>: las reglas vienen del perfil. <span className="mono">mdr migrar-politica</span> las pasa a un fichero propio.</span></>}
        </div>
        <div className="pol-banner-btns">
          <button type="button" className="pol-btn pol-btn-p" onClick={exportar}>Exportar propuesta v{siguiente}</button>
        </div>
      </section>

      {difs.length > 0 && (
        <section aria-label="Cambios de consola pendientes" className="pol-drift">
          <p><b>{difs.length === 1 ? "1 cambio hecho en la consola" : `${difs.length} cambios hechos en la consola`}</b>{" "}
            endurecen la política y aún no están en el fichero. Si Seguridad los aprueba, exporta la propuesta; si no, vuelve cada uno a la política.</p>
          <ul>
            {difs.map((d) => (
              <li key={`${d.dimension}:${d.clave}`}>
                <span className="mono pol-drift-k">{d.clave}</span>
                <span>{VALOR_LEGIBLE[d.antes ?? ""] ?? d.antes} → {VALOR_LEGIBLE[d.despues ?? ""] ?? d.despues}
                  {d.operador ? ` — ${d.operador}` : ""}{d.en ? `, ${hora(d.en)}` : ""}</span>
                <button type="button" className="pol-btn" aria-label={`Volver a la política: ${d.clave}`}
                  onClick={() => cambiar({ dimension: d.dimension, clave: d.clave, automatizacion: null })}>Volver a la política</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Sin título propio (la cabecera de la app ya dice «Políticas de respuesta») ni caja alrededor:
          la primera fila son las pestañas con el resumen a la derecha, como una barra de herramientas. */}
      <div className="pol-tabs">
        <div role="tablist" className="pol-tablist">
          {PESTANAS.map(([id, n]) => (
            <button key={id} role="tab" aria-selected={pestana === id} onClick={() => { setPestana(id); setSel(null) }} className="pol-tab">
              {n}
            </button>
          ))}
        </div>
        {(pestana === "familias" || pestana === "zonas") && resumen}
      </div>

      {aviso && <p role="alert" className="pol-alert">{aviso}</p>}

      {pestana === "resumen" && <Explicacion />}

      {pestana === "confianza" && (
        <div className="pol-panel">
          {est.confianza ? <>
            <p className="pol-panel-nota">Solo lectura: viene {est.confianza.origen === "fichero" ? <>de <span className="mono">politica.yml</span>{version != null ? ` v${version}` : ""}</> : "del perfil"}.
              Para cambiarlo, Seguridad aprueba una versión nueva.</p>
            <dl className="pol-dl">
              <dt>Administradores</dt><dd>{est.confianza.administradores.length ? est.confianza.administradores.map((ip) => <span key={ip} className="mono pol-ip">{ip}</span>) : "—"}</dd>
              <dt>Socios críticos</dt><dd>{est.confianza.socios_criticos.length ? est.confianza.socios_criticos.map((ip) => <span key={ip} className="mono pol-ip">{ip}</span>) : "—"}</dd>
              <dt>Sospechar si hay ráfaga</dt><dd>{est.confianza.rafaga ? `${est.confianza.rafaga.alertas} alertas en ${est.confianza.rafaga.en_segundos} s del mismo origen` : "—"}</dd>
              <dt>Certeza mínima</dt><dd>{est.confianza.certeza_minima != null ? String(est.confianza.certeza_minima).replace(".", ",") : "—"}</dd>
              <dt>Desconocidos graves</dt><dd>{est.confianza.revisar_desde_nivel != null ? `a revisión desde el nivel ${est.confianza.revisar_desde_nivel}` : "solo se registran"}</dd>
            </dl>
          </> : <Vacio>El servicio no informa de la confianza.</Vacio>}
        </div>
      )}

      {pestana === "intocables" && (
        <div className="pol-panel">
          <ul className="pol-frases">
            {(est.intocables ?? []).map((i) => (
              <li key={`${i.activo}:${i.servicio}`}><span className="mono">{i.activo} · {String(i.servicio)}</span> — nunca en automático
                <Origen sujeto={`${i.activo} ${i.servicio}`} origen={i.origen} version={version} /></li>
            ))}
            <li><span className="mono">plano de gestión</span> — ninguna contención lo corta <Origen sujeto="plano de gestión" origen="codigo" /></li>
            {(est.confianza?.equipos_propios ?? "humano_siempre") !== "automatica_si_confianza" && (
              <li><span className="mono">equipos propios</span> — bloquearlos exige un analista{" "}
                <Origen sujeto="equipos propios" origen={est.confianza?.equipos_propios_origen ?? "codigo"} version={version} /></li>
            )}
            {est.familias.filter((f) => f.automatizacion === "nunca_automatica").map((f) => (
              <li key={f.familia}><span className="mono">{f.familia}</span> — freno duro: nunca se contiene solo <Origen sujeto={`freno ${f.familia}`} origen="codigo" /></li>
            ))}
          </ul>
        </div>
      )}

      {(pestana === "familias" || pestana === "zonas") && <div className="pol-grid">
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
                      <Origen sujeto={f.familia} origen={f.origen} version={version} />
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
                      <Origen sujeto={`zona ${z.zona}`} origen={z.origen} version={version} />
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
                                <Origen sujeto={d.activo} origen={d.origen} version={version} />
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
      </div>}
    </div>
  )
}
