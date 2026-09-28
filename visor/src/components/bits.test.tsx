import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { SinConexion, ClaseBadge } from "./bits"

// Humo del arnés de componentes: monta React en jsdom y consulta el DOM.
describe("bits", () => {
  it("SinConexion avisa de que falta el daemon", () => {
    render(<SinConexion />)
    expect(screen.getByText(/Sin conexión con el daemon/)).toBeInTheDocument()
  })

  it("ClaseBadge sin clase pinta un guion", () => {
    render(<ClaseBadge clase={null} />)
    expect(screen.getByText("—")).toBeInTheDocument()
  })
})
