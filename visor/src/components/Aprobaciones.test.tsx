import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { Toaster } from "@/components/ui/toast"
import type { Pendiente } from "@/api"

// Capa de datos simulada: la cola que "devuelve" el sondeo y el POST de aprobar.
const h = vi.hoisted(() => ({ pendientes: [] as unknown[], aprobar: vi.fn() }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: () => h.pendientes,
  aprobar: h.aprobar,
}))
import { Aprobaciones } from "./Aprobaciones"

const INCID = "⚠ Incidente: 192.168.1.10 -> objetivo-vuln (ssh)"
const MENU = "¿Qué hacer con este incidente?\n  1) aprobar       — ejecuta la acción propuesta\n" +
  "  2) rechazar      — retiene sin ejecutar\n  3) reclasificar  — corrige la clase"
const CLASES = "Nueva clase:\n  1) fp_actividad_legitima\n  2) fp_exposicion_inexistente\n  3) no_soportada"
const tarjeta = (over: Partial<Pendiente> = {}): Pendiente => ({
  id: "7", tipo: "menu", prompt: "Elige [1-3]: ", lineas: [INCID, "Acción sugerida: BLOQUEAR_IP", MENU],
  severidad: 7, suprimidas: 0, paso: 0, ...over,
})
const vista = () => <Toaster><Aprobaciones /></Toaster>
const boton = (nombre: string) => screen.getByRole("button", { name: nombre })

describe("Aprobaciones", () => {
  beforeEach(() => { h.aprobar.mockReset(); h.pendientes = [tarjeta()] })

  it("Aprobar envía el paso del menú que se está viendo", () => {
    h.aprobar.mockResolvedValue(true)
    render(vista())
    fireEvent.click(boton("Aprobar"))
    expect(h.aprobar).toHaveBeenCalledWith("7", "1", 0)
  })

  it("mientras se envía, bloquea la tarjeta y no reenvía", () => {
    h.aprobar.mockReturnValue(new Promise(() => {}))          // el POST no vuelve
    render(vista())
    fireEvent.click(boton("Aprobar"))
    fireEvent.click(boton("Aprobar"))
    expect(h.aprobar).toHaveBeenCalledTimes(1)
    for (const b of ["Aprobar", "Rechazar", "Reclasificar"]) expect(boton(b)).toBeDisabled()
  })

  it("si se aplica, lo confirma y la tarjeta sigue bloqueada hasta salir de la cola", async () => {
    h.aprobar.mockResolvedValue(true)
    render(vista())
    fireEvent.click(boton("Rechazar"))
    expect(await screen.findByText("Rechazada: se retiene sin ejecutar")).toBeInTheDocument()
    expect(boton("Aprobar")).toBeDisabled()
  })

  it("si el backend la rechaza (409), avisa y reactiva la tarjeta", async () => {
    h.aprobar.mockResolvedValue(false)
    render(vista())
    fireEvent.click(boton("Aprobar"))
    expect(await screen.findByText("No se aplicó el veredicto")).toBeInTheDocument()
    await waitFor(() => expect(boton("Aprobar")).toBeEnabled())
  })

  it("Reclasificar deja la tarjeta esperando el menú de clases, sin aviso de éxito", async () => {
    h.aprobar.mockResolvedValue(true)
    render(vista())
    fireEvent.click(boton("Reclasificar"))
    expect(h.aprobar).toHaveBeenCalledWith("7", "3", 0)
    expect(await screen.findByText(/Cargando las clases/)).toBeInTheDocument()
    expect(boton("Aprobar")).toBeDisabled()                   // cierra la ventana de la carrera (D1)
    expect(screen.queryByText(/Aprobada|Rechazada|Reclasificada/)).not.toBeInTheDocument()
  })

  it("al llegar el menú de clases (paso nuevo) se reactiva y envía ese paso", async () => {
    h.aprobar.mockResolvedValue(true)
    const { rerender } = render(vista())
    fireEvent.click(boton("Reclasificar"))
    await screen.findByText(/Cargando las clases/)
    h.pendientes = [tarjeta({ paso: 1, lineas: [INCID, CLASES] })]
    rerender(vista())
    const clase = boton("Falso positivo (legítimo)")
    expect(clase).toBeEnabled()
    fireEvent.click(clase)
    expect(h.aprobar).toHaveBeenLastCalledWith("7", "1", 1)
    expect(await screen.findByText("Reclasificada como «Falso positivo (legítimo)»")).toBeInTheDocument()
  })

  describe("con riesgo de cascada", () => {
    const CONSEC = "Consecuencia: bloquea a 10.40.0.10 · en cascada: api-movil, middleware"
    beforeEach(() => { h.pendientes = [tarjeta({ lineas: [INCID, CONSEC, MENU] })] })

    it("Aprobar pide confirmación listando los activos y aún no envía", () => {
      render(vista())
      fireEvent.click(boton("Aprobar"))
      const dialogo = screen.getByRole("alertdialog")
      expect(dialogo).toHaveTextContent("api-movil")
      expect(dialogo).toHaveTextContent("middleware")
      expect(h.aprobar).not.toHaveBeenCalled()
    })

    it("confirmar envía el veredicto", () => {
      h.aprobar.mockResolvedValue(true)
      render(vista())
      fireEvent.click(boton("Aprobar"))
      fireEvent.click(boton("Aprobar igualmente"))
      expect(h.aprobar).toHaveBeenCalledWith("7", "1", 0)
    })

    it("cancelar no envía nada", async () => {
      render(vista())
      fireEvent.click(boton("Aprobar"))
      fireEvent.click(boton("Cancelar"))
      await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument())
      expect(h.aprobar).not.toHaveBeenCalled()
    })

    it("Rechazar no pide confirmación (no ejecuta nada)", () => {
      h.aprobar.mockResolvedValue(true)
      render(vista())
      fireEvent.click(boton("Rechazar"))
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
      expect(h.aprobar).toHaveBeenCalledWith("7", "2", 0)
    })
  })

  it("una escalada (ruta bloqueante) aprueba sin paso", () => {
    h.aprobar.mockResolvedValue(true)
    h.pendientes = [tarjeta({ tipo: "escalada", prompt: "¿aprobar? [s/N] ", lineas: [], paso: undefined })]
    render(vista())
    fireEvent.click(boton("Aprobar"))
    expect(h.aprobar).toHaveBeenCalledWith("7", "s", undefined)
  })
})
