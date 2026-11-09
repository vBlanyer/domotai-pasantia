import { describe, it, expect } from "vitest"
import type { Decision, Pendiente } from "@/api"
import {
  saludPlataforma, urgentes, conActividadDeCola, textoSla, colaResumen, incidentesSinResponsable, fallidasRecientes,
  actividadPorHora, llegadasUltimaHora, comparaConAyer, variacion, atacadoEn24h, ultimasDecisiones,
} from "./panel"
import type { IncidenteVista } from "@/incidentes"

const AHORA = Date.parse("2026-11-04T15:30:00Z")
const iso = (msAntes: number) => new Date(AHORA - msAntes).toISOString()
const MIN = 60_000, H = 3600_000
const dec = (x: Partial<Decision>): Decision => ({ tipo: "decision", ...x }) as Decision
const pend = (id: string, minAntes: number, severidad = 2): Pendiente =>
  ({ id, tipo: "aprobacion", prompt: "", lineas: [], severidad, encolado_en: iso(minAntes * MIN) }) as Pendiente

describe("salud de la plataforma en una línea", () => {
  const base = {
    conectado: true, servicios: { total: 7, caidos: 0, caidosNombres: [] }, ingestaSilencioS: 2,
    trazaOk: true, conector: { modo: "clave", problemas: 0, verificados: 3, contenibles: 5 },
  }
  it("todo bien: verde, con cuatro indicadores", () => {
    const s = saludPlataforma(base)
    expect(s.tono).toBe("ok"); expect(s.titulo).toBe("Plataforma operativa")
    expect(s.indicadores.map((i) => `${i.nombre} ${i.valor}`)).toEqual(["Servicios 7/7", "Ingesta hace 2 s", "Traza íntegra", "Conector 3/5 verificados"])
  })
  it("un conector sin configurar es un aviso, no un fallo", () => {
    const s = saludPlataforma({ ...base, conector: { ...base.conector, modo: "sin_configurar" } })
    expect(s.tono).toBe("aviso"); expect(s.titulo).toBe("Plataforma operativa, con avisos")
  })
  it("servicios caídos o traza rota: rojo con el motivo", () => {
    const s = saludPlataforma({ ...base, servicios: { total: 7, caidos: 2, caidosNombres: ["wazuh-manager", "conector"] }, trazaOk: false })
    expect(s.tono).toBe("critico")
    expect(s.titulo).toBe("Fallo en la plataforma: 2 servicios caídos: wazuh-manager, conector · la cadena de la traza está rota")
  })
  it("sin conexión con el daemon", () => {
    expect(saludPlataforma({ ...base, conectado: false }).titulo).toBe("Sin conexión con el daemon")
  })
})

describe("lo que le toca al analista", () => {
  it("las aprobaciones más urgentes primero, con lo que queda de SLA", () => {
    const u = urgentes([pend("a", 2), pend("b", 13), pend("c", 20), pend("d", 5, 4)], AHORA, 3)
    expect(u.map((x) => x.p.id)).toEqual(["c", "d", "b"])          // fuera de SLA, luego la más grave, luego la más antigua
    expect(textoSla(u[0].restanteMs)).toBe("fuera de SLA 5 min")
    expect(textoSla(u[2].restanteMs)).toBe("quedan 2 min")
    expect(colaResumen([pend("a", 2), pend("b", 13), pend("c", 20)], AHORA)).toEqual({ total: 3, fueraSla: 1, porVencer: 1 })
  })
  it("incidentes abiertos sin responsable, los activos primero", () => {
    const inc = (clave: string, activo: boolean, n: number, asignado: string | null = null, estado = "nuevo") =>
      ({ clave, activo, n, caso: { estado, asignado, notas: [] } }) as unknown as IncidenteVista
    const r = incidentesSinResponsable([inc("a", false, 50), inc("b", true, 3), inc("c", true, 9, "ana"), inc("d", true, 99, null, "resuelto")])
    expect(r.map((e) => e.clave)).toEqual(["b", "a"])
  })
  it("una campaña con pendientes recién llegadas cuenta como activa aunque la traza aún no las tenga", () => {
    const e = { clave: "inc:198.51.100", activo: false } as unknown as IncidenteVista
    const p = { ...pend("p", 5), origen_ip: "198.51.100.9" } as Pendiente
    expect(conActividadDeCola([e], [p], AHORA)[0].activo).toBe(true)
    expect(conActividadDeCola([e], [{ ...p, encolado_en: iso(2 * H) }], AHORA)[0].activo).toBe(false)
  })
  it("contenciones fallidas de las últimas 24 h, una por equipo", () => {
    const r = fallidasRecientes([
      dec({ activo: "web", contencion: "fallida", timestamp: iso(2 * H), id_decision: "x1" }),
      dec({ activo: "web", contencion: "fallida", timestamp: iso(1 * H), id_decision: "x2" }),
      dec({ activo: "atm", contencion: "fallida", timestamp: iso(30 * H) }),           // fuera de las 24 h
      dec({ activo: "atm", contencion: "contenida", timestamp: iso(1 * H) }),
    ], AHORA)
    expect(r).toHaveLength(1); expect(r[0].veces).toBe(2); expect(r[0].d.id_decision).toBe("x2")
  })
  it("lo que puede ser un ataque va primero, aunque la escalada lo contuviera, y nunca como configuración", () => {
    const f3 = { clase: "F3", descripcion: "la clave del host cambió", accion: "posible suplantación del equipo", posible_ataque: true, dispositivo: "fw-core" }
    const f2 = { clase: "F2", descripcion: "equipo sin aprovisionar", accion: "dalo de alta en Conectividad", posible_ataque: false, dispositivo: "atm" }
    const r = fallidasRecientes([
      dec({ activo: "atm", contencion: "fallida", timestamp: iso(1 * H), causa: f2 }),
      dec({ activo: "web", contencion: "contenida", timestamp: iso(2 * H), causa: f3 }),      // contuvo otro, pero ojo
      dec({ activo: "core", contencion: "contenida", timestamp: iso(1 * H) }),                // sin causa: no entra
    ], AHORA)
    expect(r.map((x) => [x.ataque, x.causa?.clase])).toEqual([[true, "F3"], [false, "F2"]])
  })
})

