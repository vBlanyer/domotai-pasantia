import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { LineaTiempo } from "./LineaTiempo"
import type { Decision } from "@/api"

describe("LineaTiempo", () => {
  it("pinta los eventos con su acción y los hitos de respuesta", () => {
    const regs = [
      { indice: 1, timestamp: "2026-10-28T10:00:00", clase: "vp_intento_acceso", prioridad: 3,
        origen_ip: "8.8.8.8", activo: "web-banking", accion_final: "BLOQUEAR_IP" },
      { indice: 2, tipo: "reversion", nodo: "fw-core", accion_id: "BLOQUEAR_IP", operador: "ana",
        decidido_en: "2026-10-28T10:15:00" },
    ] as unknown as Decision[]
    render(<LineaTiempo regs={regs} />)
    expect(screen.getByText("BLOQUEAR_IP")).toBeInTheDocument()
    expect(screen.getByText(/8\.8\.8\.8 → web-banking/)).toBeInTheDocument()
    expect(screen.getByText(/reversión de contención en fw-core/)).toBeInTheDocument()
  })

  it("vacío lo dice", () => {
    render(<LineaTiempo regs={[]} />)
    expect(screen.getByText(/Sin eventos/)).toBeInTheDocument()
  })
})
