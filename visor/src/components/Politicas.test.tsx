import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"

const h = vi.hoisted(() => ({ pol: {} as unknown, act: vi.fn(), explicar: vi.fn(), propuesta: vi.fn() }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: () => h.pol,
  actualizarPolitica: (...a: unknown[]) => h.act(...a),
  getPoliticaExplicar: () => h.explicar(),
  getPoliticaPropuesta: () => h.propuesta(),
}))
import { Politicas } from "./Politicas"

const F = [
  { familia: "acceso_credenciales", clase_tipica: "vp_intento_acceso", accion: "BLOQUEAR_IP", impacto: "localizado",
    automatizacion: "automatica_si_confianza", automatizacion_efectiva: "automatica_si_confianza", mitre: ["T1110"],
    nivel: "actuar", ruta: null, vetos: ["requiere la IP de origen en el evento"], recomendacion: { respuesta: "contener_origen", nota: "" } },
  { familia: "malware", clase_tipica: "vp_integridad", accion: "AISLAR_NODO", impacto: "alcanza_servicio",
    automatizacion: "nunca_automatica", automatizacion_efectiva: "nunca_automatica", mitre: ["T1565"],
    nivel: "actuar", ruta: null, vetos: ["nunca automática (guard duro del catálogo)"], recomendacion: null },
  { familia: "reconocimiento", clase_tipica: "vp_reconocimiento", accion: null, impacto: null,
    automatizacion: "requiere_humano", automatizacion_efectiva: "requiere_humano", mitre: [],
    nivel: "triar_y_enrutar", ruta: "analista", vetos: [], recomendacion: null },
]
const Z = [
  { zona: "dmz", automatizacion: "automatica_si_confianza", protegida: false, dispositivos: [
    { activo: "srv-web", criticidad: "alta", override: null, postura_efectiva: "automatica_si_confianza",
      cascada: ["db-1"], radio: 1, cascada_posiblemente_incompleta: false }] },
  { zona: "gestion", automatizacion: "humano_siempre", protegida: true, dispositivos: [] },
]

describe("Politicas", () => {
  beforeEach(() => { h.act.mockReset(); h.act.mockResolvedValue(undefined); h.pol = { familias: F, zonas: Z } })

  it("familias: toggles, destructiva bloqueada con razón y nota de interferencia", () => {
    render(<Politicas />)
    expect(screen.getByText("acceso_credenciales")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "acceso_credenciales HUMANO" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "malware AUTO" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "malware HUMANO" })).toBeDisabled()
    expect(screen.getByText(/freno duro/i)).toBeInTheDocument()
    expect(screen.getByText(/se tría y enruta/i)).toBeInTheDocument()
    expect(screen.getByText(/también depende de la zona/i)).toBeInTheDocument()
  })

  it("alternar una familia llama a actualizarPolitica", async () => {
    render(<Politicas />)
    fireEvent.click(screen.getByRole("button", { name: "acceso_credenciales HUMANO" }))
    await waitFor(() => expect(h.act).toHaveBeenCalledWith(
      { dimension: "familia", clave: "acceso_credenciales", automatizacion: "humano_siempre" }))
  })

  it("zonas: postura por zona, protegida sin control, override por dispositivo", async () => {
    render(<Politicas />)
    fireEvent.click(screen.getByRole("tab", { name: /Por zona y dispositivo/ }))
    expect(screen.getByText(/también depende de la familia/i)).toBeInTheDocument()
    expect(screen.getByText(/protegido · no_cortar_gestion/)).toBeInTheDocument()
    expect(screen.getByText("srv-web")).toBeInTheDocument()
    expect(screen.getByText(/alta/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "zona dmz HUMANO" }))
    await waitFor(() => expect(h.act).toHaveBeenCalledWith(
      { dimension: "zona", clave: "dmz", automatizacion: "humano_siempre" }))
    fireEvent.click(screen.getByRole("button", { name: "srv-web HEREDA" }))
    await waitFor(() => expect(h.act).toHaveBeenCalledWith(
      { dimension: "activo", clave: "srv-web", automatizacion: null }))
  })

  it("zona protegida: sus dispositivos no ofrecen override", () => {
    h.pol = { familias: F, zonas: [{ ...Z[1], dispositivos: [
      { activo: "jump-1", criticidad: "alta", override: null, postura_efectiva: "humano_siempre", cascada: [], radio: 0, cascada_posiblemente_incompleta: false }] }] }
    render(<Politicas />)
    fireEvent.click(screen.getByRole("tab", { name: /Por zona y dispositivo/ }))
    expect(screen.getByText("jump-1")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /jump-1 (HEREDA|AUTO|HUMANO)/ })).toBeNull()
  })

  it("el valor optimista se poda al confirmarlo el servidor y no tapa cambios posteriores", async () => {
    const { rerender } = render(<Politicas />)
    fireEvent.click(screen.getByRole("button", { name: "acceso_credenciales HUMANO" }))
    await waitFor(() => expect(h.act).toHaveBeenCalled())
    const con = (a: string) => ({ familias: [{ ...F[0], automatizacion: a, automatizacion_efectiva: a }, F[1], F[2]], zonas: Z })
    h.pol = con("humano_siempre"); rerender(<Politicas />)
    h.pol = con("automatica_si_confianza"); rerender(<Politicas />)
    await waitFor(() => expect(screen.getByRole("button", { name: "acceso_credenciales AUTO" }).getAttribute("aria-pressed")).toBe("true"))
  })

  it("detalle de la familia seleccionada", () => {
    render(<Politicas />)
    fireEvent.click(screen.getByRole("button", { name: "Detalle malware" }))
    expect(screen.getByText(/alcanza_servicio/)).toBeInTheDocument()
  })

  it("403 muestra el mensaje de token de operador", async () => {
    h.act.mockRejectedValue(new Error("HTTP 403"))
    render(<Politicas />)
    fireEvent.click(screen.getByRole("button", { name: "acceso_credenciales HUMANO" }))
    expect(await screen.findByText(/editar requiere token de operador/i)).toBeInTheDocument()
  })

  it("vacío lo dice", () => {
    h.pol = { familias: [], zonas: [] }
    render(<Politicas />)
    expect(screen.getByText(/Sin políticas que mostrar/)).toBeInTheDocument()
  })
})

