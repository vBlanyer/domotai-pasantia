import { describe, it, expect } from "vitest"
import { filtrarDecisiones, clasesDe, contencionDe, filtroLegible, nivelPrioridad, ventanaDe } from "./datos"
import type { Decision, Detalle } from "./api"

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

describe("contencionDe", () => {
  const orden = { accion_id: "BLOQUEAR_IP", nodo_objetivo: "objetivo-vuln" }

  it("ejecutada y verificada en el activo -> contenida allí, sin escalar", () => {
    const c = contencionDe({ orden, ejecucion: { exito: true, comando_ejecutado: "iptables -A INPUT -s 1.2.3.4 -j DROP" },
      verificacion: { verificado: true } } as Detalle)
    expect(c).toMatchObject({ estado: "contenida", ejecutada: true, verificada: true, escalada: false,
      dispositivo: "objetivo-vuln", accion: "BLOQUEAR_IP", comando: "iptables -A INPUT -s 1.2.3.4 -j DROP" })
  })

  it("el activo no respondió y la escalada contuvo en el perímetro", () => {
    const c = contencionDe({ orden, ejecucion: { exito: false }, verificacion: { verificado: false },
      escalada: { resultado: "mitigado", escalado: true, dispositivo_ejecutor: "gateway" } } as Detalle)
    expect(c).toMatchObject({ estado: "contenida", ejecutada: false, escalada: true, dispositivo: "gateway", desde: "objetivo-vuln" })
  })

  it("ni el activo ni la escalada lo lograron -> fallida", () => {
    const c = contencionDe({ orden, ejecucion: { exito: false }, verificacion: { verificado: false },
      escalada: { resultado: "fallido", escalado: true } } as Detalle)
    expect(c.estado).toBe("fallida")
  })

  it("sin topología a la que escalar y sin verificar -> fallida", () => {
    expect(contencionDe({ orden, ejecucion: { exito: true }, verificacion: { verificado: false } } as Detalle).estado)
      .toBe("fallida")
  })

  it("el analista la canceló durante la escalada -> cancelada", () => {
    const c = contencionDe({ orden, ejecucion: { exito: false }, verificacion: { verificado: false },
      escalada: { resultado: "cancelado_por_humano", escalado: false } } as Detalle)
    expect(c.estado).toBe("cancelada")
  })

  it("rechazada o reclasificada por el analista -> retenida, nada ejecutado", () => {
    expect(contencionDe({ veredicto_humano: "rechazar", accion_final: "BLOQUEAR_IP", orden: null } as Detalle).estado)
      .toBe("retenida")
    expect(contencionDe({ veredicto_humano: "reclasificar", orden: null } as Detalle).estado).toBe("retenida")
  })

  it("sin acción de contención -> sin_accion", () => {
    expect(contencionDe({ accion_final: null, orden: null } as Detalle).estado).toBe("sin_accion")
  })

  it("modo agente: manda el plan del agente", () => {
    const c = contencionDe({ mitigacion_agente: { resultado: "mitigado", escalado: true, dispositivo_ejecutor: "firewall" } } as Detalle)
    expect(c).toMatchObject({ estado: "contenida", escalada: true, dispositivo: "firewall" })
  })
})

describe("filtroLegible", () => {
  // Mismo vocabulario que validacion.filtro_legible del daemon (lo que el analista ve en la terminal).
  it("veto con acción final: queda retenida para aprobar", () => {
    expect(filtroLegible({ resultado_filtro: "veta", accion_final: "BLOQUEAR_IP" })).toBe("retenida — espera tu aprobación")
  })
  it("veto sin acción final: no se puede ejecutar", () => {
    expect(filtroLegible({ resultado_filtro: "veta", accion_final: null })).toBe("vetada — no se puede ejecutar")
  })
  it("degradada: dice por qué acción se sustituye y si espera aprobación", () => {
    expect(filtroLegible({ resultado_filtro: "degrada", accion_final: "BLOQUEAR_IP" }))
      .toBe("degradada — se sustituye por BLOQUEAR_IP")
    expect(filtroLegible({ resultado_filtro: "degrada", accion_final: "BLOQUEAR_IP", requiere_humano: true }))
      .toBe("degradada — se sustituye por BLOQUEAR_IP; espera tu aprobación")
  })
  it("permitida: automática, salvo que otra regla pida humano", () => {
    expect(filtroLegible({ resultado_filtro: "permite" })).toBe("automática")
    expect(filtroLegible({ resultado_filtro: "permite", requiere_humano: true })).toBe("permitida — espera tu aprobación")
  })
  it("sin acción y sin dato", () => {
    expect(filtroLegible({ resultado_filtro: "sin_accion" })).toBe("sin acción")
    expect(filtroLegible({})).toBeNull()
  })
})

describe("nivelPrioridad", () => {
  // Escala del motor (analisis._priorizar): 1..4, donde 4 es un acceso consumado o un intento
  // sobre un activo crítico.
  it("rotula cada nivel", () => {
    expect(nivelPrioridad(4)?.etiqueta).toBe("P4 · crítica")
    expect(nivelPrioridad(3)?.etiqueta).toBe("P3 · alta")
    expect(nivelPrioridad(2)?.etiqueta).toBe("P2 · media")
    expect(nivelPrioridad(1)?.etiqueta).toBe("P1 · baja")
  })
  it("sin prioridad (o 0, el valor por defecto de la cola) no rotula", () => {
    expect(nivelPrioridad(null)).toBeNull()
    expect(nivelPrioridad(undefined)).toBeNull()
    expect(nivelPrioridad(0)).toBeNull()
  })
  it("por encima de la escala cuenta como crítica", () => {
    expect(nivelPrioridad(7)?.etiqueta).toBe("P4 · crítica")
  })
})

describe("ventanaDe", () => {
  // /api/trazas sirve la cola del fichero: si no empieza en el registro 0, lo mostrado es parcial.
  it("ventana que empieza a mitad de la cadena: cuántos se ven de cuántos hay", () => {
    expect(ventanaDe([{ indice: 500 }, { indice: 501 }] as Decision[])).toEqual({ mostrados: 2, total: 502, desde: 500 })
  })
  it("cadena completa, vacía o sin índices (daemon antiguo): no es parcial", () => {
    expect(ventanaDe([{ indice: 0 }, { indice: 1 }] as Decision[])).toBeNull()
    expect(ventanaDe([])).toBeNull()
    expect(ventanaDe([{ id_decision: "s1" }] as Decision[])).toBeNull()
  })
})
