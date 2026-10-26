import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"

// Doble de la API: el hook incremental consume getConsola; aquí se le sirve un lote fijo.
const h = vi.hoisted(() => ({ respuesta: { hasta: 0, lineas: [] as unknown[] } }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  getConsola: async () => h.respuesta,
}))
import { Consola } from "./Consola"

const L = (n: number, linea: string) => ({ n, t: "16:02:11", linea })

describe("Consola", () => {
  beforeEach(() => { h.respuesta = { hasta: 0, lineas: [] } })

  it("muestra el feed con la hora y filtra por grupo", async () => {
    h.respuesta = { hasta: 3, lineas: [
      L(1, "⚠ Incidente: 6 alerta(s) · 192.168.1.10 → objetivo-vuln"),
      L(2, "  Clase: vp_intento_acceso · Prioridad: 3"),
      L(3, "[aviso] receptor: conexión rechazada"),
    ] }
    render(<Consola />)
    await waitFor(() => expect(screen.getByText(/Incidente: 6 alerta/)).toBeInTheDocument())
    expect(screen.getByText(/receptor: conexión rechazada/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Avisos" }))
    expect(screen.queryByText(/Incidente: 6 alerta/)).not.toBeInTheDocument()
    expect(screen.getByText(/receptor: conexión rechazada/)).toBeInTheDocument()
  })

  it("la búsqueda de texto acota el feed", async () => {
    h.respuesta = { hasta: 2, lineas: [L(1, "  Clase: vp_x"), L(2, "  Clase: vp_y")] }
    render(<Consola />)
    await waitFor(() => expect(screen.getByText(/vp_x/)).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText(/filtrar texto/), { target: { value: "vp_y" } })
    expect(screen.queryByText(/vp_x/)).not.toBeInTheDocument()
    expect(screen.getByText(/vp_y/)).toBeInTheDocument()
  })

  it("sin actividad lo dice, sin inventar conexión perdida", async () => {
    render(<Consola />)
    await waitFor(() => expect(screen.getByText(/Aún no hay actividad/)).toBeInTheDocument())
  })
})