// politica.yml en la vista (plan de la política de la empresa, tarea 5)
const CAB = { version: 3, aprobada_por: "Dirección de Seguridad", fecha: "2026-11-10", ruta: "/etc/mdr/politica.yml", huella: "9f3c" + "0".repeat(60) }
const CONF = { administradores: ["10.99.0.10"], socios_criticos: ["203.0.113.7"], rafaga: { alertas: 9, en_segundos: 60 },
  certeza_minima: 0.9, revisar_desde_nivel: 10, origen: "fichero" }
const DIF = { dimension: "familia", clave: "acceso_credenciales", antes: "automatica_si_confianza", despues: "humano_siempre", operador: "ana.perez", en: "2026-11-11T10:40:00+00:00" }
const conPolitica = (extra = {}) => ({
  familias: [{ ...F[0], origen: "consola" }, { ...F[1], origen: "codigo" }, { ...F[2], origen: "fichero" }],
  zonas: [{ ...Z[0], origen: "fichero", dispositivos: Z[0].dispositivos.map((d) => ({ ...d, origen: "por_defecto" })) }, { ...Z[1], origen: "codigo" }],
  politica: CAB, diferencias: [DIF], confianza: CONF, intocables: [{ activo: "db01", servicio: 5432, origen: "fichero" }], ...extra })

describe("Politicas con politica.yml", () => {
  beforeEach(() => {
    h.act.mockReset(); h.act.mockResolvedValue(undefined)
    h.explicar.mockReset(); h.explicar.mockResolvedValue({ frases: ["Sobre db01, una contención espera siempre a un analista."] })
    h.propuesta.mockReset(); h.propuesta.mockResolvedValue({ version: 4, yaml: "politica:\n  version: 4\n" })
    h.pol = conPolitica()
  })

  it("franja de la política vigente", () => {
    render(<Politicas />)
    expect(screen.getByText(/versión 3/)).toBeInTheDocument()
    expect(screen.getByText(/Dirección de Seguridad/)).toBeInTheDocument()
    expect(screen.getByText(/\/etc\/mdr\/politica.yml/)).toBeInTheDocument()
  })

  it("sin politica.yml lo dice", () => {
    h.pol = conPolitica({ politica: null, diferencias: [] })
    render(<Politicas />)
    expect(screen.getByText(/Sin politica\.yml/)).toBeInTheDocument()
  })

  it("cada fila dice de dónde sale su valor", () => {
    render(<Politicas />)
    expect(screen.getByLabelText("acceso_credenciales: origen consola")).toBeInTheDocument()
    expect(screen.getByLabelText("malware: origen código")).toBeInTheDocument()
    expect(screen.getByLabelText("reconocimiento: origen política v3")).toBeInTheDocument()
  })

  it("aviso de cambios de consola y volver a la política", async () => {
    render(<Politicas />)
    expect(screen.getByText(/1 cambio hecho en la consola/)).toBeInTheDocument()
    expect(screen.getByText(/ana\.perez/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Volver a la política: acceso_credenciales" }))
    await waitFor(() => expect(h.act).toHaveBeenCalledWith({ dimension: "familia", clave: "acceso_credenciales", automatizacion: null }))
  })

  it("pestaña Confianza", () => {
    render(<Politicas />)
    fireEvent.click(screen.getByRole("tab", { name: "Confianza" }))
    expect(screen.getByText("10.99.0.10")).toBeInTheDocument()
    expect(screen.getByText("203.0.113.7")).toBeInTheDocument()
    expect(screen.getByText(/9 alertas en 60 s/)).toBeInTheDocument()
  })

  it("pestaña Intocables", () => {
    render(<Politicas />)
    fireEvent.click(screen.getByRole("tab", { name: "Intocables" }))
    expect(screen.getByText(/db01 · 5432/)).toBeInTheDocument()
    expect(screen.getByText(/malware/)).toBeInTheDocument()       // los frenos duros del código también
  })

  it("pestaña En castellano pide la explicación", async () => {
    render(<Politicas />)
    fireEvent.click(screen.getByRole("tab", { name: "En castellano" }))
    expect(await screen.findByText(/Sobre db01, una contención espera siempre a un analista/)).toBeInTheDocument()
  })

  it("exportar la propuesta descarga el YAML", async () => {
    const crear = vi.fn(() => "blob:x"); const soltar = vi.fn()
    Object.assign(URL, { createObjectURL: crear, revokeObjectURL: soltar })
    render(<Politicas />)
    fireEvent.click(screen.getByRole("button", { name: /Exportar propuesta/ }))
    await waitFor(() => expect(h.propuesta).toHaveBeenCalled())
    await waitFor(() => expect(crear).toHaveBeenCalled())
  })
})

