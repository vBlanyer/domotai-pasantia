import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react"
import { ChevronDown, LogOut, UserPen } from "lucide-react"
import { comprobarSesion, fijarToken, fijarOperador, operadorActual, type ModoSesion, type Sesion } from "@/api"
import { cn } from "@/lib/utils"

// Acceso a la consola. Usa el modelo que el daemon ya tiene: un token por operador (autentica y firma)
// o un token compartido; sin token configurado la consola está abierta (laboratorio). Antes de entrar
// no se pinta ningún dato del cliente: solo si el daemon responde.

export type Motivo = "rechazado" | "caducado" | "sin_red" | "bloqueado"
export type Entrada = { modo: ModoSesion; operador: string | null }

const MENSAJE: Record<Motivo, { tono: "crit" | "aviso"; titulo: string; texto: string }> = {
  rechazado: { tono: "crit", titulo: "El daemon no reconoce ese token.", texto: "Revisa que esté completo o pide uno nuevo; puede haber sido revocado." },
  caducado: { tono: "crit", titulo: "Tu token ya no es válido.", texto: "Puede haberse revocado o el servicio se reinició con otra configuración." },
  sin_red: { tono: "aviso", titulo: "No hay respuesta del servicio MDR en este equipo.", texto: "El problema no es tu token: comprueba que el daemon está en marcha. Se reintenta solo." },
  bloqueado: { tono: "crit", titulo: "Demasiados intentos.", texto: "Espera antes de volver a probar. Los intentos quedan registrados en el daemon." },
}

function Aviso({ motivo, segundos }: { motivo: Motivo; segundos: number }) {
  const m = MENSAJE[motivo]
  return (
    <div role="alert" className={cn("flex gap-2.5 rounded-lg border px-3 py-2.5 text-sm",
      m.tono === "crit" ? "border-critico/35 bg-critico/10" : "border-aviso/35 bg-aviso/10")}>
      <span className={cn("font-bold", m.tono === "crit" ? "text-critico" : "text-aviso")}>!</span>
      <span><b className="font-semibold">{m.titulo}</b> {m.texto}{motivo === "bloqueado" && segundos > 0 ? ` Quedan ${segundos} s.` : ""}</span>
    </div>
  )
}

const BOTON = "grid h-10 w-full place-items-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-55"
const CAJA = "flex h-10 items-center gap-2 rounded-lg border bg-card px-3 text-sm focus-within:border-primary focus-within:ring-3 focus-within:ring-primary/20"

