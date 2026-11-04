import { describe, it, expect } from "vitest"
import { SLA_MS, ordenarCola, grupoDe, agrupar, saludCola, siguienteTras, historialOrigen, resueltasHoyPor, efectoAprobar } from "./aprobaciones"
import type { Decision, Pendiente } from "./api"

const AHORA = Date.parse("2026-11-04T12:00:00Z")
const hace = (min: number) => new Date(AHORA - min * 60_000).toISOString()
const pend = (x: Partial<Pendiente>): Pendiente =>
  ({ id: "1", tipo: "menu", prompt: "", lineas: [], severidad: 2, paso: 0, ...x }) as Pendiente
const enr = (alcance: string, pais?: string) => ({ alcance, inventariado: false, clasificacion_ip: "publica",
  tercero_confiable: false, legitimo: false, geolocalizable: !!pais, geo: pais ? { pais } : null })

describe("ordenarCola: fuera de SLA, luego gravedad, luego antigüedad", () => {
  it("ordena por urgencia sin mutar la entrada", () => {
    const xs = [
      pend({ id: "a", severidad: 4, encolado_en: hace(2) }),
      pend({ id: "b", severidad: 2, encolado_en: hace(20) }),   // fuera de SLA (15 min)
      pend({ id: "c", severidad: 4, encolado_en: hace(9) }),
      pend({ id: "d", severidad: 3, encolado_en: hace(1) }),
    ]
    expect(ordenarCola(xs, AHORA).map((p) => p.id)).toEqual(["b", "c", "a", "d"])
    expect(xs.map((p) => p.id)).toEqual(["a", "b", "c", "d"])
    expect(SLA_MS).toBe(15 * 60_000)
  })
})

describe("grupoDe y agrupar: por campaña /24", () => {
  it("externo por /24 con país; interno junto; sin origen aparte", () => {
    expect(grupoDe(pend({ origen_ip: "203.0.113.7", enriquecimiento_origen: enr("externo", "Rusia") as never })))
      .toEqual({ clave: "inc:203.0.113", etiqueta: "203.0.113.0/24 · Rusia" })
    expect(grupoDe(pend({ origen_ip: "10.0.40.12", enriquecimiento_origen: enr("interno") as never })))
      .toEqual({ clave: "interna", etiqueta: "Red interna" })
    expect(grupoDe(pend({}))).toEqual({ clave: "sin-origen", etiqueta: "Sin origen" })
  })
  it("conserva el orden de urgencia: el grupo va donde está su miembro más urgente", () => {
    const xs = [pend({ id: "1", origen_ip: "203.0.113.7" }), pend({ id: "2", origen_ip: "198.51.100.2" }), pend({ id: "3", origen_ip: "203.0.113.88" })]
    const g = agrupar(xs)
    expect(g.map((x) => x.clave)).toEqual(["inc:203.0.113", "inc:198.51.100"])
    expect(g[0].items.map((p) => p.id)).toEqual(["1", "3"])
  })
})

describe("saludCola", () => {
  it("cuenta cola, entradas de la última hora, fuera de SLA, la más antigua y críticas con cascada", () => {
    const CASC = "Consecuencia: bloquea a 10.0.0.5 · en cascada: api-movil"
    const s = saludCola([
      pend({ id: "a", severidad: 4, encolado_en: hace(42), lineas: [CASC] }),
      pend({ id: "b", severidad: 4, encolado_en: hace(5) }),
      pend({ id: "c", severidad: 2, encolado_en: hace(90) }),
    ], AHORA)
    expect(s).toEqual({ total: 3, ultimaHora: 2, fueraSla: 2, masAntiguaMs: 90 * 60_000, criticas: 2, criticasConCascada: 1 })
  })
  it("cola vacía", () => {
    expect(saludCola([], AHORA)).toEqual({ total: 0, ultimaHora: 0, fueraSla: 0, masAntiguaMs: 0, criticas: 0, criticasConCascada: 0 })
  })
})

