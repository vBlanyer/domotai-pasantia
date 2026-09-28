import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { AlertDialog } from "./alert-dialog"

describe("AlertDialog", () => {
  it("abierto muestra título, descripción y el contenido extra", () => {
    render(
      <AlertDialog open onOpenChange={() => {}} title="¿Bloquear pese a la cascada?"
        description="Caerán los activos que dependen de este." confirmLabel="Bloquear igualmente"
        onConfirm={() => {}}>
        <ul><li>core-db</li></ul>
      </AlertDialog>,
    )
    expect(screen.getByRole("alertdialog")).toBeInTheDocument()
    expect(screen.getByText("¿Bloquear pese a la cascada?")).toBeInTheDocument()
    expect(screen.getByText("Caerán los activos que dependen de este.")).toBeInTheDocument()
    expect(screen.getByText("core-db")).toBeInTheDocument()
  })

  it("confirmar llama a onConfirm y cierra", () => {
    const onConfirm = vi.fn(), onOpenChange = vi.fn()
    render(<AlertDialog open onOpenChange={onOpenChange} title="t" confirmLabel="Bloquear igualmente"
      onConfirm={onConfirm} />)
    fireEvent.click(screen.getByRole("button", { name: "Bloquear igualmente" }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("cancelar cierra sin confirmar", () => {
    const onConfirm = vi.fn(), onOpenChange = vi.fn()
    render(<AlertDialog open onOpenChange={onOpenChange} title="t" confirmLabel="Bloquear igualmente"
      onConfirm={onConfirm} />)
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }))
    expect(onConfirm).not.toHaveBeenCalled()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("cerrado no pinta nada", () => {
    render(<AlertDialog open={false} onOpenChange={() => {}} title="t" confirmLabel="Sí" onConfirm={() => {}} />)
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })
})
