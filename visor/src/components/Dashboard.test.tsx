import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"

// Cada sondeo devuelve lo que diga el test para esa fuente; los gráficos (Recharts) no importan aquí.
const h = vi.hoisted(() => ({ fuentes: new Map<unknown, unknown>() }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: (fn: unknown) => h.fuentes.get(fn),
}))
vi.mock("./charts", () => ({ Donut: () => null, Gauge: () => null, Tendencia: () => null }))
import { getSalud, getMetricas, getPendientes, getVerificacion, getTrazas } from "@/api"
import { Dashboard } from "./Dashboard"

const ERROR = { error: "TypeError: fetch failed" }
const METRICAS = { total: 812, fp: 3, tasa_fp: 0.004, auto: 700, pct_auto: 86.2, suprimidas: 40, mttr_seg: 12,
  por_clase: { vp_intento_acceso: 600, fp_actividad_legitima: 212 }, veredictos: {},
  por_dia: [{ dia: "09-27", n: 400 }, { dia: "09-28", n: 412 }], top_activos: [], mitre: [] }

describe("Panel", () => {
  beforeEach(() => h.fuentes.clear())

  it("sin conexión avisa y no pinta ceros como si no hubiera amenazas", () => {
    for (const f of [getSalud, getMetricas, getPendientes, getVerificacion, getTrazas]) h.fuentes.set(f, ERROR)
    render(<Dashboard conectado={false} />)
    expect(screen.getByText(/Sin conexión con el daemon/)).toBeInTheDocument()
    expect(screen.queryByText("0")).not.toBeInTheDocument()
  })

  it("los totales salen de las métricas del fichero completo, no de la ventana de trazas", () => {
    h.fuentes.set(getMetricas, METRICAS)
    h.fuentes.set(getPendientes, [])
    h.fuentes.set(getTrazas, [])                        // ventana vacía: no debe influir en los totales
    render(<Dashboard conectado />)
    expect(screen.getByText("812")).toBeInTheDocument()   // decisiones tomadas
    expect(screen.getByText("40")).toBeInTheDocument()    // alertas suprimidas
    expect(screen.queryByText(/Sin conexión con el daemon/)).not.toBeInTheDocument()
  })

  it("si no se pudo leer la cola, «sin pendientes» no se da por bueno", () => {
    h.fuentes.set(getMetricas, METRICAS)
    h.fuentes.set(getPendientes, ERROR)
    render(<Dashboard conectado />)
    expect(screen.getByText("Sin decisiones pendientes").closest("li")).toHaveTextContent("✗")
  })
})
