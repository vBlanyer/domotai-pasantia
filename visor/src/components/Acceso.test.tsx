import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react"

const h = vi.hoisted(() => ({ respuesta: null as unknown }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  comprobarSesion: vi.fn(async () => h.respuesta),
}))
import { Acceso, ChipSesion } from "./Acceso"
import { comprobarSesion, tokenActual, fijarToken, operadorActual, fijarOperador } from "@/api"

const escribir = (v: string) => fireEvent.change(screen.getByLabelText("Token de operador"), { target: { value: v } })
const entrar = () => fireEvent.click(screen.getByRole("button", { name: "Entrar" }))

describe("pantalla de acceso", () => {
  beforeEach(() => { fijarToken("", false); sessionStorage.clear(); vi.mocked(comprobarSesion).mockClear() })

  it("un token por persona entra identificado y queda en la pestaña", async () => {
    h.respuesta = { tipo: "ok", requiereToken: true, operador: "ana" }
    const onEntrar = vi.fn()
    render(<Acceso onEntrar={onEntrar} />)
    escribir("tok-ana"); entrar()
    await waitFor(() => expect(onEntrar).toHaveBeenCalledWith({ modo: "identificado", operador: "ana" }))
    expect(comprobarSesion).toHaveBeenCalledWith("tok-ana")
    expect(sessionStorage.getItem("mdr.token")).toBe("tok-ana")
  })

  it("sin «mantener la sesión» el token vive solo en memoria", async () => {
    h.respuesta = { tipo: "ok", requiereToken: true, operador: null }
    const onEntrar = vi.fn()
    render(<Acceso onEntrar={onEntrar} />)
    fireEvent.click(screen.getByRole("checkbox", { name: /Mantener la sesión/ }))
    escribir("compartido"); entrar()
    await waitFor(() => expect(onEntrar).toHaveBeenCalledWith({ modo: "compartido", operador: null }))
    expect(sessionStorage.getItem("mdr.token")).toBeNull()
    expect(tokenActual()).toBe("compartido")
  })

  it("un token rechazado lo explica y no se guarda", async () => {
    h.respuesta = { tipo: "rechazado" }
    const onEntrar = vi.fn()
    render(<Acceso onEntrar={onEntrar} />)
    escribir("malo"); entrar()
    expect(await screen.findByRole("alert")).toHaveTextContent("El daemon no reconoce ese token.")
    expect(onEntrar).not.toHaveBeenCalled()
    expect(tokenActual()).toBe("")
  })

  describe("con reloj simulado", () => {
    beforeEach(() => { vi.useFakeTimers() })
    afterEach(() => { vi.useRealTimers() })
    it("demasiados intentos bloquea el botón con cuenta atrás", () => {
      render(<Acceso motivo="bloqueado" segundos={3} onEntrar={vi.fn()} />)
      escribir("otro")
      expect(screen.getByRole("alert")).toHaveTextContent("Demasiados intentos.")
      expect(screen.getByRole("button", { name: /Entrar · 0:03/ })).toBeDisabled()
      act(() => { vi.advanceTimersByTime(3000) })
      expect(screen.queryByRole("alert")).not.toBeInTheDocument()
      expect(screen.getByRole("button", { name: "Entrar" })).toBeEnabled()
    })
  })

  it("si el daemon no responde lo dice: el problema no es el token", () => {
    render(<Acceso motivo="sin_red" onEntrar={vi.fn()} />)
    expect(screen.getByRole("alert")).toHaveTextContent("No hay respuesta del servicio MDR")
    expect(screen.getByText("Sin respuesta del daemon")).toBeInTheDocument()
  })

  it("con la consola abierta pide el nombre y avisa de que no se verifica", () => {
    fijarOperador("")
    const onNombre = vi.fn()
    render(<Acceso pedirNombre="abierta" onEntrar={vi.fn()} onNombre={onNombre} />)
    expect(screen.getByRole("note")).toHaveTextContent("Este daemon no exige token.")
    fireEvent.change(screen.getByLabelText("Tu nombre"), { target: { value: "ana.ruiz" } })
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }))
    expect(onNombre).toHaveBeenCalled()
    expect(operadorActual()).toBe("ana.ruiz")
    fijarOperador("")
  })
})

describe("chip de sesión", () => {
  it("dice quién firma y cómo; cerrar sesión solo si hay token", () => {
    const onCerrar = vi.fn()
    const { rerender } = render(<ChipSesion sesion={{ modo: "identificado", operador: "ana.ruiz", desde: Date.now() }} nombre="ana.ruiz" onCerrar={onCerrar} onCambiarNombre={vi.fn()} />)
    fireEvent.click(screen.getByRole("button", { name: "Sesión de ana.ruiz" }))
    expect(screen.getByRole("menu")).toHaveTextContent("Operador identificado por token")
    expect(screen.queryByRole("menuitem", { name: /Cambiar nombre/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("menuitem", { name: /Cerrar sesión/ }))
    expect(onCerrar).toHaveBeenCalled()
    rerender(<ChipSesion sesion={{ modo: "abierta", operador: "", desde: Date.now() }} nombre="leo" onCerrar={onCerrar} onCambiarNombre={vi.fn()} />)
    fireEvent.click(screen.getByRole("button", { name: "Sesión de leo" }))
    expect(screen.getByRole("menuitem", { name: /Cambiar nombre/ })).toBeInTheDocument()
    expect(screen.queryByRole("menuitem", { name: /Cerrar sesión/ })).not.toBeInTheDocument()
  })
})
