import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"

// Cada sondeo devuelve lo que diga el test para esa fuente (por identidad de la función).
const h = vi.hoisted(() => ({ fuentes: new Map<unknown, unknown>(), operador: "", caso: vi.fn(async () => true) }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  useSondeo: (fn: unknown) => h.fuentes.get(fn),
  operadorActual: () => h.operador,
  actualizarCaso: h.caso,
}))
import { getSalud, getMetricas, getMetricasHoy, getPendientes, getVerificacion, getTrazasPanel, getLatido, getConectividad } from "@/api"
import { Dashboard as Panel } from "./Dashboard"
import { Toaster } from "@/components/ui/toast"
import type { ComponentProps } from "react"

const Dashboard = (p: ComponentProps<typeof Panel>) => <Toaster><Panel {...p} /></Toaster>

const ERROR = { error: "TypeError: fetch failed" }
const METRICAS = { total: 812, fp: 3, tasa_fp: 0.004, auto: 700, pct_auto: 0.862, suprimidas: 0, mttr_seg: 12,
  mttr_mediano_seg: 31, sla_pct: 1, escalado_humano: 4,
  por_clase: { vp_intento_acceso: 600, fp_actividad_legitima: 212 }, veredictos: {},
  por_dia: [{ dia: "09-27", n: 400 }], top_activos: [], mitre: [] }
const SALUD = { t: null, total: 7, caidos: 0, servicios: [{ nombre: "atm", estado: "ok", depende_de: [] }] }
const hace = (min: number) => new Date(Date.now() - min * 60_000).toISOString()

