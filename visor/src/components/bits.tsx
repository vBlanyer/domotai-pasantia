import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"

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
      Sin conexión con el daemon. Arráncalo con <code className="rounded bg-black/30 px-1 font-mono text-xs">--web</code> y
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
