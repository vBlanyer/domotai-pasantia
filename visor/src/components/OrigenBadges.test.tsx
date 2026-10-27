import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { OrigenBadges } from "./OrigenBadges"
import type { Decision } from "@/api"

type Enr = NonNullable<Decision["enriquecimiento_origen"]>
const base: Enr = { alcance: "externo", inventariado: false, clasificacion_ip: "documentacion",
  tercero_confiable: false, legitimo: false, geolocalizable: false, geo: null }

describe("OrigenBadges", () => {
  it("un externo de documentación: alcance, clase de IP y «sin geolocalización»", () => {
    render(<OrigenBadges e={base} />)
    expect(screen.getByText("externo")).toBeInTheDocument()
    expect(screen.getByText(/IP de documentación/)).toBeInTheDocument()
    expect(screen.getByText(/sin geolocalización/)).toBeInTheDocument()
  })

  it("una IP pública sin base GeoIP lo dice", () => {
    render(<OrigenBadges e={{ ...base, clasificacion_ip: "publica", geolocalizable: true }} />)
    expect(screen.getByText(/sin base GeoIP/)).toBeInTheDocument()
  })

  it("marca tercero de confianza y origen legítimo", () => {
    render(<OrigenBadges e={{ ...base, tercero_confiable: true, legitimo: true }} />)
    expect(screen.getByText(/tercero de confianza/)).toBeInTheDocument()
    expect(screen.getByText(/origen legítimo/)).toBeInTheDocument()
  })

  it("sin enriquecimiento no renderiza nada", () => {
    const { container } = render(<OrigenBadges e={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
