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

import { periodoAnterior, nombreArchivo, enPeriodo, resumenRedactado, recomendaciones } from "./informe"

describe("informe en PDF: periodo anterior, nombre del archivo y textos", () => {
  it("el periodo anterior de un mes completo es el mes anterior; de un rango, otro igual justo antes", () => {
    expect(periodoAnterior("2026-10-01", "2026-10-31")).toEqual({ desde: "2026-09-01", hasta: "2026-09-30" })
    expect(periodoAnterior("2026-01-01", "2026-01-31")).toEqual({ desde: "2025-12-01", hasta: "2025-12-31" })
    expect(periodoAnterior("2026-10-11", "2026-10-20")).toEqual({ desde: "2026-10-01", hasta: "2026-10-10" })
  })
  it("el nombre del archivo nombra el periodo", () => {
    expect(nombreArchivo("2026-10-01", "2026-10-31")).toBe("Informe-MDR-2026-10")
    expect(nombreArchivo("2026-01-01", "2026-12-31")).toBe("Informe-MDR-2026")
    expect(nombreArchivo("2026-10-11", "2026-10-20")).toBe("Informe-MDR-2026-10-11_a_2026-10-20")
  })
  it("enPeriodo compara por día y tolera horas con zona", () => {
    expect(enPeriodo("2026-10-31T23:59:00Z", "2026-10-01", "2026-10-31")).toBe(true)
    expect(enPeriodo("2026-11-01T00:00:00Z", "2026-10-01", "2026-10-31")).toBe(false)
    expect(enPeriodo(null, "2026-10-01", "2026-10-31")).toBe(false)
  })
  it("el resumen se redacta con las cifras del periodo", () => {
    const t = resumenRedactado({ total: 1284, pct_auto: 0.7, pct_humano: 0.3, tasa_override: 0.012, tasa_fp: 0.009, mttr_mediano_seg: 42 } as never, "octubre de 2026")
    expect(t).toMatch(/En octubre de 2026 el servicio trató 1\s?284 amenazas/)
    expect(t).toMatch(/70 %/); expect(t).toMatch(/0,9 %/); expect(t).toMatch(/42 s/)
  })
  it("recomendaciones solo con lo que los datos justifican", () => {
    const r = recomendaciones({ total: 10, sla_incumplidos: 3, tasa_fp: 0.2, top_activos: [{ nombre: "web-banking", n: 9 }] } as never, 2, 1)
    expect(r.some((x) => /SLA/.test(x))).toBe(true)
    expect(r.some((x) => /falsos positivos/.test(x))).toBe(true)
    expect(r.some((x) => /2 contenciones fallaron/.test(x))).toBe(true)
    expect(r.some((x) => /web-banking/.test(x))).toBe(true)
    expect(recomendaciones({ total: 0, top_activos: [] } as never, 0, 0)).toEqual([])
  })
})

describe("recomendaciones en singular", () => {
  it("una sola contención fallida o un solo incidente abierto se dicen en singular", () => {
    const r = recomendaciones({ total: 10, tasa_fp: 0, sla_incumplidos: 1, top_activos: [] } as never, 1, 1)
    expect(r).toEqual([
      "Revisar el caso que superó el SLA de respuesta humana y su causa.",
      "Una contención falló: comprobar la conectividad del conector con ese equipo.",
      "Queda un incidente abierto al cierre del periodo: asignarle responsable.",
    ])
  })
})
