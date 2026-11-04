import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, within, act } from "@testing-library/react"
import type { Metricas as Datos } from "@/api"

// Modo en vivo: getMetricas() sin periodo. Modo periodo: getMetricas({desde,hasta}).
const h = vi.hoisted(() => ({ vivo: null as unknown, periodo: null as unknown }))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  getMetricas: async (p?: { desde?: string; hasta?: string }) => (p ? h.periodo : h.vivo),
  getVerificacion: async () => ({ ok: true, roto_en: null }),
  getTrazas: async () => [
    { id_decision: "d1", timestamp: `${new Date().toISOString().slice(0, 10)}T10:00:00Z`, activo: "web-banking",
      clase: "vp_intento_acceso", accion_final: "BLOQUEAR_IP", contencion: "fallida", hash: "a".repeat(64) },
  ],
}))
vi.mock("./charts", () => ({ Donut: () => null, Tendencia: () => null, Barras: () => null }))
vi.mock("./MatrizAttack", () => ({ MatrizAttack: () => null }))
import { Metricas } from "./Metricas"

const base: Datos = {
  total: 342, fp: 7, tasa_fp: 0.021, auto: 243, pct_auto: 0.71, suprimidas: 124,
  escalado_humano: 99, pct_humano: 0.29, resueltos_humano: 99, override: 8, tasa_override: 0.023,
  mttr_seg: 48, por_clase: { vp_intento_acceso: 168, no_soportada: 72 },
  veredictos: { aprobar: 10, rechazar: 2 }, por_dia: [{ dia: "2026-10-14", n: 31 }],
  top_activos: [{ nombre: "web-banking", n: 98 }], mitre: [{ tecnica: "T1110.001", n: 161 }],
  mttr_mediano_seg: 32, sla_umbral_seg: 900, sla_resueltos: 99, sla_dentro: 95, sla_incumplidos: 4, sla_pct: 0.96,
}

