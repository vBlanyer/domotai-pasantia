import { describe, it, expect } from "vitest"
import { clasificar, edadMuestraMs, MUESTRA_VIEJA_MS } from "./salud"

// Escenario del mockup: ocho servicios, db-core caída, web-banking y api-movil dependen de ella.
const S = [
  { nombre: "api-movil", estado: "ok", depende_de: ["db-core"] },
  { nombre: "db-core", estado: "caido", depende_de: [] },
  { nombre: "dns-interno", estado: "ok", depende_de: [] },
  { nombre: "fw-core", estado: "ok", depende_de: [] },
  { nombre: "ldap", estado: "ok", depende_de: ["dns-interno"] },
  { nombre: "smb-files", estado: "ok", depende_de: ["ldap"] },
  { nombre: "ssh-bastion", estado: "ok", depende_de: ["ldap"] },
  { nombre: "web-banking", estado: "ok", depende_de: ["db-core", "ldap"] },
]

describe("clasificar: caídos, degradados y operativos, en ese orden", () => {
  const filas = clasificar(S)
  const por = Object.fromEntries(filas.map((f) => [f.nombre, f]))

  it("ordena caídos primero, luego los que dependen de un caído, luego operativos (alfabético dentro)", () => {
    expect(filas.map((f) => f.nombre)).toEqual(
      ["db-core", "api-movil", "web-banking", "dns-interno", "fw-core", "ldap", "smb-files", "ssh-bastion"])
    expect(filas.map((f) => f.estado)).toEqual(["caido", "degradado", "degradado", "ok", "ok", "ok", "ok", "ok"])
  })
  it("el caído dice a quién afecta", () => {
    expect(por["db-core"].afecta).toEqual(["api-movil", "web-banking"])
  })
  it("el degradado nombra la causa aunque su sonda responda", () => {
    expect(por["web-banking"].causas).toEqual(["db-core"])
    expect(por["api-movil"].causas).toEqual(["db-core"])
  })
  it("el operativo sabe a quién sostiene y de quién depende", () => {
    expect(por["ldap"].sostiene).toEqual(["smb-files", "ssh-bastion", "web-banking"])
    expect(por["smb-files"].sostiene).toEqual([])
    expect(por["smb-files"].depende_de).toEqual(["ldap"])
    expect(por["fw-core"].sostiene).toEqual([])
  })
  it("la cascada es transitiva: a → b → c caído deja a a degradado por c", () => {
    const f = clasificar([
      { nombre: "a", estado: "ok", depende_de: ["b"] },
      { nombre: "b", estado: "ok", depende_de: ["c"] },
      { nombre: "c", estado: "caido", depende_de: [] },
    ])
    const por2 = Object.fromEntries(f.map((x) => [x.nombre, x]))
    expect(por2.a.estado).toBe("degradado"); expect(por2.a.causas).toEqual(["c"])
    expect(por2.c.afecta).toEqual(["a", "b"])
  })
  it("una dependencia que no está en la lista se ignora, y un ciclo no cuelga", () => {
    const f = clasificar([
      { nombre: "x", estado: "ok", depende_de: ["fantasma", "y"] },
      { nombre: "y", estado: "caido", depende_de: ["x"] },
    ])
    const por3 = Object.fromEntries(f.map((r) => [r.nombre, r]))
    expect(por3.x.estado).toBe("degradado"); expect(por3.x.causas).toEqual(["y"])
    expect(por3.y.afecta).toEqual(["x"])
  })
  it("sin caídos, todo operativo y nada afectado", () => {
    expect(clasificar(S.map((s) => ({ ...s, estado: "ok" }))).every((f) => f.estado === "ok")).toBe(true)
  })
})

describe("edadMuestraMs: cuánto hace de la muestra del monitor (contra la hora del daemon)", () => {
  const ahora = Date.parse("2026-11-03T15:41:13Z")
  it("muestra con hora: diferencia en ms", () => {
    expect(edadMuestraMs("2026-11-03T15:41:07Z", ahora)).toBe(6000)
  })
  it("nunca negativa (reloj del monitor adelantado)", () => {
    expect(edadMuestraMs("2026-11-03T15:41:20Z", ahora)).toBe(0)
  })
  it("sin hora o con hora inválida: null", () => {
    expect(edadMuestraMs(null, ahora)).toBeNull()
    expect(edadMuestraMs("ayer", ahora)).toBeNull()
  })
  it("el umbral de muestra vieja es un minuto", () => {
    expect(MUESTRA_VIEJA_MS).toBe(60_000)
  })
})
