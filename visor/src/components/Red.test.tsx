import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

const h = vi.hoisted(() => ({ fuentes: new Map<unknown, unknown>() }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: (fn: unknown) => h.fuentes.get(fn),
}))
import { getRed, getTrazas } from "@/api"
import { Red } from "./Red"

const act = (estado: string, extra = {}) => ({ objetivo: 0, origen: 0, contuvo_aqui: 0, pendientes: 0, estado, ...extra })
const RED = {
  nodos: [{ nombre: "fw-core", tipo: "cortafuegos", zona: null, actividad: act("contenido", { contuvo_aqui: 1 }) },
          { nombre: "web-banking", tipo: "servidor", zona: "DMZ", ip: "10.10.0.10", funcion: "banca en línea",
            criticidad: "alta", depende_de: ["middleware"], actividad: act("atacado", { objetivo: 2 }) }],
  enlaces: [["web-banking", "fw-core"]], dependencias: [], zonas: [{ nombre: "DMZ", nodos: ["web-banking"] }],
}
const TRAZAS = [
  { id_decision: "s1", indice: 0, timestamp: "2026-09-30T10:00:00Z", activo: "web-banking", origen_ip: "198.51.100.10",
    clase: "vp_intento_acceso", contencion: "contenida", dispositivo: "fw-core",
    relaciones: { "web-banking": ["objetivo"], "fw-core": ["contuvo_aqui"] } },
  { id_decision: "s2", indice: 1, timestamp: "2026-09-30T10:05:00Z", activo: "web-banking", origen_ip: "10.200.0.10",
    clase: "vp_intento_acceso", contencion: "sin_accion", relaciones: { "web-banking": ["objetivo"] } },
  { id_decision: "s3", indice: 2, timestamp: "2026-09-30T10:06:00Z", activo: "api-movil", clase: "fp_actividad_legitima",
    relaciones: { "api-movil": ["objetivo"] } },
]

describe("Red", () => {
  beforeEach(() => { h.fuentes.clear(); h.fuentes.set(getRed, RED); h.fuentes.set(getTrazas, TRAZAS) })

  it("sin selección invita a pulsar un equipo", () => {
    render(<Red onVerDecisiones={() => {}} />)
    expect(screen.getByText(/Pulsa un equipo/)).toBeInTheDocument()
  })

  it("al pulsar un equipo muestra su ficha y solo sus eventos, etiquetados", () => {
    render(<Red onVerDecisiones={() => {}} />)
    fireEvent.click(screen.getByRole("button", { name: /web-banking/ }))
    expect(screen.getByText("banca en línea")).toBeInTheDocument()
    expect(screen.getByText(/2 recibidos/)).toBeInTheDocument()
    expect(screen.getByText("198.51.100.10")).toBeInTheDocument()
    expect(screen.getByText(/contenida en fw-core/)).toBeInTheDocument()
    expect(screen.queryByText("fp_actividad_legitima")).not.toBeInTheDocument()
    expect(screen.getAllByText("objetivo").length).toBe(2)
  })

  it("el cortafuegos muestra lo que contuvo", () => {
    render(<Red onVerDecisiones={() => {}} />)
    fireEvent.click(screen.getByRole("button", { name: /fw-core/ }))
    expect(screen.getByText("contuvo aquí")).toBeInTheDocument()
  })

  it("«Ver en Decisiones» pasa el equipo", () => {
    const ver = vi.fn()
    render(<Red onVerDecisiones={ver} />)
    fireEvent.click(screen.getByRole("button", { name: /web-banking/ }))
    fireEvent.click(screen.getByRole("button", { name: /Ver en Decisiones/ }))
    expect(ver).toHaveBeenCalledWith("web-banking")
  })

  it("sin conexión con la API enseña el aviso", () => {
    h.fuentes.set(getRed, { error: "HTTP 500" })
    render(<Red onVerDecisiones={() => {}} />)
    expect(screen.getByText(/conexión/i)).toBeInTheDocument()
  })
})
