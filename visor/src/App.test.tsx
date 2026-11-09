import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, act, within } from "@testing-library/react"

// La puerta de acceso: nada de la consola se monta hasta entrar; dentro, un 401 pide volver a entrar.
const h = vi.hoisted(() => ({ respuesta: null as unknown, fuentes: new Map<unknown, unknown>() }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  comprobarSesion: vi.fn(async () => h.respuesta),
  useSondeo: (fn: unknown) => h.fuentes.get(fn),
}))
import AppReal from "./App"
import { Toaster } from "@/components/ui/toast"
const App = () => <Toaster><AppReal /></Toaster>
import { fijarToken, fijarOperador, EVENTO_NO_AUTORIZADO, cerrarSesion, tokenActual, getSalud, getConectividad, getPendientes } from "@/api"

// Montar la consola entera tarda bajo carga (suite en paralelo): las esperas llevan margen.
describe("puerta de acceso", () => {
  beforeEach(() => { cerrarSesion(); sessionStorage.clear(); fijarOperador(""); h.fuentes.clear() })

  it("con token exigido y sin token, solo la pantalla de acceso", async () => {
    h.respuesta = { tipo: "rechazado" }
    render(<App />)
    expect(await screen.findByRole("heading", { name: "Entrar a la consola" }, { timeout: 5000 })).toBeInTheDocument()
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
    expect(await screen.findByText("Consola abierta.", undefined, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Sesión de leo" })).toBeInTheDocument()
  })

  it("identificado: nombre en la cabecera, un 401 pide volver a entrar y cerrar sesión borra el token", async () => {
    fijarToken("tok-ana")
    h.respuesta = { tipo: "ok", requiereToken: true, operador: "ana" }
    render(<App />)
    expect(await screen.findByRole("button", { name: "Sesión de ana" }, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.queryByText("Consola abierta.")).not.toBeInTheDocument()
    act(() => { window.dispatchEvent(new Event(EVENTO_NO_AUTORIZADO)) })
    expect(await screen.findByRole("dialog", { name: "Volver a entrar" })).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Salir a la pantalla de acceso" }))
    expect(screen.getByRole("heading", { name: "Entrar a la consola" })).toBeInTheDocument()
    expect(tokenActual()).toBe("")
  })
})

describe("menú: icono de «Estado de servicios»", () => {
  beforeEach(() => { cerrarSesion(); sessionStorage.clear(); fijarOperador("ana"); h.fuentes.clear() })
  const entrar = async () => {
    h.respuesta = { tipo: "ok", requiereToken: false, operador: null }
    render(<App />)
    const nav = await screen.findByRole("navigation", undefined, { timeout: 5000 })
    return within(nav).getByRole("button", { name: "Estado de servicios" })
  }

  it("se pone rojo con equipos con problemas de configuración y dice por qué", { timeout: 15000 }, async () => {
    h.fuentes.set(getSalud, { t: null, total: 7, caidos: 0, servicios: [] })
    h.fuentes.set(getConectividad, { modo: "clave", equipos: [
      { nombre: "atm", ip: "10.210.0.10", protegido: false, puerto: 22, usuario: "triaje", ajustado: false, huella_fijada: null, ultima_prueba: null },
    ] })
    const boton = await entrar()
    expect(boton).toHaveAttribute("title", "1 equipo con problemas de conexión o configuración")
    expect(boton.querySelector("svg")).toHaveClass("text-critico")
  })

  it("con todo en orden, el color de siempre", { timeout: 15000 }, async () => {
    h.fuentes.set(getSalud, { t: null, total: 7, caidos: 0, servicios: [] })
    h.fuentes.set(getConectividad, { modo: "clave", equipos: [] })
    const boton = await entrar()
    expect(boton).not.toHaveAttribute("title")
    expect(boton.querySelector("svg")).not.toHaveClass("text-critico")
  })
})

describe("pie del menú: atribución de DB-IP", () => {
  beforeEach(() => { cerrarSesion(); sessionStorage.clear(); fijarOperador("ana"); h.fuentes.clear() })
  const pendiente = (asn: Record<string, string> | null) => [{ id: "1", tipo: "decision", prompt: "", lineas: [], severidad: 3,
    enriquecimiento_origen: { alcance: "externo", inventariado: false, clasificacion_ip: "publica", tercero_confiable: false,
      legitimo: false, geolocalizable: true, geo: null, asn } }]

  it("con datos de DB-IP en pantalla enlaza su atribución, que exige su licencia", { timeout: 15000 }, async () => {
    h.fuentes.set(getPendientes, pendiente({ asn: "AS15169", org: "Google LLC", fuente: "dbip" }))
    h.respuesta = { tipo: "ok", requiereToken: false, operador: null }
    render(<App />)
    const enlace = await screen.findByRole("link", { name: "IP Geolocation by DB-IP" }, { timeout: 5000 })
    expect(enlace).toHaveAttribute("href", "https://db-ip.com")
  })

  it("sin datos de DB-IP no hay enlace", { timeout: 15000 }, async () => {
    h.fuentes.set(getPendientes, pendiente({ asn: "AS15169", org: "Google LLC", fuente: "csv" }))
    h.respuesta = { tipo: "ok", requiereToken: false, operador: null }
    render(<App />)
    await screen.findByRole("navigation", undefined, { timeout: 5000 })
    expect(screen.queryByRole("link", { name: "IP Geolocation by DB-IP" })).toBeNull()
  })
})

