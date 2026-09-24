import { describe, it, expect } from "vitest"
import { filtrarDecisiones, clasesDe } from "./datos"
import type { Decision } from "./api"

const D: Decision[] = [
  { id_decision: "s1", activo: "web-banking", origen_ip: "10.40.0.10", clase: "vp_intento_acceso", accion_final: "BLOQUEAR_IP" },
  { id_decision: "s2", activo: "core-db", origen_ip: "203.0.113.9", clase: "fp_actividad_legitima", accion_final: null },
  { id_decision: "s3", activo: "web-banking", origen_ip: "10.200.0.10", clase: "no_soportada" },
]

describe("filtrarDecisiones", () => {
  it("por texto busca en activo, IP, id, clase y acción", () => {
    expect(filtrarDecisiones(D, { texto: "core", clase: "" }).map((d) => d.id_decision)).toEqual(["s2"])
    expect(filtrarDecisiones(D, { texto: "10.40", clase: "" }).map((d) => d.id_decision)).toEqual(["s1"])
    expect(filtrarDecisiones(D, { texto: "bloquear", clase: "" }).map((d) => d.id_decision)).toEqual(["s1"])
  })
  it("por clase filtra exacto, y combina con el texto", () => {
    expect(filtrarDecisiones(D, { texto: "", clase: "no_soportada" }).map((d) => d.id_decision)).toEqual(["s3"])
    expect(filtrarDecisiones(D, { texto: "web", clase: "vp_intento_acceso" }).map((d) => d.id_decision)).toEqual(["s1"])
  })
  it("sin filtros devuelve todo", () => {
    expect(filtrarDecisiones(D, { texto: " ", clase: "" }).length).toBe(3)
  })
})

describe("clasesDe", () => {
  it("clases únicas y ordenadas", () => {
    expect(clasesDe(D)).toEqual(["fp_actividad_legitima", "no_soportada", "vp_intento_acceso"])
  })
})
