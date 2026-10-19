import { describe, it, expect } from "vitest"
import { tituloConPendientes, nuevosPendientes, textoAviso, edadTexto, envejecido, msDesde } from "./alertas"
import type { Pendiente } from "./api"

const P = (id: string, extra: Partial<Pendiente> = {}): Pendiente =>
  ({ id, tipo: "decision", prompt: "", lineas: [], ...extra }) as Pendiente

describe("tituloConPendientes", () => {
  it("antepone el número cuando hay pendientes", () => {
    expect(tituloConPendientes(3, "MDR")).toBe("(3) MDR")
  })
  it("sin pendientes deja el título base", () => {
    expect(tituloConPendientes(0, "MDR")).toBe("MDR")
  })
})

describe("nuevosPendientes", () => {
  it("devuelve solo los que no estaban en la vuelta anterior", () => {
    const prev = ["1", "2"]
    const act = [P("2"), P("3"), P("4")]
    expect(nuevosPendientes(prev, act).map((p) => p.id)).toEqual(["3", "4"])
  })
  it("sin novedades, lista vacía (no re-notifica lo ya visto)", () => {
    expect(nuevosPendientes(["1", "2"], [P("1"), P("2")])).toEqual([])
  })
  it("primera vuelta: todos son nuevos", () => {
    expect(nuevosPendientes([], [P("1"), P("2")]).map((p) => p.id)).toEqual(["1", "2"])
  })
})

describe("textoAviso", () => {
  it("una sola: nombra activo y origen", () => {
    const a = textoAviso([P("1", { activo: "web-banking", origen_ip: "203.0.113.9" })])
    expect(a?.cuerpo).toContain("web-banking")
    expect(a?.cuerpo).toContain("203.0.113.9")
  })
  it("varias: cuenta cuántas esperan", () => {
    expect(textoAviso([P("1"), P("2"), P("3")])?.cuerpo).toContain("3")
  })
  it("ninguna: no hay aviso", () => {
    expect(textoAviso([])).toBeNull()
  })
})

describe("edadTexto", () => {
  it("segundos, minutos y horas", () => {
    expect(edadTexto(5_000)).toBe("hace unos segundos")
    expect(edadTexto(3 * 60_000)).toBe("hace 3 min")
    expect(edadTexto(2 * 3_600_000 + 10 * 60_000)).toBe("hace 2 h 10 min")
  })
  it("nunca negativo", () => {
    expect(edadTexto(-1000)).toBe("hace unos segundos")
  })
})

describe("envejecido", () => {
  it("marca envejecido al superar el umbral", () => {
    expect(envejecido(6 * 60_000, 5 * 60_000)).toBe(true)
    expect(envejecido(1 * 60_000, 5 * 60_000)).toBe(false)
  })
})

describe("msDesde", () => {
  it("calcula los ms desde una marca ISO", () => {
    const ahora = Date.parse("2026-10-19T12:05:00Z")
    expect(msDesde("2026-10-19T12:00:00Z", ahora)).toBe(5 * 60_000)
  })
  it("falta o no parsea -> 0 (daemon antiguo sin el campo)", () => {
    expect(msDesde(null, 1000)).toBe(0)
    expect(msDesde(undefined, 1000)).toBe(0)
    expect(msDesde("no-es-fecha", 1000)).toBe(0)
  })
  it("nunca negativo", () => {
    expect(msDesde("2026-10-19T12:10:00Z", Date.parse("2026-10-19T12:00:00Z"))).toBe(0)
  })
})
