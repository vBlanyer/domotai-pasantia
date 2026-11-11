import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"

const h = vi.hoisted(() => ({ est: {} as unknown, escanear: vi.fn(), guardar: vi.fn(), propuesta: vi.fn() }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: () => h.est,
  escanearRed: (...a: unknown[]) => h.escanear(...a),
  guardarBorrador: (...a: unknown[]) => h.guardar(...a),
  getPropuestaRed: () => h.propuesta(),
}))
vi.mock("@/components/MapaRed", () => ({ MapaRed: () => <div data-testid="mapa">mapa</div> }))
import { AsistenteRed } from "./AsistenteRed"

const eq = (o: Record<string, unknown>) => ({
  incluido: true, nombre: "", zona: "Zona 10.20.0.0/24", papel: "servidor", criticidad: "media", no_tocar: false,
  depende_de: [], funcion: "", gateway: "10.0.0.2", interfaces: [], servicios: [22], deducido: false, sin_camino: false, huella: true, ...o,
})
const BORRADOR = {
  version: 1, basado_en: "2026-11-11T15:00:00+00:00", gestion: "10.99.0.10", redes_internas: ["10.20.0.0/24"],
  salida: ["10.99.0.1"], traceroute: true,
  equipos: {
    "10.99.0.1": eq({ nombre: "fw-borde", papel: "cortafuegos", zona: null, gateway: null, interfaces: ["172.16.10.1"] }),
    "10.0.0.2": eq({ nombre: "fw-interno", papel: "cortafuegos", zona: null, gateway: "10.99.0.1", deducido: true }),
    "10.20.0.10": eq({ nombre: "srv-app01", servicios: [22, 8443] }),
    "10.20.0.30": eq({ servicios: [22, 445] }),
    "10.20.0.77": eq({ incluido: false, papel: "desconocido", servicios: [] }),
  },
}
const ESTADO = {
  escaneando: false, error: null, borrador: BORRADOR, nombres_siem: ["nas01", "srv-web01"],
  descubrimiento: { fecha: "2026-11-11T15:00:00+00:00", operador: "ana", rangos: ["10.20.0.0/24"], externo: "198.51.100.10", equipos: [] },
  por_defecto: { gestion: "10.99.0.10", rangos: ["10.20.0.0/24", "172.16.10.0/24"] },
}
const RED = { nodos: [], enlaces: [], dependencias: [], zonas: [] }
const PROP = (errores: string[] = [], avisos: string[] = []) => ({
  perfil_yaml: "ip_gestion: 10.99.0.10\n", postura_json: "{\"nodos\": {}}", politica_yaml: "politica:\n  version: 1\n",
  validacion: { errores, avisos }, red: RED,
})

beforeEach(() => {
  h.escanear.mockReset(); h.escanear.mockResolvedValue(undefined)
  h.guardar.mockReset(); h.guardar.mockResolvedValue(BORRADOR)
  h.propuesta.mockReset(); h.propuesta.mockResolvedValue(PROP())
  h.est = ESTADO
})

describe("AsistenteRed · Escanear", () => {
  it("Escanear deshabilitado sin autorización", () => {
    h.est = { ...ESTADO, borrador: null, descubrimiento: null }
    render(<AsistenteRed />)
    fireEvent.change(screen.getByLabelText(/Dirección de fuera/), { target: { value: "198.51.100.10" } })
    expect(screen.getByRole("button", { name: "Escanear" })).toBeDisabled()
    fireEvent.click(screen.getByLabelText(/autorización por escrito/))
    expect(screen.getByRole("button", { name: "Escanear" })).toBeEnabled()
  })

  it("envía rangos, externo, ritmo y puertos", async () => {
    h.est = { ...ESTADO, borrador: null, descubrimiento: null }
    render(<AsistenteRed />)
    fireEvent.click(screen.getByRole("button", { name: "Quitar 172.16.10.0/24" }))
    fireEvent.change(screen.getByLabelText(/Dirección de fuera/), { target: { value: "198.51.100.10" } })
    fireEvent.click(screen.getByLabelText(/Normal/))
    fireEvent.click(screen.getByLabelText(/autorización por escrito/))
    fireEvent.click(screen.getByRole("button", { name: "Escanear" }))
    await waitFor(() => expect(h.escanear).toHaveBeenCalledWith({
      rangos: ["10.20.0.0/24"], externo: "198.51.100.10", ritmo: "normal", puertos: "comunes", autorizado: true,
    }))
  })

  it("muestra el error del último escaneo y el escaneo en marcha", () => {
    h.est = { ...ESTADO, borrador: null, descubrimiento: null, error: "nmap falló (1): QUITTING!" }
    const { unmount } = render(<AsistenteRed />)
    expect(screen.getByText(/QUITTING/)).toBeInTheDocument()
    unmount()
    h.est = { ...ESTADO, borrador: null, descubrimiento: null, escaneando: true }
    render(<AsistenteRed />)
    expect(screen.getByText(/Escaneando/)).toBeInTheDocument()
  })
})

