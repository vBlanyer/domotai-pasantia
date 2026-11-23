import { describe, it, expect } from "vitest"
import { nombreFamilia, accionEnPalabras, resumenPolitica, intocablesDe } from "@/politicas"
import type { PoliticaEstado } from "@/api"

// La política del perfil bancario tal como la servía /api/politica el 18/11 (lo justo para el Resumen).
const fam = (familia: string, automatizacion_efectiva: string, accion: string | null, ruta: string | null = null) =>
  ({ familia, automatizacion_efectiva, automatizacion: automatizacion_efectiva, accion, ruta, clase_tipica: "x", mitre: [], vetos: [] })
const BANCO: PoliticaEstado = {
  familias: [
    fam("acceso_credenciales", "automatica_si_confianza", "BLOQUEAR_IP"),
    fam("reconocimiento", "automatica_si_confianza", "BLOQUEAR_IP"),
    fam("servicio_expuesto", "automatica_si_confianza", "BLOQUEAR_IP"),
    fam("explotacion_conocida", "requiere_humano", null, "analista"),
    fam("abuso_de_cuenta", "nunca_automatica", "FORZAR_CAMBIO_PASS"),
    fam("integridad_fichero", "nunca_automatica", "AISLAR_NODO"),
    fam("denegacion_servicio", "nunca_automatica", "LIMITAR_BANDA"),
    fam("acceso_consumado", "automatica_si_confianza", "MATAR_CONEXION"),
    fam("exfiltracion", "nunca_automatica", "BLOQUEAR_DESTINO"),
    fam("malware", "nunca_automatica", "AISLAR_NODO"),
  ],
  zonas: [{ zona: "Core", automatizacion: "automatica_si_confianza", protegida: false, dispositivos: [
    { activo: "core-db", cascada: ["middleware"], radio: 1, cascada_posiblemente_incompleta: false }] }],
  confianza: { administradores: ["10.100.0.10", "10.100.0.20"], socios_criticos: [], rafaga: { alertas: 9, en_segundos: 60 },
    certeza_minima: 0.9, revisar_desde_nivel: 10, origen: "perfil", equipos_propios: "humano_siempre" },
  intocables: [
    { activo: "core-db", servicio: 1521, origen: "perfil", funcion: "base de datos del core bancario" },
    { activo: "suelto", servicio: 8443, origen: "perfil", funcion: null },
  ],
}
const titulos = (xs: { titulo: string }[]) => xs.map((x) => x.titulo)

describe("nombres legibles", () => {
  it("de las familias, y el identificador si no hay nombre", () => {
    expect(nombreFamilia("acceso_credenciales")).toBe("Fuerza bruta")
    expect(nombreFamilia("integridad_fichero")).toBe("Cambios en ficheros vigilados")
    expect(nombreFamilia("nueva_x")).toBe("nueva_x")
  })
  it("de las acciones", () => {
    expect(accionEnPalabras("BLOQUEAR_IP")).toBe("bloquea el origen")
    expect(accionEnPalabras("MATAR_CONEXION")).toBe("corta la sesión abierta")
    expect(accionEnPalabras(null, "analista")).toBe("se tría y se enruta")
    expect(accionEnPalabras(null)).toBe("sin acción")
    expect(accionEnPalabras("ACCION_RARA")).toBe("ACCION_RARA")
  })
})

