import { Fragment, useEffect, type ReactNode } from "react"
import { createPortal } from "react-dom"
import type { Metricas } from "@/api"
import { etiquetaClase, quienDecidio, SIN_NOMBRE } from "@/datos"
import { resumenRedactado, recomendaciones } from "@/informe"
import { ESTADO_CASO } from "@/components/PanelCaso"
import type { DatosInforme } from "@/informeDatos"
import "./InformeDocumento.css"

// El informe como DOCUMENTO A4 (no una captura de la pantalla): portada, una sección por hoja con
// cabecera, pie y número, tablas en vez de gráficas interactivas. Se genera en el navegador con los
// datos del periodo; «Guardar PDF» imprime solo el documento y el PDF toma su nombre del título.

const num = (x?: number | null) => (x == null ? "—" : x.toLocaleString("es"))
const pc = (x?: number | null) => (x == null ? "—" : `${(Math.round(x * 1000) / 10).toLocaleString("es")} %`)
// segundos legibles: hasta 2 min en segundos, hasta 2 h en minutos, luego en horas
const seg = (x?: number | null) => x == null ? "—" : x < 120 ? `${Math.round(x)} s` : x < 7200 ? `${Math.round(x / 60)} min` : `${(Math.round(x / 360) / 10).toLocaleString("es")} h`
const MAX_FILAS = 12, MAX_DETALLE = 30, MAX_ANALISTAS = 6   // acotadas: cada sección cabe en su hoja A4

function Pagina({ seccion, n, total, d, children }: { seccion: string; n: number; total: number; d: DatosInforme; children: ReactNode }) {
  return (
    <section className="pagina" aria-label={`Página ${n} de ${total}`}>
      <div className="run"><span>Informe MDR · {d.para || "cliente"} · {d.periodo.etiqueta}</span><span>{seccion}</span></div>
      {children}
      <div className="pie"><span>Confidencial · uso interno del cliente</span><span>Página {n} de {total}</span></div>
    </section>
  )
}

function Barras({ filas }: { filas: { nombre: string; n: number }[] }) {
  const max = Math.max(1, ...filas.map((f) => f.n))
  return (
    <div className="barras">
      {filas.map((f) => <Fragment key={f.nombre}><span>{f.nombre}</span><i style={{ width: `${(f.n / max) * 100}%` }} /><span className="n">{num(f.n)}</span></Fragment>)}
    </div>
  )
}

// Decisiones por día como barras estáticas (SVG), con la cifra del pico y la media debajo.
function PorDia({ dias }: { dias: { dia: string; n: number }[] }) {
  if (!dias.length) return <p className="sub">Sin decisiones en el periodo.</p>
  // el hueco de cada día es el de un mes (31): con pocos días las barras no se vuelven bloques
  const max = Math.max(1, ...dias.map((x) => x.n)), w = 170 / Math.max(dias.length, 31)
  const pico = dias.reduce((a, b) => (b.n > a.n ? b : a))
  const media = Math.round(dias.reduce((a, b) => a + b.n, 0) / dias.length)
  return (
    <>
      <svg viewBox="0 0 170 40" style={{ width: "100%", height: "auto" }} aria-label="Decisiones por día">
        {dias.map((x, i) => { const h = (x.n / max) * 36; return <rect key={x.dia} x={i * w + w * 0.15} y={38 - h} width={w * 0.7} height={h} fill="#0b6a79" /> })}
        <line x1="0" y1="38.5" x2="170" y2="38.5" stroke="#1b1f24" strokeWidth=".4" />
      </svg>
      <p className="sub">Pico el {pico.dia}: {num(pico.n)} decisiones. Media diaria: {num(media)}.</p>
    </>
  )
}

