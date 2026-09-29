import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import type { Decision } from "@/api"

// El detalle se pide a /api/traza/<id>: aquí lo sirve un doble.
const h = vi.hoisted(() => ({ detalle: {} as unknown, decisiones: [] as unknown[], pedidos: [] as unknown[][] }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  getTrazaDetalle: async (...a: unknown[]) => { h.pedidos.push(a); return h.detalle },
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

  it("tras escalar muestra la orden efectiva y el intento fallido por separado", async () => {
    h.detalle = {
      id_decision: "s5", accion_propuesta: "BLOQUEAR_IP", accion_final: "BLOQUEAR_IP", resultado_filtro: "permite",
      orden: { accion_id: "BLOQUEAR_IP", nodo_objetivo: "web-banking" },
      ejecucion: { exito: false, comando_ejecutado: "iptables -A INPUT -s 198.51.100.10 -j DROP" },
      verificacion: { verificado: false }, veredicto_escalada: "aprobar",
      escalada: { resultado: "mitigado", escalado: true, dispositivo_ejecutor: "fw-core",
        orden_efectiva: { accion_id: "BLOQUEAR_IP_FIREWALL", nodo_objetivo: "fw-core" } },
    }
    fila({ id_decision: "s5", clase: "vp_intento_acceso" })
    expect(await screen.findByText(/Contenida en fw-core/)).toBeInTheDocument()
    expect(screen.getByText("BLOQUEAR_IP_FIREWALL")).toBeInTheDocument()
    expect(screen.getByText(/intento en web-banking: no respondió/)).toBeInTheDocument()
    expect(screen.queryByText("iptables -A INPUT -s 198.51.100.10 -j DROP")).not.toBeInTheDocument()
    expect(screen.getByText("escalada aprobada por el analista")).toBeInTheDocument()
  })

  it("una amenaza enrutada muestra su destino, no «sin acción»", async () => {
    h.detalle = { id_decision: "s6", ruta: "cola-appsec-banco", accion_final: null, orden: null, resultado_filtro: "sin_accion" }
    fila({ id_decision: "s6", clase: "amenaza_enrutada" })
    expect(await screen.findByText(/Enrutada a cola-appsec-banco/)).toBeInTheDocument()
    expect(screen.queryByText("Sin acción de contención")).not.toBeInTheDocument()
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

  it("la actividad propia del MDR se pinta como tal, no como decisión", () => {
    cerrada({ id_decision: "p1", tipo: "actividad_propia", activo: "web-banking" })
    expect(screen.getByText(/actividad propia del MDR en web-banking/)).toBeInTheDocument()
    expect(screen.queryByText("—")).not.toBeInTheDocument()
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

describe("Detalle de un registro con id repetido", () => {
  it("pide el detalle por el índice de la fila, no solo por el id", async () => {
    h.pedidos = []
    h.detalle = { id_decision: "s1", justificacion: "x", orden: null }
    render(<table><tbody><FilaDecision d={{ id_decision: "s1", indice: 4 }} abierto onToggle={() => {}} /></tbody></table>)
    await screen.findByText("Justificación")
    expect(h.pedidos[0]).toEqual(["s1", 4])
  })
})

