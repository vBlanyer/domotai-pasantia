import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, act } from "@testing-library/react"

// La puerta de acceso: nada de la consola se monta hasta entrar; dentro, un 401 pide volver a entrar.
const h = vi.hoisted(() => ({ respuesta: null as unknown }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  comprobarSesion: vi.fn(async () => h.respuesta),
  useSondeo: () => undefined,
}))
import AppReal from "./App"
import { Toaster } from "@/components/ui/toast"
const App = () => <Toaster><AppReal /></Toaster>
import { fijarToken, fijarOperador, EVENTO_NO_AUTORIZADO, cerrarSesion, tokenActual } from "@/api"

describe("puerta de acceso", () => {
  beforeEach(() => { cerrarSesion(); sessionStorage.clear(); fijarOperador("") })

  it("con token exigido y sin token, solo la pantalla de acceso", async () => {
    h.respuesta = { tipo: "rechazado" }
    render(<App />)
    expect(await screen.findByRole("heading", { name: "Entrar a la consola" })).toBeInTheDocument()
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()        // sin token no hay «rechazado» que explicar
  })

  it("un token guardado que ya no vale se explica como caducado", async () => {
    fijarToken("viejo")
    h.respuesta = { tipo: "rechazado" }
    render(<App />)
    expect(await screen.findByRole("alert")).toHaveTextContent("Tu token ya no es válido.")
  })

  it("la consola abierta entra con el nombre recordado y lo señala con la franja", async () => {
    fijarOperador("leo")
    h.respuesta = { tipo: "ok", requiereToken: false, operador: null }
    render(<App />)
    expect(await screen.findByText("Consola abierta.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Sesión de leo" })).toBeInTheDocument()
  })

  it("identificado: nombre en la cabecera, un 401 pide volver a entrar y cerrar sesión borra el token", async () => {
    fijarToken("tok-ana")
    h.respuesta = { tipo: "ok", requiereToken: true, operador: "ana" }
    render(<App />)
    expect(await screen.findByRole("button", { name: "Sesión de ana" })).toBeInTheDocument()
    expect(screen.queryByText("Consola abierta.")).not.toBeInTheDocument()
    act(() => { window.dispatchEvent(new Event(EVENTO_NO_AUTORIZADO)) })
    expect(screen.getByRole("dialog", { name: "Volver a entrar" })).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Salir a la pantalla de acceso" }))
    expect(screen.getByRole("heading", { name: "Entrar a la consola" })).toBeInTheDocument()
    expect(tokenActual()).toBe("")
  })
})
