import { useEffect, useMemo, useRef, useState } from "react"
import {
  useSondeo, getAsistente, escanearRed, guardarBorrador, getPropuestaRed,
  type AsistenteEstado, type BorradorRed, type EquipoBorrador, type PropuestaRed, type FalloCon,
} from "@/api"
import { MapaRed } from "@/components/MapaRed"
import "./AsistenteRed.css"

// Asistente de red: Escanear → Revisar lo encontrado → Validar y exportar (plan-asistente-de-red.md, tarea 6).
// La consola PROPONE: los ficheros se descargan y los instala el técnico; nunca se escribe el perfil vivo.

type Paso = 1 | 2 | 3
const PAPELES: [string, string][] = [["servidor", "Servidor"], ["cortafuegos", "Cortafuegos"], ["fragil", "Equipo frágil"], ["desconocido", "¿Desconocido?"]]
const CRITICIDADES: [string, string][] = [["baja", "Baja"], ["media", "Media"], ["alta", "Alta"], ["critica", "Crítica"]]
const RETARDO_MS = 600

function descargar(nombre: string, texto: string, tipo: string) {
  const url = URL.createObjectURL(new Blob([texto], { type: tipo }))
  const a = document.createElement("a")
  a.href = url; a.download = nombre
  document.body.appendChild(a); a.click(); a.remove()
  URL.revokeObjectURL(url)
}

function porIp(a: string, b: string) {
  const n = (s: string) => s.split(".").map((x) => x.padStart(3, "0")).join(".")
  return n(a).localeCompare(n(b))
}

