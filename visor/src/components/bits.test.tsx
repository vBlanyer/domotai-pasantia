import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { SinConexion, ClaseBadge, DatosCongelados, LineaCausa } from "./bits"

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

// Fase 2 del plan de fallos: lo que puede ser un ataque se marca en rojo; el resto, con lo que hay que hacer.
describe("LineaCausa", () => {
  it("posible ataque: marca roja y su propia acción, nunca de configuración", () => {
    render(<LineaCausa causa={{ clase: "F3", descripcion: "la clave del host cambió", accion: "posible suplantación del equipo: compruébalo por otro canal", posible_ataque: true, evidencia: "WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!" }} equipo="fw-core" />)
    expect(screen.getByText("posible ataque")).toBeInTheDocument()
    expect(screen.getByText(/fw-core: la clave del host cambió/)).toBeInTheDocument()
    expect(screen.getByText(/REMOTE HOST IDENTIFICATION/)).toBeInTheDocument()
    expect(screen.queryByText(/Conectividad|dalo de alta/)).not.toBeInTheDocument()
  })
  it("configuración: sin marca de ataque y con lo que hay que hacer", () => {
    render(<LineaCausa causa={{ clase: "F2", descripcion: "equipo sin aprovisionar", accion: "dalo de alta o fija su clave del host en Conectividad", posible_ataque: false }} equipo="atm" prefijo="intento en" />)
    expect(screen.queryByText("posible ataque")).not.toBeInTheDocument()
    expect(screen.getByText(/atm: equipo sin aprovisionar — dalo de alta/)).toBeInTheDocument()
  })
})
