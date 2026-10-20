import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { SinConexion, ClaseBadge, DatosCongelados } from "./bits"

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

// A2: «daemon caído», «token rechazado» y «respuesta inválida» son fallos distintos; decirle al
// analista que arranque el daemon cuando el problema es su token lo desorienta en el peor momento.
describe("SinConexion por causa", () => {
  it("auth: señala el token, no el daemon", () => {
    render(<SinConexion causa="auth" />)
    expect(screen.getByText(/token/i)).toBeInTheDocument()
    expect(screen.queryByText(/--web/)).not.toBeInTheDocument()
  })
  it("datos: señala la incompatibilidad visor/daemon", () => {
    render(<SinConexion causa="datos" />)
    expect(screen.getByText(/no entiende|versiones/i)).toBeInTheDocument()
  })
  it("sin causa: el mensaje clásico de daemon caído", () => {
    render(<SinConexion />)
    expect(screen.getByText(/Sin conexión con el daemon/)).toBeInTheDocument()
  })
})

// C2: al perder la conexión no se vacía la vista — se conservan los últimos datos con un aviso.
describe("DatosCongelados", () => {
  it("avisa de que son los últimos datos recibidos y de cuándo", () => {
    render(<DatosCongelados fallo={{ error: "x", causa: "red", desde: Date.parse("2026-10-20T10:00:00Z") }} />)
    expect(screen.getByText(/últimos datos/i)).toBeInTheDocument()
  })
})
