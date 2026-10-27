import { useRef, useState, useEffect } from "react"
import { TriangleAlert, Clock } from "lucide-react"
import { useSondeo, getPendientes, aprobar, parsearPendiente, operadorActual, fijarOperador, ahoraServidor, type Pendiente, type Opcion } from "@/api"
import { edadTexto, envejecido, msDesde } from "@/alertas"
import { etiquetaClase } from "@/datos"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { AlertDialog } from "@/components/ui/alert-dialog"
import { Cargando, SinConexion, Vacio, Punto, Prioridad, DatosCongelados } from "./bits"

// Lo que el aviso confirma tras un veredicto aplicado (mismo vocabulario que el menú del daemon).
const HECHO: Record<string, string> = {
  Aprobar: "Aprobada: se ejecuta la acción propuesta",
  Rechazar: "Rechazada: se retiene sin ejecutar",
}

// enviando: el POST está en vuelo · clases: «Reclasificar» aceptado, a la espera del submenú ·
// hecho: veredicto aplicado, la tarjeta sale de la cola en el próximo refresco.
type Estado = "listo" | "enviando" | "clases" | "hecho"
const MENSAJE: Record<Exclude<Estado, "listo">, string> = {
  enviando: "Enviando…",
  clases: "Cargando las clases…",
  hecho: "Aplicado. Sale de la cola en el próximo refresco.",
}

// Botón a partir de una opción del menú: veredicto (aprobar/rechazar/reclasificar) o una clase.
function boton(op: Opcion): { etiqueta: string; variante: "default" | "destructive" | "outline" } {
  const base = op.etiqueta.split("—")[0].trim().toLowerCase()
  if (base === "aprobar") return { etiqueta: "Aprobar", variante: "default" }
  if (base === "rechazar") return { etiqueta: "Rechazar", variante: "destructive" }
  if (base === "reclasificar") return { etiqueta: "Reclasificar", variante: "outline" }
  // submenú de clases: etiqueta legible de la fuente única (@/datos); desconocida -> la del menú
  const legible = etiquetaClase(base)
  return { etiqueta: legible !== base ? legible : op.etiqueta, variante: "outline" }
}

// La `respuesta` que espera el daemon para un veredicto, según el tipo de pendiente (para el bloque).
function respuestaPara(p: Pendiente, veredicto: "aprobar" | "rechazar"): string {
  if (p.tipo === "escalada") return veredicto === "aprobar" ? "s" : ""
  const op = parsearPendiente(p).opciones.find((o) => boton(o).etiqueta === (veredicto === "aprobar" ? "Aprobar" : "Rechazar"))
  return op ? op.n : veredicto === "aprobar" ? "1" : "2"
}

function LineaInfo({ t }: { t: string }) {
  const i = t.indexOf(": ")
  if (i === -1) return <div className="text-sm">{t}</div>
  return (
    <div className="text-sm">
      <span className="text-muted-foreground">{t.slice(0, i)}:</span> {t.slice(i + 2)}
    </div>
  )
}

// Reloj que avanza cada segundo, para que el «lleva esperando X» de la cola sea en vivo (el sondeo
// no re-renderiza si los datos no cambian). La edad sale de `encolado_en` del servidor y se compara
// contra la hora del DAEMON (ahoraServidor, anclada a la cabecera Date): el drift del reloj del
// navegador (A3, habitual en WSL2/VMs) ya no infla ni congela el SLA.
function useAhora(ms = 1000): number {
  const [ahora, setAhora] = useState(() => ahoraServidor())
  useEffect(() => {
    const t = setInterval(() => setAhora(ahoraServidor()), ms)
    return () => clearInterval(t)
  }, [ms])
  return ahora
}

