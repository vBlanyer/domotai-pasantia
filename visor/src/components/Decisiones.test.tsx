import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import type { Decision } from "@/api"

// El detalle se pide a /api/traza/<id>: aquí lo sirve un doble.
const h = vi.hoisted(() => ({ detalle: {} as unknown, decisiones: [] as unknown[] }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  getTrazaDetalle: async () => h.detalle,
  useSondeo: () => h.decisiones,
}))
import { FilaDecision, Decisiones } from "./Decisiones"

const fila = (d: Decision) => render(
  <table><tbody><FilaDecision d={d} abierto onToggle={() => {}} /></tbody></table>,
)

describe("Detalle de una decisión", () => {
  it("muestra dónde quedó contenida y desde dónde escaló", async () => {
    h.detalle = {
      id_decision: "s1", justificacion: "fuerza bruta",
      orden: { accion_id: "BLOQUEAR_IP", nodo_objetivo: "objetivo-vuln" },
      ejecucion: { exito: false }, verificacion: { verificado: false },
      escalada: { resultado: "mitigado", escalado: true, dispositivo_ejecutor: "gateway" },
    }
    fila({ id_decision: "s1", clase: "vp_intento_acceso" })
    expect(await screen.findByText("Contención")).toBeInTheDocument()
    expect(screen.getByText(/Contenida en gateway/)).toBeInTheDocument()
    expect(screen.getByText(/escaló desde objetivo-vuln/)).toBeInTheDocument()
  })

  it("una decisión retenida por el analista dice que no se ejecutó nada", async () => {
    h.detalle = { id_decision: "s2", veredicto_humano: "rechazar", accion_final: "BLOQUEAR_IP", orden: null }
    fila({ id_decision: "s2", clase: "vp_intento_acceso" })
    expect(await screen.findByText(/Retenida por el analista/)).toBeInTheDocument()
  })

  it("muestra la acción propuesta frente a la final y cómo la trató el filtro", async () => {
    h.detalle = { id_decision: "s3", accion_propuesta: "AISLAR_NODO", accion_final: "BLOQUEAR_IP",
      resultado_filtro: "degrada", requiere_humano: false, orden: null }
    fila({ id_decision: "s3", clase: "vp_intento_acceso" })
    expect(await screen.findByText("AISLAR_NODO → BLOQUEAR_IP")).toBeInTheDocument()
    expect(screen.getByText("degradada — se sustituye por BLOQUEAR_IP")).toBeInTheDocument()
  })

  it("si la propuesta pasó tal cual, no pinta flecha", async () => {
    h.detalle = { id_decision: "s4", accion_propuesta: "BLOQUEAR_IP", accion_final: "BLOQUEAR_IP",
      resultado_filtro: "permite", orden: null }
    fila({ id_decision: "s4", clase: "vp_intento_acceso" })
    expect(await screen.findByText("automática")).toBeInTheDocument()
    expect(screen.queryByText(/→/)).not.toBeInTheDocument()
  })
})

describe("Fila de la tabla de decisiones", () => {
  const cerrada = (d: Decision) => render(
    <table><tbody><FilaDecision d={d} abierto={false} onToggle={() => {}} /></tbody></table>,
  )

  it("muestra la prioridad y el desenlace de una reclasificación", () => {
    cerrada({ id_decision: "s1", prioridad: 4, clase: "vp_intento_acceso", requiere_humano: true,
      veredicto_humano: "reclasificar", clase_reclasificada: "fp_actividad_legitima" })
    expect(screen.getByText("P4 · crítica")).toBeInTheDocument()
    expect(screen.getByText("reclasificada: vp_intento_acceso → fp_actividad_legitima")).toBeInTheDocument()
    expect(screen.getByText("reclasificada")).toBeInTheDocument()
  })

  it("marca una acción degradada por el perfil", () => {
    cerrada({ id_decision: "s2", resultado_filtro: "degrada", accion_propuesta: "AISLAR_NODO", accion_final: "BLOQUEAR_IP" })
    expect(screen.getByText("BLOQUEAR_IP")).toBeInTheDocument()
    expect(screen.getByText("degradada")).toHaveAttribute("title", "propuesta: AISLAR_NODO")
  })

  it("marca una acción vetada (sin acción final)", () => {
    cerrada({ id_decision: "s3", resultado_filtro: "veta", accion_propuesta: "AISLAR_NODO", accion_final: null })
    expect(screen.getByText("AISLAR_NODO")).toBeInTheDocument()
    expect(screen.getByText("vetada")).toBeInTheDocument()
  })

  it("la tabla tiene columna de prioridad", () => {
    h.decisiones = [{ id_decision: "s1", prioridad: 3, clase: "vp_intento_acceso" }]
    render(<Decisiones />)
    expect(screen.getByRole("columnheader", { name: "Prioridad" })).toBeInTheDocument()
    expect(screen.getByText("P3 · alta")).toBeInTheDocument()
  })
})

describe("Identidad de las filas", () => {
  beforeEach(() => { h.detalle = { id_decision: "s1", justificacion: "x", orden: null } })

  it("dos registros con el mismo id no se abren juntos ni chocan sus claves", async () => {
    const err = vi.spyOn(console, "error").mockImplementation(() => {})
    h.decisiones = [{ indice: 4, id_decision: "s1", activo: "a1", clase: "vp_intento_acceso" },
                    { indice: 9, id_decision: "s1", activo: "a2", clase: "vp_intento_acceso" }]
    render(<Decisiones />)
    fireEvent.click(screen.getByText("a1"))
    expect(await screen.findAllByText("Justificación")).toHaveLength(1)
    expect(err.mock.calls.some((c) => String(c[0]).includes("same key"))).toBe(false)
    err.mockRestore()
  })

  it("la fila abierta sigue en su decisión cuando la ventana se desliza", async () => {
    h.decisiones = [{ indice: 1, id_decision: "s1", activo: "a1" }, { indice: 2, id_decision: "s2", activo: "a2" }]
    const { rerender } = render(<Decisiones />)
    fireEvent.click(screen.getByText("a2"))
    await screen.findByText("Justificación")
    h.decisiones = [{ indice: 2, id_decision: "s2", activo: "a2" }, { indice: 3, id_decision: "s3", activo: "a3" }]
    rerender(<Decisiones />)
    const detalle = screen.getByText("Justificación").closest("tr")!
    expect(detalle.previousElementSibling).toHaveTextContent("a2")
  })
})

