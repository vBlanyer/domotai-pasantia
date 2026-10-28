import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"

const h = vi.hoisted(() => ({ trazas: [] as unknown[] }))
vi.mock("@/api", async (orig) => ({ ...(await orig<typeof import("@/api")>()), useSondeo: () => h.trazas }))
import { Ubicaciones } from "./Ubicaciones"

describe("Ubicaciones", () => {
  it("pone los países en el mapa y los cubos (lab/interna) en la tabla", () => {
    h.trazas = [
      { indice: 1, origen_ip: "8.8.8.8", prioridad: 4, relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
      { indice: 2, origen_ip: "198.51.100.10", prioridad: 3, relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "documentacion", geo: null } },
    ]
    render(<Ubicaciones />)
    expect(screen.getAllByText(/Estados Unidos/).length).toBeGreaterThan(0)   // en el mapa y en la tabla
    expect(screen.getByText(/Laboratorio/)).toBeInTheDocument()
    expect(document.querySelector("svg circle")).toBeTruthy()      // un país en el mapa
  })

  it("sin geolocalizables lo dice (solo lab/internos)", () => {
    h.trazas = [{ indice: 1, origen_ip: "198.51.100.10", prioridad: 3, relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "documentacion", geo: null } }]
    render(<Ubicaciones />)
    expect(screen.getByText(/Sin orígenes geolocalizables/)).toBeInTheDocument()
  })
})