describe("actividad", () => {
  const regs = [
    dec({ timestamp: iso(10 * MIN), requiere_humano: false }),
    dec({ timestamp: iso(20 * MIN), requiere_humano: true }),
    dec({ timestamp: iso(5 * MIN), clase: "fp_actividad_legitima" }),
    dec({ timestamp: iso(3 * H) }),
    dec({ timestamp: iso(26 * H) }),                                     // ayer, antes de esta hora
    { tipo: "actividad_suprimida", timestamp: iso(1 * MIN) } as Decision,  // no es una decisión
  ]
  it("24 horas que acaban en la hora en curso, repartidas por desenlace", () => {
    const h = actividadPorHora(regs, AHORA)
    expect(h).toHaveLength(24)
    expect(h[23]).toMatchObject({ auto: 1, humano: 1, descartadas: 1 })
    expect(h[20].auto).toBe(1)
    expect(h.reduce((a, x) => a + x.auto + x.humano + x.descartadas, 0)).toBe(4)
  })
  it("las que esperan aprobación cuentan como «a un analista» en la hora en que llegaron", () => {
    const h = actividadPorHora(regs, AHORA, [pend("p1", 3), pend("p2", 30 * 60 * 24 * 2)])   // la de hace 2 días no entra
    expect(h[23].humano).toBe(2)
    expect(llegadasUltimaHora(regs, [pend("p1", 3), pend("p2", 90)], AHORA)).toBe(4)        // 3 de la traza + 1 de la cola
  })
  it("compara con ayer a la misma hora solo si la ventana llega al comienzo de ayer", () => {
    expect(comparaConAyer(regs, AHORA)).toEqual({ hoy: 4, ayer: null, ultimaHora: 3 })
    const conAyer = [dec({ timestamp: "2026-11-02T23:50:00Z" }), ...regs]
    expect(comparaConAyer(conAyer, AHORA).ayer).toBe(1)               // la de hace 26 h; la del día 2 no cuenta
    expect(comparaConAyer(regs, AHORA, true).ayer).toBe(1)            // traza entera: sin recorte, sí se compara
    expect(variacion(4, 2)).toEqual({ texto: "▲ 100 % sobre ayer a esta hora", sube: true })
    expect(variacion(4, null)).toBeNull()
    expect(variacion(4, 0)).toBeNull()                                // ayer vacío: traza que empieza hoy, no se compara
    expect(textoSla(-169 * MIN)).toBe("fuera de SLA 2 h")
  })
  it("lo atacado en 24 h sin falsos positivos, y las últimas decisiones primero", () => {
    const a = atacadoEn24h([
      dec({ timestamp: iso(MIN), clase: "vp_malware", activo: "web", contencion: "contenida" }),
      dec({ timestamp: iso(MIN), clase: "vp_malware", activo: "web", contencion: "fallida" }),
      dec({ timestamp: iso(MIN), clase: "fp_actividad_legitima", activo: "atm" }),
    ], AHORA)
    expect(a.clases).toEqual([{ clase: "vp_malware", n: 2 }])
    expect(a.equipos).toEqual([{ equipo: "web", n: 2, contenidas: 1 }])
    expect(ultimasDecisiones(regs, 2).map((d) => d.timestamp)).toEqual([regs[4].timestamp, regs[3].timestamp])   // orden de la traza, la última primero
  })
})
