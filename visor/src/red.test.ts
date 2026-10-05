import { describe, it, expect } from "vitest"
import { disposicion, DIM } from "./red"
import type { Red } from "./api"

const nodo = (nombre: string, tipo = "servidor", zona: string | null = null) => ({
  nombre, tipo, zona, actividad: { objetivo: 0, origen: 0, contuvo_aqui: 0, pendientes: 0, estado: "sin_actividad" },
})
const BANCO: Red = {
  nodos: [nodo("internet", "externo"), nodo("fw-edge", "cortafuegos"), nodo("fw-core", "cortafuegos"),
          nodo("web-banking", "servidor", "DMZ"), nodo("api-movil", "servidor", "DMZ"),
          nodo("core-db", "servidor", "Core"), nodo("mdr-siem", "gestion", "SOC")],
  enlaces: [["fw-edge", "internet"], ["fw-core", "fw-edge"], ["web-banking", "fw-core"], ["api-movil", "fw-core"],
            ["core-db", "fw-core"], ["mdr-siem", "fw-core"]],
  dependencias: [], zonas: [{ nombre: "DMZ", nodos: ["web-banking", "api-movil"] },
                            { nombre: "Core", nodos: ["core-db"] }, { nombre: "SOC", nodos: ["mdr-siem"] }],
}

describe("disposicion", () => {
  it("coloca la cadena desde internet de arriba abajo, centrada", () => {
    const d = disposicion(BANCO)
    expect(d.nodos["internet"].y).toBeLessThan(d.nodos["fw-edge"].y)
    expect(d.nodos["fw-edge"].y).toBeLessThan(d.nodos["fw-core"].y)
    expect(d.nodos["fw-core"].x).toBe(d.ancho / 2)
  })
  it("las zonas van bajo la cadena, en el orden declarado, y sus nodos en columna", () => {
    const d = disposicion(BANCO)
    expect(d.zonas.map((z) => z.nombre)).toEqual(["DMZ", "Core", "SOC"])
    expect(d.zonas[0].x).toBeLessThan(d.zonas[1].x)
    expect(d.zonas[0].y).toBeGreaterThan(d.nodos["fw-core"].y)
    expect(d.nodos["web-banking"].x).toBe(d.nodos["api-movil"].x)
    expect(d.nodos["api-movil"].y).toBeGreaterThan(d.nodos["web-banking"].y)
    expect(d.alto).toBeGreaterThan(d.zonas[0].y + d.zonas[0].h)
  })
  it("es determinista", () => {
    expect(disposicion(BANCO)).toEqual(disposicion(BANCO))
  })
  it("con más de 4 zonas pasa a una segunda fila", () => {
    const zonas = ["A", "B", "C", "D", "E"].map((z) => ({ nombre: z, nodos: [`n${z}`] }))
    const red: Red = { nodos: zonas.map((z) => nodo(z.nodos[0], "servidor", z.nombre)), enlaces: [], dependencias: [], zonas }
    const d = disposicion(red)
    expect(d.zonas[4].y).toBeGreaterThan(d.zonas[0].y)
    expect(d.nodos["nE"].y).toBeGreaterThan(d.nodos["nA"].y + DIM.nodoAlto)
  })
  it("una red vacía no rompe", () => {
    const d = disposicion({ nodos: [], enlaces: [], dependencias: [], zonas: [] })
    expect(d.ancho).toBeGreaterThan(0)
  })
})
