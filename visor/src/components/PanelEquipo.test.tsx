import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"

// Las gráficas se stubean (como en Metricas.test) para asertar los DATOS derivados, no Recharts.
vi.mock("./charts", () => ({
  Donut: ({ data }: { data: unknown[] }) => <div data-testid="donut">{data.length}</div>,
  Tendencia: ({ data }: { data: unknown[] }) => <div data-testid="tend">{data.length}</div>,
  Barras: () => null,
}))
import { PanelEquipo } from "./PanelEquipo"

const nodo = {
  nombre: "web-banking", ip: "10.10.0.10",
  actividad: { objetivo: 3, origen: 0, contuvo_aqui: 1, pendientes: 0, estado: "atacado", ultima: "2026-10-27T11:30:00" },
} as unknown as Parameters<typeof PanelEquipo>[0]["nodo"]

const eventos = [
  { indice: 1, timestamp: "2026-10-27T10:00:00", clase: "vp_intento_acceso", contencion: "contenida", requiere_humano: false, relaciones: { "web-banking": ["objetivo"] } },
  { indice: 2, timestamp: "2026-10-27T11:30:00", clase: "vp_intento_acceso", contencion: "retenida", requiere_humano: true, relaciones: { "web-banking": ["objetivo"] } },
  { indice: 3, timestamp: "2026-10-26T09:00:00", clase: "vp_malware", contencion: "contenida", requiere_humano: true, relaciones: { "web-banking": ["objetivo"] } },
] as unknown as Parameters<typeof PanelEquipo>[0]["eventos"]

describe("PanelEquipo — datos por dispositivo", () => {
  it("muestra conteos derivados de los eventos de la ventana", () => {
    render(<PanelEquipo nodo={nodo} eventos={eventos} onVerDecisiones={() => {}} />)
    expect(screen.getByText(/3 en la ventana/)).toBeInTheDocument()
    expect(screen.getByText(/1 automática/)).toBeInTheDocument()
    expect(screen.getByText(/1 retenida/)).toBeInTheDocument()
    expect(screen.getByText(/2 contenida/)).toBeInTheDocument()
  })

  it("deriva el donut por clase (2 clases) y la tendencia por día (2 días)", () => {
    render(<PanelEquipo nodo={nodo} eventos={eventos} onVerDecisiones={() => {}} />)
    expect(screen.getByTestId("donut")).toHaveTextContent("2")
    expect(screen.getByTestId("tend")).toHaveTextContent("2")
  })

  it("sin eventos no pinta gráficas", () => {
    render(<PanelEquipo nodo={nodo} eventos={[]} onVerDecisiones={() => {}} />)
    expect(screen.queryByTestId("donut")).not.toBeInTheDocument()
    expect(screen.getByText(/Sin eventos/)).toBeInTheDocument()
  })
})
