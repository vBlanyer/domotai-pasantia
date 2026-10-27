import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

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
  it("no duplica los conteos: una sola fila (actividad) y el último visto, sin fila 'en la ventana'", () => {
    render(<PanelEquipo nodo={nodo} eventos={eventos} onVerDecisiones={() => {}} />)
    expect(screen.getByText(/3 recibidos/)).toBeInTheDocument()       // la fila de actividad (autoritativa)
    expect(screen.getByText(/último:/)).toBeInTheDocument()
    expect(screen.queryByText(/en la ventana/)).not.toBeInTheDocument()   // sin la fila redundante
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

describe("PanelEquipo — correlación de atacantes", () => {
  it("lista los orígenes con su nº de ataques, alcance y otros equipos", () => {
    const nod = { nombre: "web-banking", actividad: { objetivo: 3, origen: 0, contuvo_aqui: 0, pendientes: 0, estado: "atacado", ultima: null } } as unknown as Parameters<typeof PanelEquipo>[0]["nodo"]
    const ev = [
      { indice: 1, origen_ip: "198.51.100.11", timestamp: "2026-10-27T10:00:00", clase: "vp_intento_acceso", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { alcance: "externo" } },
      { indice: 2, origen_ip: "198.51.100.11", timestamp: "2026-10-27T12:00:00", clase: "vp_intento_acceso", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { alcance: "externo" } },
    ] as unknown as Parameters<typeof PanelEquipo>[0]["eventos"]
    const todos = [...ev, { indice: 3, origen_ip: "198.51.100.11", relaciones: { "core-db": ["objetivo"] } }] as unknown as Parameters<typeof PanelEquipo>[0]["eventos"]
    render(<PanelEquipo nodo={nod} eventos={ev} todos={todos} onVerDecisiones={() => {}} />)
    expect(screen.getAllByText("198.51.100.11").length).toBeGreaterThan(0)  // en la tabla de atacantes (y en la lista)
    expect(screen.getByText("×2")).toBeInTheDocument()                 // nº de ataques contra el equipo
    expect(screen.getByText(/1 equipo/)).toBeInTheDocument()           // correlación: también en core-db
  })
})

describe("PanelEquipo — pivote y jerarquía", () => {
  const nod = { nombre: "web-banking", actividad: { objetivo: 2, origen: 0, contuvo_aqui: 0, pendientes: 0, estado: "atacado", ultima: null } } as unknown as Parameters<typeof PanelEquipo>[0]["nodo"]
  const ev = [
    { indice: 1, origen_ip: "198.51.100.11", prioridad: 4, timestamp: "2026-10-27T10:00:00", clase: "vp_intento_acceso", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { alcance: "externo" } },
  ] as unknown as Parameters<typeof PanelEquipo>[0]["eventos"]

  it("al pulsar una IP atacante pide ver sus decisiones", () => {
    const onVerOrigen = vi.fn()
    render(<PanelEquipo nodo={nod} eventos={ev} todos={ev} onVerDecisiones={() => {}} onVerOrigen={onVerOrigen} />)
    fireEvent.click(screen.getByRole("button", { name: "198.51.100.11" }))
    expect(onVerOrigen).toHaveBeenCalledWith("198.51.100.11")
  })

  it("la lista de eventos es un bloque plegable", () => {
    render(<PanelEquipo nodo={nod} eventos={ev} onVerDecisiones={() => {}} />)
    expect(screen.getByText(/Eventos recientes/)).toBeInTheDocument()
  })
})
