import { describe, it, expect, vi, afterEach } from "vitest"
import { render, fireEvent } from "@testing-library/react"
import { useRef } from "react"
import { alturaMaxima, useAjusteInspectores, MARGEN } from "@/ajusteInspector"

// El panel derecho acaba SIEMPRE en el borde de abajo del área visible: empiece donde empiece (debajo de
// las cifras y los filtros, o ya pegado arriba tras bajar), su final se ve sin bajar la página.
describe("alturaMaxima", () => {
  it("lo que queda visible desde donde empieza el panel", () => {
    // área visible de 100 a 900; el panel empieza en 400 (debajo de cifras y filtros)
    expect(alturaMaxima(400, { top: 100, bottom: 900 })).toBe(900 - 400 - MARGEN)
  })
  it("ya pegado arriba (sticky), toda el área menos los márgenes", () => {
    expect(alturaMaxima(50, { top: 100, bottom: 900 })).toBe(900 - (100 + MARGEN) - MARGEN)
  })
  it("nunca menos de un mínimo usable", () => {
    expect(alturaMaxima(890, { top: 100, bottom: 900 })).toBe(160)
  })
})

describe("useAjusteInspectores", () => {
  afterEach(() => vi.restoreAllMocks())

  function Vista() {
    const ref = useRef<HTMLElement>(null)
    useAjusteInspectores(ref)
    return <main ref={ref} data-testid="main"><section className="inspector" data-testid="panel">x</section></main>
  }

  it("fija la altura del panel y la recalcula al hacer scroll", () => {
    let topPanel = 400
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      return (this.dataset.testid === "main" ? { top: 100, bottom: 900 } : { top: topPanel, bottom: topPanel + 2000 }) as DOMRect
    })
    const { getByTestId } = render(<Vista />)
    const panel = getByTestId("panel")
    expect(panel.style.maxHeight).toBe(`${900 - 400 - MARGEN}px`)
    topPanel = 150                                                  // la página bajó: el panel subió
    fireEvent.scroll(getByTestId("main"))
    expect(panel.style.maxHeight).toBe(`${900 - 150 - MARGEN}px`)
  })
})
