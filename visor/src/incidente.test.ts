import { describe, it, expect } from "vitest"
import { estadosDelIncidente } from "./incidente"
import type { Decision, Detalle, Red } from "@/api"

const nodo = (nombre: string, ip: string | null) => ({
  nombre, ip, tipo: "host", zona: null, funcion: null, criticidad: null,
  servicios_prestados: [], depende_de: [], salud: null,
  actividad: { objetivo: 0, origen: 0, contuvo_aqui: 0, pendientes: 0, estado: "sin_actividad", ultima: null },
})
const RED: Red = {
  nodos: [nodo("web-banking", "10.10.0.10"), nodo("api-movil", "10.20.0.10"),
          nodo("core-db", "10.50.0.10"), nodo("middleware", "10.40.0.10"), nodo("fw-core", "10.0.0.1")],
  enlaces: [], dependencias: [], zonas: [],
}
const estado = (red: Red, nombre: string) => red.nodos.find((n) => n.nombre === nombre)!.actividad.estado
const dec = (d: Partial<Decision>): Decision => d as Decision

describe("estadosDelIncidente", () => {
  it("marca origen (por IP), activo atacado y cascada", () => {
    const r = estadosDelIncidente(
      dec({ activo: "core-db", origen_ip: "10.40.0.10", cascada: ["api-movil", "web-banking"] }),
      null, RED)
    expect(estado(r, "middleware")).toBe("origen")      // coincide por IP de origen
    expect(estado(r, "core-db")).toBe("atacado")
    expect(estado(r, "api-movil")).toBe("en_cascada")
    expect(estado(r, "web-banking")).toBe("en_cascada")
    expect(estado(r, "fw-core")).toBe("sin_actividad")
  })

  it("el activo retenido para humano sale como pendiente", () => {
    const r = estadosDelIncidente(dec({ activo: "core-db", requiere_humano: true }), null, RED)
    expect(estado(r, "core-db")).toBe("pendiente")
  })

  it("si se contuvo en el propio activo, sale contenido", () => {
    const det = { ejecucion: { exito: true } } as unknown as Detalle
    const r = estadosDelIncidente(dec({ activo: "core-db", veredicto_humano: "aprobar" }), det, RED)
    expect(estado(r, "core-db")).toBe("contenido")
  })

  it("si escaló, el dispositivo que contuvo sale contenido y el activo queda atacado", () => {
    const det = { escalada: { resultado: "mitigado", dispositivo_ejecutor: "fw-core" } } as unknown as Detalle
    const r = estadosDelIncidente(dec({ activo: "web-banking", origen_ip: "203.0.113.9" }), det, RED)
    expect(estado(r, "web-banking")).toBe("atacado")
    expect(estado(r, "fw-core")).toBe("contenido")
  })

  it("lee la cascada también del impacto determinado del detalle", () => {
    const det = { impacto_determinado: { activos_afectados_en_cascada: ["api-movil"] } } as unknown as Detalle
    const r = estadosDelIncidente(dec({ activo: "core-db" }), det, RED)
    expect(estado(r, "api-movil")).toBe("en_cascada")
  })
})
