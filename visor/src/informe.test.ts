import { describe, it, expect } from "vitest"
import { rangoDe, etiquetaPeriodo } from "./informe"

describe("rangoDe", () => {
  it("mes = del 1 al último día del mes de hoy (local, no UTC)", () => {
    expect(rangoDe("mes", new Date(2026, 1, 15))).toEqual({ desde: "2026-02-01", hasta: "2026-02-28" })  // feb 2026
    expect(rangoDe("mes", new Date(2026, 0, 1))).toEqual({ desde: "2026-01-01", hasta: "2026-01-31" })
  })
  it("año = del 1 ene al 31 dic del año de hoy", () => {
    expect(rangoDe("año", new Date(2026, 6, 20))).toEqual({ desde: "2026-01-01", hasta: "2026-12-31" })
  })
})

describe("etiquetaPeriodo", () => {
  it("reconoce un mes completo, un año y un rango suelto", () => {
    expect(etiquetaPeriodo("2026-10-01", "2026-10-31")).toBe("octubre de 2026")
    expect(etiquetaPeriodo("2026-01-01", "2026-12-31")).toBe("Año 2026")
    expect(etiquetaPeriodo("2026-10-03", "2026-10-09")).toBe("2026-10-03 a 2026-10-09")
    expect(etiquetaPeriodo(null, null)).toBe("Todo el histórico")
  })
})