function Tarjeta({ p, edadMs = 0, seleccionada, onSeleccion }: {
  p: Pendiente; edadMs?: number; seleccionada?: boolean; onSeleccion?: (checked: boolean) => void
}) {
  const v = parsearPendiente(p)
  const escalada = p.tipo === "escalada"
  const viejo = envejecido(edadMs)
  // Vetada sin sustituta (accion_final null; ausente = daemon antiguo): aprobar no ejecuta nada, así
  // que ni se confirma una cascada que no ocurrirá ni se anuncia una contención.
  const sinAccion = !escalada && p.accion_final === null
  const conCascada = !sinAccion && v.cascada.length > 0
  const clasificando = (v.titulo ?? "").startsWith("Nueva clase")
  const toast = useToast()
  const [estado, setEstado] = useState<Estado>("listo")
  const enVuelo = useRef(false)                 // corta el doble clic antes de que llegue el re-render

  // Envía el veredicto con el `paso` del menú que se ve. Mientras vuela, la tarjeta se bloquea; si
  // el backend lo rechaza (409: ya resuelta o menú superado) se avisa y se reactiva.
  async function responder(respuesta: string, etiqueta: string) {
    if (enVuelo.current) return
    enVuelo.current = true
    setEstado("enviando")
    const r = await aprobar(p.id, respuesta, p.paso)
    if (r !== "ok") {
      enVuelo.current = false
      setEstado("listo")
      toast({ type: "error", title: "No se aplicó el veredicto",
        description: r === "auth"
          ? "El daemon rechazó el token de la consola (401): revísalo arriba a la derecha."
          : "Ya no estaba vigente (la resolvió otro operador o cambió el menú) o se perdió la conexión con el daemon." })
      return
    }
    if (!escalada && !clasificando && etiqueta === "Reclasificar") {
      setEstado("clases")                        // sigue bloqueada hasta que llegue el submenú (paso nuevo)
      return
    }
    setEstado("hecho")
    const titulo = clasificando ? `Reclasificada como «${etiqueta}»`
      : sinAccion && etiqueta === "Aprobar" ? "Aprobada: la acción está vetada, no se ejecuta nada"
      : HECHO[etiqueta] ?? etiqueta
    toast({ type: "success", description: v.incidente, title: titulo })
  }
  const bloqueada = estado !== "listo"
  const [confirmar, setConfirmar] = useState<{ respuesta: string; etiqueta: string } | null>(null)

  // Aprobar un bloqueo que deja activos sin servicio en cascada exige un gesto consciente; rechazar
  // o reclasificar no ejecutan nada y van directos.
  function pulsar(respuesta: string, etiqueta: string) {
    if (etiqueta === "Aprobar" && conCascada) setConfirmar({ respuesta, etiqueta })
    else responder(respuesta, etiqueta)
  }

  return (
    <div className={`overflow-hidden rounded-lg border ${viejo ? "border-rose-500/50 bg-rose-500/[0.05]" : "border-amber-500/40 bg-amber-500/[0.04]"}`}>
      <div className={`flex flex-wrap items-center gap-2 border-b px-4 py-2.5 ${viejo ? "border-rose-500/25" : "border-amber-500/20"}`}>
        {onSeleccion && <input type="checkbox" aria-label="Seleccionar" checked={!!seleccionada}
          onChange={(e) => onSeleccion(e.target.checked)} className="size-4 accent-amber-600" />}
        <Punto estado="pendiente" />
        <span className="text-sm font-medium text-amber-700 dark:text-amber-300">Espera tu decisión</span>
        {!!p.severidad && <Prioridad n={p.severidad} />}
        {v.incidente && <span className="ml-1 truncate text-xs text-muted-foreground">· {v.incidente}</span>}
        <span className={`ml-auto flex shrink-0 items-center gap-1 text-xs ${viejo ? "font-medium text-rose-600 dark:text-rose-400" : "text-muted-foreground"}`}
          title="Tiempo que lleva esperando tu decisión en esta sesión">
          <Clock className="size-3" /> pendiente {edadTexto(edadMs)}
        </span>
        {!!p.suprimidas && p.suprimidas > 0 && (
          <span className="shrink-0 rounded bg-rose-500/15 px-1.5 py-0.5 text-xs font-medium text-rose-600 dark:text-rose-400">
            sigue atacando · +{p.suprimidas}
          </span>
        )}
      </div>

      <div className="space-y-3 p-4">
        {v.info.length > 0 && (
          <div className="space-y-1">
            {v.info.map((t, i) => <LineaInfo key={i} t={t} />)}
          </div>
        )}

        {v.consecuencia && (
          <div className={`flex items-start gap-2 rounded-md border p-2.5 text-sm ${
            conCascada ? "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300" : "border-border bg-muted"
          }`}>
            {conCascada && <TriangleAlert className="mt-0.5 size-4 shrink-0" />}
            <div><span className="font-medium">Consecuencia:</span> {v.consecuencia}</div>
          </div>
        )}

        {clasificando && <div className="pt-1 text-sm font-medium">Elige la clase correcta:</div>}

        <div className="flex flex-wrap gap-2">
          {escalada ? (
            <>
              <Button disabled={bloqueada} onClick={() => pulsar("s", "Aprobar")}>Aprobar</Button>
              <Button disabled={bloqueada} variant="destructive" onClick={() => pulsar("", "Rechazar")}>Rechazar</Button>
            </>
          ) : v.opciones.length > 0 ? (
            v.opciones.map((op) => {
              const b = boton(op)
              return (
                <Button key={op.n} disabled={bloqueada} variant={b.variante} onClick={() => pulsar(op.n, b.etiqueta)}>
                  {b.etiqueta}
                </Button>
              )
            })
          ) : (
            // fallback: el prompt no trajo el menú (p. ej. daemon sin la última versión)
            <>
              <Button disabled={bloqueada} onClick={() => pulsar("1", "Aprobar")}>Aprobar</Button>
              <Button disabled={bloqueada} variant="destructive" onClick={() => pulsar("2", "Rechazar")}>Rechazar</Button>
            </>
          )}
        </div>
        {estado !== "listo" && (
          <p aria-live="polite" className="text-xs text-muted-foreground">{MENSAJE[estado]}</p>
        )}
        <AlertDialog open={confirmar !== null} onOpenChange={(o) => { if (!o) setConfirmar(null) }}
          title="¿Aprobar pese a la cascada?"
          description="El bloqueo deja sin servicio a los activos que dependen de este:"
          confirmLabel="Aprobar igualmente"
          onConfirm={() => { if (confirmar) responder(confirmar.respuesta, confirmar.etiqueta) }}>
          <ul className="list-disc space-y-0.5 pl-5">{v.cascada.map((a) => <li key={a}>{a}</li>)}</ul>
        </AlertDialog>
      </div>
    </div>
  )
}

