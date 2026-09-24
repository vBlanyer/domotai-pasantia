import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { type Filtro } from "@/datos"

// Barra de filtros (búsqueda + clase) con contador de resultados. Reutilizada por Decisiones y Trazas.
export function BarraFiltros({ f, set, clases, cuenta }: {
  f: Filtro; set: (f: Filtro) => void; clases: string[]; cuenta: number
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

export function SinConexion() {
  return (
    <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-6 text-sm text-rose-700 dark:text-rose-300">
      Sin conexión con el daemon. Arráncalo con <code className="rounded bg-foreground/10 px-1 font-mono text-xs">--web</code> y
      esta vista se reconecta sola.
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

// Valor de telemetria (IP, id, hora): monoespaciada, es dato tecnico, no etiqueta decorativa.
export function Dato({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("font-mono text-xs text-muted-foreground", className)}>{children}</span>
}
