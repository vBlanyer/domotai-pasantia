import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import type { Metricas } from "@/api"

const h = vi.hoisted(() => ({ m: null as unknown }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  getMetricas: async () => h.m,
}))
import { Informe } from "./Informe"

const M: Metricas = {
  total: 342, fp: 7, tasa_fp: 0.021, auto: 243, pct_auto: 0.71, suprimidas: 124,
  escalado_humano: 99, pct_humano: 0.29, resueltos_humano: 99, override: 8, tasa_override: 0.023,
  mttr_seg: 48, por_clase: { vp_intento_acceso: 168, no_soportada: 72 }, veredictos: { aprobar: 10 },
  por_dia: [{ dia: "2026-10-14", n: 31 }], top_activos: [{ nombre: "web-banking", n: 98 }],
  mitre: [{ tecnica: "T1110.001", n: 161 }], desde: "2026-10-01", hasta: "2026-10-31",
}

describe("Informe", () => {
  it("muestra el informe del periodo con KPIs y el botón de PDF", async () => {
    h.m = M
    render(<Informe />)
    expect(await screen.findByText("octubre de 2026")).toBeInTheDocument()     // etiqueta del periodo
    expect(screen.getByText("342 decisiones en el periodo")).toBeInTheDocument()
    expect(screen.getAllByText("71%").length).toBeGreaterThan(0)                 // % automatizado (KPI + resumen)
    expect(screen.getByRole("button", { name: /Guardar PDF/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Este mes" })).toBeInTheDocument()
  })

  it("el botón Guardar PDF llama a window.print", async () => {
    h.m = M
    const print = vi.spyOn(window, "print").mockImplementation(() => {})
    render(<Informe />)
    await screen.findByText("octubre de 2026")
    fireEvent.click(screen.getByRole("button", { name: /Guardar PDF/ }))
    expect(print).toHaveBeenCalled()
  })
})
