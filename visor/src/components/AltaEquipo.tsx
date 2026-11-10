import { useEffect, useState } from "react"
import {
  guardarInventario, getPaquete, leerClaveHost, aceptarClaveHost, darDeAlta,
  type Conectividad as Datos, type EquipoConectividad, type FormatoPaquete, type PruebaConexion,
} from "@/api"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"
import { Boton, Capa, Pasos } from "./ConectividadUi"

// Asistente «Añadir equipo» (y «Papel y reglas» de un equipo existente). El MDR nunca ve una credencial
// de administrador: genera el paquete de alta del equipo, el administrador del cliente lo ejecuta, y la
// plataforma fija la clave del host (comparando la huella que imprimió el propio equipo) y prueba.

type Paso = 1 | 2 | 3 | 4
const NOMBRE = /^[a-z0-9][a-z0-9-]{1,30}$/
const IPV4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/
const lista = (t: string) => t.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean)
const campo = "h-8 w-full rounded-[7px] border border-border bg-card px-2.5 text-[13px] outline-none focus:border-ring"

function Etiqueta({ id, texto, ayuda, children }: { id: string; texto: string; ayuda?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 text-[12.5px]">
      <label htmlFor={id} className="font-medium">{texto}</label>
      {children}
      {ayuda && <span className="text-[11.5px] text-muted-foreground">{ayuda}</span>}
    </div>
  )
}

