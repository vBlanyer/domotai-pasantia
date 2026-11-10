import { describe, it, expect } from "vitest"
import { tipoDe, filtrarTipo, hashCorto, horaLocal, claveDia, etiquetaDia, describirSistema, marcaDe, pruebaDe, campanaDe } from "./trazas"
import type { Decision } from "./api"

const d = (x: Partial<Decision>): Decision => x as Decision
const auto = d({ id_decision: "a1", clase: "vp_fuerza_bruta", accion_final: "BLOQUEAR_IP" })
const hum = d({ id_decision: "h1", clase: "vp_exfiltracion", requiere_humano: true, veredicto_humano: "aprobar", veredicto_por: "Blanyer" })
const pend = d({ id_decision: "h2", clase: "vp_exfiltracion", requiere_humano: true })
const sup = d({ tipo: "actividad_suprimida", alertas_suprimidas: 14, origen_ip: "203.0.113.7", activo: "web-banking" })
const propia = d({ tipo: "actividad_propia", activo: "fw-core" })
const rev = d({ tipo: "reversion", id_decision_revertida: "s3", exito: true, nodo: "fw-core" })
const caso = d({ tipo: "actualizacion_caso", estado: "en_revision", asignado: "Ana", operador: "Blanyer" })
const err = d({ tipo: "error", error: "OSError: docker" })

describe("tipoDe: qué es cada registro de la traza", () => {
  it("decisión automática, decisión humana (resuelta o pendiente), sistema y error", () => {
    expect(tipoDe(auto)).toBe("decision")
    expect(tipoDe(hum)).toBe("humano")
    expect(tipoDe(pend)).toBe("humano")
    for (const s of [sup, propia, rev, caso]) expect(tipoDe(s)).toBe("sistema")
    expect(tipoDe(err)).toBe("error")
  })
})

describe("filtrarTipo: los chips Todo · Decisiones · Humano · Sistema", () => {
  const todos = [auto, hum, pend, sup, propia, rev, caso, err]
  it("todo no quita nada", () => expect(filtrarTipo(todos, "todo")).toEqual(todos))
  it("decisiones = automáticas + humanas", () => expect(filtrarTipo(todos, "decisiones")).toEqual([auto, hum, pend]))
  it("humano = solo las que pasaron o esperan a un analista", () => expect(filtrarTipo(todos, "humano")).toEqual([hum, pend]))
  it("sistema = supresiones, actividad propia, reversiones, casos y errores", () => expect(filtrarTipo(todos, "sistema")).toEqual([sup, propia, rev, caso, err]))
})

describe("hashCorto", () => {
  it("abrevia a 4…2, el génesis se nombra y sin hash es null", () => {
    expect(hashCorto("a3f90e77b1" + "0".repeat(54))).toBe("a3f9…00")
    expect(hashCorto("0".repeat(64))).toBe("génesis")
    expect(hashCorto(null)).toBeNull()
    expect(hashCorto(undefined)).toBeNull()
  })
})

describe("hora local y agrupación por día", () => {
  const ts = new Date(2026, 10, 3, 15, 41, 7).toISOString()   // 3 nov 2026 15:41:07 hora local
  it("horaLocal da HH:MM:SS local; lo que no se entiende se devuelve tal cual", () => {
    expect(horaLocal(ts)).toMatch(/^\d{1,2}:\d{2}:\d{2}/)
    expect(horaLocal("ayer")).toBe("ayer")
    expect(horaLocal(null)).toBe("—")
  })
  it("claveDia es la fecha local YYYY-MM-DD", () => {
    expect(claveDia(ts)).toBe("2026-11-03")
    expect(claveDia("nada")).toBe("")
  })
  it("etiquetaDia antepone Hoy / Ayer y nombra el día en español", () => {
    expect(etiquetaDia("2026-11-03", "2026-11-03")).toMatch(/^Hoy · .*noviembre/)
    expect(etiquetaDia("2026-11-02", "2026-11-03")).toMatch(/^Ayer · .*noviembre/)
    expect(etiquetaDia("2026-10-31", "2026-11-03")).toMatch(/octubre/)
    expect(etiquetaDia("2026-10-31", "2026-11-03")).not.toMatch(/Hoy|Ayer/)
  })
})