export function InformeDocumento({ d }: { d: DatosInforme }) {
  const { m, anterior: a } = d
  const s = d.secciones
  const abiertos = d.incidentes.filter((e) => e.caso.estado !== "resuelto").length
  const totalFallidas = d.fallidas.reduce((x, f) => x + f.n, 0)
  const recs = recomendaciones(m, totalFallidas, abiertos)
  const destacado = [...d.incidentes].sort((x, y) => y.n - x.n)[0]
  const hojas: { seccion: string; cuerpo: ReactNode }[] = []

  if (s.has("resumen")) hojas.push({ seccion: "Resumen ejecutivo", cuerpo: <>
    <h2>Resumen ejecutivo</h2>
    <p>{resumenRedactado(m, d.periodo.etiqueta)}</p>
    <div className="kpis">
      <div><b>{num(m.total)}</b><span>amenazas tratadas</span></div>
      <div><b>{pc(m.pct_auto)}</b><span>contenidas en automático</span></div>
      <div><b>{pc(m.tasa_fp)}</b><span>falsos positivos</span></div>
      <div><b>{pc(m.sla_pct)}</b><span>dentro de SLA ({Math.round((m.sla_umbral_seg ?? 900) / 60)} min)</span></div>
    </div>
    {destacado && <div className="destacado"><b>A destacar.</b> La campaña desde {destacado.cidr}{destacado.pais ? ` (${destacado.pais})` : ""} sumó {num(destacado.n)} decisiones contra {destacado.objetivos.slice(0, 2).map((o) => o.equipo).join(" y ")}; se contuvieron {num(destacado.contenidas)} y el caso está {(ESTADO_CASO[destacado.caso.estado]?.texto ?? destacado.caso.estado).toLowerCase()}.</div>}
    <h3>Recomendaciones</h3>
    {recs.length ? <ol style={{ margin: 0, paddingLeft: "5mm", listStyle: "decimal" }}>{recs.map((r, i) => <li key={i} style={{ marginBottom: "1.5mm" }}>{r}</li>)}</ol>
      : <p className="sub">Los datos del periodo no señalan ninguna acción pendiente.</p>}
  </> })

  if (s.has("indicadores")) {
    const fila = (k: string, f: (x: Metricas) => string) => <tr key={k}><td>{k}</td><td className="n">{f(m)}</td>{a && <td className="n">{f(a)}</td>}</tr>
    hojas.push({ seccion: "Indicadores", cuerpo: <>
      <h2>Indicadores y SLA</h2>
      <table>
        <thead><tr><th>Indicador</th><th className="n">{d.periodo.etiqueta}</th>{a && <th className="n">{d.periodo.etiquetaAnterior}</th>}</tr></thead>
        <tbody>
          {fila("Decisiones", (x) => num(x.total))}
          {fila("Contenidas en automático", (x) => pc(x.pct_auto))}
          {fila("Escaladas a un analista", (x) => pc(x.pct_humano))}
          {fila("Tasa de falsos positivos", (x) => pc(x.tasa_fp))}
          {fila("MTTR mediano", (x) => seg(x.mttr_mediano_seg))}
          {fila("MTTR medio", (x) => seg(x.mttr_seg))}
          {fila(`Dentro de SLA (${Math.round((m.sla_umbral_seg ?? 900) / 60)} min)`, (x) => pc(x.sla_pct))}
          {fila("SLA incumplidos", (x) => num(x.sla_incumplidos ?? 0))}
          {fila("Alertas de ruido evitadas", (x) => num(x.suprimidas))}
          {fila("Correcciones del analista", (x) => pc(x.tasa_override))}
        </tbody>
      </table>
      <h3>Decisiones por día</h3>
      <PorDia dias={m.por_dia} />
    </> })
  }

  if (s.has("amenazas")) hojas.push({ seccion: "Amenazas", cuerpo: <>
    <h2>Amenazas y orígenes</h2>
    <h3>Por familia</h3>
    {(m.por_familia ?? []).length ? <Barras filas={(m.por_familia ?? []).slice(0, 8).map((f) => ({ nombre: f.familia, n: f.n }))} /> : <p className="sub">Sin datos.</p>}
    <h3>Por país de origen</h3>
    <table><thead><tr><th>Ubicación</th><th className="n">Ataques</th><th className="n">% del total</th></tr></thead>
      <tbody>{(m.por_pais ?? []).slice(0, 8).map((p) => <tr key={p.pais}><td>{p.pais}</td><td className="n">{num(p.n)}</td><td className="n">{pc(m.total ? p.n / m.total : 0)}</td></tr>)}</tbody></table>
    <h3>Equipos más atacados</h3>
    <table><thead><tr><th>Equipo</th><th className="n">Ataques</th></tr></thead>
      <tbody>{m.top_activos.slice(0, 6).map((x) => <tr key={x.nombre}><td>{x.nombre}</td><td className="n">{num(x.n)}</td></tr>)}</tbody></table>
  </> })

  if (s.has("incidentes") || s.has("humanas")) {
    const humanas = Object.values(m.veredictos).reduce((x, y) => x + y, 0)
    hojas.push({ seccion: s.has("incidentes") ? "Incidentes" : "Decisiones humanas", cuerpo: <>
      <h2>{s.has("incidentes") ? "Incidentes del periodo" : "Decisiones humanas"}</h2>
      {s.has("incidentes") && <>{d.incidentes.length ? (
        <table><thead><tr><th>Campaña</th><th>Estado</th><th>Responsable</th><th className="n">Decisiones</th><th className="n">Contenidas</th></tr></thead>
          <tbody>{d.incidentes.slice(0, MAX_FILAS).map((e) => (
            <tr key={e.clave}><td>{e.cidr}{e.pais ? ` · ${e.pais}` : ""}</td>
              <td><span className={`etq ${e.caso.estado === "resuelto" ? "ok" : ""}`}>{(ESTADO_CASO[e.caso.estado]?.texto ?? e.caso.estado).toLowerCase()}</span></td>
              <td>{e.caso.asignado ?? "—"}</td><td className="n">{num(e.n)}</td><td className="n">{num(e.contenidas)}</td></tr>))}</tbody></table>
      ) : <p className="sub">Sin incidentes en el periodo dentro de la ventana de trazas cargada.</p>}
      {d.incidentes.length > MAX_FILAS && <p className="sub">… y {d.incidentes.length - MAX_FILAS} más.</p>}</>}
      {s.has("humanas") && <>
      <h3>Decisiones humanas</h3>
      <table><thead><tr><th>Veredicto</th><th className="n">Nº</th><th className="n">%</th></tr></thead>
        <tbody>{([["aprobar", "Aprobadas"], ["rechazar", "Rechazadas"], ["reclasificar", "Reclasificadas"]] as const).map(([k, t]) => (
          <tr key={k}><td>{t}</td><td className="n">{num(m.veredictos[k] ?? 0)}</td><td className="n">{pc(humanas ? (m.veredictos[k] ?? 0) / humanas : 0)}</td></tr>))}</tbody></table>
      {(m.por_analista ?? []).length > 0 && <>
        <h3>Por analista</h3>
        <table><thead><tr><th>Analista</th><th className="n">Aprob.</th><th className="n">Rechaz.</th><th className="n">Reclasif.</th><th className="n">Resp. mediana</th><th className="n">Fuera de SLA</th></tr></thead>
          <tbody>{(m.por_analista ?? []).slice(0, MAX_ANALISTAS).map((f) => (
            <tr key={f.analista ?? "—"}><td>{f.analista ?? <i className="sub">{SIN_NOMBRE}</i>}</td><td className="n">{num(f.aprobar)}</td><td className="n">{num(f.rechazar)}</td>
              <td className="n">{num(f.reclasificar)}</td><td className="n">{seg(f.mediana_seg)}</td><td className="n">{num(f.fuera_sla)}</td></tr>))}</tbody></table>
        {(m.por_analista ?? []).length > MAX_ANALISTAS && <p className="sub">… y {(m.por_analista ?? []).length - MAX_ANALISTAS} analistas más.</p>}
      </>}
      <h3>Contenciones que fallaron</h3>
      {d.fallidas.length ? <p>{d.fallidas.map((f) => <span key={f.activo}><span className="etq mal">{f.n}</span> en {f.activo}. </span>)}Conviene revisar la conectividad del conector con esos equipos.</p>
        : <p className="sub">Ninguna contención falló en el periodo.</p>}</>}
    </> })
  }

  if (s.has("detalle")) hojas.push({ seccion: "Anexo: decisiones", cuerpo: <>
    <h2>Detalle de las decisiones</h2>
    <table><thead><tr><th>Fecha</th><th>Equipo</th><th>Clase</th><th>Acción</th><th>Decidió</th></tr></thead>
      <tbody>{d.decisiones.slice(0, MAX_DETALLE).map((x, i) => (
        <tr key={`${x.id_decision}-${i}`}><td className="mono">{(x.timestamp ?? "").slice(0, 16).replace("T", " ")}</td><td>{x.activo ?? "—"}</td>
          <td>{x.clase ? etiquetaClase(x.clase) : "—"}</td><td className="mono">{x.accion_final ?? "—"}</td>
          <td>{quienDecidio(x) ?? "automática"}</td></tr>))}</tbody></table>
    {d.decisiones.length > MAX_DETALLE && <p className="sub">Se muestran {MAX_DETALLE} de {num(d.decisiones.length)}; el registro completo está en la traza.</p>}
  </> })

  if (s.has("integridad") || s.has("attack")) hojas.push({ seccion: "Anexo", cuerpo: <>
    <h2>{s.has("integridad") ? "Integridad y método" : "Cobertura y método"}</h2>
    {s.has("integridad") && <>
      <h3>Integridad de la traza</h3>
      <p>Cada decisión se encadena con la anterior mediante SHA-256. La verificación de la cadena completa a la fecha de generación fue{" "}
        <b>{d.verificacion == null ? "no disponible" : d.verificacion.ok ? "correcta: ningún registro fue alterado" : `fallida: la cadena se rompe en el registro #${(d.verificacion.roto_en ?? 0) + 1}`}</b>.</p>
      <table><tbody>
        <tr><td>Decisiones del periodo</td><td className="n">{num(m.total)}</td></tr>
        <tr><td>Hash del último registro cargado</td><td className="n mono">{d.ultimoHash ? `${d.ultimoHash.slice(0, 16)}…${d.ultimoHash.slice(-6)}` : "—"}</td></tr>
      </tbody></table>
    </>}
    {s.has("attack") && <>
      <h3>Cobertura MITRE ATT&amp;CK</h3>
      <p>{m.mitre.length ? `${m.mitre.length} técnicas observadas: ${m.mitre.map((t) => `${t.tecnica} (${num(t.n)})`).join(", ")}.` : "Sin técnicas registradas en el periodo."}</p>
    </>}
    <h3>Método</h3>
    <p>Las alertas proceden del SIEM del cliente; el MDR las clasifica, decide la respuesta según la política acordada y deja traza de cada paso. Los porcentajes se calculan sobre las decisiones del periodo.</p>
    <h3>Glosario</h3>
    <p><b>MTTR</b>: tiempo hasta la decisión de un analista. <b>SLA</b>: decisión humana dentro del umbral acordado. <b>Falso positivo</b>: alerta descartada como actividad legítima.</p>
  </> })

  const total = hojas.length + 1
  return (
    <div className="doc-informe">
      <section className="pagina portada" aria-label={`Página 1 de ${total}`}>
        <div className="marca"><b>M</b>MDR · consola de triaje</div>
        <div>
          <div className="titulo">Informe de detección y respuesta gestionada</div>
          <div className="subtitulo">{d.periodo.etiqueta[0].toUpperCase() + d.periodo.etiqueta.slice(1)}{d.para ? ` · ${d.para}` : ""}</div>
        </div>
        <div className="meta">
          <span>Periodo</span><span>{d.periodo.desde} a {d.periodo.hasta}</span>
          <span>Para</span><span>{d.para || "—"}</span>
          <span>Generado</span><span>{d.generado.en}{d.generado.por ? ` · ${d.generado.por}` : ""}</span>
          <span>Registros</span><span>{num(m.total)} decisiones encadenadas</span>
          <span>Integridad</span><span className="mono">{d.verificacion == null ? "no verificada" : d.verificacion.ok ? "cadena íntegra" : "cadena ROTA"}{d.ultimoHash ? ` · último hash ${d.ultimoHash.slice(0, 12)}…` : ""}</span>
        </div>
      </section>
      {hojas.map((h, i) => <Pagina key={h.seccion} seccion={h.seccion} n={i + 2} total={total} d={d}>{h.cuerpo}</Pagina>)}
    </div>
  )
}