function Escanear({ est }: { est: AsistenteEstado }) {
  const [rangos, setRangos] = useState<string[] | null>(null)
  const [nuevo, setNuevo] = useState("")
  const [externo, setExterno] = useState("")
  const [ritmo, setRitmo] = useState<"suave" | "normal">("suave")
  const [lista, setLista] = useState<string | null>(null)
  const [autorizado, setAutorizado] = useState(false)
  const [fallo, setFallo] = useState<string | null>(null)
  const actuales = rangos ?? est.por_defecto.rangos
  const listo = autorizado && actuales.length > 0 && externo.trim() !== "" && !est.escaneando

  const escanear = async () => {
    setFallo(null)
    const puertos = lista === null ? "comunes" : lista.split(",").map((x) => Number(x.trim())).filter((x) => x > 0)
    try {
      await escanearRed({ rangos: actuales, externo: externo.trim(), ritmo, puertos, autorizado })
    } catch (e) {
      setFallo((e as Error).message)
    }
  }
  return (
    <div className="asr-dos">
      <section className="asr-tarjeta" aria-labelledby="asr-que">
        <h2 id="asr-que">Qué escanear</h2>
        <div className="asr-campo">
          <span className="asr-etq">Rangos de la red del cliente</span>
          <div className="asr-chips">
            {actuales.map((r) => (
              <span key={r} className="asr-chip">{r}
                <button type="button" aria-label={`Quitar ${r}`} onClick={() => setRangos(actuales.filter((x) => x !== r))}>×</button>
              </span>
            ))}
          </div>
          <div className="asr-fila">
            <label className="asr-oculto" htmlFor="asr-nuevo">Añadir rango</label>
            <input id="asr-nuevo" className="asr-input asr-mono" placeholder="10.30.0.0/24" value={nuevo} onChange={(e) => setNuevo(e.target.value)} />
            <button type="button" className="asr-sec" disabled={!nuevo.trim()}
              onClick={() => { setRangos([...actuales, nuevo.trim()]); setNuevo("") }}>+ Añadir rango</button>
          </div>
          <p className="asr-ayuda">Pasan a ser las <b>redes internas</b> del perfil. Solo redes privadas, de /22 como mucho.</p>
        </div>
        <div className="asr-campo">
          <label className="asr-etq" htmlFor="asr-gestion">IP del MDR (plano de gestión)</label>
          <input id="asr-gestion" className="asr-input asr-mono" value={est.por_defecto.gestion ?? ""} readOnly />
          <p className="asr-ayuda">La del perfil. Ninguna contención la corta, y la propuesta de política la declara de confianza: el escaneo sale de aquí.</p>
        </div>
        <div className="asr-campo">
          <label className="asr-etq" htmlFor="asr-externo">Dirección de fuera para trazar la salida</label>
          <input id="asr-externo" className="asr-input asr-mono" placeholder="198.51.100.10" value={externo} onChange={(e) => setExterno(e.target.value)} />
          <p className="asr-ayuda">El traceroute hacia ella muestra por qué cortafuegos se sale a internet.</p>
        </div>
        <fieldset className="asr-campo">
          <legend className="asr-etq">Ritmo</legend>
          <div className="asr-opciones">
            <label className={`asr-opcion${ritmo === "suave" ? " sel" : ""}`}><input type="radio" name="asr-ritmo" checked={ritmo === "suave"} onChange={() => setRitmo("suave")} />
              <span>Suave (recomendado)<small>Más lento; no satura impresoras ni cámaras.</small></span></label>
            <label className={`asr-opcion${ritmo === "normal" ? " sel" : ""}`}><input type="radio" name="asr-ritmo" checked={ritmo === "normal"} onChange={() => setRitmo("normal")} />
              <span>Normal<small>Más rápido; para redes sin equipos frágiles.</small></span></label>
          </div>
        </fieldset>
        <fieldset className="asr-campo">
          <legend className="asr-etq">Puertos</legend>
          <div className="asr-opciones">
            <label className={`asr-opcion${lista === null ? " sel" : ""}`}><input type="radio" name="asr-puertos" checked={lista === null} onChange={() => setLista(null)} />
              <span>Los 1000 más comunes<small>Como «mdr escanear».</small></span></label>
            <label className={`asr-opcion${lista !== null ? " sel" : ""}`}><input type="radio" name="asr-puertos" checked={lista !== null} onChange={() => setLista("22,80,443")} />
              <span>Lista propia<small>Números separados por comas.</small></span></label>
          </div>
          {lista !== null && (
            <input aria-label="Lista de puertos" className="asr-input asr-mono" value={lista} onChange={(e) => setLista(e.target.value)} />
          )}
        </fieldset>
      </section>
      <div className="asr-col">
        <section className="asr-aviso" aria-labelledby="asr-antes">
          <h2 id="asr-antes">Antes de escanear</h2>
          <ul>
            <li>Escanear la red del cliente exige su <b>autorización por escrito</b>.</li>
            <li>El escaneo genera alertas en el SIEM del cliente. Avísale; el MDR las reconoce como suyas.</li>
            <li>Nada de lo que se encuentre se aplica solo: todo pasa por tu revisión.</li>
          </ul>
          <label className="asr-check"><input type="checkbox" checked={autorizado} onChange={(e) => setAutorizado(e.target.checked)} />
            Tengo la autorización por escrito del cliente para escanear estos rangos</label>
        </section>
        <section className="asr-tarjeta" aria-labelledby="asr-hara">
          <h2 id="asr-hara">Qué hará</h2>
          <ol className="asr-que">
            <li><b>Quién hay:</b> un barrido de los rangos.</li>
            <li><b>Qué ofrece cada uno:</b> sus puertos abiertos (y la postura que el motor necesita).</li>
            <li><b>Por dónde se llega:</b> un traceroute a cada equipo y hacia fuera.</li>
            <li><b>Quién es quién:</b> la huella SSH de cada equipo, para reconocer las interfaces de un mismo cortafuegos.</li>
          </ol>
          <div className="asr-fila">
            <button type="button" className="asr-primario" disabled={!listo} onClick={escanear}>Escanear</button>
            <span className="asr-ayuda">Tarda unos minutos a ritmo suave.</span>
          </div>
          {est.escaneando && <p className="asr-estado" role="status">Escaneando… la página se actualiza sola al terminar.</p>}
          {(fallo || est.error) && <p className="asr-error" role="alert">{fallo ?? `El último escaneo falló: ${est.error}`}</p>}
          {est.descubrimiento && (
            <p className="asr-ayuda">Último escaneo: {new Date(est.descubrimiento.fecha).toLocaleString("es")} por {est.descubrimiento.operador ?? "—"}.</p>
          )}
        </section>
      </div>
    </div>
  )
}

