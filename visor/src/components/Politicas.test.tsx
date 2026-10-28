import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"

const h = vi.hoisted(() => ({ pol: [] as unknown[] }))
vi.mock("@/api", async (orig) => ({ ...(await orig<typeof import("@/api")>()), useSondeo: () => h.pol }))
import { Politicas } from "./Politicas"

const F = [
  { familia: "acceso_credenciales", clase_tipica: "vp_intento_acceso", accion: "BLOQUEAR_IP", impacto: "localizado",
    automatizacion: "automatica_si_confianza", mitre: ["T1110"], nivel: "actuar", ruta: null,
    vetos: ["requiere la IP de origen en el evento"], recomendacion: { respuesta: "contener_origen", nota: "" } },
  { familia: "integridad_fichero", clase_tipica: "vp_integridad", accion: "AISLAR_NODO", impacto: "alcanza_servicio",
    automatizacion: "nunca_automatica", mitre: ["T1565"], nivel: "actuar", ruta: null,
    vetos: ["nunca automática (guard duro del catálogo): siempre pasa por un humano"], recomendacion: null },
]

describe("Politicas", () => {
  it("muestra, por familia, la acción, la automatización legible y los vetos", () => {
    h.pol = F
    render(<Politicas />)
    expect(screen.getByText("acceso_credenciales")).toBeInTheDocument()
    expect(screen.getByText("integridad_fichero")).toBeInTheDocument()
    expect(screen.getByText("BLOQUEAR_IP")).toBeInTheDocument()
    expect(screen.getByText("AISLAR_NODO")).toBeInTheDocument()
    expect(screen.getByText(/auto si confianza/)).toBeInTheDocument()
    expect(screen.getByText("nunca automática")).toBeInTheDocument()
    expect(screen.getByText(/requiere la IP de origen/)).toBeInTheDocument()
  })

  it("vacío lo dice", () => {
    h.pol = []
    render(<Politicas />)
    expect(screen.getByText(/Sin políticas que mostrar/)).toBeInTheDocument()
  })
})
