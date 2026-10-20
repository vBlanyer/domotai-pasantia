import { describe, it, expect } from "vitest"
import { filtrarDecisiones, clasesDe, contencionDe, filtroLegible, nivelPrioridad, ventanaDe, esDecision, estadoDeCasos, etiquetaClase, colorClase } from "./datos"
import type { Decision, Detalle } from "./api"

const D: Decision[] = [
  { id_decision: "s1", activo: "web-banking", origen_ip: "10.40.0.10", clase: "vp_intento_acceso", accion_final: "BLOQUEAR_IP" },
  { id_decision: "s2", activo: "core-db", origen_ip: "203.0.113.9", clase: "fp_actividad_legitima", accion_final: null },
  { id_decision: "s3", activo: "web-banking", origen_ip: "10.200.0.10", clase: "no_soportada" },
]

describe("esDecision", () => {
  it("no cuenta como decisión las reversiones, errores, actividad suprimida/propia ni las actualizaciones de caso", () => {
    const tipos = ["decision", null, "reversion", "error", "actividad_suprimida", "actividad_propia", "actualizacion_caso"]
    expect(tipos.map((tipo) => esDecision({ tipo } as Decision))).toEqual([true, true, false, false, false, false, false])
  })
})

describe("estadoDeCasos", () => {
  it("pliega la última actualización por decisión y acumula las notas", () => {
    const regs = [
      { tipo: "decision", id_decision: "d1" },
      { tipo: "actualizacion_caso", id_decision: "d1", estado: "en_revision", asignado: "ana", decidido_en: "t1" },
      { tipo: "actualizacion_caso", id_decision: "d1", nota: "parece C2 real", operador: "ana", decidido_en: "t2" },
      { tipo: "actualizacion_caso", id_decision: "d1", estado: "resuelto", decidido_en: "t3" },
    ] as Decision[]
    const c = estadoDeCasos(regs)["d1"]
    expect(c.estado).toBe("resuelto")               // el último estado gana
    expect(c.asignado).toBe("ana")                  // se conserva el último asignado
    expect(c.notas.map((n) => n.texto)).toEqual(["parece C2 real"])
    expect(c.actualizado_en).toBe("t3")
  })
  it("una decisión sin actualizaciones no aparece (estado implícito 'nuevo')", () => {
    expect(estadoDeCasos([{ tipo: "decision", id_decision: "d1" }] as Decision[])).toEqual({})
  })
})

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
  it("filtra por equipo según las relaciones del registro", () => {
    const ds = [{ id_decision: "s1", relaciones: { "web-banking": ["objetivo"] } },
                { id_decision: "s2", relaciones: { "fw-core": ["contuvo_aqui"], "api-movil": ["objetivo"] } },
                { id_decision: "s3" }] as Decision[]
    expect(filtrarDecisiones(ds, { texto: "", clase: "", equipo: "fw-core" }).map((d) => d.id_decision)).toEqual(["s2"])
    expect(filtrarDecisiones(ds, { texto: "", clase: "", equipo: null }).length).toBe(3)
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

  it("el activo no respondió y la escalada contuvo en el perímetro: manda la orden efectiva", () => {
    const c = contencionDe({ orden, ejecucion: { exito: false, comando_ejecutado: "iptables -A INPUT -s 1.2.3.4 -j DROP" },
      verificacion: { verificado: false },
      escalada: { resultado: "mitigado", escalado: true, dispositivo_ejecutor: "gateway",
        orden_efectiva: { accion_id: "BLOQUEAR_IP_FIREWALL", nodo_objetivo: "gateway" } } } as Detalle)
    expect(c).toMatchObject({ estado: "contenida", escalada: true, dispositivo: "gateway", desde: "objetivo-vuln",
      accion: "BLOQUEAR_IP_FIREWALL", ejecutada: true, verificada: true, comando: undefined,
      intento: { nodo: "objetivo-vuln", ejecutada: false, verificada: false } })
  })

  it("una amenaza enrutada dice a dónde se envió", () => {
    expect(contencionDe({ ruta: "cola-appsec-banco", accion_final: null, orden: null } as Detalle))
      .toMatchObject({ estado: "enrutada", destino: "cola-appsec-banco" })
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
  it("revisar: no_soportada de severidad alta escalada a revisión, sin acción", () => {
    expect(filtroLegible({ resultado_filtro: "revisar", accion_final: null, requiere_humano: true }))
      .toBe("revisar — alerta no soportada de severidad alta, sin acción automática")
  })
  it("en una decisión ya resuelta habla en pasado y dice qué decidió el analista", () => {
    expect(filtroLegible({ resultado_filtro: "veta", accion_final: "BLOQUEAR_IP", veredicto_humano: "rechazar" }))
      .toBe("retenida — requirió aprobación · rechazada")
    expect(filtroLegible({ resultado_filtro: "degrada", accion_final: "BLOQUEAR_IP", requiere_humano: true,
      veredicto_humano: "aprobar" })).toBe("degradada — se sustituyó por BLOQUEAR_IP · requirió aprobación · aprobada")
    expect(filtroLegible({ resultado_filtro: "permite", requiere_humano: true, veredicto_humano: "reclasificar" }))
      .toBe("permitida — requirió aprobación · reclasificada")
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

// A1 de la auditoría: las etiquetas de clase vivían TRIPLICADAS (Dashboard/Metricas/Aprobaciones) y
// dos copias no conocían las familias 9ª/10ª. Una sola fuente, completa.
describe("etiquetaClase", () => {
  it("cubre las clases de las 10 familias, incluidas exfiltración y malware", () => {
    for (const c of ["vp_intento_acceso", "vp_reconocimiento", "vp_integridad", "vp_denegacion_servicio",
                     "vp_abuso_cuenta", "vp_acceso_consumado", "vp_exfiltracion", "vp_malware",
                     "fp_actividad_legitima", "fp_exposicion_inexistente", "no_soportada", "amenaza_enrutada"]) {
      expect(etiquetaClase(c), c).not.toBe(c)            // ninguna se muestra como id crudo
    }
    expect(etiquetaClase("vp_exfiltracion")).toMatch(/exfiltraci/i)
    expect(etiquetaClase("vp_malware")).toMatch(/malware/i)
  })
  it("una clase desconocida cae al id (no se inventa nada)", () => {
    expect(etiquetaClase("vp_del_futuro")).toBe("vp_del_futuro")
  })
})

// A10: el color de la dona era por POSICIÓN alfabética — una clase nueva en vivo desplazaba el color
// de todas las demás a mitad de sesión. Color por identidad de la clase, estable.
describe("colorClase", () => {
  const PALETA = ["#111", "#222", "#333", "#444", "#555", "#666", "#777", "#888"]
  it("la misma clase recibe el mismo color estén las que estén", () => {
    expect(colorClase("vp_malware", PALETA)).toBe(colorClase("vp_malware", PALETA))
    expect(colorClase("vp_intento_acceso", PALETA)).not.toBe(colorClase("vp_reconocimiento", PALETA))
  })
  it("una clase desconocida también recibe un color estable de la paleta", () => {
    const c = colorClase("clase_rara", PALETA)
    expect(PALETA).toContain(c)
    expect(colorClase("clase_rara", PALETA)).toBe(c)
  })
})
