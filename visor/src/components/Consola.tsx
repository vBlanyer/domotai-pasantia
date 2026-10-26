import { useEffect, useRef, useState } from "react"
import { getConsola, type Fallo } from "@/api"
import { clasificarLinea, filtrarConsola, type LineaConsola, type TipoLinea } from "@/datos"
import { Cargando, SinConexion } from "./bits"
import { cn } from "@/lib/utils"

const TOPE_CLIENTE = 1000   // mismo tope que el buffer del daemon: la vista nunca crece sin límite

// Feed incremental: pide solo las líneas nuevas (?desde=cursor) cada 2 s y las acumula acotadas.
// Un fallo del sondeo conserva lo acumulado (el feed es local) y se señala sin vaciar nada.
function useConsola(ms = 2000) {
  const [lineas, setLineas] = useState<LineaConsola[] | null>(null)
  const [fallo, setFallo] = useState<Fallo | null>(null)
  const cursor = useRef(0)
  useEffect(() => {
    let vivo = true
    const tick = async () => {
      const r = await getConsola(cursor.current)
      if (!vivo) return
      if ("error" in r) {
        setFallo(r)
        return
      }
      setFallo(null)
      cursor.current = r.hasta
      if (r.lineas.length) {
        setLineas((prev) => [...(prev ?? []), ...r.lineas].slice(-TOPE_CLIENTE))
      } else {
        setLineas((prev) => prev ?? [])
      }
    }
    tick()
    const id = setInterval(tick, ms)
    return () => { vivo = false; clearInterval(id) }
  }, [ms])
  return { lineas, fallo }
}

const TONO: Record<TipoLinea, string> = {
  incidente: "text-amber-600 dark:text-amber-400",
  decision: "text-foreground",
  supresion: "text-muted-foreground",
  error: "text-rose-600 dark:text-rose-400",
  propia: "text-muted-foreground italic",
  aviso: "text-amber-700 dark:text-amber-300",
  otro: "text-muted-foreground",
}

const GRUPOS: [string, string][] = [
  ["todo", "Todo"], ["decisiones", "Decisiones"], ["incidentes", "Incidentes"], ["avisos", "Avisos"],
]

export function Consola() {
  const { lineas, fallo } = useConsola()
  const [grupo, setGrupo] = useState("todo")
  const [texto, setTexto] = useState("")
  const [autoScroll, setAutoScroll] = useState(true)
  const fin = useRef<HTMLDivElement>(null)
  const caja = useRef<HTMLDivElement>(null)

  // Auto-scroll al llegar líneas, PAUSADO si el analista subió a leer (se reanuda al volver abajo).
  useEffect(() => {
    // llamada opcional: jsdom (tests) no implementa scrollIntoView
    if (autoScroll) fin.current?.scrollIntoView?.({ block: "end" })
  }, [lineas, autoScroll])
  function alDesplazar() {
    const c = caja.current
    if (!c) return
    setAutoScroll(c.scrollHeight - c.scrollTop - c.clientHeight < 40)
  }

  if (lineas === null && fallo) return <SinConexion causa={fallo.causa} />
  if (lineas === null) return <Cargando />
  const visibles = filtrarConsola(lineas, grupo, texto)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1 rounded-lg border border-border bg-muted/40 p-1">
          {GRUPOS.map(([id, nombre]) => (
            <button key={id} onClick={() => setGrupo(id)}
              className={cn("rounded-md px-3 py-1.5 text-sm transition-colors",
                grupo === id ? "bg-card font-medium text-foreground shadow-sm"
                             : "text-muted-foreground hover:text-foreground")}>
              {nombre}
            </button>
          ))}
        </div>
        <input value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="filtrar texto…"
          className="h-9 w-56 rounded-md border border-border bg-card px-3 text-sm outline-none focus:border-ring" />
        <span className="ml-auto text-xs text-muted-foreground">
          {visibles.length} de {lineas.length} línea(s) · últimas {TOPE_CLIENTE} del daemon
          {!autoScroll && " · auto-scroll en pausa (baja al final para reanudar)"}
        </span>
      </div>

      {fallo && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          ⚠ se perdió la conexión con el daemon — el feed conserva lo recibido y se reanuda solo.
        </div>
      )}

      <div ref={caja} onScroll={alDesplazar}
        className="h-[70vh] overflow-y-auto rounded-lg border border-border bg-card">
        {lineas.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">
            Aún no hay actividad en esta sesión del daemon. Las líneas aparecen aquí según el sistema
            decide, bloquea, verifica o avisa — lo mismo que narra su terminal.
          </p>
        ) : (
          <pre className="m-0 whitespace-pre-wrap break-words p-3 font-mono text-xs leading-relaxed">
            {visibles.map((l) => (
              <div key={l.n} className={TONO[clasificarLinea(l.linea)]}>
                <span className="select-none text-muted-foreground/60">{l.t} </span>{l.linea}
              </div>
            ))}
            <div ref={fin} />
          </pre>
        )}
      </div>
    </div>
  )
}