// Vista previa a pantalla completa. «Guardar PDF» imprime SOLO el documento: marca el <html> para que
// la hoja de impresión oculte la consola y pone el nombre del archivo como título mientras imprime.
export function VistaPreviaInforme({ d, onCerrar }: { d: DatosInforme; onCerrar: () => void }) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onCerrar() }
    window.addEventListener("keydown", esc)
    return () => window.removeEventListener("keydown", esc)
  }, [onCerrar])
  const guardar = () => {
    const titulo = document.title
    const html = document.documentElement
    const fin = () => { document.title = titulo; html.classList.remove("imprimiendo-informe"); window.removeEventListener("afterprint", fin) }
    window.addEventListener("afterprint", fin)
    html.classList.add("imprimiendo-informe")
    document.title = d.nombre
    window.print()
    setTimeout(fin, 1000)      // por si el navegador no emite afterprint
  }
  return createPortal(
    <div className="doc-previa" role="dialog" aria-label="Vista previa del informe">
      <div className="barra">
        <b>Vista previa del PDF</b><span className="nombre">{d.nombre}.pdf</span>
        <span style={{ marginLeft: "auto" }} />
        <button type="button" onClick={onCerrar}>Cerrar</button>
        <button type="button" className="pri" onClick={guardar}>Guardar PDF</button>
      </div>
      <div className="hojas"><InformeDocumento d={d} /></div>
    </div>,
    document.body,
  )
}
