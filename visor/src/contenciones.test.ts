import { describe, it, expect } from "vitest"
import { UMBRAL_VIEJA_MS, enriquecer, resumenContenciones, ordenarContenciones, agruparContenciones, serieIntentos } from "./contenciones"
import type { Contencion, Decision } from "./api"

const AHORA = Date.parse("2026-11-04T12:00:00Z")
const hace = (h: number) => new Date(AHORA - h * 3600_000).toISOString()
const c = (x: Partial<Contencion>): Contencion => ({ id_decision: "d", indice: 1, objetivo: "203.0.113.7", ip: "203.0.113.7",
  activo: "web-banking", nodo: "fw-core", accion_id: "BLOQUEAR_IP", ts: hace(2), ...x }) as Contencion
const t = (x: Partial<Decision>): Decision => x as Decision
const TRAZAS = [
  t({ indice: 1, id_decision: "d", clase: "vp_fuerza_bruta", confianza: 0.97, origen_ip: "203.0.113.7", timestamp: hace(2.5),
      enriquecimiento_origen: { alcance: "externo", geo: { pais: "Rusia" } } as never }),
  t({ indice: 2, origen_ip: "203.0.113.7", timestamp: hace(1), tipo: "actividad_suprimida", alertas_suprimidas: 13 }),
  t({ indice: 3, origen_ip: "203.0.113.7", timestamp: hace(0.2), clase: "vp_fuerza_bruta" }),
  t({ indice: 4, origen_ip: "203.0.113.7", timestamp: hace(3) }),                                    // antes del bloqueo
  t({ indice: 5, id_decision: "h", requiere_humano: true, veredicto_humano: "aprobar", veredicto_por: "Blanyer", clase: "vp_exfiltracion" }),
]

describe("enriquecer: lo que la vista cuenta de cada contención", () => {
  it("cruza con la traza: país, clase, quién decidió, dónde y cuántos intentos paró después", () => {
    const [e] = enriquecer([c({})], TRAZAS, AHORA)
    expect(e).toMatchObject({ pais: "Rusia", clase: "vp_fuerza_bruta", confianza: 0.97, decidio: "automática", enBorde: true,
      intentos: 14, edadMs: 2 * 3600_000, vieja: false })
    expect(e.ultimoIntento).toBe(hace(0.2))
  })
  it("decidió un humano, vía escalada, en el propio equipo, vieja y sin datos en la ventana", () => {
    const [h, esc, eq, vieja] = enriquecer([
      c({ id_decision: "h", indice: 5 }), c({ id_decision: "x", indice: 99, via_escalada: true }),
      c({ nodo: "web-banking" }), c({ indice: 98, id_decision: "z", ts: new Date(AHORA - UMBRAL_VIEJA_MS - 1).toISOString() }),
    ], TRAZAS, AHORA)
    expect(h.decidio).toBe("aprobó Blanyer")
    expect(esc.decidio).toBe("vía escalada")
    expect(eq.enBorde).toBe(false)
    expect(vieja.vieja).toBe(true)
    expect(esc.clase).toBeNull()
  })
  it("un bloqueo de destino (exfiltración) no cuenta intentos de origen", () => {
    expect(enriquecer([c({ accion_id: "BLOQUEAR_DESTINO" })], TRAZAS, AHORA)[0].intentos).toBeNull()
  })
})

describe("resumen, orden y agrupación", () => {
  const es = enriquecer([
    c({ indice: 1, id_decision: "d" }),
    c({ indice: 7, id_decision: "e", ip: "198.51.100.2", objetivo: "198.51.100.2", accion_id: "BLOQUEAR_DESTINO", activo: "api-movil", ts: hace(30) }),
    c({ indice: 8, id_decision: "f", ip: null, objetivo: "backdoor", accion_id: "FORZAR_CAMBIO_PASS", nodo: "web-banking", ts: hace(24 * 9) }),
  ], TRAZAS, AHORA)
  it("resumen", () => {
    expect(resumenContenciones(es, AHORA)).toEqual({
      activas: 3, hoy: 1, enBorde: 2, enEquipos: 1, masAntigua: { edadMs: 24 * 9 * 3600_000, activo: "web-banking" },
      insisten: 1, viejas: 1, porAccion: [["BLOQUEAR_DESTINO", 1], ["BLOQUEAR_IP", 1], ["FORZAR_CAMBIO_PASS", 1]],
    })
  })
  it("ordenar: recientes, antiguas o más intentos", () => {
    expect(ordenarContenciones(es, "reciente").map((e) => e.c.indice)).toEqual([1, 7, 8])
    expect(ordenarContenciones(es, "antigua").map((e) => e.c.indice)).toEqual([8, 7, 1])
    expect(ordenarContenciones(es, "intentos")[0].c.indice).toBe(1)
  })
  it("agrupar por dónde se aplica (por defecto), por acción, por equipo protegido o sin agrupar", () => {
    expect(agruparContenciones(es, "donde").map((g) => g.etiqueta)).toEqual(["fw-core · contiene para otros equipos", "web-banking · en el propio equipo"])
    expect(agruparContenciones(es, "accion").map((g) => g.items.length)).toEqual([1, 1, 1])
    expect(agruparContenciones(es, "activo").map((g) => g.etiqueta)).toEqual(["protege web-banking", "protege api-movil"])
    expect(agruparContenciones(es, "ninguno")[0].cabecera).toBe(false)
  })
})

describe("serieIntentos: intentos por hora antes y después del bloqueo", () => {
  it("cuenta por horas, marca las de después y suma las supresiones", () => {
    const s = serieIntentos(TRAZAS, "203.0.113.7", hace(2), AHORA)
    expect(s.filter((b) => !b.despues).reduce((a, b) => a + b.n, 0)).toBe(2)    // indices 1 y 4
    expect(s.filter((b) => b.despues).reduce((a, b) => a + b.n, 0)).toBe(14)
  })
})
