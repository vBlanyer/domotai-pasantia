import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, within, waitFor } from "@testing-library/react"
import { Toaster } from "@/components/ui/toast"

const h = vi.hoisted(() => ({ trazas: [] as unknown[], contenciones: [] as unknown[], caso: { estado: "nuevo", asignado: null, notas: [] } as unknown, actualizar: vi.fn(async () => true) }))
vi.mock("@/api", async (orig) => {
  const real = await orig<typeof import("@/api")>()
  return {
    ...real,
    useSondeo: (fn: unknown) => (fn === real.getContenciones ? h.contenciones : h.trazas),
    getCaso: () => Promise.resolve(h.caso),
    actualizarCaso: h.actualizar,
  }
})
import { Incidentes } from "./Incidentes"

const ahora = Date.now()
const hace = (min: number) => new Date(ahora - min * 60_000).toISOString()
const REGS = [
  { indice: 1, id_decision: "d1", origen_ip: "203.0.113.9", prioridad: 4, timestamp: hace(30), relaciones: { "web-banking": ["objetivo"] },
    clase: "vp_intento_acceso", accion_final: "BLOQUEAR_IP", contencion: "contenida" },
  { indice: 2, id_decision: "d2", origen_ip: "203.0.113.20", prioridad: 3, timestamp: hace(25), relaciones: { "core-db": ["objetivo"] },
    clase: "vp_intento_acceso", accion_final: "BLOQUEAR_IP", contencion: "contenida" },
  { indice: 3, id_decision: "d3", origen_ip: "1.1.1.1", prioridad: 2, timestamp: hace(60 * 30), relaciones: { "web-banking": ["objetivo"] },
    clase: "vp_intento_acceso", accion_final: "MATAR_CONEXION" },
  { indice: 4, tipo: "actualizacion_caso", id_decision: "inc:203.0.113", estado: "en_revision", asignado: "Blanyer", decidido_en: hace(20) },
]
const vista = (props = {}) => render(<Toaster><Incidentes {...props} /></Toaster>)
const fila = (clave: string) => document.querySelector(`[data-incidente="${clave}"] button`) as HTMLElement
const caso = () => within(screen.getByRole("region", { name: "Incidente" }))

describe("Incidentes", () => {
  beforeEach(() => { h.trazas = REGS; h.contenciones = []; h.actualizar.mockClear(); h.caso = { estado: "nuevo", asignado: null, notas: [] } })

  it("agrupa las IPs rotadas de un /24 en un incidente con su caso plegado, quién lo lleva y si sigue activo", () => {
    vista()
    expect(within(fila("inc:203.0.113")).getByText("203.0.113.0/24")).toBeInTheDocument()
    expect(within(fila("inc:203.0.113")).getByText("En revisión")).toBeInTheDocument()
    expect(within(fila("inc:203.0.113")).getByText("Blanyer")).toBeInTheDocument()
    expect(within(fila("inc:203.0.113")).getByTitle(/activo ahora/)).toBeInTheDocument()
    expect(within(fila("inc:1.1.1")).getByText("sin asignar")).toBeInTheDocument()
  })

  it("el caso se abre a la derecha con la historia, los equipos y solo la cronología de su bloque", () => {
    vista()
    expect(caso().getByText(/2 IPs del mismo bloque atacaron 2 equipos/)).toBeInTheDocument()
    expect(within(caso().getByRole("list", { name: "Equipos atacados" })).getAllByRole("listitem")).toHaveLength(2)
    expect(caso().getAllByText("BLOQUEAR_IP")).toHaveLength(2)             // las decisiones del /24…
    expect(caso().queryByText("MATAR_CONEXION")).not.toBeInTheDocument()   // …y no la de 1.1.1.1
    expect(caso().getByText("Caso")).toBeInTheDocument()                    // panel del caso a nivel incidente
  })

  it("por defecto solo los abiertos; «Resueltos» y «Todos» cambian la lista", () => {
    h.trazas = [...REGS, { indice: 5, tipo: "actualizacion_caso", id_decision: "inc:1.1.1", estado: "resuelto", nota: "proveedor", decidido_en: hace(5) }]
    vista()
    expect(fila("inc:1.1.1")).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: /^Resueltos/ }))
    expect(within(fila("inc:1.1.1")).getByText(/cerrado: «proveedor»/)).toBeInTheDocument()
    expect(fila("inc:203.0.113")).toBeNull()
  })

  it("al pulsar otro incidente, el caso cambia sin salir de la vista; los saltos llevan su bloque", () => {
    const verDec = vi.fn()
    vista({ onVerDecisiones: verDec })
    fireEvent.click(fila("inc:1.1.1"))
    expect(fila("inc:1.1.1")).toHaveAttribute("aria-current", "true")
    fireEvent.click(caso().getByRole("button", { name: "Ver las decisiones del bloque" }))
    expect(verDec).toHaveBeenCalledWith("1.1.1.")
  })

  it("llegando desde otra vista abre ese incidente", () => {
    vista({ claveInicial: "inc:1.1.1" })
    expect(fila("inc:1.1.1")).toHaveAttribute("aria-current", "true")
  })

  it("«Resolver con esta nota» cierra el caso con el motivo", async () => {
    vista()
    fireEvent.change(caso().getByLabelText("Nota del analista"), { target: { value: "falso positivo de un proveedor" } })
    fireEvent.click(caso().getByRole("button", { name: "Resolver con esta nota" }))
    await waitFor(() => expect(h.actualizar).toHaveBeenCalledWith("inc:203.0.113", { estado: "resuelto", nota: "falso positivo de un proveedor" }))
  })

  it("sin ataques agrupables lo dice", () => {
    h.trazas = []
    vista()
    expect(screen.getByText(/Sin incidentes/)).toBeInTheDocument()
  })

  it("pagina los incidentes a 20 por página y «Siguiente» avanza", () => {
    h.trazas = Array.from({ length: 25 }, (_, i) => ({
      indice: i + 1, origen_ip: `203.0.${i}.9`, prioridad: 3, timestamp: hace(i),
      relaciones: { "web-banking": ["objetivo"] }, clase: "vp_intento_acceso",
    }))
    vista()
    const filas = () => document.querySelectorAll("[data-incidente]").length
    expect(filas()).toBe(20)
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }))
    expect(filas()).toBe(5)
  })
})
