import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { MapaRed } from "./MapaRed"
import type { Red } from "@/api"

const act = (estado: string) => ({ objetivo: 1, origen: 0, contuvo_aqui: 0, pendientes: 0, estado })
const RED: Red = {
  nodos: [{ nombre: "fw-core", tipo: "cortafuegos", zona: null, actividad: act("contenido") },
          { nombre: "web-banking", tipo: "servidor", zona: "DMZ", actividad: act("atacado") },
          { nombre: "taquilla", tipo: "puesto", zona: "Sucursal", actividad: act("pendiente") },
          { nombre: "core-db", tipo: "servidor", zona: "DMZ", actividad: act("caido") },
          { nombre: "atm", tipo: "puesto", zona: "Sucursal", actividad: act("sin_actividad") }],
  enlaces: [["web-banking", "fw-core"], ["taquilla", "fw-core"]], dependencias: [["web-banking", "core-db"]],
  zonas: [{ nombre: "DMZ", nodos: ["web-banking", "core-db"] }, { nombre: "Sucursal", nodos: ["taquilla", "atm"] }],
}

describe("MapaRed", () => {
  it("cada estado se anuncia con texto, no solo con color", () => {
    render(<MapaRed red={RED} seleccionado={null} onSeleccionar={() => {}} dependencias />)
    expect(screen.getByRole("button", { name: "web-banking, atacado" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "taquilla, espera tu decisión" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "fw-core, contenido" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "core-db, caído" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "atm, sin actividad" })).toBeInTheDocument()
    expect(screen.getByText("DMZ")).toBeInTheDocument()
  })
  it("se selecciona con clic y con Enter o Espacio", () => {
    const sel = vi.fn()
    render(<MapaRed red={RED} seleccionado={null} onSeleccionar={sel} dependencias />)
    fireEvent.click(screen.getByRole("button", { name: /web-banking/ }))
    fireEvent.keyDown(screen.getByRole("button", { name: /taquilla/ }), { key: "Enter" })
    fireEvent.keyDown(screen.getByRole("button", { name: /atm/ }), { key: " " })
    expect(sel.mock.calls.map((c) => c[0])).toEqual(["web-banking", "taquilla", "atm"])
  })
  it("marca el seleccionado y puede ocultar las dependencias", () => {
    const { container, rerender } = render(<MapaRed red={RED} seleccionado="web-banking" onSeleccionar={() => {}} dependencias />)
    expect(screen.getByRole("button", { name: /web-banking/ })).toHaveAttribute("aria-pressed", "true")
    expect(container.querySelectorAll("[data-dependencia]").length).toBe(1)
    rerender(<MapaRed red={RED} seleccionado={null} onSeleccionar={() => {}} dependencias={false} />)
    expect(container.querySelectorAll("[data-dependencia]").length).toBe(0)
  })
})
