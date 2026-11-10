import { useEffect, useState } from "react"
import { RefreshCw, TriangleAlert } from "lucide-react"
import {
  getConectividad, probarConexion, probarEquipo, guardarConexion, guardarUsuarioDefecto, leerClaveHost, aceptarClaveHost,
  quitarInventario, sesionActual, operadorActual, generarClaveConector,
  type Conectividad as Datos, type EquipoConectividad, type PruebaConexion, type Fallo,
} from "@/api"
import { estadoEquipo, resumenConectividad, reglasDe, papelTexto, franjaPermisos, MODOS, type Tono } from "@/conectividad"
import { Cargando, SinConexion } from "./bits"
import { AlertDialog } from "@/components/ui/alert-dialog"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"
import { Boton, Bloqueado, Seccion, Pasos, Deriva } from "./ConectividadUi"
import { AltaEquipo } from "./AltaEquipo"
import { RotacionClave } from "./RotacionClave"

// Vista «Conectividad»: cómo entra el conector a cada equipo, qué clave del host tiene fijada, si su sudo
// coincide con su papel y si la conexión funciona; y desde aquí, dar de alta equipos y rotar la clave.
// Probar y cambiar exigen operador identificado; la clave privada no llega nunca al navegador.

const TEXTO: Record<Tono, string> = { ok: "text-ok", aviso: "text-aviso", critico: "text-critico", neutro: "text-muted-foreground" }
const PUNTO: Record<Tono, string> = { ok: "bg-ok", aviso: "bg-aviso", critico: "bg-critico", neutro: "bg-muted-foreground/50" }
const PILDORA: Record<Tono, string> = { ok: "bg-ok/15 text-ok", aviso: "bg-aviso/15 text-aviso", critico: "bg-critico/15 text-critico", neutro: "bg-enrutado/15 text-enrutado" }
const corta = (h?: string | null) => (h ? `${h.slice(0, 10)}…${h.slice(-3)}` : null)
const fecha = (iso?: string | null) => {
  if (!iso) return "—"
  const t = new Date(iso)
  return isNaN(t.getTime()) ? iso : t.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
}
const MOTIVO_CORTO = "exige tu token de operador"
const TEXTO_CAMBIO: Record<string, string> = {
  clave_host: "clave del host aceptada", prueba: "prueba", lectura_clave_host: "clave del host leída", inventario: "papel e inventario",
  alta: "dado de alta", equipo: "ajuste", usuario_defecto: "usuario por defecto",
}

type Asistente = { equipo: EquipoConectividad | null; paso?: 1 | 2 | 3 | 4 } | null

