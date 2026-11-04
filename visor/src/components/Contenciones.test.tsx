import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { Toaster } from "@/components/ui/toast"

// useSondeo devuelve por fuente; setPausa/revertir*/watchlistAgregar son espías.
const h = vi.hoisted(() => ({
  fuentes: new Map<unknown, unknown>(),
  setPausa: vi.fn(async () => true),
  revertirTodo: vi.fn(async () => ({ revertidas: 2, fallidas: 0 })),
  revertirUna: vi.fn(async () => ({ revertida: true })),
  vigilar: vi.fn(async () => []),
}))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: (fn: unknown) => h.fuentes.get(fn),
  setPausa: h.setPausa,
  revertirTodo: h.revertirTodo,
  revertirUna: h.revertirUna,
  watchlistAgregar: h.vigilar,
}))
import { getContenciones, getPausa, getTrazas } from "@/api"
import { Contenciones } from "./Contenciones"

const ahora = Date.now()
const hace = (min: number) => new Date(ahora - min * 60_000).toISOString()
const BLOQUEOS = [
  { id_decision: "s1", indice: 3, objetivo: "198.51.100.10", ip: "198.51.100.10", activo: "api-movil", nodo: "fw-core", accion_id: "BLOQUEAR_IP", ts: hace(120),
    via_escalada: false, regla: "iptables -A INPUT -s 198.51.100.10 -j DROP", reversion_cmd: "iptables -D INPUT -s 198.51.100.10 -j DROP" },
  { id_decision: "s7", indice: 9, objetivo: "backdoor", usuario: "backdoor", ip: null, activo: "web-banking", nodo: "web-banking", accion_id: "FORZAR_CAMBIO_PASS", ts: hace(60 * 24 * 9),
    regla: null, reversion_cmd: "passwd -u backdoor" },
]
const TRAZAS = [
  { indice: 3, id_decision: "s1", clase: "vp_fuerza_bruta", origen_ip: "198.51.100.10", timestamp: hace(121) },
  { indice: 20, origen_ip: "198.51.100.10", timestamp: hace(30), tipo: "actividad_suprimida", alertas_suprimidas: 5 },
]
const vista = () => <Toaster><Contenciones /></Toaster>
const inspector = () => within(screen.getByRole("region", { name: "Contención" }))
const fila = (indice: number) => document.querySelector(`[data-contencion="${indice}"]`) as HTMLElement

