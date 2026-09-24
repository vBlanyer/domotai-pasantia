import { describe, it, expect } from "vitest"
import { SaludSchema, PendienteSchema, DecisionSchema, DetalleSchema, EquipoSchema, controlesDePendiente, baseApi } from "./api"

describe("DecisionSchema", () => {
  it("acepta tipo/alertas_suprimidas nulos (una decisión normal los trae null)", () => {
    const d = DecisionSchema.parse({ id_decision: "s1", clase: "vp_intento_acceso", tipo: null, alertas_suprimidas: null })
    expect(d.tipo).toBeNull()
  })
  it("acepta un resumen de actividad suprimida", () => {
    const d = DecisionSchema.parse({ tipo: "actividad_suprimida", alertas_suprimidas: 3 })
    expect(d.alertas_suprimidas).toBe(3)
  })
  it("conserva confianza, MITRE, justificador y RAG del resumen enriquecido", () => {
    const d = DecisionSchema.parse({
      id_decision: "s1", confianza: 1.0, version_justificador: "plantilla-0",
      tecnica_mitre: ["T1110.001"], con_rag: false, motivo: "bloquea a 1.2.3.4",
    })
    expect(d.confianza).toBe(1.0)
    expect(d.tecnica_mitre).toEqual(["T1110.001"])
    expect(d.version_justificador).toBe("plantilla-0")
    expect(d.con_rag).toBe(false)
  })
})

describe("DetalleSchema", () => {
  it("parsea el detalle completo (justificación, MITRE, pasajes RAG) y tolera campos extra", () => {
    const d = DetalleSchema.parse({
      id_decision: "s1", justificacion: "Alerta 5760 …", version_justificador: "plantilla-0",
      consulta_rag: "tecnica MITRE T1110", pasajes_usados: ["mitre-T1110"],
      pasajes: [{ id: "mitre-T1110", titulo: "T1110 Brute Force", texto: "fuerza bruta SSH" }],
      justificacion_estructurada: { evidencia: { regla: "5760" }, tecnica_mitre: ["T1110.001"] },
      impacto_determinado: { nivel: "localizado", motivo: "bloquea a 1.2.3.4" },
      campo_no_modelado: 123,
    })
    expect(d.justificacion).toContain("5760")
    expect(d.pasajes_usados?.[0]).toBe("mitre-T1110")
    expect(d.pasajes?.[0].titulo).toBe("T1110 Brute Force")
    expect(d.justificacion_estructurada?.tecnica_mitre).toEqual(["T1110.001"])
    expect(d.impacto_determinado?.motivo).toBe("bloquea a 1.2.3.4")
  })
})

describe("EquipoSchema", () => {
  it("parsea un equipo del inventario (categoría requerida, resto tolerante)", () => {
    const e = EquipoSchema.parse({
      nombre: "web-banking", ip: "10.10.0.10", funcion: "banca en linea", criticidad: "alta",
      categoria: "servidor", servicios_prestados: [443, 80], depende_de: ["middleware"], estado: "ok",
    })
    expect(e.categoria).toBe("servidor")
    expect(e.servicios_prestados).toEqual([443, 80])
  })
  it("acepta un cortafuegos sin estado (sin monitor de salud)", () => {
    const e = EquipoSchema.parse({ nombre: "fw-core", ip: "10.0.0.1", categoria: "cortafuegos", estado: null })
    expect(e.estado).toBeNull()
  })
})

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