describe("resumenPolitica", () => {
  const r = resumenPolitica(BANCO)

  it("la frase cuenta los tipos de ataque por columna", () => {
    expect(r.frase).toBe("De 10 tipos de ataque, el MDR contiene 4 solo (si está seguro), deja 1 a un analista y 5 nunca los toca solo. Todo lo que hace se puede deshacer.")
  })

  it("lo que contiene solo, con su acción en palabras y la certeza", () => {
    expect(titulos(r.solo)).toEqual(["Fuerza bruta", "Reconocimiento (escaneo)", "Servicio expuesto", "Intrusión consumada"])
    expect(r.solo[0].detalle).toBe("bloquea el origen")
    expect(r.certeza).toBe(0.9)
  })

  it("lo que espera a un analista: familias, equipos propios, intocables (con o sin zona) y lo no reconocido", () => {
    expect(titulos(r.humano)).toEqual(["Explotación conocida", "Bloquear un equipo propio",
      "core-db · base de datos del core bancario", "suelto", "Alertas que no reconoce, de nivel 10 o más"])
    // lo exacto: la excepción impide CERRAR el puerto solo (bloquear al atacante sigue pudiendo ser automático)
    expect(r.humano[2].detalle).toBe("no se cierra el puerto 1521 en automático · del perfil")
    expect(r.humano[3].detalle).toBe("no se cierra el puerto 8443 en automático · del perfil")
  })

  it("lo que nunca hace solo acaba en su propia conexión", () => {
    expect(titulos(r.nunca)).toEqual(["Abuso de cuenta", "Cambios en ficheros vigilados", "Denegación de servicio",
      "Exfiltración / C2", "Malware", "Cortar la conexión del MDR con los equipos"])
  })

  it("en quién confía", () => {
    expect(r.confianza).toBe("Se fía de 10.100.0.10, 10.100.0.20 (administradores) salvo ráfaga de 9 alertas en 60 s")
  })

  it("un servicio anterior sin confianza ni intocables no rompe", () => {
    const viejo = resumenPolitica({ familias: BANCO.familias, zonas: [] })
    expect(viejo.confianza).toBeNull()
    expect(viejo.certeza).toBeNull()
    expect(titulos(viejo.humano)).toEqual(["Explotación conocida", "Bloquear un equipo propio"])
  })

  it("si la política deja los equipos propios con certeza, no salen como espera", () => {
    const abierta = resumenPolitica({ ...BANCO, confianza: { ...BANCO.confianza!, equipos_propios: "automatica_si_confianza" } })
    expect(titulos(abierta.humano)).not.toContain("Bloquear un equipo propio")
  })

  it("sin familias en automático, la columna verde queda vacía", () => {
    const todo = resumenPolitica({ ...BANCO, familias: [fam("reconocimiento", "humano_siempre", "BLOQUEAR_IP")] })
    expect(todo.solo).toEqual([])
    expect(todo.frase).toContain("contiene 0 solo")
  })
})

describe("resumenPolitica: lo que el motor hace de verdad", () => {
  it("un freno del código sigue en «nunca» aunque la política le ponga «con analista»", () => {
    const r = resumenPolitica({ ...BANCO, familias: [{ ...fam("malware", "nunca_automatica", "AISLAR_NODO"), automatizacion_efectiva: "humano_siempre" }] })
    expect(titulos(r.nunca)).toContain("Malware")
    expect(titulos(r.humano)).not.toContain("Malware")
  })

  it("si los externos desconocidos esperan a un analista, el bloqueo del origen deja de ser automático", () => {
    const r = resumenPolitica({ ...BANCO, confianza: { ...BANCO.confianza!, externos_desconocidos: "humano_siempre" } })
    expect(r.solo).toEqual([])
    expect(r.humano[0]).toEqual({ titulo: "Fuerza bruta", detalle: "bloquea el origen · con un atacante externo, espera a un analista" })
    expect(r.frase).toContain("contiene 0 solo")
  })

  it("una zona o un equipo en HUMANO salen como espera", () => {
    const r = resumenPolitica({ ...BANCO, zonas: [
      { zona: "Core", automatizacion: "humano_siempre", protegida: false, dispositivos: [] },
      { zona: "DMZ", automatizacion: "automatica_si_confianza", protegida: false, dispositivos: [
        { activo: "web", override: "humano_siempre", cascada: [], radio: 0, cascada_posiblemente_incompleta: false },
        { activo: "api", override: null, cascada: [], radio: 0, cascada_posiblemente_incompleta: false }] },
      { zona: "SOC", automatizacion: "humano_siempre", protegida: true, dispositivos: [] }] })
    expect(titulos(r.humano)).toContain("Zona Core: todo espera a un analista")
    expect(titulos(r.humano)).toContain("Equipo web: todo espera a un analista")
    expect(titulos(r.humano).join()).not.toContain("api")
    expect(titulos(r.humano).join()).not.toContain("SOC")      // la de gestión ya sale en «nunca»
  })
})

describe("intocablesDe", () => {
  it("los puertos intocables de un equipo", () => {
    expect(intocablesDe(BANCO, "core-db")).toEqual([1521])
    expect(intocablesDe(BANCO, "otro")).toEqual([])
    expect(intocablesDe({ familias: [], zonas: [] }, "core-db")).toEqual([])
  })
})
