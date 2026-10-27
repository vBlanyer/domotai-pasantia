import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

const h = vi.hoisted(() => ({ trazas: [] as unknown[] }))
vi.mock("@/api", async (orig) => ({ ...(await orig<typeof import("@/api")>()), useSondeo: () => h.trazas }))
import { PerfilAtacante } from "./PerfilAtacante"

describe("PerfilAtacante", () => {
  it("muestra los equipos que atacó y pivota a sus decisiones", () => {
    h.trazas = [
      { indice: 1, origen_ip: "198.51.100.10", prioridad: 4, timestamp: "2026-10-27T10:00:00", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { alcance: "externo", clasificacion_ip: "documentacion", inventariado: false, tercero_confiable: false, legitimo: false, geolocalizable: false, geo: null } },
      { indice: 2, origen_ip: "198.51.100.10", prioridad: 2, timestamp: "2026-10-27T12:00:00", relaciones: { "core-db": ["objetivo"] } },
    ]
    const onVerDecisiones = vi.fn()
    render(<PerfilAtacante ip="198.51.100.10" onVolver={() => {}} onVerDecisiones={onVerDecisiones} />)
    expect(screen.getByText("198.51.100.10")).toBeInTheDocument()
    expect(screen.getByText("web-banking")).toBeInTheDocument()
    expect(screen.getByText("core-db")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Ver sus decisiones/i }))
    expect(onVerDecisiones).toHaveBeenCalledWith("198.51.100.10")
  })
})

describe("PerfilAtacante — riesgo", () => {
  it("muestra la insignia de riesgo del atacante", () => {
    h.trazas = [
      { indice: 1, origen_ip: "198.51.100.10", prioridad: 4, timestamp: "2026-10-27T10:00:00", relaciones: { "web-banking": ["objetivo"] } },
      { indice: 2, origen_ip: "198.51.100.10", prioridad: 4, timestamp: "2026-10-27T11:00:00", relaciones: { "core-db": ["objetivo"] } },
    ]
    render(<PerfilAtacante ip="198.51.100.10" onVolver={() => {}} onVerDecisiones={() => {}} />)
    expect(screen.getByText(/Riesgo:/)).toBeInTheDocument()
  })
})