describe("siguienteTras: a dónde salta el inspector tras decidir", () => {
  it("la siguiente no resuelta; al final, la anterior; sin nada, null", () => {
    expect(siguienteTras(["a", "b", "c"], "a", new Set(["a"]))).toBe("b")
    expect(siguienteTras(["a", "b", "c"], "a", new Set(["a", "b"]))).toBe("c")
    expect(siguienteTras(["a", "b", "c"], "c", new Set(["c"]))).toBe("b")
    expect(siguienteTras(["a"], "a", new Set(["a"]))).toBeNull()
  })
})

const dec = (x: Partial<Decision>): Decision => x as Decision
describe("historialOrigen y resueltasHoyPor", () => {
  const T = [
    dec({ timestamp: "2026-10-31T09:00:00Z", origen_ip: "203.0.113.7", activo: "web-banking", clase: "vp_fuerza_bruta", accion_final: "BLOQUEAR_IP", contencion: "contenida" }),
    dec({ timestamp: "2026-11-02T10:00:00Z", origen_ip: "203.0.113.7", activo: "api-movil", clase: "vp_fuerza_bruta", accion_final: "BLOQUEAR_IP", requiere_humano: true, veredicto_humano: "aprobar", veredicto_por: "Blanyer", contencion: "contenida" }),
    dec({ timestamp: "2026-11-04T08:00:00Z", origen_ip: "203.0.113.7", tipo: "actividad_suprimida", alertas_suprimidas: 3 }),
    dec({ timestamp: "2026-11-04T09:00:00Z", origen_ip: "8.8.8.8", veredicto_humano: "rechazar", veredicto_por: "Blanyer" }),
    dec({ origen_ip: "203.0.113.7" }),   // sin hora (p. ej. una pendiente): no es historia
  ]
  it("lo que ya pasó con el origen, lo más reciente primero, sin registros de sistema", () => {
    const h = historialOrigen(T, "203.0.113.7")
    expect(h.map((x) => x.quien)).toEqual(["aprobó Blanyer", "automática"])
    expect(h[0].texto).toMatch(/api-movil/)
    expect(h[0].desenlace).toBe("contenida")
    expect(historialOrigen(T, null)).toEqual([])
  })
  it("cuántas resolvió hoy el operador", () => {
    expect(resueltasHoyPor(T, "Blanyer", "2026-11-04")).toBe(1)
    expect(resueltasHoyPor(T, "", "2026-11-04")).toBe(0)
  })
  it("cuenta por el día de la decisión del analista, no por el de la alerta", () => {
    const ayerResueltaHoy = dec({ timestamp: "2026-11-03T23:50:00Z", decidido_en: "2026-11-04T00:05:00Z", veredicto_humano: "aprobar", veredicto_por: "ana" })
    const hoyResueltaAyer = dec({ timestamp: "2026-11-04T00:01:00Z", decidido_en: "2026-11-03T23:59:00Z", veredicto_humano: "aprobar", veredicto_por: "ana" })
    expect(resueltasHoyPor([ayerResueltaHoy, hoyResueltaAyer], "ana", "2026-11-04")).toBe(1)
  })
  it("el historial del origen dice cuándo no hay nombre", () => {
    const h = historialOrigen([dec({ timestamp: "2026-11-04T10:00:00Z", origen_ip: "10.0.0.9", veredicto_humano: "aprobar" })], "10.0.0.9")
    expect(h[0].quien).toBe("aprobó · sin nombre registrado")
  })
})

