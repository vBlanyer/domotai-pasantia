import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"

const h = vi.hoisted(() => ({ fuentes: new Map<unknown, unknown>() }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: (fn: unknown) => h.fuentes.get(fn),
}))
import { getEquipos, getTrazas } from "@/api"
import { Equipos } from "./Equipos"

const EQUIPOS = [{ nombre: "web-banking", categoria: "servidor", ip: "10.40.0.5", criticidad: "alta", estado: "ok" }]

describe("Equipos", () => {
  beforeEach(() => { h.fuentes.clear(); h.fuentes.set(getEquipos, EQUIPOS) })

  it("si la traza no se puede leer, no da la postura por «sin actividad»", () => {
    h.fuentes.set(getTrazas, { error: "HTTP 500" })
    render(<Equipos />)
    expect(screen.getByText(/Postura de seguridad no disponible/)).toBeInTheDocument()
    expect(screen.queryByText("sin actividad")).not.toBeInTheDocument()
  })

  it("con la traza leída, la postura se calcula como siempre", () => {
    h.fuentes.set(getTrazas, [])
    render(<Equipos />)
    expect(screen.getByText("sin actividad")).toBeInTheDocument()
    expect(screen.queryByText(/Postura de seguridad no disponible/)).not.toBeInTheDocument()
  })

  it("si la traza leída es parcial, dice que la postura es de la actividad reciente", () => {
    h.fuentes.set(getTrazas, [{ indice: 10, id_decision: "s11", activo: "web-banking", clase: "vp_intento_acceso" }])
    render(<Equipos />)
    expect(screen.getByText(/últimos 1 de 11 registros/)).toBeInTheDocument()
  })

  it("el login del propio MDR no cuenta como ataque originado por su nodo", () => {
    h.fuentes.set(getEquipos, [{ nombre: "mdr-siem", categoria: "gestion", ip: "10.100.0.10", criticidad: "critica", estado: "ok" }])
    h.fuentes.set(getTrazas, [{ indice: 0, id_decision: "p1", tipo: "actividad_propia", origen_ip: "10.100.0.10", activo: "web-banking" }])
    render(<Equipos />)
    expect(screen.queryByText(/originó/)).not.toBeInTheDocument()
    expect(screen.getByText("sin actividad")).toBeInTheDocument()
  })
})
