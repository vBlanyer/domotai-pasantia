import { useState } from "react"
import { Moon, Sun } from "lucide-react"
import { useSondeo, getSalud, getPendientes, getPausa } from "@/api"
import { useTema } from "@/tema"
import { Dashboard } from "@/components/Dashboard"
import { Metricas } from "@/components/Metricas"
import { Salud } from "@/components/Salud"
import { Red } from "@/components/Red"
import { Decisiones } from "@/components/Decisiones"
import { Aprobaciones } from "@/components/Aprobaciones"
import { Trazas } from "@/components/Trazas"
import { Contenciones } from "@/components/Contenciones"
import { VistaIncidente } from "@/components/VistaIncidente"
import { Punto } from "@/components/bits"
import type { Decision } from "@/api"

type Vista = "panel" | "metricas" | "salud" | "red" | "decisiones" | "aprobaciones" | "trazas" | "contenciones" | "incidente"

const NAV: { id: Vista; nombre: string }[] = [
  { id: "panel", nombre: "Panel" },
  { id: "metricas", nombre: "Métricas e informe" },
  { id: "salud", nombre: "Estado de servicios" },
  { id: "red", nombre: "Red" },
  { id: "decisiones", nombre: "Decisiones" },
  { id: "aprobaciones", nombre: "Aprobaciones" },
  { id: "contenciones", nombre: "Contenciones activas" },
  { id: "trazas", nombre: "Trazas" },
]

export default function App() {
  const [vista, setVista] = useState<Vista>("panel")
  const [equipo, setEquipo] = useState<string | null>(null)
  const [incidente, setIncidente] = useState<Decision | null>(null)
  const { oscuro, alternar } = useTema()
  const salud = useSondeo(getSalud)
  const pend = useSondeo(getPendientes)
  const pausa = useSondeo(getPausa)
  const pausada = !!(pausa && !("error" in pausa) && pausa.pausada)
  const conectado = salud !== undefined && !("error" in salud)
  const nPend = Array.isArray(pend) ? pend.length : 0
  const titulo = vista === "incidente" ? "Incidente" : NAV.find((n) => n.id === vista)!.nombre

  return (
    <div className="flex min-h-screen bg-[#f7f7f5] text-foreground dark:bg-[#0d0d0d]">
      <aside className="flex w-56 shrink-0 flex-col bg-[#0f1e33] text-slate-300 print:hidden">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="grid size-8 place-items-center rounded-md bg-cyan-500/20 text-sm font-bold text-cyan-300">M</div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-white">MDR</div>
            <div className="text-[11px] text-slate-400">consola de triaje</div>
          </div>
        </div>
        <nav className="mt-2 flex-1 px-3">
          {NAV.map((n) => (
            <button
              key={n.id}
              onClick={() => setVista(n.id)}
              className={`mb-1 flex w-full items-center justify-between rounded-md px-3 py-2 text-sm transition-colors ${
                vista === n.id ? "bg-white/10 font-medium text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"
              }`}
            >
              <span>{n.nombre}</span>
              {n.id === "aprobaciones" && nPend > 0 && (
                <span className="rounded bg-amber-400 px-1.5 text-xs font-semibold text-[#0f1e33]">{nPend}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="flex items-center gap-2 px-5 py-4 text-xs">
          <Punto estado={conectado ? "ok" : "caido"} />
          <span className={conectado ? "text-emerald-400" : "text-rose-400"}>{conectado ? "en vivo" : "sin conexión"}</span>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-card px-8 py-4 print:hidden">
          <h1 className="font-heading text-lg font-semibold">{titulo}</h1>
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-2">
              <Punto estado={conectado ? "ok" : "caido"} />
              <span className="text-muted-foreground">{conectado ? "datos en vivo" : "sin conexión con el daemon"}</span>
            </span>
            <button
              onClick={alternar}
              aria-label={oscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
              title={oscuro ? "Tema claro" : "Tema oscuro"}
              className="grid size-9 place-items-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {oscuro ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-auto px-8 py-6 print:overflow-visible print:p-0">
          {pausada && (
            <div className="mb-4 flex items-center gap-2 rounded-md border border-rose-500/50 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-700 dark:text-rose-300 print:hidden">
              ⏸ Automatización en pausa — toda contención automática espera aprobación humana.
              {vista !== "contenciones" && (
                <button onClick={() => setVista("contenciones")} className="ml-auto underline underline-offset-2">Gestionar</button>
              )}
            </div>
          )}
          {vista === "panel" && <Dashboard conectado={conectado} />}
          {vista === "metricas" && <Metricas />}
          {vista === "salud" && <Salud />}
          {vista === "red" && <Red onVerDecisiones={(n) => { setEquipo(n); setVista("decisiones") }} />}
          {vista === "decisiones" && (
            <Decisiones equipo={equipo} onQuitarEquipo={() => setEquipo(null)}
              onVerIncidente={(d) => { setIncidente(d); setVista("incidente") }} />
          )}
          {vista === "aprobaciones" && <Aprobaciones />}
          {vista === "trazas" && <Trazas />}
          {vista === "contenciones" && <Contenciones />}
          {vista === "incidente" && incidente && (
            <VistaIncidente decision={incidente} onVolver={() => setVista("decisiones")} />
          )}
        </main>
      </div>
    </div>
  )
}