describe("AsistenteRed · Revisar", () => {
  it("la tabla sale del borrador y sugiere nombres del SIEM", async () => {
    render(<AsistenteRed />)
    expect(screen.getByDisplayValue("srv-app01")).toBeInTheDocument()
    expect(screen.getByText("8443")).toBeInTheDocument()
    expect(screen.getAllByText(/fw-interno/).length).toBeGreaterThan(0)          // «llega por»
    const lista = document.getElementById("nombres-siem")!
    expect(lista.querySelectorAll("option")).toHaveLength(2)
    expect(await screen.findByTestId("mapa")).toBeInTheDocument()
  })

  it("cambiar el nombre guarda el borrador", async () => {
    render(<AsistenteRed />)
    const campo = screen.getByLabelText("Nombre en el SIEM de 10.20.0.30")
    fireEvent.change(campo, { target: { value: "nas01" } })
    await waitFor(() => expect(h.guardar).toHaveBeenCalledWith({ "10.20.0.30": { nombre: "nas01" } }), { timeout: 2000 })
  })

  it("lo que falta para exportar son los errores de la validación", async () => {
    h.propuesta.mockResolvedValue(PROP(["10.20.0.30: falta su nombre en el SIEM"]))
    render(<AsistenteRed />)
    expect(await screen.findByText(/falta su nombre en el SIEM/)).toBeInTheDocument()
  })
})

describe("AsistenteRed · lo revisado llega a la propuesta", () => {
  it("tras guardar, la propuesta se vuelve a pedir y refleja el cambio", async () => {
    h.propuesta.mockResolvedValueOnce(PROP(["10.20.0.30: falta su nombre en el SIEM"])).mockResolvedValue(PROP())
    const guardado = { ...BORRADOR, equipos: { ...BORRADOR.equipos, "10.20.0.30": { ...BORRADOR.equipos["10.20.0.30"], nombre: "nas01" } } }
    h.guardar.mockResolvedValue(guardado)
    render(<AsistenteRed />)
    expect(await screen.findByText(/falta su nombre en el SIEM/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText("Nombre en el SIEM de 10.20.0.30"), { target: { value: "nas01" } })
    expect(await screen.findByText(/Nada: puedes validar y exportar/, undefined, { timeout: 2500 })).toBeInTheDocument()
    const llamadasTrasGuardar = h.propuesta.mock.invocationCallOrder.filter((n) => n > h.guardar.mock.invocationCallOrder[0])
    expect(llamadasTrasGuardar.length).toBeGreaterThan(0)
  })

  it("«Depende de» deja escribir varias dependencias separadas por comas", async () => {
    render(<AsistenteRed />)
    const campo = screen.getByLabelText("Depende de (10.20.0.30)") as HTMLInputElement
    fireEvent.change(campo, { target: { value: "srv-db01," } })
    expect(campo.value).toBe("srv-db01,")
    fireEvent.change(campo, { target: { value: "srv-db01, nas01" } })
    await waitFor(() => expect(h.guardar).toHaveBeenCalledWith({ "10.20.0.30": { depende_de: ["srv-db01", "nas01"] } }), { timeout: 2000 })
  })
})

describe("AsistenteRed · Exportar", () => {
  it("con errores no deja descargar", async () => {
    h.propuesta.mockResolvedValue(PROP(["nombre repetido: x"]))
    render(<AsistenteRed />)
    fireEvent.click(screen.getByRole("tab", { name: /Validar y exportar/ }))
    expect(await screen.findByRole("button", { name: /perfil\.yml/ })).toBeDisabled()
  })

  it("descarga perfil.yml", async () => {
    const crear = vi.fn(() => "blob:x"); const soltar = vi.fn()
    Object.assign(URL, { createObjectURL: crear, revokeObjectURL: soltar })
    render(<AsistenteRed />)
    fireEvent.click(screen.getByRole("tab", { name: /Validar y exportar/ }))
    fireEvent.click(await screen.findByRole("button", { name: /perfil\.yml/ }))
    const blob = (crear.mock.calls[0] as unknown as [Blob])[0]
    expect(await blob.text()).toBe("ip_gestion: 10.99.0.10\n")
    expect(screen.getByText(/no escribe el perfil vivo/)).toBeInTheDocument()
  })

  it("avisa de los equipos fuera de la cadena", async () => {
    h.propuesta.mockResolvedValue(PROP([], ["srv-db01 está fuera de la cadena de contención: su contención va a los cortafuegos perimetrales (fw-borde)"]))
    render(<AsistenteRed />)
    fireEvent.click(screen.getByRole("tab", { name: /Validar y exportar/ }))
    expect(await screen.findByText(/srv-db01 está fuera de la cadena/)).toBeInTheDocument()
  })
})
