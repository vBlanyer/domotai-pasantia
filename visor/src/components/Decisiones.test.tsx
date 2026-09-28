import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import type { Decision } from "@/api"

// El detalle se pide a /api/traza/<id>: aquí lo sirve un doble.
const h = vi.hoisted(() => ({ detalle: {} as unknown }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  getTrazaDetalle: async () => h.detalle,
}))
import { FilaDecision } from "./Decisiones"

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
