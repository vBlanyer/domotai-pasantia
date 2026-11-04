import { useEffect, useState, type ReactNode } from "react"
import { RefreshCw } from "lucide-react"
import {
  getConectividad, probarConexion, guardarConexion, guardarUsuarioDefecto, leerClaveHost, aceptarClaveHost,
  type Conectividad as Datos, type EquipoConectividad, type PruebaConexion, type Fallo,
} from "@/api"
import { estadoEquipo, resumenConectividad, MODOS, type Tono } from "@/conectividad"
import { Cargando, SinConexion } from "./bits"
import { AlertDialog } from "@/components/ui/alert-dialog"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"

// Vista «Conectividad»: cómo entra el conector a cada equipo, qué clave del host tiene fijada, si el
// sudo es el mínimo y si la conexión funciona. Editar exige operador identificado; la clave privada
// no llega nunca al navegador (solo su huella y la clave pública).

const TEXTO: Record<Tono, string> = { ok: "text-ok", aviso: "text-aviso", critico: "text-critico", neutro: "text-muted-foreground" }
const PUNTO: Record<Tono, string> = { ok: "bg-ok", aviso: "bg-aviso", critico: "bg-critico", neutro: "bg-muted-foreground/50" }
const PILDORA: Record<Tono, string> = { ok: "bg-ok/15 text-ok", aviso: "bg-aviso/15 text-aviso", critico: "bg-critico/15 text-critico", neutro: "bg-enrutado/15 text-enrutado" }
const corta = (h?: string | null) => (h ? `${h.slice(0, 10)}…${h.slice(-3)}` : null)
const fecha = (iso?: string | null) => {
  if (!iso) return "—"
  const t = new Date(iso)
  return isNaN(t.getTime()) ? iso : t.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
}

function Boton({ children, tono = "normal", ...p }: { children: ReactNode; tono?: "pri" | "dan" | "normal" } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" {...p}
      className={cn("inline-flex h-8 items-center gap-1.5 rounded-[8px] border px-3 text-[13px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
        tono === "pri" ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
          : tono === "dan" ? "border-critico/45 bg-card text-critico hover:bg-critico/10"
          : "border-border bg-card hover:bg-muted", p.className)}>
      {children}
    </button>
  )
}

function Seccion({ titulo, extra, children }: { titulo: string; extra?: ReactNode; children: ReactNode }) {
  return (
    <div className="border-b border-border px-4 py-3 last:border-b-0">
      <h4 className="mb-2 flex items-center justify-between gap-2 text-[11px] font-medium text-muted-foreground"><span>{titulo}</span>{extra}</h4>
      {children}
    </div>
  )
}

function Pasos({ p }: { p: PruebaConexion }) {
  return (
    <ul className="space-y-1 rounded-md border border-border bg-muted px-3 py-2 font-mono text-[11.5px]">
      {p.pasos.map((x, i) => (
        <li key={i} className="grid grid-cols-[14px_1fr] gap-1.5">
          <span className={x.ok ? "text-ok" : "text-critico"}>{x.ok ? "✓" : "✕"}</span>
          <span>{x.paso}<span className="block font-sans text-[11px] text-muted-foreground">{x.detalle}</span></span>
        </li>
      ))}
    </ul>
  )
}

