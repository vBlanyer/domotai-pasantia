import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

const h = vi.hoisted(() => ({ lista: [] as unknown[], agregar: vi.fn(async () => []) }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: () => h.lista,
  watchlistAgregar: h.agregar,
  watchlistQuitar: vi.fn(async () => []),
}))
import { Watchlist } from "./Watchlist"

describe("Watchlist", () => {
  it("lista los indicadores y permite añadir uno", () => {
    h.lista = [{ indicador: "198.51.100.10", nota: "C2" }]
    render(<Watchlist />)
    expect(screen.getByText(/198\.51\.100\.10/)).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText(/IP o CIDR/i), { target: { value: "203.0.113.9" } })
    fireEvent.click(screen.getByRole("button", { name: /Añadir/i }))
    expect(h.agregar).toHaveBeenCalledWith("203.0.113.9", "")
  })
})