function Inspector({ d, e, onCambio, onAsistente }: { d: Datos; e: EquipoConectividad; onCambio: () => void; onAsistente: (a: Asistente) => void }) {
  const toast = useToast()
  const est = estadoEquipo(e)
  const reg = reglasDe(e)
  const puede = d.permisos?.probar ?? d.editable
  const [puerto, setPuerto] = useState(String(e.puerto))
  const [usuario, setUsuario] = useState(e.ajustado && e.usuario !== (d.usuario_defecto ?? d.usuario_entorno) ? e.usuario : "")
  const [ocupado, setOcupado] = useState<null | "probar" | "guardar" | "leer" | "aceptar">(null)
  const [prueba, setPrueba] = useState<PruebaConexion | null>(e.ultima_prueba ?? null)
  const [host, setHost] = useState<{ fijada?: string | null; presentada?: string | null; coincide?: boolean } | null>(null)
  const [confirmar, setConfirmar] = useState(false)
  const [quitar, setQuitar] = useState(false)
  const [coincide, setCoincide] = useState(false)
  const defecto = d.usuario_defecto ?? d.usuario_entorno
  const puertoNum = /^\d+$/.test(puerto) ? Number(puerto) : NaN
  const puertoOk = puertoNum >= 1 && puertoNum <= 65535
  const cambiado = puertoNum !== e.puerto || (usuario || defecto) !== e.usuario
  const ajuste = { puerto: puertoOk && puertoNum !== 22 ? puertoNum : null, usuario: usuario.trim() || null }
  const editable = puede && !e.protegido
  const pendiente = e.alta === "pendiente"
  const sinFijar = !e.huella_fijada && !e.protegido && !pendiente     // primera vez: fijar, no «cambiada»

  const aviso = (titulo: string, r: { status: number; datos: Record<string, unknown> }) =>
    toast({ type: "error", title: titulo, description: String(r.datos.error ?? `HTTP ${r.status}`) })
  async function probar() {
    setOcupado("probar")
    const r = await probarConexion(e.nombre, ajuste)
    setOcupado(null)
    if (r.status === 200) setPrueba(r.datos as unknown as PruebaConexion)
    else aviso("No se pudo probar", r)
    onCambio()
  }
  async function guardar() {
    setOcupado("guardar")
    const r = await guardarConexion(e.nombre, ajuste)
    setOcupado(null)
    if (r.datos.prueba) setPrueba(r.datos.prueba as PruebaConexion)
    if (r.status === 200) toast({ type: "success", title: `Guardado: ${e.nombre}`, description: "La prueba pasó con los ajustes nuevos." })
    else if (r.status === 409 && r.datos.prueba) toast({ type: "error", title: "No se guardó: la prueba falló", description: "Revisa el resultado de la prueba." })
    else aviso("No se guardó", r)
    onCambio()
  }
  async function leer() {
    setOcupado("leer")
    const r = await leerClaveHost(e.nombre)
    setOcupado(null)
    if (r.status === 200) setHost(r.datos as typeof host)
    else aviso("No se pudo leer la clave del equipo", r)
  }
  async function aceptar(reemplazar = false) {
    if (!host?.presentada) return
    setOcupado("aceptar")
    const r = await aceptarClaveHost(e.nombre, host.presentada, reemplazar)
    setOcupado(null)
    if (r.status === 200) { toast({ type: "success", title: `Clave del host aceptada: ${e.nombre}` }); setHost(null); setPrueba(null) }
    else aviso("No se aceptó la clave", r)
    onCambio()
  }
  async function quitarInv() {
    const r = await quitarInventario(e.nombre)
    if (r.status === 200) toast({ type: "success", title: pendiente ? `Alta de ${e.nombre} quitada` : `${e.nombre} vuelve al catálogo completo` })
    else aviso("No se pudo", r)
    onCambio()
  }

  const cambiosEquipo = d.cambios.filter((c) => c.clave === e.nombre)
  const campo = "h-[30px] rounded-[7px] border border-border bg-card px-2.5 text-[13px] outline-none focus:border-ring disabled:bg-muted disabled:text-muted-foreground"
  const reglas = prueba?.reglas
  return (
    <section aria-label="Equipo" className="overflow-hidden rounded-lg border border-border bg-card text-sm lg:sticky lg:top-3">
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-base font-semibold">{e.nombre}
          <span className={cn("rounded px-1.5 text-[11px] font-medium", PILDORA[est.tono])}>{est.texto}</span>
        </div>
        <div className="text-xs text-muted-foreground">{[e.ip, e.zona, e.funcion].filter(Boolean).join(" · ")}</div>
      </div>
      {est.aviso && (
        <div role="alert" className="border-b border-critico/30 bg-critico/5 px-4 py-2 text-xs text-critico">
          <p className="font-semibold">{e.sin_acceso ? `${est.aviso.ataque ? "Posible ataque: " : ""}el MDR no tiene acceso a este equipo`
            : est.aviso.ataque ? "Posible ataque" : "La última contención en este equipo falló"}</p>
          <p>{[est.aviso.sub, e.sin_acceso ? "las contenciones escalan directamente" : e.operativo?.accion].filter(Boolean).join(" · ")}.{prueba ? " La prueba de conexión es anterior: vuelve a probar para confirmarlo." : ""}</p>
        </div>
      )}

      {pendiente && (
        <Seccion titulo="Alta pendiente">
          <p className="text-[13px]">Falta ejecutar su paquete de alta en el equipo, fijar su clave del host y probar. Hasta entonces el motor no lo ve.</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {puede ? <>
              <Boton tono="pri" onClick={() => onAsistente({ equipo: e, paso: 3 })}>Ver el paquete de alta</Boton>
              <Boton onClick={() => onAsistente({ equipo: e, paso: 4 })}>Verificar y dar de alta</Boton>
              <Boton tono="dan" onClick={() => setQuitar(true)}>Quitar el alta</Boton>
            </> : <Bloqueado accion="Continuar el alta" motivo={MOTIVO_CORTO} />}
          </div>
        </Seccion>
      )}

      {sinFijar && (
        <Seccion titulo="Fijar la clave del host">
          <div className="space-y-2 rounded-md border border-aviso/40 bg-aviso/10 px-3 py-2.5 text-[13px]">
            <p>El conector solo entra en un equipo cuya clave del host está fijada. Léela del equipo y compárala con la huella que imprimió su paquete de alta al ejecutarse en el equipo.</p>
            {!puede ? <Bloqueado accion="Fijar la clave del host" motivo={MOTIVO_CORTO} />
              : !host ? <Boton onClick={leer} disabled={ocupado !== null}>{ocupado === "leer" ? "Leyendo…" : "Leer la clave del equipo"}</Boton>
              : !host.presentada ? <p className="text-critico">El equipo no respondió: comprueba que sshd está en marcha y que la red llega.</p>
              : <>
                <p className="rounded border border-border bg-card px-2 py-1.5 font-mono text-xs [overflow-wrap:anywhere]">{host.presentada}</p>
                <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-primary" checked={coincide} onChange={(x) => setCoincide(x.target.checked)} />Coincide con la que imprimió el equipo</label>
                <Boton tono="pri" onClick={() => aceptar()} disabled={!coincide || ocupado !== null}>{ocupado === "aceptar" ? "Fijando…" : "Fijar esta clave"}</Boton>
              </>}
          </div>
        </Seccion>
      )}

      {(est.id === "host_cambiada" || (host && host.presentada && !host.coincide && !pendiente && !!e.huella_fijada)) && (
        <Seccion titulo="Clave del host cambiada">
          <div className="space-y-2 rounded-md border border-critico/40 bg-critico/10 px-3 py-2.5 text-[13px]">
            <p><b className="text-critico">El equipo presenta una clave distinta de la fijada.</b> Puede ser una reinstalación legítima o alguien suplantando al equipo: compruébala por otro canal antes de aceptarla. Mientras tanto el conector no entra.</p>
            {host ? (
              <div className="grid grid-cols-[80px_1fr] gap-x-2 gap-y-0.5 text-xs">
                <span className="text-muted-foreground">Fijada</span><span className="font-mono text-muted-foreground line-through [overflow-wrap:anywhere]">{host.fijada ?? "ninguna"}</span>
                <span className="text-muted-foreground">Presenta</span><span className="font-mono text-critico [overflow-wrap:anywhere]">{host.presentada ?? "no responde"}</span>
              </div>
            ) : puede ? <Boton onClick={leer} disabled={ocupado !== null}>Leer la clave que presenta</Boton> : <Bloqueado accion="Leer la clave" motivo={MOTIVO_CORTO} />}
            {host?.presentada && !host.coincide && editable && (
              <Boton tono="dan" onClick={() => setConfirmar(true)} disabled={ocupado !== null}>Aceptar la nueva clave…</Boton>
            )}
          </div>
        </Seccion>
      )}

      {!e.protegido && !pendiente && (
        <Seccion titulo="Papel y reglas" extra={puede ? <Boton className="h-6 px-2 text-xs" onClick={() => onAsistente({ equipo: e, paso: 2 })}>Editar</Boton> : null}>
          <p className="text-[13px]">{e.papel
            ? <><b className="font-medium">{papelTexto(e, d.papeles)}</b>{e.servicios?.length ? ` · servicios: ${e.servicios.join(", ")}` : ""}{e.cuentas_cualquiera ? " · cuentas: cualquiera salvo las del sistema" : e.cuentas?.length ? ` · cuentas: ${e.cuentas.join(", ")}` : ""}</>
            : <span className="text-muted-foreground">Sin papel declarado: su sudoers es el catálogo entero. Declara su papel para reducirlo a lo que necesita.</span>}</p>
          <p className="mt-1.5 flex items-center gap-1.5 text-xs"><span className={cn("size-2 rounded-full", PUNTO[reg.tono])} /><span className={TEXTO[reg.tono]}>Reglas en el equipo: {reg.texto}</span>{reg.sub && <span className="text-muted-foreground">· {reg.sub}</span>}</p>
          {reglas && (reglas.sobran.length > 0 || reglas.faltan.length > 0) && (
            <div className="mt-2 space-y-2">
              {reglas.sobran.length > 0 && <p className="text-xs text-critico">Alguien cambió el sudoers en el equipo: el conector puede hacer más de lo que debe.</p>}
              <Deriva sobran={reglas.sobran} faltan={reglas.faltan} />
              {puede && <Boton tono={reglas.sobran.length ? "pri" : "normal"} className="h-7 text-xs" onClick={() => onAsistente({ equipo: e, paso: 3 })}>Generar paquete de corrección</Boton>}
            </div>
          )}
          {e.papel && puede && <button type="button" onClick={() => setQuitar(true)} className="mt-1.5 text-xs text-muted-foreground hover:text-foreground">Quitar el papel (volver al catálogo completo)</button>}
        </Seccion>
      )}

      {!pendiente && (
        <Seccion titulo="Cómo entra el conector" extra={cambiado && editable ? <span>cambios sin guardar</span> : null}>
          <div className="grid grid-cols-[100px_1fr] items-center gap-x-2.5 gap-y-1.5 text-[13px]">
            <span className="text-muted-foreground">Plano</span>
            <span>SSH <span className="text-xs text-muted-foreground">· docker exec y API del equipo: previstos, no disponibles</span></span>
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
      )}

      {!sinFijar && <Seccion titulo="Clave del host fijada" extra={!e.protegido && e.huella_fijada && (puede ? <Boton className="h-6 px-2 text-xs" onClick={leer} disabled={ocupado !== null}>Volver a leer del equipo</Boton> : null)}>
        <p className="font-mono text-xs [overflow-wrap:anywhere]">{e.huella_fijada ?? <span className="font-sans text-aviso">sin fijar{pendiente ? ": se fija al verificar el alta" : ": dalo de alta desde «Añadir equipo» o ejecuta su paquete"}</span>}</p>
        {host?.coincide && <p className="mt-1 text-xs text-ok">El equipo presenta la misma clave que la fijada.</p>}
        <p className="mt-1 text-xs text-muted-foreground">El conector rechaza la conexión si el equipo presenta otra clave. Cambiarla exige confirmarla aquí.</p>
      </Seccion>}

      {!pendiente && (
        <Seccion titulo="Prueba de conexión" extra={prueba?.en ? <span>{fecha(prueba.en)} · {prueba.usuario}@:{prueba.puerto}{prueba.por ? ` · ${prueba.por}` : ""}</span> : null}>
          {prueba ? <Pasos p={prueba} /> : <p className="text-xs text-muted-foreground">Aún no se ha probado.</p>}
        </Seccion>
      )}

      {cambiosEquipo.length > 0 && (
        <Seccion titulo="Registro">
          <ul className="space-y-1 text-xs">
            {cambiosEquipo.slice(0, 6).map((c, i) => (
              <li key={i} className="grid grid-cols-[96px_1fr] gap-2">
                <span className="font-mono text-[11px] text-muted-foreground">{fecha(c.timestamp)}</span>
                <span>{TEXTO_CAMBIO[c.dimension] ?? c.dimension}{c.dimension === "prueba" && c.despues && typeof c.despues === "object" ? `: ${(c.despues as { estado?: string }).estado}` : ""} · {c.operador ?? "—"}</span>
              </li>
            ))}
          </ul>
        </Seccion>
      )}

      {!e.protegido && !pendiente && (
        <div className="space-y-2 bg-muted px-4 py-3">
          {puede ? (
            <div className="flex flex-wrap gap-2">
              <Boton tono="pri" onClick={guardar} disabled={!cambiado || !puertoOk || ocupado !== null}>{ocupado === "guardar" ? "Probando…" : "Probar y guardar"}</Boton>
              <Boton onClick={probar} disabled={!puertoOk || ocupado !== null}>{ocupado === "probar" ? "Probando…" : "Probar sin guardar"}</Boton>
              <Boton onClick={() => { setPuerto(String(e.puerto)); setUsuario("") }} disabled={!cambiado || ocupado !== null}>Descartar</Boton>
            </div>
          ) : <Bloqueado accion="Probar y cambiar ajustes" motivo={MOTIVO_CORTO} />}
          {puede && <p className="text-[11.5px] text-muted-foreground">Se guarda solo si la prueba pasa. Cada prueba y cada cambio quedan en el registro con tu operador.</p>}
        </div>
      )}

      <AlertDialog open={confirmar} onOpenChange={(o) => { if (!o) setConfirmar(false) }}
        title={`¿Aceptar la nueva clave del host de ${e.nombre}?`}
        description="Solo si has comprobado por otro canal que el equipo es el legítimo. El conector volverá a entrar con esta clave."
        confirmLabel="Aceptar la nueva clave" onConfirm={() => aceptar(true)}>
        <p className="font-mono text-xs [overflow-wrap:anywhere]">{host?.presentada}</p>
      </AlertDialog>
      <AlertDialog open={quitar} onOpenChange={(o) => { if (!o) setQuitar(false) }}
        title={pendiente ? `¿Quitar el alta pendiente de ${e.nombre}?` : `¿Quitar el papel de ${e.nombre}?`}
        description={pendiente ? "Se borra del inventario operativo. Si ya ejecutaste su paquete, el usuario del conector sigue en el equipo." : "Vuelve al catálogo completo: el motor podrá proponerle cualquier acción y la prueba comparará con el catálogo entero."}
        confirmLabel={pendiente ? "Quitar el alta" : "Quitar el papel"} onConfirm={quitarInv} />
    </section>
  )
}

