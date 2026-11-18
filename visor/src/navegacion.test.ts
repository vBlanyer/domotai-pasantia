import { describe, it, expect } from "vitest"
import { vistaDeHash, hashDeVista, vistaVisible } from "@/navegacion"

// La vista activa vive en la URL (#/politicas): sobrevive a recargar y el navegador puede ir atrás.
describe("navegación por la URL", () => {
  it("lee la vista del hash", () => {
    expect(vistaDeHash("#/politicas")).toBe("politicas")
    expect(vistaDeHash("#/aprobaciones")).toBe("aprobaciones")
  })

  it("sin hash, o con uno que no es una vista, abre el panel", () => {
    expect(vistaDeHash("")).toBe("panel")
    expect(vistaDeHash("#/no-existe")).toBe("panel")
    expect(vistaDeHash("#politicas")).toBe("panel")
  })

  it("escribe el hash de la vista", () => {
    expect(hashDeVista("contenciones")).toBe("#/contenciones")
    expect(vistaDeHash(hashDeVista("trazas"))).toBe("trazas")
  })

  it("una vista de detalle sin sus datos (tras recargar) vuelve a la vista de la que sale", () => {
    expect(vistaVisible("atacante", { atacante: false, incidente: false })).toBe("red")
    expect(vistaVisible("incidente", { atacante: false, incidente: false })).toBe("decisiones")
    expect(vistaVisible("atacante", { atacante: true, incidente: false })).toBe("atacante")
    expect(vistaVisible("politicas", { atacante: false, incidente: false })).toBe("politicas")
  })
})
