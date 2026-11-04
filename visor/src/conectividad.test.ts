import { describe, it, expect } from "vitest"
import { estadoEquipo, resumenConectividad, MODOS } from "./conectividad"
import type { EquipoConectividad } from "./api"

const eq = (x: Partial<EquipoConectividad>): EquipoConectividad =>
  ({ nombre: "fw", ip: "10.0.0.1", protegido: false, puerto: 22, usuario: "triaje", ajustado: false, huella_fijada: "SHA256:A", ultima_prueba: null, ...x }) as EquipoConectividad
const prueba = (estado: string, ok = estado === "verificada") => ({ ok, estado, pasos: [] })

describe("estadoEquipo", () => {
  it("protegido, sin probar y sin aprovisionar según la huella", () => {
    expect(estadoEquipo(eq({ protegido: true })).id).toBe("protegido")
    expect(estadoEquipo(eq({})).id).toBe("sin_probar")
    expect(estadoEquipo(eq({ huella_fijada: null })).id).toBe("sin_aprovisionar")
  })
  it("la última prueba manda", () => {
    expect(estadoEquipo(eq({ ultima_prueba: prueba("verificada") })).tono).toBe("ok")
    expect(estadoEquipo(eq({ ultima_prueba: prueba("host_cambiada") }))).toMatchObject({ id: "host_cambiada", tono: "critico", texto: "bloqueada" })
    expect(estadoEquipo(eq({ ultima_prueba: prueba("privilegio_de_mas") })).tono).toBe("aviso")
    expect(estadoEquipo(eq({ ultima_prueba: prueba("sin_acceso") })).tono).toBe("critico")
  })
})

describe("resumenConectividad", () => {
  it("cuenta contenibles (sin protegidos), verificadas, clave cambiada y sin aprovisionar", () => {
    expect(resumenConectividad([
      eq({ ultima_prueba: prueba("verificada") }), eq({ ultima_prueba: prueba("host_cambiada") }),
      eq({ huella_fijada: null }), eq({ ultima_prueba: prueba("sin_aprovisionar") }), eq({ protegido: true }), eq({}),
    ])).toEqual({ contenibles: 5, verificadas: 1, hostCambiada: 1, sinAprovisionar: 2, sinProbar: 1 })
  })
  it("nombra los modos del conector", () => {
    expect(MODOS.map((m) => m.id)).toEqual(["clave", "directo", "password"])
  })
})
