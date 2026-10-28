import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

const h = vi.hoisted(() => ({ trazas: [] as unknown[] }))
vi.mock("@/api", async (orig) => ({ ...(await orig<typeof import("@/api")>()), useSondeo: () => h.trazas }))
import { Incidentes } from "./Incidentes"

describe("Incidentes", () => {
  it("lista campañas /24 como incidentes con su estado de caso y pivota al pulsar", () => {
    h.trazas = [
      { indice: 1, origen_ip: "203.0.113.9", prioridad: 4, timestamp: "2026-10-28T10:00:00",
        relaciones: { "web-banking": ["objetivo"] }, clase: "vp_intento_acceso" },
      { indice: 2, origen_ip: "203.0.113.20", prioridad: 3, timestamp: "2026-10-28T10:05:00",
        relaciones: { "core-db": ["objetivo"] }, clase: "vp_intento_acceso" },
      { indice: 3, tipo: "actualizacion_caso", id_decision: "inc:203.0.113", estado: "en_revision",
        decidido_en: "2026-10-28T10:10:00" },
    ]
    const onVerIncidente = vi.fn()
    render(<Incidentes onVerIncidente={onVerIncidente} />)
    expect(screen.getByText("203.0.113.0/24")).toBeInTheDocument()   // las IPs rotadas = un incidente
    expect(screen.getByText("En revisión")).toBeInTheDocument()       // estado del caso de incidente plegado
    fireEvent.click(screen.getByText("203.0.113.0/24"))
    expect(onVerIncidente).toHaveBeenCalledWith("inc:203.0.113", "203.0.113.0/24")
  })

  it("sin ataques agrupables lo dice", () => {
    h.trazas = []
    render(<Incidentes onVerIncidente={() => {}} />)
    expect(screen.getByText(/Sin incidentes/)).toBeInTheDocument()
  })
})
