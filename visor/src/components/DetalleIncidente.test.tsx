import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { Toaster } from "@/components/ui/toast"

const h = vi.hoisted(() => ({ trazas: [] as unknown[] }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: () => h.trazas,
  getCaso: () => Promise.resolve({ estado: "nuevo", asignado: null, notas: [] }),
}))
import { DetalleIncidente } from "./DetalleIncidente"

describe("DetalleIncidente", () => {
  it("muestra las decisiones del /24 en la línea de tiempo y el panel de caso del incidente", () => {
    h.trazas = [
      { indice: 1, id_decision: "d1", origen_ip: "203.0.113.9", prioridad: 4, timestamp: "2026-10-28T10:00:00",
        relaciones: { "web-banking": ["objetivo"] }, clase: "vp_intento_acceso", accion_final: "BLOQUEAR_IP" },
      { indice: 2, id_decision: "d2", origen_ip: "203.0.113.20", prioridad: 3, timestamp: "2026-10-28T10:05:00",
        relaciones: { "core-db": ["objetivo"] }, clase: "vp_intento_acceso", accion_final: "BLOQUEAR_IP" },
      { indice: 3, origen_ip: "1.1.1.1", timestamp: "2026-10-28T10:06:00",
        relaciones: { "web-banking": ["objetivo"] }, clase: "vp_intento_acceso", accion_final: "MATAR_CONEXION" },
    ]
    render(<Toaster><DetalleIncidente clave="inc:203.0.113" cidr="203.0.113.0/24" onVolver={() => {}} /></Toaster>)
    expect(screen.getByText("203.0.113.0/24")).toBeInTheDocument()     // cabecera del incidente
    expect(screen.getByText("Caso")).toBeInTheDocument()               // PanelCaso a nivel incidente
    // la línea de tiempo trae las decisiones del /24 (BLOQUEAR_IP ×2) pero NO la de 1.1.1.1 (MATAR_CONEXION)
    expect(screen.getAllByText("BLOQUEAR_IP").length).toBe(2)
    expect(screen.queryByText("MATAR_CONEXION")).not.toBeInTheDocument()
  })
})
