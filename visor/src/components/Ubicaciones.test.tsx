import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, within } from "@testing-library/react"

const h = vi.hoisted(() => ({ trazas: [] as unknown[] }))
vi.mock("@/api", async (orig) => ({ ...(await orig<typeof import("@/api")>()), useSondeo: () => h.trazas }))
import { Ubicaciones } from "./Ubicaciones"

describe("Ubicaciones", () => {
  it("pone los países en el mapa y los cubos (lab/interna) en la tabla", () => {
    h.trazas = [
      { indice: 1, origen_ip: "8.8.8.8", prioridad: 4, relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
      { indice: 2, origen_ip: "198.51.100.10", prioridad: 3, relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "documentacion", geo: null } },
    ]
    render(<Ubicaciones />)
    expect(screen.getAllByText(/Estados Unidos/).length).toBeGreaterThan(0)   // en el mapa y en la tabla
    expect(screen.getByText(/Documentación \(IPs de ejemplo\)/)).toBeInTheDocument()
    expect(document.querySelector("svg circle")).toBeTruthy()      // un país en el mapa
    expect(document.querySelectorAll("svg path").length).toBeGreaterThan(20)   // siluetas de tierra (mapamundi)
  })

  it("el filtro cambia la métrica del mapa y numera el punto; mitigados = contenida", () => {
    h.trazas = [
      { indice: 1, origen_ip: "8.8.8.1", contencion: "contenida", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
      { indice: 2, origen_ip: "8.8.8.2", contencion: "fallida", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
      { indice: 3, origen_ip: "8.8.8.3", contencion: "sin_accion", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
    ]
    render(<Ubicaciones />)
    // por defecto «En curso» = 2 (recibidos no contenidos): el punto del mapa lleva el 2
    const svg = document.querySelector("svg")!
    expect(within(svg as unknown as HTMLElement).getByText("2")).toBeTruthy()
    // al filtrar «Mitigados», el punto pasa a 1 (solo el contenido)
    fireEvent.click(screen.getByRole("button", { name: /Mitigados/i }))
    expect(within(document.querySelector("svg") as unknown as HTMLElement).getByText("1")).toBeTruthy()
  })

  it("sin geolocalizables lo dice (solo lab/internos)", () => {
    h.trazas = [{ indice: 1, origen_ip: "198.51.100.10", prioridad: 3, relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "documentacion", geo: null } }]
    render(<Ubicaciones />)
    expect(screen.getByText(/Sin orígenes geolocalizables/)).toBeInTheDocument()
  })

  it("al pulsar un país navega según el filtro: Total→Decisiones(país), En curso→Aprobaciones", () => {
    h.trazas = [
      { indice: 1, origen_ip: "8.8.8.1", contencion: "fallida", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
    ]
    const onVerPais = vi.fn(), onVerAprobaciones = vi.fn()
    render(<Ubicaciones onVerPais={onVerPais} onVerAprobaciones={onVerAprobaciones} />)
    // filtro «Total» → Decisiones filtradas por el país
    fireEvent.click(screen.getByRole("button", { name: /Total/i }))
    fireEvent.click(screen.getByTitle("Ver en Decisiones"))
    expect(onVerPais).toHaveBeenCalledWith("Estados Unidos")
    expect(onVerAprobaciones).not.toHaveBeenCalled()
    // filtro «En curso» → Aprobaciones
    fireEvent.click(screen.getByRole("button", { name: /En curso/i }))
    fireEvent.click(screen.getByTitle("Ver en Aprobaciones"))
    expect(onVerAprobaciones).toHaveBeenCalled()
  })

  it("hover sobre un punto muestra el desglose de las tres métricas", () => {
    h.trazas = [
      { indice: 1, origen_ip: "8.8.8.1", contencion: "contenida", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
      { indice: 2, origen_ip: "8.8.8.2", contencion: "fallida", relaciones: { "web-banking": ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -122 } } },
    ]
    render(<Ubicaciones />)
    fireEvent.mouseMove(document.querySelector("svg circle")!, { clientX: 100, clientY: 100 })
    expect(screen.getByText(/En curso 1/)).toBeInTheDocument()
    expect(screen.getByText(/Total 2/)).toBeInTheDocument()
    expect(screen.getByText(/Mitigados 1/)).toBeInTheDocument()
  })

  it("pagina la tabla de ubicaciones a 20 por página y «Siguiente» avanza", () => {
    h.trazas = Array.from({ length: 25 }, (_, i) => ({
      indice: i + 1, origen_ip: `8.8.${i}.8`, prioridad: 2, relaciones: { "web-banking": ["objetivo"] },
      enriquecimiento_origen: { clasificacion_ip: "publica", geo: { pais: `País ${i + 1}`, codigo: `P${i + 1}`, lat: 10 + i, lon: 10 + i } },
    }))
    render(<Ubicaciones />)
    const filas = () => screen.getByRole("table").querySelectorAll("tbody tr").length
    expect(filas()).toBe(20)
    expect(screen.getByText(/Página 1 de 2/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }))
    expect(filas()).toBe(5)
  })

  it("sin base de geolocalización lo avisa (la atribución de DB-IP va al pie del menú)", () => {
    h.trazas = [{ indice: 1, origen_ip: "45.1.2.3", relaciones: { web01: ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo: null, geo_base: false } }]
    const { unmount } = render(<Ubicaciones />)
    expect(screen.getByText(/No hay base de geolocalización/)).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "IP Geolocation by DB-IP" })).toBeNull()
    unmount()
    h.trazas = [{ indice: 1, origen_ip: "8.8.8.8", relaciones: { web01: ["objetivo"] }, enriquecimiento_origen: { clasificacion_ip: "publica", geo_base: true, geo: { pais: "Estados Unidos", codigo: "US", lat: 37, lon: -95, fuente: "dbip" } } }]
    render(<Ubicaciones />)
    expect(screen.queryByText(/No hay base de geolocalización/)).toBeNull()
  })
})
