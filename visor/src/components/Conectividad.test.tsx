import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { Toaster } from "@/components/ui/toast"

const h = vi.hoisted(() => ({
  datos: {} as unknown,
  probar: vi.fn(), guardar: vi.fn(), defecto: vi.fn(), leer: vi.fn(), aceptar: vi.fn(),
}))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  getConectividad: async () => h.datos,
  probarConexion: h.probar, guardarConexion: h.guardar, guardarUsuarioDefecto: h.defecto,
  leerClaveHost: h.leer, aceptarClaveHost: h.aceptar,
}))
import { Conectividad } from "./Conectividad"

const PRUEBA_OK = { ok: true, estado: "verificada", en: "2026-11-04T10:00:00Z", puerto: 2222, usuario: "triaje",
  pasos: [{ paso: "entra y ejecuta un comando del catálogo", ok: true, detalle: "correctos" }, { paso: "sudo deniega lo que está fuera del catálogo", ok: true, detalle: "denegado" }] }
const equipo = (x: object) => ({ nombre: "fw-core", ip: "10.0.0.1", zona: "Borde", tipo: "cortafuegos", funcion: null, protegido: false,
  puerto: 22, usuario: "triaje", ajustado: false, huella_fijada: "SHA256:FWFIJADA", ultima_prueba: null, ...x })
const base = (x: object = {}) => ({
  modo: "clave", nodo_gestion: "clab-banco-mdr-siem", editable: true, motivo_no_editable: null,
  usuario_defecto: null, usuario_entorno: "triaje", ruta_clave: "/root/.ssh/triaje", known_hosts: "/root/.ssh/known_hosts_triaje",
  clave: { huella: "SHA256:CONECTOR", tipo: "ED25519", publica: "ssh-ed25519 AAAA conector" },
  equipos: [equipo({}), equipo({ nombre: "db-core", ip: "10.0.20.10", huella_fijada: "SHA256:DBVIEJA", ultima_prueba: { ok: false, estado: "host_cambiada", pasos: [] } }),
            equipo({ nombre: "monitor", ip: "10.0.30.3", protegido: true })],
  cambios: [], ...x,
})
const vista = () => <Toaster><Conectividad /></Toaster>
const region = () => within(screen.getByRole("region", { name: "Equipo" }))

describe("Conectividad", () => {
  beforeEach(() => { for (const f of [h.probar, h.guardar, h.defecto, h.leer, h.aceptar]) f.mockReset(); h.datos = base() })

  it("enseña el conector, su huella, el resumen y cada equipo; nunca una clave privada", async () => {
    render(vista())
    expect(await screen.findByText("SHA256:CONECTOR")).toBeInTheDocument()
    expect(screen.getByText("Clave · vía nodo de gestión")).toHaveAttribute("aria-current", "true")
    expect(screen.getByText("no se contiene")).toBeInTheDocument()                    // monitor protegido
    expect(screen.getByText("bloqueada")).toBeInTheDocument()                          // db-core
    expect(region().getByText("fw-core")).toBeInTheDocument()                          // el primero contenible
    expect(document.body.textContent).not.toMatch(/PRIVATE KEY/)
  })

  it("sin operador es solo lectura y dice por qué", async () => {
    h.datos = base({ editable: false, motivo_no_editable: "solo lectura: editar exige un operador identificado por su token" })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    expect(screen.getByLabelText("Puerto")).toBeDisabled()
    expect(screen.queryByRole("button", { name: "Probar y guardar" })).not.toBeInTheDocument()
    expect(screen.getAllByText(/editar exige un operador/).length).toBeGreaterThan(0)
  })

  it("«Probar y guardar» manda el ajuste y, si la prueba falla, enseña por qué y no guarda", async () => {
    h.guardar.mockResolvedValue({ status: 409, datos: { guardado: false, prueba: { ok: false, estado: "sin_aprovisionar",
      pasos: [{ paso: "entra y ejecuta un comando del catálogo", ok: false, detalle: "el equipo no acepta la clave del conector" }] } } })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    fireEvent.change(screen.getByLabelText("Puerto"), { target: { value: "2222" } })
    fireEvent.click(screen.getByRole("button", { name: "Probar y guardar" }))
    await waitFor(() => expect(h.guardar).toHaveBeenCalledWith("fw-core", { puerto: 2222, usuario: null }))
    expect(await screen.findByText("el equipo no acepta la clave del conector")).toBeInTheDocument()
    expect(await screen.findByText("No se guardó: la prueba falló")).toBeInTheDocument()
  })

  it("«Probar sin guardar» enseña los pasos", async () => {
    h.probar.mockResolvedValue({ status: 200, datos: PRUEBA_OK })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    fireEvent.click(screen.getByRole("button", { name: "Probar sin guardar" }))
    expect(await screen.findByText("sudo deniega lo que está fuera del catálogo")).toBeInTheDocument()
    expect(h.probar).toHaveBeenCalledWith("fw-core", { puerto: null, usuario: null })
  })

  it("una clave del host cambiada se lee, se compara y solo se acepta confirmando", async () => {
    h.leer.mockResolvedValue({ status: 200, datos: { fijada: "SHA256:DBVIEJA", presentada: "SHA256:DBNUEVA", coincide: false } })
    h.aceptar.mockResolvedValue({ status: 200, datos: { huella: "SHA256:DBNUEVA" } })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    fireEvent.click(screen.getByRole("button", { name: "Ver db-core" }))
    fireEvent.click(region().getByRole("button", { name: "Leer la clave que presenta" }))
    expect(await region().findByText("SHA256:DBNUEVA")).toBeInTheDocument()
    fireEvent.click(region().getByRole("button", { name: "Aceptar la nueva clave…" }))
    expect(h.aceptar).not.toHaveBeenCalled()
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Aceptar la nueva clave" }))
    await waitFor(() => expect(h.aceptar).toHaveBeenCalledWith("db-core", "SHA256:DBNUEVA"))
  })
})