export function Conectividad() {
  const toast = useToast()
  const [d, setD] = useState<Datos | Fallo | undefined>()
  const [sel, setSel] = useState<string | null>(null)
  const [defecto, setDefecto] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const [asistente, setAsistente] = useState<Asistente>(null)
  const [rotar, setRotar] = useState(false)
  const [probando, setProbando] = useState<string | null>(null)
  const [tipoClave, setTipoClave] = useState<"ed25519" | "rsa">("ed25519")
  const [generando, setGenerando] = useState(false)
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
  const puede = d.permisos?.probar ?? d.editable
  const motivo = d.permisos?.motivo ?? d.motivo_no_editable
  const sesion = sesionActual()
  const franja = franjaPermisos(puede, motivo, sesion?.modo ?? null, operadorActual(), !!d.permisos?.generar_clave)
  const elegido = d.equipos.find((e) => e.nombre === sel) ?? d.equipos.find((e) => !e.protegido) ?? d.equipos[0]
  const valorDefecto = defecto ?? d.usuario_defecto ?? ""
  const modoNombre = MODOS.find((m) => m.id === d.modo)?.nombre ?? (d.modo === "sin_configurar" ? "sin configurar" : d.modo)
  const contenibles = d.equipos.filter((e) => !e.protegido && e.alta !== "pendiente" && e.huella_fijada)
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
  async function generar() {
    setGenerando(true)
    const res = await generarClaveConector(tipoClave)
    setGenerando(false)
    if (res.status === 200) toast({ type: "success", title: "Clave del conector generada", description: "Copia su clave pública o sigue con el papel y el paquete de cada equipo." })
    else toast({ type: "error", title: "No se generó", description: String(res.datos.error ?? `HTTP ${res.status}`) })
    recargar()
  }
  async function probarTodos() {
    let fallos = 0
    for (const e of contenibles) {
      setProbando(e.nombre)
      const res = await probarEquipo(e.nombre)
      if (res.status !== 200 || !(res.datos as { ok?: boolean }).ok) fallos += 1
    }
    setProbando(null)
    recargar()
    toast({ type: fallos ? "error" : "success", title: fallos ? `${fallos} de ${contenibles.length} equipos con problemas` : `Los ${contenibles.length} equipos verificados` })
  }

  return (
    <div className="space-y-3">
      <div role="status" className={cn("flex gap-2.5 rounded-lg border px-3.5 py-2.5 text-[13px]",
        franja.tono === "ok" ? "border-ok/35 bg-ok/8" : "border-aviso/35 bg-aviso/10")}>
        <span className={cn("font-bold", franja.tono === "ok" ? "text-ok" : "text-aviso")}>{franja.tono === "ok" ? "✓" : "!"}</span>
        <span><b className="font-semibold">{franja.titulo}</b> {franja.texto}</span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {puede ? <>
          <Boton tono="pri" onClick={() => setAsistente({ equipo: null })}>+ Añadir equipo</Boton>
          <Boton onClick={() => setRotar(true)}>{d.rotacion ? "Rotación de la clave en curso…" : "Rotar la clave del conector…"}</Boton>
          <Boton onClick={probarTodos} disabled={!!probando || !contenibles.length}>{probando ? `Probando ${probando}…` : "Probar todos"}</Boton>
        </> : <Bloqueado accion="Añadir equipos, rotar la clave y probar" motivo={MOTIVO_CORTO} />}
        <span className="ml-auto text-xs text-muted-foreground">Modo del conector: <b className="font-medium text-foreground">{modoNombre}</b>{d.nodo_gestion ? <> · <span className="font-mono">{d.nodo_gestion}</span></> : null} · se elige al arrancar el daemon</span>
      </div>

      {/* el conector, global */}
      <div className="overflow-hidden rounded-lg border border-border bg-card text-sm">
        <div className="grid lg:grid-cols-[1.2fr_1fr]">
          <div className="space-y-1.5 border-b border-border px-4 py-3 lg:border-b-0 lg:border-r">
            <div className="text-[11px] text-muted-foreground">Clave del conector{d.clave?.tipo ? ` (${d.clave.tipo.toLowerCase()})` : ""}</div>
            {d.clave ? <p className="font-mono text-xs [overflow-wrap:anywhere]">{d.clave.huella}</p>
              : d.falta_clave ? (
                <div className="space-y-2 text-xs">
                  <p className="font-medium text-critico">No hay clave del conector: sin ella no entra en ningún equipo ni contiene.</p>
                  {d.permisos?.generar_clave ? <>
                    <div className="flex flex-wrap gap-3" role="radiogroup" aria-label="Tipo de clave">
                      <label className="flex items-center gap-1.5"><input type="radio" name="tipo-clave" className="accent-primary" checked={tipoClave === "ed25519"} onChange={() => setTipoClave("ed25519")} />ed25519 (recomendada)</label>
                      <label className="flex items-center gap-1.5"><input type="radio" name="tipo-clave" className="accent-primary" checked={tipoClave === "rsa"} onChange={() => setTipoClave("rsa")} />RSA 3072 (equipos con OpenSSH antiguo)</label>
                    </div>
                    <Boton tono="pri" onClick={generar} disabled={generando}>{generando ? "Generando…" : "Generar la clave del conector"}</Boton>
                    <p className="text-muted-foreground">La privada se crea y se queda donde vive el conector{d.nodo_gestion ? <> (<span className="font-mono">{d.nodo_gestion}</span>)</> : ""}; aquí solo llega la pública.</p>
                  </> : <Bloqueado accion="Generar la clave" motivo={MOTIVO_CORTO} />}
                </div>)
              : <p className="text-xs text-muted-foreground">{d.modo === "sin_configurar" ? <span className="font-medium text-critico">Sin configurar: no se alcanza el nodo de gestión ({d.nodo_gestion ?? "TRIAJE_NODO_GESTION"}).</span> : "No disponible en este modo."}</p>}
            <div className="flex flex-wrap items-center gap-1.5">
              <Boton className="h-6 px-2 text-xs" onClick={copiar} disabled={!d.clave?.publica}>Copiar clave pública</Boton>
              <span className="text-xs text-muted-foreground">vive en <span className="font-mono">{d.ruta_clave}</span>{d.rotacion ? " · hay una rotación en curso" : ""}</span>
            </div>
          </div>
          <div className="space-y-1.5 px-4 py-3">
            <label htmlFor="cx-defecto" className="text-[11px] text-muted-foreground">Usuario por defecto en los equipos</label>
            <div className="flex flex-wrap items-center gap-1.5">
              <input id="cx-defecto" value={valorDefecto} placeholder={d.usuario_entorno} onChange={(x) => setDefecto(x.target.value)} disabled={!puede}
                className="h-[30px] w-40 rounded-[7px] border border-border bg-card px-2.5 text-[13px] outline-none focus:border-ring disabled:bg-muted disabled:text-muted-foreground" />
              {puede && defecto !== null && defecto !== (d.usuario_defecto ?? "") && <Boton tono="pri" className="h-[30px]" onClick={guardarDefecto}>Guardar</Boton>}
              {!puede && <Bloqueado accion="Cambiarlo" motivo={MOTIVO_CORTO} />}
            </div>
            <p className="text-xs text-muted-foreground">Sin contraseña, solo clave, y sudo limitado al papel de cada equipo.</p>
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

      <div className="grid items-start gap-3.5 lg:grid-cols-[minmax(0,1.35fr)_minmax(370px,1fr)]">
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="bg-muted text-left text-[11.5px] text-muted-foreground">
                <th className="px-3 py-2 font-medium">Equipo</th><th className="px-3 py-2 font-medium">Papel</th><th className="px-3 py-2 font-medium">Conexión</th>
                <th className="px-3 py-2 font-medium">Reglas en el equipo</th><th className="px-3 py-2 font-medium">Clave del host</th>
              </tr>
            </thead>
            <tbody>
              {d.equipos.map((e) => {
                const est = estadoEquipo(e)
                const reg = reglasDe(e)
                const activo = elegido?.nombre === e.nombre
                return (
                  <tr key={e.nombre} data-equipo={e.nombre} onClick={() => setSel(e.nombre)}
                    className={cn("cursor-pointer border-t border-border hover:bg-muted/50", activo && "bg-primary/10 shadow-[inset_3px_0_0_var(--primary)]",
                      (est.tono === "critico" || reg.tono === "critico") && !activo && "bg-critico/5")}>
                    <td className="px-3 py-2"><button type="button" className="text-left font-semibold whitespace-nowrap" aria-label={`Ver ${e.nombre}`}>{e.nombre}</button>
                      <span className="block text-[11.5px] text-muted-foreground">{[e.ip, e.zona].filter(Boolean).join(" · ")}</span></td>
                    {e.protegido ? <td colSpan={4} className="px-3 py-2 text-xs text-muted-foreground">Canal de gestión del MDR: no se contiene ni se configura desde aquí.</td> : <>
                      <td className="px-3 py-2">{papelTexto(e, d.papeles) ?? <span className="text-muted-foreground">sin papel</span>}
                        {(e.servicios?.length || e.cuentas?.length || e.cuentas_cualquiera) ? <span className="block text-[11.5px] text-muted-foreground">{[...(e.servicios ?? []), ...(e.cuentas_cualquiera ? ["cualquier cuenta"] : (e.cuentas ?? []).map((c) => `cuenta ${c}`))].join(" · ")}</span> : null}</td>
                      <td className="px-3 py-2">{est.aviso && <span className="mb-0.5 flex items-center gap-1.5 text-[11.5px] font-semibold whitespace-nowrap text-critico" title={est.aviso.sub}>
                          <TriangleAlert className="size-3" aria-hidden />{est.aviso.texto}</span>}
                        <span className={cn("inline-flex items-center gap-1.5 font-medium whitespace-nowrap", TEXTO[est.tono])}>
                        <span className={cn("size-2 rounded-full", PUNTO[est.tono])} />{est.texto}</span>
                        <span className="block text-[11.5px] text-muted-foreground">{est.sub}</span></td>
                      <td className="px-3 py-2"><span className={cn("rounded px-1.5 text-[11px] font-medium", PILDORA[reg.tono])}>{reg.texto}</span>
                        {reg.sub && <span className="block text-[11.5px] text-muted-foreground">{reg.sub}</span>}</td>
                      <td className="px-3 py-2 font-mono text-xs">{corta(e.huella_fijada) ?? <span className="font-sans text-muted-foreground">sin fijar</span>}</td>
                    </>}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {elegido ? <Inspector key={`${elegido.nombre}:${elegido.puerto}:${elegido.usuario}:${elegido.alta}:${elegido.ultima_prueba?.en}`} d={d} e={elegido} onCambio={recargar} onAsistente={setAsistente} />
          : <div className="rounded-lg border border-dashed border-border bg-card px-4 py-5 text-sm text-muted-foreground">El perfil no declara equipos con IP.</div>}
      </div>

      {asistente && <AltaEquipo d={d} equipo={asistente.equipo} pasoInicial={asistente.paso} onCerrar={() => setAsistente(null)} onCambio={recargar} />}
      {rotar && <RotacionClave d={d} onCerrar={() => setRotar(false)} onCambio={recargar} />}
    </div>
  )
}
