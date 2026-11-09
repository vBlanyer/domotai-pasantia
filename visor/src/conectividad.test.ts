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

describe("alta pendiente, antigüedad de la prueba, reglas y franja", () => {
  const AHORA = Date.parse("2026-11-04T12:00:00Z")
  it("un alta pendiente no cuenta como contenible y una prueba de hace días avisa", async () => {
    const { estadoEquipo, resumenConectividad, reglasDe, franjaPermisos } = await import("./conectividad")
    expect(estadoEquipo(eq({ alta: "pendiente" }), AHORA).texto).toBe("alta pendiente")
    expect(resumenConectividad([eq({ alta: "pendiente" }), eq({})]).contenibles).toBe(1)
    const vieja = { ...prueba("verificada"), en: "2026-11-01T12:00:00Z" }
    expect(estadoEquipo(eq({ ultima_prueba: vieja }), AHORA)).toMatchObject({ id: "verificada_vieja", texto: "hace 3 días", tono: "aviso" })
    const reciente = { ...prueba("verificada"), en: "2026-11-04T10:00:00Z", por: "ana" }
    expect(estadoEquipo(eq({ ultima_prueba: reciente }), AHORA).sub).toBe("hace 2 h · ana")
    expect(reglasDe(eq({ ultima_prueba: { ...prueba("privilegio_de_mas"), reglas: { estado: "sobran", sobran: ["cat *"], faltan: [] } } })).tono).toBe("critico")
    expect(reglasDe(eq({ ultima_prueba: { ...prueba("verificada"), reglas: { estado: "faltan", sobran: [], faltan: ["a", "b"] } } })).sub).toBe("faltan 2")
    expect(franjaPermisos(true, null, "identificado", "ana").titulo).toBe("Firmas como ana, verificado por tu token.")
    expect(franjaPermisos(true, null, "abierta", "leo").texto).toContain("sin verificar (leo)")
    expect(franjaPermisos(false, "probar y cambiar exigen un operador identificado por su token", "compartido", "").titulo).toBe("Con el token compartido.")
    expect(franjaPermisos(false, "el conector está en modo laboratorio o sin configurar: probar y cambiar no aplicarían", "identificado", "ana").titulo).toBe("Solo lectura.")
  })
})
