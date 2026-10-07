import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"

const h = vi.hoisted(() => ({ val: undefined as unknown }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: () => h.val,
}))
import { Contenciones } from "./Contenciones"

describe("Contenciones activas", () => {
  beforeEach(() => { h.val = undefined })

  it("sin datos aún muestra «cargando»", () => {
    render(<Contenciones />)
    expect(screen.getByText(/cargando/i)).toBeInTheDocument()
  })

  it("lista las contenciones activas de la traza (IP, cuenta o servicio)", () => {
    h.val = [
      { id_decision: "s1", objetivo: "198.51.100.10", ip: "198.51.100.10", activo: "api-movil", nodo: "api-movil", accion_id: "BLOQUEAR_IP", ts: "2026-10-07T10:00:00Z", via_escalada: false },
      { id_decision: "s4", objetivo: "203.0.113.9", ip: "203.0.113.9", activo: "core-db", nodo: "fw-core", accion_id: "BLOQUEAR_IP_FIREWALL", ts: "2026-10-07T11:00:00Z", via_escalada: true },
      { id_decision: "s7", objetivo: "backdoor", usuario: "backdoor", ip: null, activo: "web-banking", nodo: "web-banking", accion_id: "FORZAR_CAMBIO_PASS", ts: "2026-10-07T12:00:00Z" },
    ]
    render(<Contenciones />)
    expect(screen.getByText("3 contenciones activas")).toBeInTheDocument()
    expect(screen.getByText("198.51.100.10")).toBeInTheDocument()
    expect(screen.getByText("backdoor")).toBeInTheDocument()                 // cuenta bloqueada, no IP
    expect(screen.getByText("FORZAR_CAMBIO_PASS")).toBeInTheDocument()
    expect(screen.getByText(/fw-core \(escalada\)/)).toBeInTheDocument()
  })

  it("sin contenciones avisa de que no hay nada bloqueado", () => {
    h.val = []
    render(<Contenciones />)
    expect(screen.getByText(/No hay contenciones activas/)).toBeInTheDocument()
  })

  it("si no hay conexión lo dice", () => {
    h.val = { error: "TypeError: fetch failed" }
    render(<Contenciones />)
    expect(screen.getByText(/Sin conexión/)).toBeInTheDocument()
  })
})
