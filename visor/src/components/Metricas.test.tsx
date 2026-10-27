import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import type { Metricas as Datos } from "@/api"

// Modo en vivo: getMetricas() sin periodo. Modo periodo: getMetricas({desde,hasta}).
const h = vi.hoisted(() => ({ vivo: null as unknown, periodo: null as unknown }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  getMetricas: async (p?: { desde?: string; hasta?: string }) => (p ? h.periodo : h.vivo),
}))
vi.mock("./charts", () => ({ Donut: () => null, Tendencia: () => null, Barras: () => null }))
vi.mock("./MatrizAttack", () => ({ MatrizAttack: () => null }))
import { Metricas } from "./Metricas"

const base: Datos = {
  total: 342, fp: 7, tasa_fp: 0.021, auto: 243, pct_auto: 0.71, suprimidas: 124,
  escalado_humano: 99, pct_humano: 0.29, resueltos_humano: 99, override: 8, tasa_override: 0.023,
  mttr_seg: 48, por_clase: { vp_intento_acceso: 168, no_soportada: 72 },
  veredictos: { aprobar: 10, rechazar: 2 }, por_dia: [{ dia: "2026-10-14", n: 31 }],
  top_activos: [{ nombre: "web-banking", n: 98 }], mitre: [{ tecnica: "T1110.001", n: 161 }],
  mttr_mediano_seg: 32, sla_umbral_seg: 900, sla_resueltos: 99, sla_dentro: 95, sla_incumplidos: 4, sla_pct: 0.96,
}

describe("Métricas (vista unificada métricas + informe)", () => {
  beforeEach(() => { h.vivo = null; h.periodo = null })

  it("por defecto mide en vivo, con el donut de veredictos y el botón de PDF", async () => {
    h.vivo = { ...base }                                                    // en vivo: sin desde/hasta
    render(<Metricas />)
    expect(await screen.findByText("En vivo · sesión actual")).toBeInTheDocument()   // etiqueta del modo vivo
    expect(screen.getByText("Veredictos humanos")).toBeInTheDocument()      // donut exclusivo de Métricas
    expect(screen.getByRole("button", { name: "En vivo" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Guardar PDF/ })).toBeInTheDocument()
  })

  it("muestra los tiempos de respuesta y el SLA", async () => {
    h.vivo = { ...base }
    render(<Metricas />)
    expect(await screen.findByText("MTTR mediano")).toBeInTheDocument()
    expect(screen.getByText(/dentro de SLA \(15 min\)/)).toBeInTheDocument()
    expect(screen.getByText("SLA incumplidos")).toBeInTheDocument()
  })

  it("al elegir «Este mes» consulta el periodo y muestra su etiqueta", async () => {
    h.vivo = { ...base }
    h.periodo = { ...base, desde: "2026-10-01", hasta: "2026-10-31" }
    render(<Metricas />)
    await screen.findByText("En vivo · sesión actual")
    fireEvent.click(screen.getByRole("button", { name: "Este mes" }))
    expect(await screen.findByText("octubre de 2026")).toBeInTheDocument()
    expect(screen.getByText("342 decisiones en el periodo")).toBeInTheDocument()
  })

  it("el botón Guardar PDF llama a window.print", () => {
    h.vivo = { ...base }
    const print = vi.spyOn(window, "print").mockImplementation(() => {})
    render(<Metricas />)
    fireEvent.click(screen.getByRole("button", { name: /Guardar PDF/ }))
    expect(print).toHaveBeenCalled()
  })
})