function BarraOperador() {
  const [nombre, setNombre] = useState(operadorActual())
  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      <span>Operador:</span>
      <input value={nombre} placeholder="tu nombre (queda en la traza)"
        onChange={(e) => { setNombre(e.target.value); fijarOperador(e.target.value) }}
        className="w-56 rounded-md border border-border bg-card px-2 py-1 text-foreground" />
    </label>
  )
}

export function Aprobaciones() {
  const p = useSondeo(getPendientes)
  const ahora = useAhora()   // hook incondicional (antes de cualquier return); 1 Hz para el SLA en vivo
  const [sel, setSel] = useState<Set<string>>(new Set())
  const [confirmarBloque, setConfirmarBloque] = useState(false)
  const toast = useToast()
  // Con la conexión perdida pero datos previos, la cola se sigue mostrando (congelada) con aviso:
  // vaciarla en un parpadeo de red haría «desaparecer» decisiones que siguen esperando (C2).
  const lista = !p ? null : "error" in p ? (p.datos ?? null) : p
  const fallo = p && "error" in p ? p : null
  const elegidas = (lista ?? []).filter((x) => sel.has(x.id))
  const alternar = (id: string, c: boolean) => setSel((s) => { const n = new Set(s); c ? n.add(id) : n.delete(id); return n })

  // Acciones en bloque: aplica el mismo veredicto a las seleccionadas (reusa el POST por decisión).
  async function enBloque(veredicto: "aprobar" | "rechazar") {
    setConfirmarBloque(false)
    let ok = 0, falladas = 0
    for (const x of elegidas) {
      const r = await aprobar(x.id, respuestaPara(x, veredicto), x.paso)
      r === "ok" ? ok++ : falladas++
    }
    setSel(new Set())
    toast({ type: falladas ? "error" : "success",
      title: `${ok} ${veredicto === "aprobar" ? "aprobada(s)" : "rechazada(s)"}${falladas ? ` · ${falladas} sin aplicar` : ""}` })
  }

  const cuerpo = !p ? <Cargando />
    : lista === null ? <SinConexion causa={fallo?.causa} />
    : lista.length === 0 ? <Vacio>Nada que aprobar ahora mismo. Cuando una decisión necesite un humano, aparecerá aquí.</Vacio>
    // la clave incluye el paso: un menú nuevo (submenú de clases) monta la tarjeta con estado limpio
    : <div className="space-y-4">{lista.map((x) => (
        <Tarjeta key={`${x.id}:${x.paso ?? 0}`} p={x} edadMs={msDesde(x.encolado_en, ahora)}
          seleccionada={sel.has(x.id)} onSeleccion={(c) => alternar(x.id, c)} />
      ))}</div>
  return (
    <div className="space-y-4">
      <BarraOperador />
      {elegidas.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card p-3 text-sm">
          <span className="font-medium">{elegidas.length} seleccionada(s)</span>
          <Button size="sm" variant="destructive" onClick={() => enBloque("rechazar")}>Rechazar seleccionadas</Button>
          <Button size="sm" onClick={() => setConfirmarBloque(true)}>Aprobar seleccionadas</Button>
          <button onClick={() => setSel(new Set())} className="ml-auto text-xs text-muted-foreground hover:underline">quitar selección</button>
        </div>
      )}
      {fallo && lista !== null && <DatosCongelados fallo={fallo} />}
      {cuerpo}
      <AlertDialog open={confirmarBloque} onOpenChange={(o) => { if (!o) setConfirmarBloque(false) }}
        title={`¿Aprobar ${elegidas.length} decisión(es)?`}
        description="Se ejecutará la acción propuesta de cada una (contención). Revisa que es lo que quieres."
        confirmLabel="Aprobar todas" onConfirm={() => enBloque("aprobar")} />
    </div>
  )
}
