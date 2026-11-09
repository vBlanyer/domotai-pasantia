import type { ButtonHTMLAttributes, ReactNode } from "react"
import { Lock } from "lucide-react"
import type { PruebaConexion } from "@/api"
import { cn } from "@/lib/utils"

// Piezas compartidas de la vista Conectividad, el asistente de alta y la rotación de la clave.

export function Boton({ children, tono = "normal", ...p }: { children: ReactNode; tono?: "pri" | "dan" | "normal" } & ButtonHTMLAttributes<HTMLButtonElement>) {
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

// Una acción que esta sesión no puede hacer: candado y el motivo al lado, en vez de un botón gris mudo.
export function Bloqueado({ accion, motivo }: { accion: string; motivo: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11.5px] text-muted-foreground" title={motivo}>
      <Lock className="size-3" aria-hidden />{accion} · {motivo}
    </span>
  )
}

export function Seccion({ titulo, extra, children }: { titulo: string; extra?: ReactNode; children: ReactNode }) {
  return (
    <div className="border-b border-border px-4 py-3 last:border-b-0">
      <h4 className="mb-2 flex items-center justify-between gap-2 text-[11px] font-medium text-muted-foreground"><span>{titulo}</span>{extra}</h4>
      {children}
    </div>
  )
}

export function Pasos({ p }: { p: PruebaConexion }) {
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

// Lo que sobra y lo que falta en el sudoers del equipo frente a su papel.
export function Deriva({ sobran, faltan }: { sobran: string[]; faltan: string[] }) {
  if (!sobran.length && !faltan.length) return null
  return (
    <div className="overflow-hidden rounded-md border border-border font-mono text-[11.5px]">
      {sobran.map((r) => <div key={`+${r}`} className="flex justify-between gap-3 bg-critico/10 px-2.5 py-1 text-critico"><span>+ {r}</span><span className="font-sans">sobra</span></div>)}
      {faltan.map((r) => <div key={`-${r}`} className="flex justify-between gap-3 bg-aviso/10 px-2.5 py-1 text-aviso"><span>− {r}</span><span className="font-sans">falta</span></div>)}
    </div>
  )
}

export function Capa({ titulo, onCerrar, children, ancho = "max-w-4xl" }: { titulo: string; onCerrar: () => void; children: ReactNode; ancho?: string }) {
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-[#0d1117]/55 p-4 backdrop-blur-[2px]" role="dialog" aria-modal aria-label={titulo}
      onKeyDown={(e) => { if (e.key === "Escape") onCerrar() }}>
      <div className={cn("mx-auto my-6 overflow-hidden rounded-xl border border-border bg-card shadow-2xl", ancho)}>
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <h2 className="text-base font-semibold">{titulo}</h2>
          <button type="button" onClick={onCerrar} className="text-sm text-muted-foreground hover:text-foreground">Cerrar</button>
        </div>
        {children}
      </div>
    </div>
  )
}
