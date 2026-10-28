import { describe, it, expect } from "vitest"
import { filtrarDecisiones, clasesDe, contencionDe, filtroLegible, nivelPrioridad, ventanaDe, esDecision, estadoDeCasos, etiquetaClase, colorClase, ETIQUETA_CLASE, clasificarLinea, filtrarConsola, paginar, agruparPorDia, atacantesDe, agruparPorSubred, campanasDe, perfilAtacante, pasosRunbook, riesgoEquipo, riesgoAtacante, enWatchlist, ubicacionesDe } from "./datos"
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
  it("por texto también busca el país geo (pivote desde Ubicaciones)", () => {
    const ds = [
      { id_decision: "a", origen_ip: "8.8.8.8", enriquecimiento_origen: { geo: { pais: "Estados Unidos", codigo: "US" } } },
      { id_decision: "b", origen_ip: "5.45.0.1", enriquecimiento_origen: { geo: { pais: "Rusia", codigo: "RU" } } },
    ] as unknown as Decision[]
    expect(filtrarDecisiones(ds, { texto: "Estados Unidos", clase: "" }).map((d) => d.id_decision)).toEqual(["a"])
    expect(filtrarDecisiones(ds, { texto: "rusia", clase: "" }).map((d) => d.id_decision)).toEqual(["b"])
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

// Revisión: con 13 clases canónicas y una paleta de 8, las dos clases más frecuentes del canon
// (intento de acceso y FP legítimo) compartían color. La paleta cubre el canon completo.
describe("colorClase sin colisiones en el canon", () => {
  it("las 13 clases canónicas reciben colores DISTINTOS con la paleta real", async () => {
    const { CATEGORICO_LIGHT } = await import("./theme")
    const clases = Object.keys(ETIQUETA_CLASE)
    const colores = clases.map((c) => colorClase(c, CATEGORICO_LIGHT))
    expect(new Set(colores).size).toBe(clases.length)
  })
})

// Vista «Consola»: la clasificación de cada línea del feed (para los filtros) es pura y por
// prefijo — los prefijos son los que emite el daemon (stream._linea_* / _resumen_incidente).
describe("clasificarLinea", () => {
  it("reconoce los prefijos reales del daemon", () => {
    expect(clasificarLinea("⚠ Incidente: 6 alerta(s) · x")).toBe("incidente")
    expect(clasificarLinea("  Clase: vp_intento_acceso · Prioridad: 3")).toBe("decision")
    expect(clasificarLinea("⏸ En cola (espera al analista) · vp_x")).toBe("decision")
    expect(clasificarLinea("↩ 1.2.3.4 → srv · ya decidido")).toBe("supresion")
    expect(clasificarLinea("✗ e3: no se pudo procesar")).toBe("error")
    expect(clasificarLinea("↺ actividad propia del MDR en srv")).toBe("propia")
    expect(clasificarLinea("[aviso] receptor: conexión rechazada")).toBe("aviso")
    expect(clasificarLinea("[red] escuchando alertas en 0.0.0.0:5514")).toBe("aviso")
    // narración de la caja negra: la ejecución de la respuesta y sus detalles
    expect(clasificarLinea("▶ s12 BLOQUEAR_IP en objetivo-vuln (…): iptables -A …")).toBe("ejecucion")
    expect(clasificarLinea("✔ s12 verificada — contenida")).toBe("ejecucion")
    expect(clasificarLinea("⇪ s12 el activo no respondió → fw-core")).toBe("ejecucion")
    expect(clasificarLinea("↶ des-bloqueo en masa: 3 revertida(s)")).toBe("ejecucion")
    // la verificación FALLIDA es narración de la respuesta, no un error de proceso (revisión)
    expect(clasificarLinea("✗ s12 NO verificada: la contención no se confirmó")).toBe("ejecucion")
    expect(clasificarLinea("✗ e3: no se pudo procesar el incidente")).toBe("error")
    expect(clasificarLinea("· s12 política: retenida — bloquea a puesto")).toBe("detalle")
    expect(clasificarLinea("cualquier otra cosa")).toBe("otro")
  })

  it("reconoce el diario del operador: veredictos, kill switch, caso y arranque", () => {
    expect(clasificarLinea("✓ s12 aprobada por ana → ejecutando BLOQUEAR_IP")).toBe("decision")
    expect(clasificarLinea("✋ s12 rechazada por ana — retenida sin ejecutar")).toBe("decision")
    expect(clasificarLinea("↻ s12 reclasificada por luis: vp_x → fp_y — retenida sin ejecutar")).toBe("decision")
    // ↻ (veredicto) no es ↺ (actividad propia): son flechas distintas
    expect(clasificarLinea("↺ actividad propia del MDR en srv")).toBe("propia")
    expect(clasificarLinea("☰ s1 caso: estado → en_revision · por ana")).toBe("detalle")
    expect(clasificarLinea("⏻ automatización EN PAUSA — toda contención espera al humano · por ana")).toBe("aviso")
    expect(clasificarLinea("[inicio] monitor activo · perfil cliente_generico.yml")).toBe("aviso")
  })
})

describe("filtrarConsola", () => {
  const L = (linea: string, n = 1) => ({ n, t: "16:02:11", linea })
  const lineas = [L("⚠ Incidente: x", 1), L("  Clase: vp_x", 2), L("[aviso] y", 3)]
  it("filtra por grupo y por texto, y 'todo' no filtra", () => {
    expect(filtrarConsola(lineas, "todo", "").length).toBe(3)
    expect(filtrarConsola(lineas, "avisos", "").map((l) => l.n)).toEqual([3])
    expect(filtrarConsola(lineas, "todo", "vp_x").map((l) => l.n)).toEqual([2])
  })
  it("el grupo decisiones incluye la decisión, la supresión y el detalle", () => {
    const ls = [L("  Clase: vp_x", 1), L("↩ repetida", 2), L("⚠ Incidente", 3), L("· s1 política: x", 4)]
    expect(filtrarConsola(ls, "decisiones", "").map((l) => l.n)).toEqual([1, 2, 4])
  })

  it("el grupo ejecución aísla la respuesta sobre la red", () => {
    const ls = [L("▶ s1 BLOQUEAR_IP …", 1), L("✔ s1 verificada", 2), L("⚠ Incidente", 3),
                L("↶ des-bloqueo en masa", 4)]
    expect(filtrarConsola(ls, "ejecucion", "").map((l) => l.n)).toEqual([1, 2, 4])
  })
})

describe("paginar", () => {
  const xs = Array.from({ length: 30 }, (_, i) => i)
  it("corta a la página pedida y cuenta las páginas", () => {
    const r = paginar(xs, 1, 25)
    expect(r.filas).toHaveLength(25)
    expect(r).toMatchObject({ pagina: 1, paginas: 2, total: 30 })
    expect(paginar(xs, 2, 25).filas).toEqual(xs.slice(25))
  })
  it("clampa una página fuera de rango a [1, paginas]", () => {
    expect(paginar(xs, 99, 25).pagina).toBe(2)
    expect(paginar(xs, 0, 25).pagina).toBe(1)
  })
  it("una lista vacía es una sola página vacía", () => {
    expect(paginar([], 1, 25)).toMatchObject({ filas: [], pagina: 1, paginas: 1, total: 0 })
  })
})

describe("agruparPorDia", () => {
  it("cuenta eventos por día e ignora los sin timestamp, ordenando cronológicamente", () => {
    const ds = [
      { timestamp: "2026-10-27T10:00:00" }, { timestamp: "2026-10-27T11:30:00" },
      { timestamp: "2026-10-26T09:00:00" }, { timestamp: null },
    ] as unknown as Decision[]
    expect(agruparPorDia(ds)).toEqual([{ dia: "2026-10-26", n: 1 }, { dia: "2026-10-27", n: 2 }])
  })
  it("una lista vacía da []", () => {
    expect(agruparPorDia([])).toEqual([])
  })
})

describe("paginar: desplazamiento y tamaño por defecto", () => {
  const xs = Array.from({ length: 30 }, (_, i) => i)
  it("expone `desde` (desplazamiento) y el tamaño por defecto es 20", () => {
    expect(paginar(xs, 2, 10).desde).toBe(10)
    expect(paginar(xs, 1).filas).toHaveLength(20)
  })
})

describe("atacantesDe", () => {
  const ev = [
    { origen_ip: "198.51.100.11", timestamp: "2026-10-27T10:00:00", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { alcance: "externo" } },
    { origen_ip: "198.51.100.11", timestamp: "2026-10-27T12:00:00", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { alcance: "externo" } },
    { origen_ip: "10.200.0.11", timestamp: "2026-10-27T09:00:00", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { alcance: "interno" } },
    { origen_ip: null, timestamp: "2026-10-27T09:30:00", relaciones: { "web-banking": ["objetivo"] } },        // host-injected sin IP → se ignora
    { origen_ip: "198.51.100.11", timestamp: "2026-10-27T13:00:00", relaciones: { "web-banking": ["origen"] } }, // el equipo como ORIGEN, no ataque recibido → se ignora
  ] as unknown as Decision[]

  it("cuenta ataques por IP contra el equipo, ordenados de más a menos", () => {
    const r = atacantesDe(ev, "web-banking")
    expect(r.map((a) => [a.ip, a.n])).toEqual([["198.51.100.11", 2], ["10.200.0.11", 1]])
    expect(r[0].alcance).toBe("externo")
    expect(r[0].ultima).toBe("2026-10-27T12:00:00")
  })

  it("correlaciona en qué otros equipos pegó la misma IP (todos)", () => {
    const todos = [...ev, { origen_ip: "198.51.100.11", relaciones: { "core-db": ["objetivo"] } }] as unknown as Decision[]
    const r = atacantesDe(ev, "web-banking", todos)
    expect(r.find((a) => a.ip === "198.51.100.11")!.otrosEquipos).toEqual(["core-db"])
    expect(r.find((a) => a.ip === "10.200.0.11")!.otrosEquipos).toEqual([])
  })
})

describe("atacantesDe: ranking por gravedad", () => {
  it("ordena por prioridad máxima y luego por nº de ataques; expone prioridad", () => {
    const ev = [
      { origen_ip: "a", prioridad: 2, relaciones: { x: ["objetivo"] } },
      { origen_ip: "a", prioridad: 2, relaciones: { x: ["objetivo"] } },   // a: n2, prio2
      { origen_ip: "b", prioridad: 4, relaciones: { x: ["objetivo"] } },   // b: n1, prio4 (más grave)
    ] as unknown as Decision[]
    const r = atacantesDe(ev, "x")
    expect(r.map((at) => at.ip)).toEqual(["b", "a"])     // b primero por gravedad, aunque tenga menos ataques
    expect(r[0].prioridad).toBe(4)
  })
})

describe("agruparPorSubred", () => {
  it("colapsa por /24 sumando ataques e IPs, con gravedad máxima y unión de 'también en'", () => {
    const at = [
      { ip: "198.51.100.10", n: 3, prioridad: 4, ultima: "t2", alcance: "externo", otrosEquipos: [] },
      { ip: "198.51.100.11", n: 1, prioridad: 2, ultima: "t1", alcance: "externo", otrosEquipos: ["core-db"] },
      { ip: "10.0.0.5", n: 2, prioridad: 3, ultima: "t3", alcance: "interno", otrosEquipos: [] },
    ]
    const g = agruparPorSubred(at)
    const banco = g.find((x) => x.cidr === "198.51.100.0/24")!
    expect(banco).toMatchObject({ ips: 2, n: 4, prioridad: 4, prefijo: "198.51.100." })
    expect(banco.otrosEquipos).toEqual(["core-db"])
    expect(g.find((x) => x.cidr === "10.0.0.0/24")!.ips).toBe(1)
    expect(g[0].cidr).toBe("198.51.100.0/24")        // ordenado por gravedad (P4) primero
  })
})

describe("campanasDe", () => {
  it("agrupa por bloque de origen a través de equipos, con objetivos, gravedad y ventana", () => {
    const t = [
      { origen_ip: "198.51.100.10", prioridad: 4, timestamp: "t2", relaciones: { "web-banking": ["objetivo"] } },
      { origen_ip: "198.51.100.11", prioridad: 3, timestamp: "t1", relaciones: { "core-db": ["objetivo"] } },
      { origen_ip: "198.51.100.10", prioridad: 2, timestamp: "t3", relaciones: { "web-banking": ["objetivo"] } },
      { origen_ip: null, relaciones: { "web-banking": ["objetivo"] } },     // sin IP → se ignora
    ] as unknown as Decision[]
    const c = campanasDe(t)
    expect(c).toHaveLength(1)
    expect(c[0]).toMatchObject({ cidr: "198.51.100.0/24", ips: 2, n: 3, prioridad: 4, prefijo: "198.51.100." })
    expect(c[0].objetivos).toEqual([{ equipo: "web-banking", n: 2 }, { equipo: "core-db", n: 1 }])
    expect(c[0].primera).toBe("t1"); expect(c[0].ultima).toBe("t3")
  })
})

describe("perfilAtacante", () => {
  it("resume una IP: ataques, equipos atacados, gravedad, ventana y enriquecimiento", () => {
    const t = [
      { origen_ip: "198.51.100.10", prioridad: 4, timestamp: "2026-10-27T10:00:00", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { alcance: "externo", clasificacion_ip: "documentacion" } },
      { origen_ip: "198.51.100.10", prioridad: 2, timestamp: "2026-10-27T12:00:00", relaciones: { "core-db": ["objetivo"] } },
      { origen_ip: "9.9.9.9", prioridad: 4, timestamp: "2026-10-27T11:00:00", relaciones: { "web-banking": ["objetivo"] } },  // otra IP
    ] as unknown as Decision[]
    const p = perfilAtacante(t, "198.51.100.10")
    expect(p).toMatchObject({ ip: "198.51.100.10", n: 2, prioridad: 4, primera: "2026-10-27T10:00:00", ultima: "2026-10-27T12:00:00" })
    expect(p.equipos).toEqual([{ equipo: "web-banking", n: 1, ultima: "2026-10-27T10:00:00" }, { equipo: "core-db", n: 1, ultima: "2026-10-27T12:00:00" }])
    expect(p.enriquecimiento?.alcance).toBe("externo")
  })
})

describe("pasosRunbook", () => {
  it("da los pasos recomendados de una familia conocida y [] para una desconocida/FP", () => {
    expect(pasosRunbook("vp_intento_acceso").length).toBeGreaterThan(0)
    expect(pasosRunbook("fp_actividad_legitima")).toEqual([])
    expect(pasosRunbook(null)).toEqual([])
  })
})

describe("riesgoEquipo / riesgoAtacante", () => {
  const nod = (extra = {}) => ({ nombre: "web-banking", criticidad: "alta", actividad: { pendientes: 0 }, ...extra }) as unknown as Parameters<typeof riesgoEquipo>[0]
  it("sin ataques recibidos, el riesgo del equipo es bajo", () => {
    expect(riesgoEquipo(nod(), []).nivel).toBe("bajo")
  })
  it("un ataque P4 contra un activo crítico con pendientes sube el riesgo y expone los factores", () => {
    const ev = [{ prioridad: 4, relaciones: { "web-banking": ["objetivo"] } }] as unknown as Parameters<typeof riesgoEquipo>[1]
    const r = riesgoEquipo(nod({ actividad: { pendientes: 2 } }), ev)
    expect(["alto", "critico"]).toContain(r.nivel)
    expect(r.factores.some((f) => /prioridad 4/.test(f))).toBe(true)
    expect(r.factores.some((f) => /pendiente/.test(f))).toBe(true)
  })
  it("un atacante que pega a varios equipos con P4 es crítico", () => {
    const r = riesgoAtacante({ n: 5, prioridad: 4, equipos: [{ equipo: "a", n: 2, ultima: null }, { equipo: "b", n: 2, ultima: null }, { equipo: "c", n: 1, ultima: null }] } as unknown as Parameters<typeof riesgoAtacante>[0])
    expect(r.nivel).toBe("critico")
    expect(r.factores.some((f) => /3 equipos/.test(f))).toBe(true)
  })
})

describe("enWatchlist", () => {
  const wl = [{ indicador: "198.51.100.10", nota: "C2" }, { indicador: "203.0.113.0/24", nota: "bloque malo" }]
  it("marca por IP exacta y por /24, y no marca lo que no está", () => {
    expect(enWatchlist("198.51.100.10", wl)?.nota).toBe("C2")
    expect(enWatchlist("203.0.113.55", wl)?.nota).toBe("bloque malo")   // dentro del /24
    expect(enWatchlist("10.0.0.1", wl)).toBeNull()
    expect(enWatchlist(null, wl)).toBeNull()
  })
})

describe("ubicacionesDe", () => {
  it("agrupa por país real, red interna y laboratorio (ataques recibidos)", () => {
    const t = [
      { origen_ip: "8.8.8.8", prioridad: 4, relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
      { origen_ip: "198.51.100.10", prioridad: 3, relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "documentacion", geo: null } },
      { origen_ip: "10.0.0.5", prioridad: 2, relaciones: { "core-db": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "privada", geo: null } },
    ] as unknown as Decision[]
    const u = ubicacionesDe(t)
    const porClave = Object.fromEntries(u.map((x) => [x.clave, x]))
    expect(porClave["US"]).toMatchObject({ nombre: "Estados Unidos", n: 1, codigo: "US" })
    expect(porClave["US"].lat).toBe(37)
    expect(porClave["lab"].nombre).toBe("Laboratorio / documentación")
    expect(porClave["interna"].nombre).toBe("Red interna")
  })

  it("parte el total en mitigados (contenida) y en curso (el resto)", () => {
    const t = [
      { origen_ip: "8.8.8.1", contencion: "contenida", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
      { origen_ip: "8.8.8.2", contencion: "fallida",   relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
      { origen_ip: "8.8.8.3", contencion: "sin_accion", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
    ] as unknown as Decision[]
    const us = ubicacionesDe(t).find((x) => x.clave === "US")!
    expect(us).toMatchObject({ n: 3, mitigados: 1, enCurso: 2 })   // total = mitigados + enCurso
  })
})