function Inspector({ d, e, onCambio }: { d: Datos; e: EquipoConectividad; onCambio: () => void }) {
  const toast = useToast()
  const est = estadoEquipo(e)
  const [puerto, setPuerto] = useState(String(e.puerto))
  const [usuario, setUsuario] = useState(e.ajustado && e.usuario !== (d.usuario_defecto ?? d.usuario_entorno) ? e.usuario : "")
  const [ocupado, setOcupado] = useState<null | "probar" | "guardar" | "leer" | "aceptar">(null)
  const [prueba, setPrueba] = useState<PruebaConexion | null>(e.ultima_prueba ?? null)
  const [host, setHost] = useState<{ fijada?: string | null; presentada?: string | null; coincide?: boolean } | null>(null)
  const [confirmar, setConfirmar] = useState(false)
  const defecto = d.usuario_defecto ?? d.usuario_entorno
  const puertoNum = /^\d+$/.test(puerto) ? Number(puerto) : NaN
  const puertoOk = puertoNum >= 1 && puertoNum <= 65535
  const cambiado = puertoNum !== e.puerto || (usuario || defecto) !== e.usuario
  const ajuste = { puerto: puertoOk && puertoNum !== 22 ? puertoNum : null, usuario: usuario.trim() || null }
  const editable = d.editable && !e.protegido

  async function probar() {
    setOcupado("probar")
    const r = await probarConexion(e.nombre, ajuste)
    setOcupado(null)
    if (r.status === 200) setPrueba(r.datos as unknown as PruebaConexion)
    else toast({ type: "error", title: "No se pudo probar", description: String(r.datos.error ?? `HTTP ${r.status}`) })
    onCambio()
  }
  async function guardar() {
    setOcupado("guardar")
    const r = await guardarConexion(e.nombre, ajuste)
    setOcupado(null)
    if (r.datos.prueba) setPrueba(r.datos.prueba as PruebaConexion)
    if (r.status === 200) toast({ type: "success", title: `Guardado: ${e.nombre}`, description: "La prueba pasó con los ajustes nuevos." })
    else if (r.status === 409 && r.datos.prueba) toast({ type: "error", title: "No se guardó: la prueba falló", description: "Revisa el resultado de la prueba." })
    else toast({ type: "error", title: "No se guardó", description: String(r.datos.error ?? `HTTP ${r.status}`) })
    onCambio()
  }
  async function leer() {
    setOcupado("leer")
    const r = await leerClaveHost(e.nombre)
    setOcupado(null)
    if (r.status === 200) setHost(r.datos as typeof host)
    else toast({ type: "error", title: "No se pudo leer la clave del equipo", description: String(r.datos.error ?? `HTTP ${r.status}`) })
  }
  async function aceptar() {
    if (!host?.presentada) return
    setOcupado("aceptar")
    const r = await aceptarClaveHost(e.nombre, host.presentada)
    setOcupado(null)
    if (r.status === 200) { toast({ type: "success", title: `Clave del host aceptada: ${e.nombre}` }); setHost(null); setPrueba(null) }
    else toast({ type: "error", title: "No se aceptó la clave", description: String(r.datos.error ?? `HTTP ${r.status}`) })
    onCambio()
  }

  const cambiosEquipo = d.cambios.filter((c) => c.clave === e.nombre)
  const campo = "h-[30px] rounded-[7px] border border-border bg-card px-2.5 text-[13px] outline-none focus:border-ring disabled:bg-muted disabled:text-muted-foreground"
  return (
    <section aria-label="Equipo" className="overflow-hidden rounded-lg border border-border bg-card text-sm lg:sticky lg:top-3">
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-base font-semibold">{e.nombre}
          <span className={cn("rounded px-1.5 text-[11px] font-medium", PILDORA[est.tono])}>{est.texto}</span>
        </div>
        <div className="text-xs text-muted-foreground">{[e.ip, e.zona, e.funcion].filter(Boolean).join(" · ")}</div>
      </div>

      {(est.id === "host_cambiada" || (host && host.presentada && !host.coincide)) && (
        <Seccion titulo="Clave del host cambiada">
          <div className="space-y-2 rounded-md border border-critico/40 bg-critico/10 px-3 py-2.5 text-[13px]">
            <p><b className="text-critico">El equipo presenta una clave distinta de la fijada.</b> Puede ser una reinstalación legítima o alguien suplantando al equipo: compruébala por otro canal antes de aceptarla. Mientras tanto el conector no entra.</p>
            {host ? (
              <div className="grid grid-cols-[80px_1fr] gap-x-2 gap-y-0.5 text-xs">
                <span className="text-muted-foreground">Fijada</span><span className="font-mono text-muted-foreground line-through [overflow-wrap:anywhere]">{host.fijada ?? "ninguna"}</span>
                <span className="text-muted-foreground">Presenta</span><span className="font-mono text-critico [overflow-wrap:anywhere]">{host.presentada ?? "no responde"}</span>
              </div>
            ) : <Boton onClick={leer} disabled={ocupado !== null}>Leer la clave que presenta</Boton>}
            {host?.presentada && !host.coincide && editable && (
              <Boton tono="dan" onClick={() => setConfirmar(true)} disabled={ocupado !== null}>Aceptar la nueva clave…</Boton>
            )}
          </div>
        </Seccion>
      )}

      <Seccion titulo="Cómo entra el conector" extra={cambiado && editable ? <span>cambios sin guardar</span> : null}>
        <div className="grid grid-cols-[100px_1fr] items-center gap-x-2.5 gap-y-1.5 text-[13px]">
          <span className="text-muted-foreground">Plano</span>
          <span className="inline-flex w-fit gap-0.5 rounded-[8px] border border-border bg-muted p-0.5 text-[12.5px]">
            <span className="rounded-[6px] bg-card px-2.5 py-0.5 font-medium shadow-sm">SSH</span>
            <span className="px-2.5 py-0.5 text-muted-foreground opacity-50" title="Driver documentado como trabajo futuro">docker exec</span>
            <span className="px-2.5 py-0.5 text-muted-foreground opacity-50" title="Driver documentado como trabajo futuro">API del equipo</span>
          </span>
          <span className="text-muted-foreground">Dirección</span><span className="text-muted-foreground">{e.ip} · del perfil de red</span>
          <label htmlFor="cx-puerto" className="text-muted-foreground">Puerto</label>
          <input id="cx-puerto" inputMode="numeric" value={puerto} onChange={(x) => setPuerto(x.target.value.trim())} disabled={!editable}
            className={cn(campo, "w-24", !puertoOk && "border-critico")} />
          <label htmlFor="cx-usuario" className="text-muted-foreground">Usuario</label>
          <input id="cx-usuario" value={usuario} placeholder={`${defecto} (por defecto)`} onChange={(x) => setUsuario(x.target.value)} disabled={!editable}
            className={cn(campo, "w-44")} />
          <span className="text-muted-foreground">Clave</span>
          <span className="text-muted-foreground">la del conector{d.clave ? ` (${d.clave.tipo ?? ""} · ${corta(d.clave.huella)})` : ""}</span>
        </div>
      </Seccion>

      <Seccion titulo="Clave del host fijada" extra={!e.protegido && <Boton className="h-6 px-2 text-xs" onClick={leer} disabled={ocupado !== null}>Volver a leer del equipo</Boton>}>
        <p className="font-mono text-xs [overflow-wrap:anywhere]">{e.huella_fijada ?? <span className="font-sans text-aviso">sin fijar: aprovisiona el equipo con el script de mínimo privilegio</span>}</p>
        {host?.coincide && <p className="mt-1 text-xs text-ok">El equipo presenta la misma clave que la fijada.</p>}
        <p className="mt-1 text-xs text-muted-foreground">El conector rechaza la conexión si el equipo presenta otra clave. Cambiarla exige confirmarla aquí.</p>
      </Seccion>

      <Seccion titulo="Lo que puede hacer con sudo">
        <p className="text-xs text-muted-foreground">El sudoers se genera desde el catálogo cerrado de acciones; no se edita a mano. La prueba comprueba que un comando del catálogo se permite y uno fuera de él se deniega.</p>
      </Seccion>

      <Seccion titulo="Prueba de conexión" extra={prueba?.en ? <span>{fecha(prueba.en)} · {prueba.usuario}@:{prueba.puerto}</span> : null}>
        {prueba ? <Pasos p={prueba} /> : <p className="text-xs text-muted-foreground">Aún no se ha probado en esta sesión.</p>}
      </Seccion>

      {cambiosEquipo.length > 0 && (
        <Seccion titulo="Cambios">
          <ul className="space-y-1 text-xs">
            {cambiosEquipo.slice(0, 6).map((c, i) => (
              <li key={i} className="grid grid-cols-[96px_1fr] gap-2">
                <span className="font-mono text-[11px] text-muted-foreground">{fecha(c.timestamp)}</span>
                <span>{c.dimension === "clave_host" ? "clave del host aceptada" : `ajuste ${JSON.stringify(c.despues ?? "quitado")}`} · {c.operador ?? "—"}</span>
              </li>
            ))}
          </ul>
        </Seccion>
      )}

      {!e.protegido && (
        <div className="space-y-2 bg-muted px-4 py-3">
          <div className="flex flex-wrap gap-2">
            {editable && <Boton tono="pri" onClick={guardar} disabled={!cambiado || !puertoOk || ocupado !== null}>{ocupado === "guardar" ? "Probando…" : "Probar y guardar"}</Boton>}
            <Boton onClick={probar} disabled={!puertoOk || ocupado !== null || d.modo === "password" || d.modo === "sin_configurar"}>{ocupado === "probar" ? "Probando…" : "Probar sin guardar"}</Boton>
            {editable && <Boton onClick={() => { setPuerto(String(e.puerto)); setUsuario("") }} disabled={!cambiado || ocupado !== null}>Descartar</Boton>}
          </div>
          <p className="text-[11.5px] text-muted-foreground">
            {editable ? "Se guarda solo si la prueba pasa. Cada cambio queda en el registro de auditoría con tu operador." : d.motivo_no_editable}
          </p>
        </div>
      )}

      <AlertDialog open={confirmar} onOpenChange={(o) => { if (!o) setConfirmar(false) }}
        title={`¿Aceptar la nueva clave del host de ${e.nombre}?`}
        description="Solo si has comprobado por otro canal que el equipo es el legítimo. El conector volverá a entrar con esta clave."
        confirmLabel="Aceptar la nueva clave" onConfirm={aceptar}>
        <p className="font-mono text-xs [overflow-wrap:anywhere]">{host?.presentada}</p>
      </AlertDialog>
    </section>
  )
}

