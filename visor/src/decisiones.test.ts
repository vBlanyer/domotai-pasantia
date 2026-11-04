import { describe, it, expect } from "vitest"
import { desenlaceDe, resumenDecisiones, pasaFiltro, pasosDe, FILTROS_DECISION } from "./decisiones"
import type { Decision, Detalle } from "./api"

const d = (x: Partial<Decision>): Decision => ({ id_decision: "s", clase: "vp_intento_acceso", ...x }) as Decision

describe("desenlaceDe: en qué acabó cada decisión", () => {
  it("prioriza lo que conviene revisar", () => {
    expect(desenlaceDe(d({ contencion: "fallida" })).id).toBe("fallida")
    expect(desenlaceDe(d({ veredicto_humano: "reclasificar", clase_reclasificada: "fp_actividad_legitima" })).id).toBe("reclasificada")
    expect(desenlaceDe(d({ veredicto_humano: "rechazar" })).id).toBe("rechazada")
    expect(desenlaceDe(d({ resultado_filtro: "veta", accion_final: null })).id).toBe("vetada")
    expect(desenlaceDe(d({ requiere_humano: true })).id).toBe("pendiente")
    expect(desenlaceDe(d({ contencion: "contenida" }))).toMatchObject({ id: "contenida", tono: "ok", degradada: false })
    expect(desenlaceDe(d({ contencion: "contenida", resultado_filtro: "degrada" })).degradada).toBe(true)
    expect(desenlaceDe(d({ contencion: "enrutada" })).id).toBe("enrutada")
    expect(desenlaceDe(d({ clase: "fp_actividad_legitima" })).id).toBe("falso_positivo")
    expect(desenlaceDe(d({ tipo: "reversion" })).id).toBe("sistema")
  })
})

describe("resumen y filtros", () => {
  const ds = [
    d({ contencion: "contenida" }), d({ contencion: "contenida", requiere_humano: true, veredicto_humano: "aprobar" }),
    d({ requiere_humano: true, veredicto_humano: "rechazar" }), d({ requiere_humano: true, veredicto_humano: "reclasificar" }),
    d({ resultado_filtro: "degrada", contencion: "contenida" }), d({ resultado_filtro: "veta", accion_final: null }),
    d({ contencion: "fallida" }), d({ tipo: "actividad_suprimida" }),
  ]
  it("cuenta solo decisiones y separa lo que pasó con ellas", () => {
    expect(resumenDecisiones(ds)).toEqual({ total: 7, autoContenidas: 2, humano: 3, aprobadas: 1, corregidas: 2,
      rechazadas: 1, reclasificadas: 1, frenadas: 2, degradadas: 1, vetadas: 1, fallidas: 1 })
  })
  it("cada filtro deja lo suyo; «todas» incluye los registros de sistema", () => {
    const n = (id: string) => ds.filter((x) => pasaFiltro(x, id as never)).length
    expect(FILTROS_DECISION[0].id).toBe("todas")
    expect(n("todas")).toBe(8)
    expect(n("frenadas")).toBe(2)
    expect(n("corregidas")).toBe(2)
    expect(n("fallidas")).toBe(1)
    expect(n("contenidas")).toBe(3)
  })
})

describe("pasosDe: el recorrido de la decisión en seis pasos", () => {
  it("con el detalle: alerta, clasificación, propuesta, política, analista y ejecución", () => {
    const det = {
      justificacion_estructurada: { evidencia: { origen_ip: "203.0.113.7", activo: "web-banking", regla: 100100 }, tecnica_mitre: ["T1110"] },
      accion_propuesta: "AISLAR_NODO", accion_final: "BLOQUEAR_IP", resultado_filtro: "degrada",
      impacto_determinado: { nivel: "localizado", motivo: "bloquea a 203.0.113.7", activos_afectados_en_cascada: [] },
      orden: { accion_id: "BLOQUEAR_IP", nodo_objetivo: "fw-core" }, ejecucion: { exito: true }, verificacion: { verificado: true },
    } as unknown as Detalle
    const p = pasosDe(d({ confianza: 0.97, prioridad: 4, origen_ip: "203.0.113.7", activo: "web-banking" }), det)
    expect(p.map((x) => x.titulo)).toEqual(["Alerta del SIEM", "Clasificación", "Propuesta del motor", "Política del cliente", "Analista", "Ejecución"])
    expect(p[0].texto).toMatch(/203\.0\.113\.7 contra web-banking/)
    expect(p[1]).toMatchObject({ estado: "ok", etiqueta: "confianza 0.97" })
    expect(p[2].texto).toMatch(/AISLAR_NODO/)
    expect(p[3]).toMatchObject({ estado: "aviso", etiqueta: "degrada" })
    expect(p[4]).toMatchObject({ estado: "neutro", etiqueta: "no hizo falta" })
    expect(p[5]).toMatchObject({ estado: "ok", etiqueta: "contenida" })
  })
  it("veto, corrección del analista, cascada y fallo se marcan", () => {
    const det = { resultado_filtro: "veta", accion_propuesta: "BLOQUEAR_IP", accion_final: null, orden: null,
      impacto_determinado: { activos_afectados_en_cascada: ["api-movil"] } } as unknown as Detalle
    const p = pasosDe(d({ requiere_humano: true, veredicto_humano: "reclasificar", veredicto_por: "ana", clase_reclasificada: "fp_actividad_legitima" }), det)
    expect(p[1].estado).toBe("aviso")                    // el analista corrigió la clase
    expect(p[2]).toMatchObject({ estado: "aviso" })       // cascada
    expect(p[3]).toMatchObject({ estado: "critico", etiqueta: "veta" })
    expect(p[4]).toMatchObject({ estado: "humano", etiqueta: "reclasificó ana" })
    const sinNombre = pasosDe(d({ requiere_humano: true, veredicto_humano: "aprobar", decidido_en: "2026-11-04T18:55:14Z", espera_humana_s: 24.4 }), null)
    expect(sinNombre[4].etiqueta).toBe("aprobó · sin nombre registrado")
    expect(sinNombre[4].texto).toMatch(/^aprobó la propuesta · \d{2}:\d{2}:\d{2} · 24 s después de llegar a la cola$/)
    expect(p[5].estado).toBe("neutro")
  })
  it("sin el detalle aún, usa lo que trae la lista", () => {
    const p = pasosDe(d({ contencion: "fallida", accion_final: "MATAR_CONEXION" }), null)
    expect(p[5]).toMatchObject({ estado: "critico", etiqueta: "fallida" })
  })
})

describe("«Decididas por mí»", () => {
  it("solo las que firmó el operador de la sesión con su veredicto", () => {
    const mia = d({ veredicto_humano: "aprobar", veredicto_por: "ana" })
    const otra = d({ veredicto_humano: "aprobar", veredicto_por: "leo" })
    const auto = d({})
    expect([mia, otra, auto].filter((x) => pasaFiltro(x, "decididas_por_mi", "ana"))).toEqual([mia])
    expect(pasaFiltro(mia, "decididas_por_mi", "")).toBe(false)
    expect(FILTROS_DECISION.some((f) => f.id === "decididas_por_mi")).toBe(true)
  })
})
