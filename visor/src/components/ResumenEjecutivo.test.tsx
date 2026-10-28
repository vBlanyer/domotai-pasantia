import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import type { Metricas as Datos } from "@/api"

const h = vi.hoisted(() => ({ m: null as unknown }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  getMetricas: async () => h.m,   // el resumen ejecutivo siempre consulta por periodo
}))
vi.mock("./charts", () => ({ Donut: () => null, Barras: () => null }))
vi.mock("./MatrizAttack", () => ({ MatrizAttack: () => null }))
import { ResumenEjecutivo } from "./ResumenEjecutivo"

const base: Datos = {
  total: 342, fp: 7, tasa_fp: 0.021, auto: 243, pct_auto: 0.71, suprimidas: 124,
  escalado_humano: 99, pct_humano: 0.29, resueltos_humano: 99, override: 8, tasa_override: 0.023,
  mttr_seg: 48, por_clase: { vp_intento_acceso: 168 }, veredictos: { aprobar: 10 },
  por_dia: [{ dia: "2026-10-14", n: 31 }], top_activos: [{ nombre: "web-banking", n: 98 }],
  mitre: [{ tecnica: "T1110.001", n: 161 }], mttr_mediano_seg: 32, sla_umbral_seg: 900,
  sla_resueltos: 99, sla_dentro: 95, sla_incumplidos: 4, sla_pct: 0.96,
}

describe("ResumenEjecutivo", () => {
  it("muestra los titulares, las secciones por familia/ubicación y exporta a PDF", async () => {
    h.m = { ...base, por_familia: [{ familia: "acceso_credenciales", n: 120 }], por_pais: [{ pais: "Estados Unidos", n: 80 }] }
    render(<ResumenEjecutivo />)
    expect(await screen.findByText("Amenazas tratadas")).toBeInTheDocument()
    expect(screen.getByText("Contenidas en automático")).toBeInTheDocument()
    expect(screen.getByText("Amenazas por familia")).toBeInTheDocument()
    expect(screen.getByText("Orígenes por ubicación")).toBeInTheDocument()
    const print = vi.spyOn(window, "print").mockImplementation(() => {})
    fireEvent.click(screen.getByRole("button", { name: /Guardar PDF/i }))
    expect(print).toHaveBeenCalled()
    print.mockRestore()
  })
})