describe("Contenciones activas + kill switch", () => {
  beforeEach(() => {
    h.fuentes.clear(); for (const f of [h.setPausa, h.revertirTodo, h.revertirUna, h.vigilar]) f.mockClear()
    h.fuentes.set(getContenciones, BLOQUEOS); h.fuentes.set(getPausa, { pausada: false }); h.fuentes.set(getTrazas, TRAZAS)
  })

  it("lista las contenciones (IP o cuenta) con dónde se aplican y lo que lleva parado", () => {
    render(vista())
    expect(screen.getByRole("button", { name: "Revertir todas (2)…" })).toBeInTheDocument()
    expect(within(fila(3)).getByText("198.51.100.10")).toBeInTheDocument()
    expect(within(fila(3)).getByText("5 intentos parados")).toBeInTheDocument()     // supresiones después del bloqueo
    expect(within(fila(9)).getByText("backdoor")).toBeInTheDocument()
    expect(screen.getByText(/fw-core · contiene para otros equipos/)).toBeInTheDocument()
  })

  it("el inspector enseña la regla aplicada y la que la quita", () => {
    render(vista())
    expect(inspector().getByText("iptables -A INPUT -s 198.51.100.10 -j DROP")).toBeInTheDocument()
    expect(inspector().getByText("iptables -D INPUT -s 198.51.100.10 -j DROP")).toBeInTheDocument()
  })

  it("el interruptor pausa la automatización cuando está activa, y en pausa ofrece reanudar", () => {
    const { unmount } = render(vista())
    fireEvent.click(screen.getByRole("button", { name: "Pausar automatización" }))
    expect(h.setPausa).toHaveBeenCalledWith(true)
    unmount()
    h.fuentes.set(getPausa, { pausada: true })
    render(vista())
    fireEvent.click(screen.getByRole("button", { name: "Reanudar automatización" }))
    expect(h.setPausa).toHaveBeenCalledWith(false)
  })

  it("«Revertir todas» exige escribir el número antes de revertir", async () => {
    render(vista())
    fireEvent.click(screen.getByRole("button", { name: "Revertir todas (2)…" }))
    const dialogo = within(screen.getByRole("alertdialog"))
    expect(dialogo.getByRole("button", { name: "Revertir todas" })).toBeDisabled()
    fireEvent.change(dialogo.getByLabelText("Número de contenciones a revertir"), { target: { value: "3" } })
    expect(dialogo.getByRole("button", { name: "Revertir todas" })).toBeDisabled()
    fireEvent.change(dialogo.getByLabelText("Número de contenciones a revertir"), { target: { value: "2" } })
    fireEvent.click(dialogo.getByRole("button", { name: "Revertir todas" }))
    expect(h.revertirTodo).toHaveBeenCalled()
    expect(await screen.findByText(/Revertidas 2/)).toBeInTheDocument()
  })

  it("sin contenciones activas no hay nada que revertir", () => {
    h.fuentes.set(getContenciones, [])
    render(vista())
    expect(screen.getByRole("button", { name: "Revertir todas (0)…" })).toBeDisabled()
    expect(screen.getByText(/No hay contenciones activas/)).toBeInTheDocument()
  })

  it("se revierte SOLO la contención del inspector, con confirmación", async () => {
    render(vista())
    fireEvent.click(within(fila(9)).getByRole("button"))                         // abre la de 'backdoor'
    fireEvent.click(inspector().getByRole("button", { name: "Revertir…" }))
    expect(h.revertirUna).not.toHaveBeenCalled()
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Revertir" }))
    await waitFor(() => expect(h.revertirUna).toHaveBeenCalledWith(9))
    expect(h.vigilar).not.toHaveBeenCalled()
  })

  it("«Revertir y vigilar» revierte y pone la IP en la watchlist", async () => {
    render(vista())
    fireEvent.click(inspector().getByRole("button", { name: "Revertir y vigilar…" }))
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Revertir y vigilar" }))
    await waitFor(() => expect(h.vigilar).toHaveBeenCalledWith("198.51.100.10", expect.stringContaining("s1")))
    expect(h.revertirUna).toHaveBeenCalledWith(3)
  })

  it("marca las de más de 7 días y deja revertirlas aparte", () => {
    render(vista())
    expect(screen.getByRole("button", { name: "Revertir las de más de 7 días (1)…" })).toBeEnabled()
    fireEvent.click(screen.getByRole("button", { name: /Más de 7 días/ }))
    expect(document.querySelectorAll("[data-contencion]")).toHaveLength(1)
  })

  it("pagina las contenciones a 20 por página sin perder el total", () => {
    h.fuentes.set(getContenciones, Array.from({ length: 25 }, (_, i) => ({ ...BLOQUEOS[0], id_decision: `s${i}`, indice: i, objetivo: `198.51.100.${i}`, ip: `198.51.100.${i}` })))
    render(vista())
    expect(screen.getByRole("button", { name: "Revertir todas (25)…" })).toBeInTheDocument()
    const filas = () => document.querySelectorAll("[data-contencion]").length
    expect(filas()).toBe(20)
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }))
    expect(filas()).toBe(5)
  })

  it("una acción sin objetivo (aislar) nombra el equipo entero, y los filtros usan nombres legibles", () => {
    h.fuentes.set(getContenciones, [{ id_decision: "s3", indice: 4, objetivo: null, ip: null, activo: "web-banking", nodo: "web-banking", accion_id: "AISLAR_NODO", ts: hace(5) }])
    render(vista())
    expect(within(fila(4)).getByText("web-banking (equipo entero)")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /^Aislar nodo 1$/ })).toBeInTheDocument()
    expect(inspector().getByText(/web-banking vuelve a estar conectado a la red/)).toBeInTheDocument()
    expect(inspector().queryByRole("button", { name: "Revertir y vigilar…" })).not.toBeInTheDocument()
  })
})