describe("describirSistema: los registros de sistema dicen qué pasó", () => {
  it("la auditoría de Conectividad dice qué se tocó y quién", () => {
    const r = { tipo: "auditoria_conectividad", dimension: "clave_host", clave: "fw-core", operador: "ana" } as never
    expect(describirSistema(r)).toEqual({ titulo: "Conectividad", detalle: "clave_host · fw-core · por ana" })
    expect(tipoDe(r)).toBe("sistema")
  })
  it("supresión, actividad propia, reversión, caso y error", () => {
    expect(describirSistema(sup)).toEqual({ titulo: "Ruido suprimido", detalle: "14 alertas más de 203.0.113.7 contra web-banking" })
    expect(describirSistema(propia)).toEqual({ titulo: "Actividad propia del MDR", detalle: "login de gestión en fw-core, no es amenaza" })
    expect(describirSistema(rev)).toEqual({ titulo: "Reversión de s3", detalle: "aplicada en fw-core" })
    expect(describirSistema(d({ tipo: "reversion", id_decision_revertida: "s9", exito: false }))).toEqual({ titulo: "Reversión de s9", detalle: "falló" })
    expect(describirSistema(caso)).toEqual({ titulo: "Caso actualizado", detalle: "en revisión · asignado a Ana · por Blanyer" })
    expect(describirSistema(err)).toEqual({ titulo: "Error al procesar", detalle: "OSError: docker" })
  })
})

describe("marcaDe: integridad por registro a partir de la verificación de la cadena", () => {
  it("sin verificación aún, nada; cadena íntegra, todo ok", () => {
    expect(marcaDe(5, null)).toBeNull()
    expect(marcaDe(5, { ok: true, roto: null })).toBe("ok")
  })
  it("rota en k: antes ok, en k roto, después «tras» (cuelga de un eslabón alterado)", () => {
    const c = { ok: false, roto: 1279 }
    expect(marcaDe(1278, c)).toBe("ok")
    expect(marcaDe(1279, c)).toBe("roto")
    expect(marcaDe(1280, c)).toBe("tras")
  })
})

describe("pruebaDe: las tres líneas de la prueba de la cadena, con la ventana que hay", () => {
  const ant = d({ indice: 1278, hash: "f".repeat(64) })
  const r = d({ indice: 1279, hash_previo: "f".repeat(64), hash: "1".repeat(64) })
  it("con el anterior en la ventana, dice si el enlace cuadra", () => {
    expect(pruebaDe(r, ant)).toEqual({ previo: "f".repeat(64), hashAnterior: "f".repeat(64), enlaza: true, guardado: "1".repeat(64) })
    expect(pruebaDe({ ...r, hash_previo: "e".repeat(64) }, ant).enlaza).toBe(false)
  })
  it("sin el anterior (fuera de la ventana o génesis), el enlace no se puede comprobar aquí", () => {
    expect(pruebaDe(r, undefined).enlaza).toBeNull()
    expect(pruebaDe(d({ indice: 0, hash_previo: "0".repeat(64), hash: "a".repeat(64) }), undefined).enlaza).toBe(true)   // génesis
  })
})

describe("campanaDe: el incidente (campaña /24) al que pertenece el origen", () => {
  it("de una IPv4 saca prefijo, clave de caso y cidr; sin IP o no IPv4, null", () => {
    expect(campanaDe("203.0.113.7")).toEqual({ prefijo: "203.0.113.", clave: "inc:203.0.113", cidr: "203.0.113.0/24" })
    expect(campanaDe(null)).toBeNull()
    expect(campanaDe("fe80::1")).toBeNull()
  })
})
