import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

const h = vi.hoisted(() => ({ trazas: [] as unknown[] }))
vi.mock("@/api", async (orig) => ({ ...(await orig<typeof import("@/api")>()), useSondeo: () => h.trazas }))
import { Campanas } from "./Campanas"

describe("Campañas", () => {
  it("agrupa los ataques por bloque de origen y a qué equipos pegó; el bloque pivota", () => {
    h.trazas = [
      { indice: 1, origen_ip: "198.51.100.10", prioridad: 4, timestamp: "t2", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { alcance: "externo" } },
      { indice: 2, origen_ip: "198.51.100.11", prioridad: 3, timestamp: "t1", relaciones: { "core-db": ["objetivo"] } },
      { indice: 3, origen_ip: "198.51.100.10", prioridad: 2, timestamp: "t3", relaciones: { "web-banking": ["objetivo"] } },
    ]
    const onVerOrigen = vi.fn()
    render(<Campanas onVerOrigen={onVerOrigen} />)
    expect(screen.getByText("198.51.100.0/24")).toBeInTheDocument()
    expect(screen.getByText(/2 IPs/)).toBeInTheDocument()
    expect(screen.getByText("×3")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "198.51.100.0/24" }))
    expect(onVerOrigen).toHaveBeenCalledWith("198.51.100.")
  })

  it("sin ataques lo dice", () => {
    h.trazas = []
    render(<Campanas onVerOrigen={() => {}} />)
    expect(screen.getByText(/Sin campañas/i)).toBeInTheDocument()
  })
})