describe("Métricas (vista unificada métricas + informe)", () => {
  beforeEach(() => { h.vivo = null; h.periodo = null })

  it("por defecto mide en vivo, con el donut de veredictos y el botón de PDF", async () => {
    h.vivo = { ...base }                                                    // en vivo: sin desde/hasta
    render(<Metricas />)
    expect(await screen.findByText("En vivo · sesión actual")).toBeInTheDocument()   // etiqueta del modo vivo
    expect(screen.getByText("Veredictos humanos")).toBeInTheDocument()      // donut exclusivo de Métricas
    expect(screen.getByRole("button", { name: "En vivo" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Vista previa del PDF/ })).toBeDisabled()   // en vivo no se exporta
  })

  it("decisiones por analista, con las sin nombre al final; sin el dato (daemon anterior) no se pinta", async () => {
    h.vivo = { ...base, por_analista: [
      { analista: "Blanyer.Vielma", aprobar: 3, rechazar: 0, reclasificar: 0, total: 3, mediana_seg: 102, fuera_sla: 0 },
      { analista: null, aprobar: 5, rechazar: 0, reclasificar: 0, total: 5, mediana_seg: 76, fuera_sla: 1 },
    ] }
    const { unmount } = render(<Metricas />)
    expect(await screen.findByText("Decisiones por analista")).toBeInTheDocument()
    expect(screen.getByText("Blanyer.Vielma").closest("tr")).toHaveTextContent("Blanyer.Vielma300102 s0")
    expect(screen.getByText("sin nombre registrado")).toBeInTheDocument()
    unmount()
    h.vivo = { ...base }
    render(<Metricas />)
    await screen.findByText("En vivo · sesión actual")
    expect(screen.queryByText("Decisiones por analista")).not.toBeInTheDocument()
  })

  it("muestra los tiempos de respuesta y el SLA", async () => {
    h.vivo = { ...base }
    render(<Metricas />)
    expect(await screen.findByText("MTTR mediano")).toBeInTheDocument()
    expect(screen.getByText(/dentro de SLA \(15 min\)/)).toBeInTheDocument()
    expect(screen.getByText("SLA incumplidos")).toBeInTheDocument()
  })

  it("al elegir «Este mes» consulta el periodo y muestra su etiqueta", async () => {
    h.vivo = { ...base }
    h.periodo = { ...base, desde: "2026-10-01", hasta: "2026-10-31" }
    render(<Metricas />)
    await screen.findByText("En vivo · sesión actual")
    fireEvent.click(screen.getByRole("button", { name: "Este mes" }))
    expect(await screen.findByText("octubre de 2026")).toBeInTheDocument()
    expect(screen.getByText("342 decisiones en el periodo")).toBeInTheDocument()
  })

  const abrirPrevia = async () => {
    h.vivo = { ...base }
    h.periodo = { ...base, desde: "2026-10-01", hasta: "2026-10-31" }
    render(<Metricas />)
    await screen.findByText("En vivo · sesión actual")
    fireEvent.click(screen.getByRole("button", { name: "Este mes" }))
    await screen.findByText("342 decisiones en el periodo")
  }

  it("con un periodo, la vista previa muestra el documento paginado con su nombre de archivo", async () => {
    await abrirPrevia()
    expect(screen.getAllByText(/^Informe-MDR-\d{4}-\d{2}\.pdf$/).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole("button", { name: /Vista previa del PDF/ }))
    const previa = await screen.findByRole("dialog", { name: "Vista previa del informe" })
    const hojas = within(previa).getAllByRole("region", { name: /^Página \d+ de \d+$/ })
    expect(hojas.length).toBe(6)     // portada + resumen, indicadores, amenazas, incidentes y humanas, anexo
    expect(within(previa).getByText("Resumen ejecutivo", { selector: "h2" })).toBeInTheDocument()
    expect(within(previa).getByText(/cadena íntegra/)).toBeInTheDocument()
    expect(within(previa).getByText(/en web-banking/)).toBeInTheDocument()   // la contención fallida del periodo
  })

  it("quitar una sección la saca del documento", async () => {
    await abrirPrevia()
    fireEvent.click(screen.getByRole("checkbox", { name: "Amenazas y orígenes" }))
    fireEvent.click(screen.getByRole("button", { name: /Vista previa del PDF/ }))
    const previa = await screen.findByRole("dialog", { name: "Vista previa del informe" })
    expect(within(previa).queryByText("Amenazas y orígenes", { selector: "h2" })).toBeNull()
    expect(within(previa).getAllByRole("region", { name: /^Página/ }).length).toBe(5)
  })

  it("«Guardar PDF» imprime solo el documento con el nombre del archivo como título y luego lo restaura", async () => {
    await abrirPrevia()
    fireEvent.click(screen.getByRole("button", { name: /Vista previa del PDF/ }))
    const previa = await screen.findByRole("dialog", { name: "Vista previa del informe" })
    document.title = "Consola MDR"
    let enImpresion = { titulo: "", marcado: false }
    const print = vi.spyOn(window, "print").mockImplementation(() => {
      enImpresion = { titulo: document.title, marcado: document.documentElement.classList.contains("imprimiendo-informe") }
    })
    fireEvent.click(within(previa).getByRole("button", { name: "Guardar PDF" }))
    expect(print).toHaveBeenCalled()
    expect(enImpresion.titulo).toMatch(/^Informe-MDR-\d{4}-\d{2}$/)
    expect(enImpresion.marcado).toBe(true)
    act(() => { window.dispatchEvent(new Event("afterprint")) })
    expect(document.title).toBe("Consola MDR")
    expect(document.documentElement.classList.contains("imprimiendo-informe")).toBe(false)
    fireEvent.click(within(previa).getByRole("button", { name: "Cerrar" }))
    expect(screen.queryByRole("dialog", { name: "Vista previa del informe" })).toBeNull()
  })
})