export function AltaEquipo({ d, equipo, pasoInicial, onCerrar, onCambio }: {
  d: Datos; equipo?: EquipoConectividad | null; pasoInicial?: Paso; onCerrar: () => void; onCambio: () => void
}) {
  const toast = useToast()
  const existente = !!equipo && equipo.alta !== "pendiente"        // solo su papel y reglas
  const nuevo = !equipo || equipo.alta === "pendiente"
  const papeles = d.papeles ?? []
  const acciones = d.acciones ?? []
  const [paso, setPaso] = useState<Paso>(pasoInicial ?? (existente ? 2 : 1))
  const [nombre, setNombre] = useState(equipo?.nombre ?? "")
  const [ip, setIp] = useState(equipo?.ip ?? "")
  const [zona, setZona] = useState(equipo?.zona ?? d.zonas?.[0] ?? "")
  const [funcion, setFuncion] = useState(equipo?.funcion ?? "")
  const [criticidad, setCriticidad] = useState(equipo?.criticidad ?? "media")
  const [depende, setDepende] = useState<string[]>(equipo?.depende_de ?? [])
  const [interfaz, setInterfaz] = useState(equipo?.interfaz ?? "")
  const [papel, setPapel] = useState(equipo?.papel ?? "servidor")
  const [elegidas, setElegidas] = useState<Set<string>>(() => new Set(equipo?.acciones ?? papeles.find((p) => p.id === (equipo?.papel ?? "servidor"))?.acciones ?? []))
  const [servicios, setServicios] = useState((equipo?.servicios ?? []).join(", "))
  const [cuentas, setCuentas] = useState((equipo?.cuentas ?? []).join(", "))
  const [cualquiera, setCualquiera] = useState(!!equipo?.cuentas_cualquiera)
  const [formato, setFormato] = useState<FormatoPaquete>("script")
  const [paquete, setPaquete] = useState<{ nombre: string; contenido: string } | null>(null)
  const [host, setHost] = useState<{ presentada?: string | null; fijada?: string | null } | null>(null)
  const [coincide, setCoincide] = useState(false)
  const [prueba, setPrueba] = useState<PruebaConexion | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // el paquete se pide al entrar en el paso 3 o al cambiar de formato (respuesta asíncrona del daemon)
  useEffect(() => {
    if (paso !== 3 || !nombre) return
    let vivo = true
    getPaquete(nombre, formato).then((r) => {
      if (!vivo) return
      if ("error" in r) setError(`No se pudo generar el paquete (${r.error})`)
      else setPaquete({ nombre: r.nombre, contenido: r.contenido })
    })
    return () => { vivo = false }
  }, [paso, formato, nombre])

  const elegirPapel = (id: string) => { setPapel(id); setElegidas(new Set(papeles.find((p) => p.id === id)?.acciones ?? [])) }
  const alternar = (id: string) => setElegidas((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const paso1Ok = NOMBRE.test(nombre) && IPV4.test(ip) && !!zona
  const sinLista = (lst: string) => acciones.filter((a) => a.lista === lst && elegidas.has(a.id))

  async function guardarReglas() {
    setOcupado(true); setError(null)
    const r = await guardarInventario({
      nombre, papel, acciones: [...elegidas], servicios: lista(servicios), cuentas: cualquiera ? [] : lista(cuentas), cuentas_cualquiera: cualquiera,
      ...(nuevo ? { ip, zona, funcion, criticidad, depende_de: depende, interfaz: interfaz.trim() || null } : {}),
    })
    setOcupado(false)
    if (r.status !== 200) { setError(String(r.datos.error ?? `HTTP ${r.status}`)); return }
    onCambio(); setPaquete(null); setPaso(3)
  }
  async function leer() {
    setOcupado(true); setError(null)
    const r = await leerClaveHost(nombre)
    setOcupado(false)
    if (r.status === 200) setHost(r.datos as typeof host)
    else setError(String(r.datos.error ?? `HTTP ${r.status}`))
  }
  async function alta() {
    if (!host?.presentada) return
    setOcupado(true); setError(null)
    if (host.fijada !== host.presentada) {
      // la casilla «Coincide con la que imprimió el equipo» es la confirmación explícita
      const a = await aceptarClaveHost(nombre, host.presentada, !!host.fijada)
      if (a.status !== 200) { setOcupado(false); setError(String(a.datos.error ?? `HTTP ${a.status}`)); return }
    }
    const r = await darDeAlta(nombre, host.presentada)
    setOcupado(false)
    if (r.datos.prueba) setPrueba(r.datos.prueba as PruebaConexion)
    onCambio()
    if (r.status === 200) { toast({ type: "success", title: `${nombre} dado de alta`, description: "El motor ya puede contener en él." }); onCerrar() }
    else setError(String(r.datos.error ?? `HTTP ${r.status}`))
  }
  function descargar() {
    if (!paquete) return
    const url = URL.createObjectURL(new Blob([paquete.contenido], { type: "text/plain" }))
    const a = document.createElement("a"); a.href = url; a.download = paquete.nombre; a.click()
    URL.revokeObjectURL(url)
  }
  async function copiar() {
    try { await navigator.clipboard.writeText(paquete?.contenido ?? ""); toast({ type: "success", title: "Paquete copiado" }) }
    catch { toast({ type: "error", title: "El navegador no permitió copiar" }) }
  }

  const pasos: { n: Paso; t: string }[] = existente
    ? [{ n: 2, t: "Papel y reglas" }, { n: 3, t: "Paquete de corrección" }]
    : [{ n: 1, t: "Inventario" }, { n: 2, t: "Papel y reglas" }, { n: 3, t: "Paquete de alta" }, { n: 4, t: "Verificar y dar de alta" }]
  return (
    <Capa titulo={existente ? `Papel y reglas de ${nombre}` : equipo ? `Alta de ${nombre}` : "Añadir equipo"} onCerrar={onCerrar}>
      <ol className="flex border-b border-border">
        {pasos.map((p) => (
          <li key={p.n} aria-current={p.n === paso ? "step" : undefined}
            className={cn("flex flex-1 items-center gap-2 border-r border-border px-4 py-2.5 text-[12.5px] last:border-r-0",
              p.n === paso ? "bg-primary/7 font-semibold" : "text-muted-foreground")}>
            <span className={cn("grid size-[22px] shrink-0 place-items-center rounded-full text-[11.5px]",
              p.n < paso ? "bg-ok/18 text-ok" : p.n === paso ? "bg-primary text-primary-foreground" : "bg-muted")}>{p.n < paso ? "✓" : p.n - (existente ? 1 : 0)}</span>{p.t}
          </li>
        ))}
      </ol>
      <div className="space-y-4 px-5 py-4">
        {error && <p role="alert" className="rounded-md border border-critico/35 bg-critico/10 px-3 py-2 text-[13px] text-critico">{error}</p>}

        {paso === 1 && (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <Etiqueta id="al-nombre" texto="Nombre" ayuda="Minúsculas, números y guiones."><input id="al-nombre" className={campo} value={nombre} onChange={(e) => setNombre(e.target.value.trim())} disabled={!!equipo} /></Etiqueta>
              <Etiqueta id="al-ip" texto="IP" ayuda="Dentro de las redes internas del perfil."><input id="al-ip" className={cn(campo, "font-mono")} value={ip} onChange={(e) => setIp(e.target.value.trim())} /></Etiqueta>
              <Etiqueta id="al-zona" texto="Zona"><select id="al-zona" className={campo} value={zona} onChange={(e) => setZona(e.target.value)}>{(d.zonas ?? []).map((z) => <option key={z}>{z}</option>)}</select></Etiqueta>
              <Etiqueta id="al-funcion" texto="Función"><input id="al-funcion" className={campo} value={funcion} maxLength={80} onChange={(e) => setFuncion(e.target.value)} /></Etiqueta>
              <Etiqueta id="al-crit" texto="Criticidad" ayuda="El motor la usa para decidir qué automatiza."><select id="al-crit" className={campo} value={criticidad} onChange={(e) => setCriticidad(e.target.value)}>{(d.criticidades ?? ["baja", "media", "alta"]).map((c) => <option key={c}>{c}</option>)}</select></Etiqueta>
              <Etiqueta id="al-if" texto="Interfaz (opcional)" ayuda="Para poder limitar su banda."><input id="al-if" className={cn(campo, "font-mono")} value={interfaz} placeholder="eth1" onChange={(e) => setInterfaz(e.target.value.trim())} /></Etiqueta>
            </div>
            <div className="space-y-1.5 text-[12.5px]">
              <div className="font-medium">Depende de</div>
              <div className="flex flex-wrap gap-1.5">{(d.activos ?? []).map((a) => (
                <button key={a} type="button" aria-pressed={depende.includes(a)} onClick={() => setDepende((x) => x.includes(a) ? x.filter((y) => y !== a) : [...x, a])}
                  className={cn("rounded-full border px-2.5 py-0.5 font-mono text-xs", depende.includes(a) ? "border-primary/45 bg-primary/12" : "border-border text-muted-foreground")}>{a}</button>))}</div>
            </div>
            <div className="flex justify-end"><Boton tono="pri" onClick={() => setPaso(2)} disabled={!paso1Ok}>Siguiente: papel y reglas</Boton></div>
          </>
        )}

        {paso === 2 && (
          <>
            <p className="text-[12.5px] text-muted-foreground">El papel decide qué acciones del catálogo le aplican. Su sudoers será solo eso, y el motor no le propondrá lo que no admita.</p>
            <div className="grid gap-2.5 sm:grid-cols-3" role="radiogroup" aria-label="Papel del equipo">
              {papeles.map((p) => (
                <button key={p.id} type="button" role="radio" aria-checked={papel === p.id} onClick={() => elegirPapel(p.id)}
                  className={cn("rounded-[10px] border px-3 py-2.5 text-left text-[12.5px]", papel === p.id ? "border-primary ring-3 ring-primary/15" : "border-border")}>
                  <b className="mb-0.5 block text-[13.5px]">{p.nombre}</b>{p.descripcion}
                </button>
              ))}
            </div>
            <fieldset className="grid gap-x-5 gap-y-1.5 sm:grid-cols-2">
              <legend className="mb-1.5 text-[12.5px] font-medium">Acciones que admite</legend>
              {acciones.map((a) => (
                <label key={a.id} className="flex items-center gap-2 text-[12.5px]">
                  <input type="checkbox" className="size-4 accent-primary" checked={elegidas.has(a.id)} onChange={() => alternar(a.id)} />
                  <span className="font-mono text-xs">{a.id}</span>
                  {a.nunca_automatica && <span className="text-[11px] text-muted-foreground">· nunca automática</span>}
                </label>
              ))}
            </fieldset>
            <div className="grid gap-3 sm:grid-cols-2">
              <Etiqueta id="al-serv" texto="Servicios que se pueden parar" ayuda={sinLista("servicios").length && !lista(servicios).length ? "Sin lista no se podrá parar ninguno: nunca «cualquier servicio»." : "Separados por comas."}>
                <input id="al-serv" className={cn(campo, "font-mono")} value={servicios} placeholder="nginx" onChange={(e) => setServicios(e.target.value)} /></Etiqueta>
              <Etiqueta id="al-cuentas" texto="Cuentas que se pueden bloquear" ayuda={cualquiera
                ? "El sudoers admite cualquier cuenta; el motor nunca bloquea root ni las cuentas del sistema."
                : "Nunca root ni las cuentas del sistema."}>
                <input id="al-cuentas" className={cn(campo, "font-mono disabled:bg-muted")} value={cualquiera ? "" : cuentas} disabled={cualquiera}
                  placeholder={cualquiera ? "cualquiera salvo las del sistema" : "appqr"} onChange={(e) => setCuentas(e.target.value)} />
                <label className="flex items-center gap-2 text-[12px]"><input type="checkbox" className="size-4 accent-primary" checked={cualquiera} onChange={(e) => setCualquiera(e.target.checked)} />
                  Cualquier cuenta salvo las del sistema (para las que crea el atacante)</label></Etiqueta>
            </div>
            <div className="flex justify-between">
              {!existente ? <Boton onClick={() => setPaso(1)}>Atrás</Boton> : <span />}
              <Boton tono="pri" onClick={guardarReglas} disabled={ocupado || elegidas.size === 0}>{ocupado ? "Guardando…" : existente ? "Guardar y generar el paquete de corrección" : "Generar el paquete de alta"}</Boton>
            </div>
          </>
        )}

        {paso === 3 && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex gap-0.5 rounded-[8px] border border-border bg-muted p-0.5 text-[12.5px]" role="tablist" aria-label="Formato del paquete">
                {([["script", "Script"], ["ansible", "Ansible"], ["sudoers", "Solo el sudoers"]] as const).map(([f, t]) => (
                  <button key={f} type="button" role="tab" aria-selected={formato === f} onClick={() => { setFormato(f); setPaquete(null) }}
                    className={cn("rounded-[6px] px-3 py-1", formato === f ? "bg-card font-medium shadow-sm" : "text-muted-foreground")}>{t}</button>))}
              </div>
              <span className="ml-auto" />
              <Boton onClick={copiar} disabled={!paquete}>Copiar</Boton>
              <Boton tono="pri" onClick={descargar} disabled={!paquete}>Descargar {paquete?.nombre ?? ""}</Boton>
            </div>
            <pre className="max-h-[420px] overflow-auto rounded-lg bg-[#0d1117] px-4 py-3 font-mono text-[11.5px] leading-relaxed text-[#c9d4e0]">{paquete?.contenido ?? "Generando…"}</pre>
            <p className="text-xs text-muted-foreground">Lo ejecuta el administrador del cliente, a mano o con su herramienta de configuración. Solo lleva la clave <b>pública</b> del conector: la plataforma no pide ni guarda contraseñas de administrador.</p>
            <div className="flex justify-between">
              <Boton onClick={() => setPaso(2)}>Atrás</Boton>
              {existente ? <Boton tono="pri" onClick={onCerrar}>Hecho: vuelve a probar el equipo</Boton>
                : <Boton tono="pri" onClick={() => setPaso(4)}>Ya está ejecutado</Boton>}
            </div>
          </>
        )}

        {paso === 4 && (
          <>
            <div className="grid gap-4 sm:grid-cols-[1.25fr_1fr]">
              <div className="space-y-2 text-[12.5px]">
                <div className="font-medium">Clave que presenta {nombre} ahora</div>
                {host ? <div className="rounded-md border border-border bg-muted px-2.5 py-2 font-mono text-[12.5px] [overflow-wrap:anywhere]">{host.presentada ?? "no responde"}</div>
                  : <Boton onClick={leer} disabled={ocupado}>Leer la clave del equipo</Boton>}
                <p className="text-[11.5px] text-muted-foreground">Compárala con la que imprimió el paquete en el equipo. Si no coincide, alguien está en medio: no sigas.</p>
                {host?.presentada && (
                  <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-primary" checked={coincide} onChange={(e) => setCoincide(e.target.checked)} />Coincide con la que imprimió el equipo</label>
                )}
              </div>
              <div className="space-y-2 text-[12.5px]">
                <div className="font-medium">Prueba</div>
                {prueba ? <Pasos p={prueba} /> : <p className="text-muted-foreground">Al dar de alta se prueba la conexión completa: entrar, el catálogo, la denegación y que sudo coincida con su papel.</p>}
              </div>
            </div>
            <div className="flex justify-between">
              <Boton onClick={() => setPaso(3)}>Atrás</Boton>
              <Boton tono="pri" onClick={alta} disabled={!host?.presentada || !coincide || ocupado}>{ocupado ? "Probando…" : `Dar de alta ${nombre}`}</Boton>
            </div>
          </>
        )}
      </div>
    </Capa>
  )
}