describe("efectoAprobar: qué pasa si apruebas, en una frase", () => {
  it("acción con cascada, vetada y escalada", () => {
    const e = efectoAprobar(pend({ accion_final: "BLOQUEAR_IP", origen_ip: "1.2.3.4",
      lineas: ["Consecuencia: bloquea a 1.2.3.4 en fw-core · en cascada: api-movil"] }))
    expect(e.titulo).toBe("Se ejecuta BLOQUEAR_IP contra 1.2.3.4")
    expect(e.detalle).toBe("bloquea a 1.2.3.4 en fw-core · en cascada: api-movil")
    expect(e.cascada).toEqual(["api-movil"])
    expect(e.ejecuta).toBe(true)
    const v = efectoAprobar(pend({ accion_final: null, lineas: ["Consecuencia: (vetada) bloquea · en cascada: x"] }))
    expect(v.ejecuta).toBe(false); expect(v.cascada).toEqual([])
    expect(efectoAprobar(pend({ tipo: "escalada", accion_final: "AISLAR_NODO" })).titulo).toMatch(/escalada/i)
  })
})

import { ordenarPor, agruparPor, ORDENES, AGRUPACIONES } from "./aprobaciones"

describe("ordenarPor: el criterio lo elige el analista", () => {
  const xs = [
    pend({ id: "a", severidad: 4, encolado_en: hace(2) }),
    pend({ id: "b", severidad: 2, encolado_en: hace(20) }),
    pend({ id: "c", severidad: 3, encolado_en: hace(9) }),
  ]
  it("por tiempo: recientes primero (por defecto) o antiguas primero", () => {
    expect(ORDENES[0].id).toBe("reciente")
    expect(ordenarPor(xs, "reciente", AHORA).map((p) => p.id)).toEqual(["a", "c", "b"])
    expect(ordenarPor(xs, "antigua", AHORA).map((p) => p.id)).toEqual(["b", "c", "a"])
  })
  it("por gravedad y por urgencia (fuera de SLA primero)", () => {
    expect(ordenarPor(xs, "gravedad", AHORA).map((p) => p.id)).toEqual(["a", "c", "b"])
    expect(ordenarPor(xs, "urgencia", AHORA).map((p) => p.id)).toEqual(["b", "a", "c"])
  })
})

describe("agruparPor: sin agrupar por defecto, o por país, campaña, activo, familia o gravedad", () => {
  const xs = [
    pend({ id: "1", origen_ip: "203.0.113.7", activo: "web", clase: "vp_fuerza_bruta", severidad: 4, enriquecimiento_origen: enr("externo", "Rusia") as never }),
    pend({ id: "2", origen_ip: "198.51.100.2", activo: "api", clase: "vp_exfiltracion", severidad: 2, enriquecimiento_origen: enr("externo", "China") as never }),
    pend({ id: "3", origen_ip: "203.0.113.88", activo: "web", severidad: 4, enriquecimiento_origen: enr("externo", "Rusia") as never }),
  ]
  it("sin agrupar = un solo grupo sin cabecera, en el orden recibido", () => {
    expect(AGRUPACIONES[0].id).toBe("ninguno")
    const g = agruparPor(xs, "ninguno")
    expect(g).toHaveLength(1); expect(g[0].cabecera).toBe(false)
    expect(g[0].items.map((p) => p.id)).toEqual(["1", "2", "3"])
  })
  it("por país, por activo, por familia y por gravedad conservan el orden dentro de cada grupo", () => {
    expect(agruparPor(xs, "pais").map((g) => [g.etiqueta, g.items.map((p) => p.id)])).toEqual([["Rusia", ["1", "3"]], ["China", ["2"]]])
    expect(agruparPor(xs, "activo").map((g) => g.etiqueta)).toEqual(["web", "api"])
    expect(agruparPor(xs, "clase").map((g) => g.items.length)).toEqual([1, 1, 1])
    expect(agruparPor(xs, "clase")[2].etiqueta).toBe("Sin clase")
    expect(agruparPor(xs, "gravedad").map((g) => g.etiqueta)).toEqual(["P4 · crítica", "P2 · media"])
    expect(agruparPor(xs, "campana")[0].etiqueta).toBe("203.0.113.0/24 · Rusia")
  })
})
