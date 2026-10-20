import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { nivelPrioridad, type Filtro } from "@/datos"

// Barra de filtros (búsqueda + clase) con contador de resultados. Reutilizada por Decisiones y Trazas.
export function BarraFiltros({ f, set, clases, cuenta, equipo, onQuitarEquipo }: {
  f: Filtro; set: (f: Filtro) => void; clases: string[]; cuenta: number
  equipo?: string | null; onQuitarEquipo?: () => void
}) {
  const campo = "h-9 rounded-md border border-border bg-card px-3 text-sm outline-none focus:border-ring"
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input value={f.texto} onChange={(e) => set({ ...f, texto: e.target.value })}
        placeholder="Buscar activo, IP, id…" className={cn(campo, "w-56")} />
      <select value={f.clase} onChange={(e) => set({ ...f, clase: e.target.value })} className={cn(campo, "px-2")}>
        <option value="">Todas las clases</option>
        {clases.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
      {equipo && (
        <span className="flex items-center gap-1 rounded bg-muted px-2 py-1 text-xs">
          equipo: <b>{equipo}</b>
          <button aria-label="Quitar el filtro de equipo" onClick={onQuitarEquipo} className="ml-1">✕</button>
        </span>
      )}
      <span className="text-xs text-muted-foreground">{cuenta} resultado(s)</span>
    </div>
  )
}

// Punto de estado: verde = ok, ambar = espera humano, rojo = caido/critico.
export function Punto({ estado }: { estado: "ok" | "caido" | "pendiente" }) {
  const color = estado === "ok" ? "bg-emerald-400" : estado === "pendiente" ? "bg-amber-400" : "bg-rose-400"
  return <span className={cn("inline-block size-2 shrink-0 rounded-full", color, estado !== "ok" && "animate-pulse")} />
}

export function Cargando() {
  return <p className="p-6 text-sm text-muted-foreground">cargando…</p>
}

export function Vacio({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-border/60 p-10 text-center text-sm text-muted-foreground">
      {children}
    </div>
  )
}

// A2: el mensaje nombra la causa real — mandar a arrancar el daemon cuando el problema es el token
// (401) o una respuesta que no valida desorienta al analista en el peor momento.
export function SinConexion({ causa }: { causa?: "auth" | "red" | "http" | "datos" }) {
  const cuerpo = causa === "auth"
    ? <>El daemon rechazó las credenciales (401): revisa el <b>token</b> de la consola (arriba a la derecha).</>
    : causa === "datos"
    ? <>El daemon respondió, pero con datos que este visor no entiende: ¿versiones distintas de visor y daemon?</>
    : <>Sin conexión con el daemon. Arráncalo con <code className="rounded bg-foreground/10 px-1 font-mono text-xs">--web</code> y
      esta vista se reconecta sola.</>
  return (
    <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-6 text-sm text-rose-700 dark:text-rose-300">
      {cuerpo}
    </div>
  )
}

// C2: al perder la conexión, la vista conserva la última tabla recibida bajo este aviso en vez de
// vaciarse al primer parpadeo de red. `desde` = cuándo llegaron esos datos (hora local del navegador).
export function DatosCongelados({ fallo }: { fallo: { error?: string; causa?: "auth" | "red" | "http" | "datos"; desde?: number } }) {
  const hora = fallo.desde ? new Date(fallo.desde).toLocaleTimeString() : null
  const motivo = fallo.causa === "auth" ? "el daemon rechazó el token (401)"
    : fallo.causa === "datos" ? "la última respuesta no validó"
    : "se perdió la conexión con el daemon"
  return (
    <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
      ⚠ {motivo} — mostrando los últimos datos recibidos{hora ? ` (${hora})` : ""}.
    </div>
  )
}

// Color de la clase de decision: la amenaza tira a rojo, el FP se apaga, lo enrutado a ambar.
export function ClaseBadge({ clase }: { clase?: string | null }) {
  if (!clase) return <span className="text-muted-foreground">—</span>
  const v = clase.startsWith("vp_") ? "destructive"
    : clase === "amenaza_enrutada" ? "default"
    : clase.startsWith("fp_") ? "secondary" : "outline"
  return <Badge variant={v as "destructive" | "default" | "secondary" | "outline"} className="font-normal">{clase}</Badge>
}

// Gravedad de la decisión (P1..P4) con su rótulo; el color refuerza, no sustituye al texto.
const TONO_PRIORIDAD = [
  "bg-slate-500/15 text-slate-600 dark:text-slate-300",
  "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  "bg-rose-500/15 text-rose-700 dark:text-rose-300",
]
export function Prioridad({ n }: { n?: number | null }) {
  const nivel = nivelPrioridad(n)
  if (!nivel) return <span className="text-muted-foreground">—</span>
  return (
    <span className={cn("whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium", TONO_PRIORIDAD[nivel.n - 1])}>
      {nivel.etiqueta}
    </span>
  )
}

// Valor de telemetria (IP, id, hora): monoespaciada, es dato tecnico, no etiqueta decorativa.
export function Dato({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("font-mono text-xs text-muted-foreground", className)}>{children}</span>
}