function Revisar({ borrador, nombres, propuesta, onCambio }: {
  borrador: BorradorRed; nombres: string[]; propuesta: PropuestaRed | null
  onCambio: (ip: string, campo: keyof EquipoBorrador, valor: unknown) => void
}) {
  // «Depende de» se escribe como texto (con sus comas) y se guarda como lista: si el campo mostrara la lista
  // ya limpia, la coma desaparecería al teclearla.
  const [depTexto, setDepTexto] = useState<Record<string, string>>({})
  const ips = Object.keys(borrador.equipos).sort(porIp)
  const nombreDe = (ip: string) => borrador.equipos[ip]?.nombre || ip
  const llegaPor = (e: EquipoBorrador) =>
    e.sin_camino ? "sin camino" : e.gateway ? nombreDe(e.gateway) : e.papel === "cortafuegos" ? "— (borde)" : "directo"
  return (
    <>
      <section className="asr-tarjeta" aria-labelledby="asr-equipos">
        <h2 id="asr-equipos">Equipos encontrados</h2>
        <p className="asr-ayuda">El nombre debe ser el que el equipo trae en las alertas del SIEM: es el que el MDR usará para reconocerlo.
          Las sugerencias son nombres que las alertas ya han traído y el perfil aún no conoce.</p>
        <datalist id="nombres-siem">{nombres.map((n) => <option key={n} value={n} />)}</datalist>
        <div className="asr-caja-tabla">
          <table className="asr-tabla">
            <thead><tr><th>Incluir</th><th>Nombre en el SIEM</th><th>IP</th><th>Servicios</th><th>Llega por</th><th>Zona</th><th>Papel</th><th>Criticidad</th><th>No tocar</th><th>Depende de</th></tr></thead>
            <tbody>
              {ips.map((ip) => {
                const e = borrador.equipos[ip]
                const fw = e.papel === "cortafuegos"
                return (
                  <tr key={ip} className={e.incluido ? "" : "asr-descartado"}>
                    <td><input type="checkbox" aria-label={`Incluir ${ip}`} checked={e.incluido} onChange={(x) => onCambio(ip, "incluido", x.target.checked)} /></td>
                    <td>
                      <input className={`asr-input asr-nombre${e.incluido && !e.nombre ? " asr-falta" : ""}`} list="nombres-siem"
                        aria-label={`Nombre en el SIEM de ${ip}`} placeholder="escribe el nombre" value={e.nombre}
                        onChange={(x) => onCambio(ip, "nombre", x.target.value)} />
                      {e.interfaces.length > 0 && <span className="asr-nota">también {e.interfaces.join(", ")}</span>}
                    </td>
                    <td className="asr-mono">{ip}</td>
                    <td><span className="asr-serv">{e.servicios.length ? e.servicios.map((p) => <span key={p} className="asr-p">{p}</span>) : <span className="asr-nota">ninguno</span>}</span></td>
                    <td className={e.sin_camino ? "asr-ojo" : ""}>{llegaPor(e)}{e.deducido && <span className="asr-nota">deducido: confírmalo</span>}</td>
                    <td>{fw ? "—" : <input className="asr-input asr-zona" aria-label={`Zona de ${ip}`} value={e.zona ?? ""} onChange={(x) => onCambio(ip, "zona", x.target.value)} />}</td>
                    <td><select className="asr-input" aria-label={`Papel de ${ip}`} value={e.papel} onChange={(x) => onCambio(ip, "papel", x.target.value)}>
                      {PAPELES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></td>
                    <td><select className="asr-input" aria-label={`Criticidad de ${ip}`} value={e.criticidad} onChange={(x) => onCambio(ip, "criticidad", x.target.value)}>
                      {CRITICIDADES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></td>
                    <td>{fw ? "—" : <input type="checkbox" aria-label={`No tocar ${ip} directamente`} checked={e.no_tocar} onChange={(x) => onCambio(ip, "no_tocar", x.target.checked)} />}</td>
                    <td>{fw ? "—" : <input className="asr-input asr-dep" aria-label={`Depende de (${ip})`} placeholder="nombres, con comas"
                      value={depTexto[ip] ?? e.depende_de.join(", ")}
                      onChange={(x) => {
                        setDepTexto({ ...depTexto, [ip]: x.target.value })
                        onCambio(ip, "depende_de", x.target.value.split(",").map((t) => t.trim()).filter(Boolean))
                      }} />}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
      <div className="asr-dos">
        <section className="asr-tarjeta" aria-labelledby="asr-mapa">
          <h2 id="asr-mapa">Así queda el mapa</h2>
          {propuesta ? <MapaRed red={propuesta.red} seleccionado={null} onSeleccionar={() => {}} dependencias ataques={false} cascada={false} />
            : <p className="asr-ayuda">Dibujando…</p>}
        </section>
        <section className="asr-tarjeta" aria-labelledby="asr-falta">
          <h2 id="asr-falta">Falta para exportar</h2>
          {!propuesta ? <p className="asr-ayuda">Comprobando…</p>
            : propuesta.validacion.errores.length === 0 ? <p className="asr-ok">Nada: puedes validar y exportar.</p>
            : <ul className="asr-lista">{propuesta.validacion.errores.map((x) => <li key={x}>{x}</li>)}</ul>}
        </section>
      </div>
    </>
  )
}

function Exportar({ propuesta }: { propuesta: PropuestaRed | null }) {
  const [vista, setVista] = useState<"perfil" | "postura" | "politica">("perfil")
  if (!propuesta) return <p className="asr-ayuda">Comprobando la propuesta…</p>
  const { errores, avisos } = propuesta.validacion
  const bloqueado = errores.length > 0
  const ficheros: [typeof vista, string, string, string][] = [
    ["perfil", "perfil.yml", propuesta.perfil_yaml, "application/x-yaml"],
    ["postura", "postura.json", propuesta.postura_json, "application/json"],
    ["politica", "politica.yml", propuesta.politica_yaml, "application/x-yaml"],
  ]
  return (
    <div className="asr-dos">
      <div className="asr-col">
        <section className="asr-tarjeta" aria-labelledby="asr-val">
          <h2 id="asr-val">Validación</h2>
          <p className={bloqueado ? "asr-error" : "asr-ok"}>{bloqueado ? `${errores.length} error(es): corrígelos en «Revisar»` : `Sin errores · ${avisos.length} aviso(s)`}</p>
          {errores.length > 0 && <ul className="asr-lista">{errores.map((x) => <li key={x}>{x}</li>)}</ul>}
          {avisos.length > 0 && <ul className="asr-lista asr-avisos">{avisos.map((x) => <li key={x}>{x}</li>)}</ul>}
        </section>
        <section className="asr-tarjeta" aria-labelledby="asr-desc">
          <h2 id="asr-desc">Descargar</h2>
          <div className="asr-fila">
            {ficheros.map(([, nombre, texto, tipo]) => (
              <button key={nombre} type="button" className="asr-sec" disabled={bloqueado} onClick={() => descargar(nombre, texto, tipo)}>Descargar {nombre}</button>
            ))}
          </div>
          <p className="asr-ayuda">politica.yml es una propuesta: el MDR como administrador y todo esperando a un analista, pendiente de que la apruebe Seguridad.</p>
        </section>
        <section className="asr-tarjeta" aria-labelledby="asr-sig">
          <h2 id="asr-sig">Siguientes pasos</h2>
          <ol className="asr-que">
            <li>Revisa los ficheros y pásalos por el control de cambios del cliente.</li>
            <li>Compruébalo: <code>sudo mdr validar-perfil perfil.yml</code></li>
            <li>Instálalos (<code>/etc/mdr/perfil.yml</code>, <code>/var/lib/mdr/postura.json</code>, y la política cuando la apruebe Seguridad) y reinicia el servicio.</li>
            <li>En Conectividad, da de alta cada equipo: paquete de alta, huella SSH y prueba.</li>
          </ol>
        </section>
        <p className="asr-regla">La consola <b>no escribe el perfil vivo</b>: cambiar la red cambia dónde y cómo contiene el MDR, así que lo aplica el técnico.</p>
      </div>
      <section className="asr-tarjeta" aria-labelledby="asr-prev">
        <h2 id="asr-prev">Vista previa</h2>
        <div role="tablist" aria-label="Ficheros" className="asr-pestanas">
          {ficheros.map(([id, nombre]) => (
            <button key={id} type="button" role="tab" aria-selected={vista === id} className={vista === id ? "on" : ""} onClick={() => setVista(id)}>{nombre}</button>
          ))}
        </div>
        <pre className="asr-pre">{ficheros.find(([id]) => id === vista)![2]}</pre>
      </section>
    </div>
  )
}

export function AsistenteRed() {
  const t = useSondeo(getAsistente, 3000)
  // El estado trae su propio `error` (el del último escaneo): el fallo del sondeo se distingue por no traer `escaneando`.
  const est: AsistenteEstado | undefined = t && "escaneando" in t ? t : (t as FalloCon<AsistenteEstado> | undefined)?.datos
  const [paso, setPaso] = useState<Paso | null>(null)
  const [local, setLocal] = useState<BorradorRed | null>(null)
  const [propuesta, setPropuesta] = useState<PropuestaRed | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  const [guardados, setGuardados] = useState(0)
  const pendiente = useRef<Record<string, Partial<EquipoBorrador>>>({})
  const reloj = useRef<ReturnType<typeof setTimeout> | null>(null)

  const remoto = est?.borrador ?? null
  const borrador = local && remoto && local.basado_en === remoto.basado_en ? local : remoto
  // La propuesta la calcula el servidor con SU borrador: se pide cuando ese cambia (sondeo) o justo después de
  // guardar, nunca con cada pulsación (el servidor aún no tendría el cambio).
  const claveRemota = useMemo(() => JSON.stringify(remoto), [remoto])
  const actual: Paso = paso ?? (borrador ? 2 : 1)

  useEffect(() => {
    if (!borrador) return
    let vivo = true
    getPropuestaRed().then((r) => { if (vivo && !("error" in r)) setPropuesta(r) })
    return () => { vivo = false }
  }, [claveRemota, guardados])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => { if (reloj.current) clearTimeout(reloj.current) }, [])

  if (!est) return <p className="asr-ayuda">Cargando el asistente…</p>

  const cambiar = (ip: string, campo: keyof EquipoBorrador, valor: unknown) => {
    if (!borrador) return
    const nuevo = { ...borrador, equipos: { ...borrador.equipos, [ip]: { ...borrador.equipos[ip], [campo]: valor } } }
    setLocal(nuevo)
    pendiente.current = { ...pendiente.current, [ip]: { ...(pendiente.current[ip] ?? {}), [campo]: valor } }
    if (reloj.current) clearTimeout(reloj.current)
    reloj.current = setTimeout(async () => {
      const cambios = pendiente.current
      pendiente.current = {}
      try {
        setLocal(await guardarBorrador(cambios))
        setFallo(null)
        setGuardados((n) => n + 1)
      } catch (e) {
        setFallo(`No se guardó: ${(e as Error).message}`)
      }
    }, RETARDO_MS)
  }

  const pasos: [Paso, string][] = [[1, "Escanear"], [2, "Revisar lo encontrado"], [3, "Validar y exportar"]]
  return (
    <div className="asr">
      {/* el título ya está en la barra superior, como en las demás vistas */}
      <header className="asr-cab">
        <p>Describe una red nueva a partir de un escaneo. Propone el perfil para que lo revises; no lo aplica.</p>
      </header>
      <div role="tablist" aria-label="Pasos del asistente" className="asr-pasos">
        {pasos.map(([n, nombre]) => (
          <button key={n} type="button" role="tab" aria-selected={actual === n} className={actual === n ? "on" : ""}
            disabled={n > 1 && !borrador} onClick={() => setPaso(n)}><b>{n}</b>{nombre}</button>
        ))}
      </div>
      {fallo && <p className="asr-error" role="alert">{fallo}</p>}
      {actual === 1 && <Escanear est={est} />}
      {actual === 2 && borrador && <Revisar borrador={borrador} nombres={est.nombres_siem} propuesta={propuesta} onCambio={cambiar} />}
      {actual === 3 && <Exportar propuesta={propuesta} />}
    </div>
  )
}
