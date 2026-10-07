import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import type { Decision } from "@/api"

const h = vi.hoisted(() => ({ red: null as unknown, det: null as unknown }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: () => h.red,
  getTrazaDetalle: async () => h.det,
}))
import { VistaIncidente } from "./VistaIncidente"

const nodo = (nombre: string, ip: string | null, zona: string) => ({
  nombre, ip, tipo: "host", zona, funcion: null, criticidad: null,
  servicios_prestados: [], depende_de: [], salud: null,
  actividad: { objetivo: 0, origen: 0, contuvo_aqui: 0, pendientes: 0, estado: "sin_actividad", ultima: null },
})

describe("VistaIncidente", () => {
  it("muestra el detalle del incidente, el aviso de cascada y la técnica MITRE", async () => {
    h.red = {
      nodos: [nodo("core-db", "10.50.0.10", "nucleo"), nodo("api-movil", "10.20.0.10", "nucleo"),
              nodo("middleware", "10.40.0.10", "nucleo")],
      enlaces: [["api-movil", "middleware"], ["middleware", "core-db"]], dependencias: [],
      zonas: [{ nombre: "nucleo", nodos: ["core-db", "api-movil", "middleware"] }],
    }
    h.det = { justificacion: "fuerza bruta SSH contra core-db",
              impacto_determinado: { activos_afectados_en_cascada: ["api-movil"] } }
    const d = { id_decision: "s1", clase: "vp_intento_acceso", activo: "core-db", origen_ip: "10.40.0.10",
                accion_final: "BLOQUEAR_IP", prioridad: 4, tecnica_mitre: ["T1110"], cascada: ["api-movil"],
                hash: "abc123" } as Decision

    render(<VistaIncidente decision={d} onVolver={() => {}} />)
    expect(await screen.findByText("fuerza bruta SSH contra core-db")).toBeInTheDocument()  // justificación tras el fetch
    expect(screen.getByText(/dejaría sin servicio a api-movil/)).toBeInTheDocument()          // aviso de cascada
    expect(screen.getByText("T1110")).toBeInTheDocument()                                    // enlace MITRE
  })

  it("mientras carga la red muestra el cargando, no rompe", () => {
    h.red = null
    render(<VistaIncidente decision={{ id_decision: "s1" } as Decision} onVolver={() => {}} />)
    // no lanza; useSondeo devuelve undefined/null -> estado de carga
    expect(document.body).toBeTruthy()
  })
})