describe("Panel", () => {
  beforeEach(() => { h.fuentes.clear(); h.operador = ""; h.caso.mockClear() })

  it("sin conexión lo dice en la línea de salud y no pinta ceros como si no hubiera amenazas", () => {
    for (const f of [getSalud, getMetricas, getMetricasHoy, getPendientes, getVerificacion, getTrazasPanel, getLatido, getConectividad]) h.fuentes.set(f, ERROR)
    render(<Dashboard conectado={false} />)
    expect(screen.getByText(/Sin conexión con el daemon/)).toBeInTheDocument()
    expect(screen.queryByText("0")).not.toBeInTheDocument()
  })

  it("las cifras del día salen de las métricas del fichero completo, no de la ventana de trazas", () => {
    h.fuentes.set(getMetricasHoy, METRICAS)
    h.fuentes.set(getMetricas, { ...METRICAS, suprimidas: 40 })   // el ruido evitado es de la sesión
    h.fuentes.set(getPendientes, [])
    h.fuentes.set(getTrazasPanel, [])
    render(<Dashboard conectado />)
    expect(screen.getByText("812")).toBeInTheDocument()     // decisiones hoy
    expect(screen.getByText("40")).toBeInTheDocument()      // ruido evitado (sesión)
    expect(screen.getByText("86 %")).toBeInTheDocument()    // contenidas en automático
  })

  it("la salud cabe en una línea y se pone roja con el motivo si algo cae", () => {
    h.fuentes.set(getSalud, { ...SALUD, caidos: 1, servicios: [{ nombre: "wazuh-manager", estado: "caido", depende_de: [] }] })
    h.fuentes.set(getVerificacion, { ok: true })
    render(<Dashboard conectado />)
    const linea = screen.getByRole("region", { name: "Salud de la plataforma" })
    expect(within(linea).getByText(/Fallo en la plataforma: 1 servicio caído: wazuh-manager/)).toBeInTheDocument()
    expect(within(linea).getByText("6/7")).toBeInTheDocument()
  })

  it("si no se pudo leer la cola, no se da por vacía", () => {
    h.fuentes.set(getMetricasHoy, METRICAS)
    h.fuentes.set(getPendientes, ERROR)
    render(<Dashboard conectado />)
    expect(screen.getByText("no se pudo leer la cola")).toBeInTheDocument()
    expect(screen.getByText("No se pudo leer la cola de aprobaciones.")).toBeInTheDocument()
    expect(screen.queryByText("Nada pendiente ahora mismo.")).not.toBeInTheDocument()
  })

  it("«Te toca» enseña las aprobaciones más urgentes con su SLA y abre la elegida", () => {
    h.fuentes.set(getPendientes, [
      { id: "p1", tipo: "menu", prompt: "", lineas: [], encolado_en: hace(2), clase: "vp_reconocimiento", activo: "atm" },
      { id: "p2", tipo: "menu", prompt: "", lineas: [], encolado_en: hace(13), clase: "vp_malware", activo: "web-banking", accion_final: "AISLAR_NODO" },
    ])
    const ir = vi.fn()
    render(<Dashboard conectado onVerAprobaciones={ir} />)
    const toca = screen.getByRole("region", { name: "Te toca" })
    const filas = within(toca).getAllByRole("button", { name: "Revisar" })
    expect(filas).toHaveLength(2)
    expect(within(toca).getByText("quedan 2 min")).toBeInTheDocument()      // la de hace 13 min va primero
    fireEvent.click(filas[0])
    expect(ir).toHaveBeenCalledWith("p2")
    expect(screen.getByText("1 vencen en < 5 min")).toBeInTheDocument()
  })

  it("el KPI de aprobaciones lleva a la vista de Aprobaciones", () => {
    h.fuentes.set(getPendientes, [{ id: "1", tipo: "menu", prompt: "x", lineas: [] }])
    const ir = vi.fn()
    render(<Dashboard conectado onVerAprobaciones={ir} />)
    fireEvent.click(screen.getByText("Esperan a un humano").closest("button")!)
    expect(ir).toHaveBeenCalled()
  })

  it("un incidente activo sin responsable se puede asignar desde el panel", async () => {
    h.operador = "ana"
    h.fuentes.set(getPendientes, [])
    h.fuentes.set(getTrazasPanel, [
      { tipo: "decision", id_decision: "d1", timestamp: hace(3), origen_ip: "198.51.100.7", activo: "web-banking",
        relaciones: { "web-banking": ["objetivo"] }, contencion: "contenida", clase: "vp_intento_acceso" },
    ])
    render(<Dashboard conectado />)
    const toca = screen.getByRole("region", { name: "Te toca" })
    expect(within(toca).getByText("198.51.100.0/24")).toBeInTheDocument()
    fireEvent.click(within(toca).getByRole("button", { name: "Asignarme" }))
    await waitFor(() => expect(h.caso).toHaveBeenCalledWith("inc:198.51.100", { asignado: "ana" }))
  })

  it("las últimas decisiones dicen quién decidió las que pasaron por un analista", () => {
    h.fuentes.set(getTrazasPanel, [
      { tipo: "decision", id_decision: "d1", timestamp: hace(5), activo: "core-db", clase: "vp_intento_acceso", veredicto_humano: "aprobar", veredicto_por: "Blanyer.Vielma", contencion: "contenida" },
      { tipo: "decision", id_decision: "d2", timestamp: hace(4), activo: "atm", clase: "vp_intento_acceso", veredicto_humano: "aprobar", contencion: "contenida" },
      { tipo: "decision", id_decision: "d3", timestamp: hace(3), activo: "web-banking", clase: "vp_reconocimiento", contencion: "contenida" },
    ])
    render(<Dashboard conectado />)
    const ultimas = screen.getByRole("region", { name: "Últimas decisiones" })
    expect(within(ultimas).getByText(/Blanyer\.Vielma/)).toBeInTheDocument()
    expect(within(ultimas).getByText(/sin nombre registrado/)).toBeInTheDocument()
    const [automatica] = within(ultimas).getAllByRole("listitem")          // la más reciente: automática
    expect(automatica).toHaveTextContent("web-banking")
    expect(automatica).not.toHaveTextContent(/sin nombre|Vielma/)
  })

  it("un fallo CON datos previos conserva las cifras y avisa, no vacía el panel (C2)", () => {
    h.fuentes.set(getMetricasHoy, { error: "x", causa: "red", datos: METRICAS, desde: Date.now() })
    h.fuentes.set(getPendientes, [])
    render(<Dashboard conectado={false} />)
    expect(screen.getByText("812")).toBeInTheDocument()
    expect(screen.getAllByText(/Sin conexión|se perdió la conexión/).length).toBeGreaterThan(0)
  })
})
