import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { Paginador } from "./Paginador"

describe("Paginador", () => {
  it("ofrece elegir el tamaño (10/20/50) y avisa del cambio", () => {
    const onTam = vi.fn()
    render(<Paginador pagina={1} paginas={2} total={30} tam={20} onPagina={() => {}} onTam={onTam} />)
    const sel = screen.getByLabelText("Filas por página") as HTMLSelectElement
    expect([...sel.querySelectorAll("option")].map((o) => o.value)).toEqual(["10", "20", "50"])
    expect(sel.value).toBe("20")
    fireEvent.change(sel, { target: { value: "50" } })
    expect(onTam).toHaveBeenCalledWith(50)
  })

  it("muestra el selector aunque haya una sola página si la lista supera el mínimo", () => {
    render(<Paginador pagina={1} paginas={1} total={15} tam={20} onPagina={() => {}} onTam={() => {}} />)
    expect(screen.getByLabelText("Filas por página")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Siguiente" })).not.toBeInTheDocument()   // 1 página: sin prev/next
  })

  it("no renderiza nada si la lista cabe en la página más pequeña", () => {
    const { container } = render(<Paginador pagina={1} paginas={1} total={8} tam={20} onPagina={() => {}} onTam={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