// Formulario del token, compartido por la pantalla de acceso y el aviso de sesión caducada.
function FormToken({ motivoInicial, segundosIniciales = 0, boton, onEntrar, recordarVisible = true, onDaemon }: {
  motivoInicial?: Motivo; segundosIniciales?: number; boton: string; onEntrar: (e: Entrada) => void
  recordarVisible?: boolean; onDaemon?: (responde: boolean) => void
}) {
  const [token, setToken] = useState("")
  const [ver, setVer] = useState(false)
  const [recordar, setRecordar] = useState(true)
  const [motivo, setMotivo] = useState<Motivo | null>(motivoInicial ?? null)
  const [segundos, setSegundos] = useState(segundosIniciales)
  const [enviando, setEnviando] = useState(false)
  const campo = useRef<HTMLInputElement>(null)

  // cuenta atrás del bloqueo por intentos
  useEffect(() => {
    if (motivo !== "bloqueado") return
    const t = setInterval(() => setSegundos((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
  }, [motivo])

  // sin daemon: reintenta cada 5 s sin token; al volver, quita el aviso (o entra si la consola es abierta)
  useEffect(() => {
    if (motivo !== "sin_red") return
    const t = setInterval(async () => {
      const r = await comprobarSesion("")
      if (r.tipo === "sin_red") return
      onDaemon?.(true)
      setMotivo(null)
      if (r.tipo === "ok" && !r.requiereToken) onEntrar({ modo: "abierta", operador: null })
    }, 5000)
    return () => clearInterval(t)
  }, [motivo, onEntrar, onDaemon])

  const bloqueado = motivo === "bloqueado" && segundos > 0
  const visible = motivo === "bloqueado" && !bloqueado ? null : motivo     // acabado el bloqueo, el aviso se va
  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (!token.trim() || enviando || bloqueado) return
    setEnviando(true)
    const r = await comprobarSesion(token.trim())
    setEnviando(false)
    onDaemon?.(r.tipo !== "sin_red")
    if (r.tipo === "ok") {
      if (!r.requiereToken) return onEntrar({ modo: "abierta", operador: null })
      fijarToken(token.trim(), recordar)
      return onEntrar({ modo: r.operador ? "identificado" : "compartido", operador: r.operador })
    }
    if (r.tipo === "bloqueado") setSegundos(r.segundos)
    setMotivo(r.tipo)
    campo.current?.focus()
  }

  return (
    <form onSubmit={enviar} className="flex flex-col gap-4" noValidate>
      {visible && <Aviso motivo={visible} segundos={segundos} />}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="token-operador" className="text-[13px] font-medium">Token de operador</label>
        <div className={cn(CAJA, motivo === "rechazado" || motivo === "caducado" ? "border-critico ring-3 ring-critico/15" : "border-border")}>
          <input id="token-operador" ref={campo} autoFocus type={ver ? "text" : "password"} value={token} autoComplete="off" spellCheck={false}
            onChange={(e) => { setToken(e.target.value); if (motivo === "rechazado" || motivo === "caducado") setMotivo(null) }}
            className="min-w-0 flex-1 bg-transparent font-mono tracking-wider outline-none" />
          <button type="button" onClick={() => setVer((v) => !v)} className="text-xs font-medium text-info hover:underline">{ver ? "Ocultar" : "Mostrar"}</button>
        </div>
        <span className="text-xs text-muted-foreground">Tu token te identifica: lo que apruebes o cambies queda firmado con tu nombre en la traza.</span>
      </div>
      {recordarVisible && (
        <label className="flex items-start gap-2 text-[13px]">
          <input type="checkbox" checked={recordar} onChange={(e) => setRecordar(e.target.checked)} className="mt-0.5 size-4 accent-primary" />
          <span>Mantener la sesión en esta pestaña<span className="block text-xs text-muted-foreground">Al cerrar la pestaña se borra. Nunca se guarda en el disco.</span></span>
        </label>
      )}
      <button type="submit" className={BOTON} disabled={!token.trim() || enviando || bloqueado}>
        {bloqueado ? `${boton} · 0:${String(segundos).padStart(2, "0")}` : enviando ? "Comprobando…" : boton}
      </button>
    </form>
  )
}

function FormNombre({ modo, onListo }: { modo: Exclude<ModoSesion, "identificado">; onListo: () => void }) {
  const [nombre, setNombre] = useState(operadorActual())
  const enviar = (e: FormEvent) => { e.preventDefault(); if (!nombre.trim()) return; fijarOperador(nombre.trim()); onListo() }
  return (
    <form onSubmit={enviar} className="flex flex-col gap-4">
      <div role="note" className="flex gap-2.5 rounded-lg border border-aviso/35 bg-aviso/10 px-3 py-2.5 text-sm">
        <span className="font-bold text-aviso">!</span>
        <span>{modo === "abierta"
          ? <><b className="font-semibold">Este daemon no exige token.</b> Cualquiera con acceso a este equipo puede usar la consola. Solo es aceptable en el laboratorio.</>
          : <><b className="font-semibold">Entraste con el token compartido.</b> El daemon no sabe quién eres: tu nombre firma tus acciones sin verificarse.</>}</span>
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="nombre-operador" className="text-[13px] font-medium">Tu nombre</label>
        <div className={cn(CAJA, "border-border")}>
          <input id="nombre-operador" autoFocus value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={60}
            className="min-w-0 flex-1 bg-transparent outline-none" placeholder="nombre.apellido" />
        </div>
        <span className="text-xs text-muted-foreground">Se usa para firmar tus acciones, sin comprobarlo.</span>
      </div>
      <button type="submit" className={BOTON} disabled={!nombre.trim()}>Continuar</button>
    </form>
  )
}

function Malla() {
  return (
    <svg className="pointer-events-none absolute -right-14 top-28 w-72 opacity-20" viewBox="0 0 200 200" fill="none" stroke="#3cc6da" strokeWidth="1" aria-hidden>
      <circle cx="40" cy="40" r="4" /><circle cx="150" cy="30" r="4" /><circle cx="100" cy="100" r="6" /><circle cx="30" cy="160" r="4" />
      <circle cx="170" cy="150" r="4" /><circle cx="110" cy="180" r="3" />
      <path d="M40 40L100 100L150 30M100 100L30 160M100 100L170 150M100 100L110 180M150 30L170 150" />
    </svg>
  )
}

// Pantalla completa de acceso: marca a la izquierda (siempre oscura), formulario a la derecha.
export function Acceso({ motivo, segundos, pedirNombre, onEntrar, onNombre }: {
  motivo?: Motivo; segundos?: number; pedirNombre?: Exclude<ModoSesion, "identificado">
  onEntrar: (e: Entrada) => void; onNombre?: () => void
}) {
  const [responde, setResponde] = useState(motivo !== "sin_red")
  return (
    <div className="grid min-h-dvh bg-background text-foreground md:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <aside className="relative flex min-h-56 flex-col justify-between overflow-hidden bg-[#0d1117] px-8 py-8 text-[#c9d4e0] md:px-12 md:py-10">
        <Malla />
        <div className="flex items-center gap-2.5">
          <div className="grid size-9 place-items-center rounded-lg bg-[#3cc6da]/20 font-bold text-[#3cc6da]">M</div>
          <div className="leading-tight"><div className="text-sm font-semibold text-[#e6edf3]">MDR</div><div className="text-[11.5px] text-[#7d8a99]">consola de triaje</div></div>
        </div>
        <div className="my-8 hidden md:block">
          <h2 className="mb-2.5 max-w-[18ch] text-[1.6rem] font-semibold leading-tight tracking-tight text-[#e6edf3]">Detección y respuesta gestionada</h2>
          <p className="max-w-[40ch] text-sm text-[#8b98a9]">Triaje de las alertas del SIEM del cliente, con cada decisión firmada y encadenada en la traza.</p>
        </div>
        <div className="flex flex-col gap-1.5 text-xs text-[#7d8a99]">
          <span className="flex items-center gap-2"><span className={cn("size-2 rounded-full", responde ? "bg-[#3fb950]" : "bg-[#f0785f]")} />
            {responde ? "Daemon disponible en este equipo" : "Sin respuesta del daemon"}</span>
          <span>Conexión local, sin pasar por la red</span>
        </div>
      </aside>
      <main className="flex items-center justify-center bg-card px-6 py-10 md:px-14">
        <div className="w-full max-w-md space-y-5">
          <div>
            <h1 className="text-[1.35rem] font-semibold tracking-tight">{pedirNombre ? "¿Quién está al mando?" : "Entrar a la consola"}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{pedirNombre ? "Tu nombre aparecerá en la traza junto a cada acción que firmes." : "Usa el token de operador que te asignó el responsable del servicio."}</p>
          </div>
          {pedirNombre ? <FormNombre modo={pedirNombre} onListo={() => onNombre?.()} />
            : <FormToken motivoInicial={motivo} segundosIniciales={segundos} boton="Entrar" onEntrar={onEntrar} onDaemon={setResponde} />}
          {!pedirNombre && (
            <p className="border-t border-border pt-3.5 text-xs text-muted-foreground">
              ¿Sin token? Pídelo al responsable del servicio MDR. Se configura en el daemon con <span className="font-mono">TRIAJE_CONSOLA_OPERADORES</span> (un token por persona).
            </p>
          )}
        </div>
      </main>
    </div>
  )
}

// La sesión dejó de valer dentro de la consola: se vuelve a entrar sin perder la vista.
export function Reautenticar({ onEntrar, onSalir }: { onEntrar: (e: Entrada) => void; onSalir: () => void }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[#0d1117]/55 p-4 backdrop-blur-[2px]" role="dialog" aria-modal aria-label="Volver a entrar">
      <div className="w-full max-w-sm space-y-3 rounded-xl border border-border bg-card p-6 shadow-2xl">
        <h2 className="text-base font-semibold">Tu token ya no es válido</h2>
        <p className="text-[13px] text-muted-foreground">El daemon lo rechazó: puede haberse revocado o el servicio se reinició con otra configuración. Vuelve a entrar y seguirás en esta misma vista.</p>
        <FormToken boton="Volver a entrar" onEntrar={onEntrar} recordarVisible={false} />
        <button type="button" onClick={onSalir} className="w-full text-center text-xs font-medium text-muted-foreground hover:text-foreground">Salir a la pantalla de acceso</button>
      </div>
    </div>
  )
}

const iniciales = (n: string) => n.split(/[\s._-]+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("") || "?"
const DESCRIPCION: Record<ModoSesion, string> = {
  identificado: "Operador identificado por token · firma sus acciones",
  compartido: "Token compartido · el nombre no lo verifica el daemon",
  abierta: "Consola abierta · el nombre no se verifica",
}

function Item({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return <button type="button" role="menuitem" onClick={onClick} className="flex w-full items-center gap-2 border-t border-border px-3.5 py-2.5 text-left text-[13px] hover:bg-muted">{children}</button>
}

// Quién eres, en la cabecera: nombre con menú (descripción, desde cuándo, cambiar nombre, cerrar sesión).
export function ChipSesion({ sesion, nombre, onCerrar, onCambiarNombre }: { sesion: Sesion; nombre: string; onCerrar: () => void; onCambiarNombre: () => void }) {
  const [abierto, setAbierto] = useState(false)
  const caja = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!abierto) return
    const fuera = (e: MouseEvent) => { if (e.target instanceof Node && !caja.current?.contains(e.target)) setAbierto(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setAbierto(false) }
    document.addEventListener("mousedown", fuera); document.addEventListener("keydown", esc)
    return () => { document.removeEventListener("mousedown", fuera); document.removeEventListener("keydown", esc) }
  }, [abierto])
  const etiqueta = nombre || "sin nombre"
  return (
    <div ref={caja} className="relative">
      <button type="button" onClick={() => setAbierto((a) => !a)} aria-haspopup="menu" aria-expanded={abierto} aria-label={`Sesión de ${etiqueta}`}
        className="flex items-center gap-2 rounded-full border border-border py-0.5 pl-0.5 pr-2.5 text-[13px] transition-colors hover:bg-muted">
        <span className={cn("grid size-7 place-items-center rounded-full text-xs font-semibold",
          sesion.modo === "identificado" ? "bg-primary/20 text-primary" : "bg-aviso/15 text-aviso")}>{iniciales(etiqueta)}</span>
        <span className="hidden max-w-36 truncate sm:inline">{etiqueta}</span>
        <ChevronDown className="size-3.5 text-muted-foreground" />
      </button>
      {abierto && (
        <div role="menu" className="absolute right-0 top-full z-40 mt-2 w-64 overflow-hidden rounded-xl border border-border bg-card shadow-xl">
          <div className="px-3.5 py-2.5">
            <div className="truncate text-sm font-semibold">{etiqueta}</div>
            <div className="text-xs text-muted-foreground">{DESCRIPCION[sesion.modo]}</div>
          </div>
          <div className="border-t border-border px-3.5 py-2 text-xs text-muted-foreground">
            Sesión en esta pestaña desde las {new Date(sesion.desde).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}
          </div>
          {sesion.modo !== "identificado" && <Item onClick={() => { setAbierto(false); onCambiarNombre() }}><UserPen className="size-4" />Cambiar nombre</Item>}
          {sesion.modo !== "abierta" && <Item onClick={() => { setAbierto(false); onCerrar() }}><LogOut className="size-4" />Cerrar sesión</Item>}
        </div>
      )}
    </div>
  )
}

export function BandaAbierta() {
  return (
    <div role="status" className="flex items-center gap-2 border-b border-aviso/40 bg-aviso/12 px-4 py-1.5 text-xs md:px-8 print:hidden">
      <b className="font-semibold text-aviso">Consola abierta.</b>
      <span>Este daemon no exige token: modo laboratorio. Cualquiera con acceso a este equipo puede usarla.</span>
    </div>
  )
}