export function Conectividad() {
  const toast = useToast()
  const [d, setD] = useState<Datos | Fallo | undefined>()
  const [sel, setSel] = useState<string | null>(null)
  const [defecto, setDefecto] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const recargar = () => setVersion((v) => v + 1)
  useEffect(() => {
    let vivo = true
    const pedir = () => getConectividad().then((r) => { if (vivo) setD(r) })
    pedir()
    const id = setInterval(pedir, 30000)
    return () => { vivo = false; clearInterval(id) }
  }, [version])

  if (!d) return <Cargando />
  if ("error" in d) return <SinConexion causa={d.causa} />
  const r = resumenConectividad(d.equipos)
  const elegido = d.equipos.find((e) => e.nombre === sel) ?? d.equipos.find((e) => !e.protegido) ?? d.equipos[0]
  const valorDefecto = defecto ?? d.usuario_defecto ?? ""
  const copiar = async () => {
    try { await navigator.clipboard.writeText(d.clave?.publica ?? ""); toast({ type: "success", title: "Clave pública copiada" }) }
    catch { toast({ type: "error", title: "El navegador no permitió copiar" }) }
  }
  const guardarDefecto = async () => {
    const res = await guardarUsuarioDefecto(valorDefecto.trim() || null)
    if (res.status === 200) { toast({ type: "success", title: "Usuario por defecto guardado" }); setDefecto(null) }
    else toast({ type: "error", title: "No se guardó", description: String(res.datos.error ?? `HTTP ${res.status}`) })
    recargar()
  }

  return (
    <div className="space-y-3">
      {/* el conector, global */}
      <div className="overflow-hidden rounded-lg border border-border bg-card text-sm">
        <div className="grid lg:grid-cols-[1.15fr_1.3fr_1fr]">
          <div className="space-y-1.5 border-b border-border px-4 py-3 lg:border-b-0 lg:border-r">
            <div className="text-[11px] text-muted-foreground">Cómo se conecta el MDR</div>
            <div className="inline-flex flex-wrap gap-0.5 rounded-[8px] border border-border bg-muted p-0.5 text-[12.5px]" aria-label="Modo del conector">
              {MODOS.map((m) => (
                <span key={m.id} aria-current={d.modo === m.id}
                  className={cn("rounded-[6px] px-2.5 py-0.5", d.modo === m.id ? "bg-card font-medium shadow-sm" : "text-muted-foreground opacity-60")}>{m.nombre}</span>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              {d.modo === "sin_configurar" ? <span className="font-medium text-critico">Sin configurar: no se ejecuta ninguna contención hasta aprovisionar la clave.</span>
                : d.modo === "password" ? <span className="font-medium text-aviso">Modo laboratorio: contraseña por defecto y sin verificar la clave del host.</span>
                : <>{d.nodo_gestion ? <>Nodo de gestión: <span className="font-mono">{d.nodo_gestion}</span> · </> : null}si falta la clave no se ejecuta ninguna contención.</>}
              {" "}Se elige al arrancar el daemon (TRIAJE_SSH_MODO).
            </p>
          </div>
          <div className="space-y-1.5 border-b border-border px-4 py-3 lg:border-b-0 lg:border-r">
            <div className="text-[11px] text-muted-foreground">Clave del conector{d.clave?.tipo ? ` (${d.clave.tipo.toLowerCase()})` : ""}</div>
            {d.clave ? <p className="font-mono text-xs [overflow-wrap:anywhere]">{d.clave.huella}</p> : <p className="text-xs text-muted-foreground">No disponible en este modo.</p>}
            <div className="flex flex-wrap items-center gap-1.5">
              <Boton className="h-6 px-2 text-xs" onClick={copiar} disabled={!d.clave?.publica}>Copiar clave pública</Boton>
              <Boton className="h-6 px-2 text-xs" disabled title="Rotar rompe la entrada en todos los equipos hasta re-aprovisionarlos: se hace con lab/scripts/aprovisionar-minimo-privilegio.sh">Rotar: generar par nuevo</Boton>
              <span className="text-xs text-muted-foreground">vive en <span className="font-mono">{d.ruta_clave}</span></span>
            </div>
          </div>
          <div className="space-y-1.5 px-4 py-3">
            <label htmlFor="cx-defecto" className="text-[11px] text-muted-foreground">Usuario por defecto en los equipos</label>
            <div className="flex items-center gap-1.5">
              <input id="cx-defecto" value={valorDefecto} placeholder={d.usuario_entorno} onChange={(x) => setDefecto(x.target.value)} disabled={!d.editable}
                className="h-[30px] w-40 rounded-[7px] border border-border bg-card px-2.5 text-[13px] outline-none focus:border-ring disabled:bg-muted disabled:text-muted-foreground" />
              {d.editable && defecto !== null && defecto !== (d.usuario_defecto ?? "") && <Boton tono="pri" className="h-[30px]" onClick={guardarDefecto}>Guardar</Boton>}
            </div>
            <p className="text-xs text-muted-foreground">Sin contraseña, solo clave, y sudo limitado al catálogo de acciones.</p>
          </div>
        </div>
        <div className="grid grid-cols-2 border-t border-border sm:grid-cols-[repeat(4,minmax(0,1fr))_auto]">
          {([["Equipos contenibles", r.contenibles, ""], ["Conexión verificada", r.verificadas, "text-ok"],
             ["Clave del host cambiada", r.hostCambiada, r.hostCambiada ? "text-critico" : ""], ["Sin aprovisionar", r.sinAprovisionar, r.sinAprovisionar ? "text-aviso" : ""]] as const).map(([k, v, cls]) => (
            <div key={k} className="border-r border-border px-4 py-2 last:border-r-0">
              <div className="text-[11px] text-muted-foreground">{k}</div>
              <div className={cn("text-lg font-semibold tabular-nums", cls)}>{v}</div>
            </div>
          ))}
          <div className="flex items-center px-4"><Boton className="h-7 text-xs" onClick={recargar}><RefreshCw className="size-3.5" />Actualizar</Boton></div>
        </div>
      </div>
      {!d.editable && d.motivo_no_editable && (
        <p role="status" className="rounded-md border border-border bg-muted px-3 py-2 text-xs text-muted-foreground">{d.motivo_no_editable}.</p>
      )}

      <div className="grid items-start gap-3.5 lg:grid-cols-[minmax(0,1.35fr)_minmax(370px,1fr)]">
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="bg-muted text-left text-[11.5px] text-muted-foreground">
                <th className="px-3 py-2 font-medium">Equipo</th><th className="px-3 py-2 font-medium">Conexión</th>
                <th className="px-3 py-2 font-medium">Entra por</th><th className="px-3 py-2 font-medium">Clave del host</th>
              </tr>
            </thead>
            <tbody>
              {d.equipos.map((e) => {
                const est = estadoEquipo(e)
                const activo = elegido?.nombre === e.nombre
                return (
                  <tr key={e.nombre} data-equipo={e.nombre} onClick={() => setSel(e.nombre)}
                    className={cn("cursor-pointer border-t border-border hover:bg-muted/50", activo && "bg-primary/10 shadow-[inset_3px_0_0_var(--primary)]",
                      est.tono === "critico" && !activo && "bg-critico/5")}>
                    <td className="px-3 py-2"><button type="button" className="text-left font-semibold whitespace-nowrap" aria-label={`Ver ${e.nombre}`}>{e.nombre}</button>
                      <span className="block text-[11.5px] text-muted-foreground">{[e.ip, e.zona].filter(Boolean).join(" · ")}</span></td>
                    <td className="px-3 py-2"><span className={cn("inline-flex items-center gap-1.5 font-medium whitespace-nowrap", TEXTO[est.tono])}>
                      <span className={cn("size-2 rounded-full", PUNTO[est.tono])} />{est.texto}</span>
                      <span className="block text-[11.5px] text-muted-foreground">{est.sub}</span></td>
                    <td className="px-3 py-2 text-muted-foreground">{e.protegido ? "—" : `ssh · ${e.usuario}@:${e.puerto}`}{e.ajustado && <span className="ml-1 rounded bg-info/15 px-1 text-[10.5px] text-info">ajustado</span>}</td>
                    <td className="px-3 py-2 font-mono text-xs">{e.protegido ? "—" : corta(e.huella_fijada) ?? <span className="font-sans text-muted-foreground">sin fijar</span>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {elegido ? <Inspector key={`${elegido.nombre}:${elegido.puerto}:${elegido.usuario}`} d={d} e={elegido} onCambio={recargar} />
          : <div className="rounded-lg border border-dashed border-border bg-card px-4 py-5 text-sm text-muted-foreground">El perfil no declara equipos con IP.</div>}
      </div>
    </div>
  )
}
