import { describe, it, expect } from "vitest"
import { SaludSchema, PendienteSchema, controlesDePendiente, baseApi } from "./api"

describe("baseApi", () => {
  it("relativa en producción, 8787 en dev, override con VITE_API", () => {
    expect(baseApi({ DEV: false })).toBe("")
    expect(baseApi({ DEV: true })).toBe("http://127.0.0.1:8787")
    expect(baseApi({ VITE_API: "http://x", DEV: true })).toBe("http://x")
  })
})

describe("esquemas Zod", () => {
  it("acepta una salud válida", () => {
    const ok = SaludSchema.parse({ t: "x", servicios: [{ nombre: "a", estado: "ok", depende_de: [] }], caidos: 0, total: 1 })
    expect("total" in ok && ok.total).toBe(1)
  })
  it("acepta salud sin datos", () => {
    expect(SaludSchema.parse({ sin_datos: true })).toEqual({ sin_datos: true })
  })
  it("rechaza una salud malformada", () => {
    expect(() => SaludSchema.parse({ servicios: "no-es-lista" })).toThrow()
  })
  it("acepta una pendiente válida", () => {
    expect(PendienteSchema.parse({ id: "1", tipo: "menu", prompt: "x", lineas: [] }).id).toBe("1")
  })
})

describe("controlesDePendiente", () => {
  it("escalada ofrece aprobar='s' y rechazar=''", () => {
    const c = controlesDePendiente({ id: "1", tipo: "escalada", prompt: "[s/N]", lineas: [] })
    expect(c.map((x) => x.respuesta)).toEqual(["s", ""])
  })
  it("menú ofrece 1 y 2", () => {
    const c = controlesDePendiente({ id: "1", tipo: "menu", prompt: "Elige", lineas: [] })
    expect(c.map((x) => x.respuesta)).toEqual(["1", "2"])
  })
})
