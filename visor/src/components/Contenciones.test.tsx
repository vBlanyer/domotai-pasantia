import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"

// useSondeo devuelve por fuente; setPausa/revertirTodo son espías.
const h = vi.hoisted(() => ({
  fuentes: new Map<unknown, unknown>(),
  setPausa: vi.fn(async () => true),
  revertirTodo: vi.fn(async () => ({ revertidas: 2, fallidas: 0 })),
  revertirUna: vi.fn(async () => ({ revertida: true })),
}))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: (fn: unknown) => h.fuentes.get(fn),
  setPausa: h.setPausa,
  revertirTodo: h.revertirTodo,
  revertirUna: h.revertirUna,
}))
import { getContenciones, getPausa } from "@/api"
import { Contenciones } from "./Contenciones"

const BLOQUEOS = [
  { id_decision: "s1", indice: 3, objetivo: "198.51.100.10", ip: "198.51.100.10", activo: "api-movil", nodo: "api-movil", accion_id: "BLOQUEAR_IP", ts: "t", via_escalada: false },
  { id_decision: "s7", indice: 9, objetivo: "backdoor", usuario: "backdoor", ip: null, activo: "web-banking", nodo: "web-banking", accion_id: "FORZAR_CAMBIO_PASS", ts: "t" },
]

describe("Contenciones activas + kill switch", () => {
  beforeEach(() => { h.fuentes.clear(); h.setPausa.mockClear(); h.revertirTodo.mockClear(); h.revertirUna.mockClear() })

  it("lista las contenciones activas (IP, cuenta o servicio)", () => {
    h.fuentes.set(getContenciones, BLOQUEOS)
    h.fuentes.set(getPausa, { pausada: false })
    render(<Contenciones />)
    expect(screen.getByText("2 contenciones activas")).toBeInTheDocument()
    expect(screen.getByText("198.51.100.10")).toBeInTheDocument()
    expect(screen.getByText("backdoor")).toBeInTheDocument()
    expect(screen.getByText("FORZAR_CAMBIO_PASS")).toBeInTheDocument()
  })

  it("el toggle pausa la automatización cuando está activa", () => {
    h.fuentes.set(getContenciones, [])
    h.fuentes.set(getPausa, { pausada: false })
    render(<Contenciones />)
    fireEvent.click(screen.getByRole("button", { name: "Pausar automatización" }))
    expect(h.setPausa).toHaveBeenCalledWith(true)
  })

  it("en pausa, el toggle ofrece reanudar", () => {
    h.fuentes.set(getContenciones, [])
    h.fuentes.set(getPausa, { pausada: true })
    render(<Contenciones />)
    fireEvent.click(screen.getByRole("button", { name: "Reanudar automatización" }))
    expect(h.setPausa).toHaveBeenCalledWith(false)
  })

  it("«Revertir todo» pide confirmación y entonces revierte", async () => {
    h.fuentes.set(getContenciones, BLOQUEOS)
    h.fuentes.set(getPausa, { pausada: false })
    render(<Contenciones />)
    fireEvent.click(screen.getByRole("button", { name: "Revertir todo" }))
    expect(h.revertirTodo).not.toHaveBeenCalled()                 // aún no: solo pidió confirmación
    fireEvent.click(screen.getByRole("button", { name: "Sí, revertir" }))
    expect(h.revertirTodo).toHaveBeenCalled()
    await waitFor(() => expect(screen.getByText(/Revertidas 2/)).toBeInTheDocument())
  })

  it("«Revertir todo» está deshabilitado sin contenciones activas", () => {
    h.fuentes.set(getContenciones, [])
    h.fuentes.set(getPausa, { pausada: false })
    render(<Contenciones />)
    expect(screen.getByRole("button", { name: "Revertir todo" })).toBeDisabled()
  })

  it("cada fila puede revertir SOLO su contención, con confirmación", async () => {
    h.fuentes.set(getContenciones, BLOQUEOS)
    h.fuentes.set(getPausa, { pausada: false })
    render(<Contenciones />)
    // dos botones por fila: uno por contención activa
    const botones = screen.getAllByRole("button", { name: "Revertir" })
    expect(botones).toHaveLength(2)
    fireEvent.click(botones[1])                                   // la fila de 'backdoor' (índice 9)
    expect(h.revertirUna).not.toHaveBeenCalled()                 // aún no: pide confirmación
    fireEvent.click(screen.getByRole("button", { name: "Sí" }))
    expect(h.revertirUna).toHaveBeenCalledWith(9)                // revierte por el índice de traza
  })
})
