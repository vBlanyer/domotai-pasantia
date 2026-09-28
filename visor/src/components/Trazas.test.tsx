import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

// /api/trazas sirve una ventana (los últimos N); /api/verificar recorre el fichero entero.
const h = vi.hoisted(() => ({ trazas: [] as unknown[], verif: {} as unknown }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: () => h.trazas,
  getVerificacion: async () => h.verif,
}))
import { Trazas } from "./Trazas"

const reg = (indice: number, id: string) =>
  ({ indice, id_decision: id, hash: String(indice).padStart(64, "a"), hash_previo: String(indice - 1).padStart(64, "a") })

describe("Trazas", () => {
  it("numera por la posición en la cadena y marca el registro roto aunque la ventana empiece a mitad", async () => {
    h.trazas = [reg(500, "s501"), reg(501, "s502")]
    h.verif = { ok: false, roto_en: 501, motivo: "el hash no coincide" }
    render(<Trazas />)
    expect(screen.getByText("501")).toBeInTheDocument()                 // # = índice global + 1
    fireEvent.click(screen.getByRole("button", { name: "Verificar la cadena" }))
    const alterado = await screen.findByText("alterado")
    expect(alterado.closest("tr")).toHaveTextContent("s502")
  })

  it("registros con el mismo id no chocan sus claves", () => {
    const err = vi.spyOn(console, "error").mockImplementation(() => {})
    h.trazas = [reg(3, "s1"), reg(7, "s1")]
    render(<Trazas />)
    expect(err.mock.calls.some((c) => String(c[0]).includes("same key"))).toBe(false)
    err.mockRestore()
  })

  it("avisa de que la lista es parcial", () => {
    h.trazas = [reg(500, "s501"), reg(501, "s502")]
    render(<Trazas />)
    expect(screen.getByText(/últimos 2 de 502 registros/)).toBeInTheDocument()
  })

  it("si el registro alterado queda fuera de la ventana, lo dice", async () => {
    h.trazas = [reg(500, "s501"), reg(501, "s502")]
    h.verif = { ok: false, roto_en: 3, motivo: "el hash no coincide" }
    render(<Trazas />)
    fireEvent.click(screen.getByRole("button", { name: "Verificar la cadena" }))
    expect(await screen.findByText(/registro alterado \(#4\) queda fuera de los mostrados/)).toBeInTheDocument()
    expect(screen.queryByText("alterado")).not.toBeInTheDocument()
  })
})
