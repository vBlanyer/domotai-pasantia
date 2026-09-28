import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { Toaster } from "./toast"
import { useToast } from "./use-toast"

function Disparador({ type }: { type?: "success" | "error" | "info" }) {
  const toast = useToast()
  return <button onClick={() => toast({ title: "Decisión aplicada", description: "s7 aprobada", type })}>lanzar</button>
}

describe("toast", () => {
  it("muestra el aviso con título y descripción", async () => {
    render(<Toaster><Disparador /></Toaster>)
    fireEvent.click(screen.getByText("lanzar"))
    expect(await screen.findByText("Decisión aplicada")).toBeInTheDocument()
    expect(screen.getByText("s7 aprobada")).toBeInTheDocument()
    expect(screen.getByRole("region", { name: "Avisos" })).toBeInTheDocument()   // anunciada en español
  })

  it("se cierra con el botón Cerrar", async () => {
    render(<Toaster><Disparador /></Toaster>)
    fireEvent.click(screen.getByText("lanzar"))
    // Base UI oculta el cierre a la tecnología de asistencia (aria-hidden, nombre accesible vacío)
    // hasta que la pila se expande con foco o puntero: se localiza por su aria-label.
    fireEvent.click(await screen.findByLabelText("Cerrar aviso"))
    await waitFor(() => expect(screen.queryByText("Decisión aplicada")).not.toBeInTheDocument())
  })

  it("marca el tono para distinguir un error de un éxito", async () => {
    render(<Toaster><Disparador type="error" /></Toaster>)
    fireEvent.click(screen.getByText("lanzar"))
    const titulo = await screen.findByText("Decisión aplicada")
    expect(titulo.closest("[data-tono]")).toHaveAttribute("data-tono", "error")
  })
})
