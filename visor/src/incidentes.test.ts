import { describe, it, expect } from "vitest"
import { incidentesDe, resumenIncidentes, pasaFiltroIncidente, ordenarIncidentes, historiaDe, ACTIVO_MS } from "./incidentes"
import type { Decision } from "./api"

const AHORA = Date.parse("2026-11-04T12:00:00Z")
const hace = (min: number) => new Date(AHORA - min * 60_000).toISOString()
const d = (x: Partial<Decision>): Decision => ({ relaciones: { [x.activo ?? "web-banking"]: ["objetivo"] }, ...x }) as Decision
const REGS: Decision[] = [
  d({ indice: 1, id_decision: "a", origen_ip: "203.0.113.7", activo: "web-banking", prioridad: 4, timestamp: hace(60 * 24 * 3), contencion: "contenida",
      enriquecimiento_origen: { alcance: "externo", geo: { pais: "Rusia" } } as never }),
  d({ indice: 2, id_decision: "b", origen_ip: "203.0.113.88", activo: "api-movil", prioridad: 3, timestamp: hace(9), contencion: "fallida" }),
  d({ indice: 3, id_decision: "c", origen_ip: "203.0.113.7", activo: "web-banking", prioridad: 4, timestamp: hace(20), requiere_humano: true,
      veredicto_humano: "aprobar", contencion: "contenida", resultado_filtro: "degrada" }),
  d({ indice: 4, id_decision: "e", origen_ip: "198.51.100.2", activo: "api-movil", prioridad: 2, timestamp: hace(300), contencion: "contenida" }),
  { indice: 5, tipo: "actualizacion_caso", id_decision: "inc:203.0.113", estado: "en_revision", asignado: "Blanyer", decidido_en: hace(100) } as Decision,
  { indice: 6, tipo: "actualizacion_caso", id_decision: "inc:198.51.100", estado: "resuelto", nota: "proveedor", operador: "Ana", decidido_en: hace(50) } as Decision,
]

describe("incidentesDe: cada campaña /24 con su caso y lo que pasó", () => {
  const [a, b] = incidentesDe(REGS, AHORA)
  it("junta las IPs del bloque, el caso plegado, el país y si sigue activo", () => {
    expect(a).toMatchObject({ clave: "inc:203.0.113", cidr: "203.0.113.0/24", ips: 2, n: 3, prioridad: 4, pais: "Rusia", activo: true,
      contenidas: 2, aprobadas: 1, frenadas: 1, caso: { estado: "en_revision", asignado: "Blanyer" } })
    expect(a.objetivos).toEqual([{ equipo: "web-banking", n: 2, contenidas: 2 }, { equipo: "api-movil", n: 1, contenidas: 0 }])
    expect(b).toMatchObject({ clave: "inc:198.51.100", activo: false, caso: { estado: "resuelto" } })
    expect(ACTIVO_MS).toBe(3600_000)
  })
  it("sin caso registrado, nuevo y sin asignar", () => {
    const [x] = incidentesDe([d({ origen_ip: "41.0.0.1", timestamp: hace(1) })], AHORA)
    expect(x.caso).toMatchObject({ estado: "nuevo", asignado: null })
  })
})

describe("resumen, filtros y orden", () => {
  const es = incidentesDe(REGS, AHORA)
  it("resumen de casos", () => {
    expect(resumenIncidentes(es, "Blanyer")).toEqual({ total: 2, abiertos: 1, sinAsignar: 0, activos: 1, nuevos: 0, enRevision: 1, mios: 1, resueltos: 1 })
  })
  it("abiertos por defecto; solo míos", () => {
    expect(es.filter((e) => pasaFiltroIncidente(e, "abiertos", "")).map((e) => e.cidr)).toEqual(["203.0.113.0/24"])
    expect(es.filter((e) => pasaFiltroIncidente(e, "resueltos", "")).length).toBe(1)
    expect(es.filter((e) => pasaFiltroIncidente(e, "todos", "Ana")).length).toBe(0)       // ninguno asignado a Ana
  })
  it("orden por actividad reciente, gravedad o antigüedad", () => {
    expect(ordenarIncidentes(es, "reciente").map((e) => e.cidr)).toEqual(["203.0.113.0/24", "198.51.100.0/24"])
    expect(ordenarIncidentes(es, "antiguo")[0].cidr).toBe("203.0.113.0/24")
    expect(ordenarIncidentes(es, "gravedad")[0].prioridad).toBe(4)
  })
})

describe("historiaDe: la historia del ataque en una frase", () => {
  it("cuenta IPs, equipos, duración, contención y si sigue activo", () => {
    const h = historiaDe(incidentesDe(REGS, AHORA)[0], AHORA)
    expect(h).toMatch(/2 IPs del mismo bloque atacaron 2 equipos durante 3 días/)
    expect(h).toMatch(/Se contuvieron 2 de 3/)
    expect(h).toMatch(/Sigue activo/)
  })
})
