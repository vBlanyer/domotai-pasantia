import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"

const h = vi.hoisted(() => ({ trazas: [] as unknown[], rdns: { ip: "", rdns: null as string | null } }))
vi.mock("@/api", async (orig) => ({ ...(await orig<typeof import("@/api")>()),
  useSondeo: () => h.trazas, getRdns: () => Promise.resolve(h.rdns) }))
import { PerfilAtacante } from "./PerfilAtacante"

describe("PerfilAtacante", () => {
  it("muestra los equipos que atacó y pivota a sus decisiones", () => {
    h.trazas = [
      { indice: 1, origen_ip: "198.51.100.10", prioridad: 4, timestamp: "2026-10-27T10:00:00", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { alcance: "externo", clasificacion_ip: "documentacion", inventariado: false, tercero_confiable: false, legitimo: false, geolocalizable: false, geo: null } },
      { indice: 2, origen_ip: "198.51.100.10", prioridad: 2, timestamp: "2026-10-27T12:00:00", relaciones: { "core-db": ["objetivo"] } },
    ]
    const onVerDecisiones = vi.fn()
    render(<PerfilAtacante ip="198.51.100.10" onVolver={() => {}} onVerDecisiones={onVerDecisiones} />)
    expect(screen.getByText("198.51.100.10")).toBeInTheDocument()
    expect(screen.getByText("web-banking")).toBeInTheDocument()
    expect(screen.getByText("core-db")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Ver sus decisiones/i }))
    expect(onVerDecisiones).toHaveBeenCalledWith("198.51.100.10")
  })
})

describe("PerfilAtacante — rDNS opt-in", () => {
  const publica = [
    { indice: 1, origen_ip: "8.8.8.8", prioridad: 3, timestamp: "2026-10-27T10:00:00", relaciones: { "web-banking": ["objetivo"] },
      enriquecimiento_origen: { alcance: "externo", clasificacion_ip: "publica", inventariado: false, tercero_confiable: false, legitimo: false, geolocalizable: true, geo: null } },
  ]
  it("ofrece resolver el DNS inverso solo en IP pública y dice «sin resolución» si está apagado", async () => {
    h.trazas = publica
    h.rdns = { ip: "8.8.8.8", rdns: null }
    render(<PerfilAtacante ip="8.8.8.8" onVolver={() => {}} onVerDecisiones={() => {}} />)
    const boton = screen.getByRole("button", { name: /Resolver \(opt-in\)/i })
    fireEvent.click(boton)
    await waitFor(() => expect(screen.getByText(/sin resolución/)).toBeInTheDocument())
  })

  it("muestra el PTR cuando el backend lo resuelve", async () => {
    h.trazas = publica
    h.rdns = { ip: "8.8.8.8", rdns: "dns.google" }
    render(<PerfilAtacante ip="8.8.8.8" onVolver={() => {}} onVerDecisiones={() => {}} />)
    fireEvent.click(screen.getByRole("button", { name: /Resolver \(opt-in\)/i }))
    await waitFor(() => expect(screen.getByText("dns.google")).toBeInTheDocument())
  })

  it("no ofrece rDNS para una IP de documentación", () => {
    h.trazas = [{ indice: 1, origen_ip: "198.51.100.10", prioridad: 2, timestamp: "2026-10-27T10:00:00", relaciones: { "core-db": ["objetivo"] },
      enriquecimiento_origen: { alcance: "externo", clasificacion_ip: "documentacion", inventariado: false, tercero_confiable: false, legitimo: false, geolocalizable: false, geo: null } }]
    render(<PerfilAtacante ip="198.51.100.10" onVolver={() => {}} onVerDecisiones={() => {}} />)
    expect(screen.queryByRole("button", { name: /Resolver \(opt-in\)/i })).not.toBeInTheDocument()
  })
})

describe("PerfilAtacante — riesgo", () => {
  it("muestra la insignia de riesgo del atacante", () => {
    h.trazas = [
      { indice: 1, origen_ip: "198.51.100.10", prioridad: 4, timestamp: "2026-10-27T10:00:00", relaciones: { "web-banking": ["objetivo"] } },
      { indice: 2, origen_ip: "198.51.100.10", prioridad: 4, timestamp: "2026-10-27T11:00:00", relaciones: { "core-db": ["objetivo"] } },
    ]
    render(<PerfilAtacante ip="198.51.100.10" onVolver={() => {}} onVerDecisiones={() => {}} />)
    expect(screen.getByText(/Riesgo:/)).toBeInTheDocument()
  })
})
