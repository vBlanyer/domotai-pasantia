import { describe, it, expect } from "vitest"
import { readFileSync } from "node:fs"
import { join } from "node:path"

// El panel derecho de cada vista (inspector) tiene su propio scroll: se queda a la vista sin alargar la
// página. jsdom no calcula el layout, así que se comprueba el contrato: todos usan la clase `inspector`
// (sticky + altura máxima del área visible + overflow), ninguno el sticky suelto de antes.
const SRC = join(__dirname)
const leer = (f: string) => readFileSync(join(SRC, f), "utf-8")
const VISTAS = ["Aprobaciones", "Decisiones", "Trazas", "Contenciones", "Incidentes", "Conectividad", "Red"]

describe("paneles derechos con scroll propio", () => {
  it.each(VISTAS)("%s usa la clase inspector y no el sticky suelto", (v) => {
    const s = leer(`components/${v}.tsx`)
    expect(s).toMatch(/className="inspector /)
    expect(s).not.toContain("lg:sticky")
  })

  it("la clase limita la altura al área visible y da scroll", () => {
    const css = leer("index.css")
    expect(css).toMatch(/\.inspector\s*\{[^}]*position:\s*sticky[^}]*max-height:\s*calc\(100cqh[^}]*overflow-y:\s*auto/)
  })

  it("la consola ajusta el alto de los paneles a lo que queda visible desde donde empiezan", () => {
    const app = leer("App.tsx")
    expect(app).toMatch(/useAjusteInspectores\(\w+\)/)
    expect(app).toMatch(/<main ref=\{\w+\}/)
  })

  it("el área principal es el contenedor de esa altura", () => {
    expect(leer("App.tsx")).toMatch(/<main [^>]*className="[^"]*\[container-type:size\]/)
  })
})
