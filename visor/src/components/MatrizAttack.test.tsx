import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { MatrizAttack } from "./MatrizAttack"
import { TECNICAS } from "@/attack"

describe("MatrizAttack", () => {
  it("agrupa cada técnica observada bajo su táctica y muestra el conteo", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T1110", n: 161 }, { tecnica: "T1210", n: 137 }]} />)
    // columnas por táctica (nuestra taxonomía, no las 14 de enterprise)
    expect(screen.getByText("Acceso a credenciales")).toBeInTheDocument()   // T1110
    expect(screen.getByText("Movimiento lateral")).toBeInTheDocument()      // T1210
    const celda = document.querySelector('[data-tecnica="T1110"]')
    expect(celda).toHaveAttribute("data-activa", "true")
    expect(celda).toHaveTextContent("161")
  })

  it("una técnica cubierta pero no vista aparece inactiva (tenue)", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T1110", n: 10 }]} />)
    expect(document.querySelector('[data-tecnica="T1110"]')).toHaveAttribute("data-activa", "true")
    // T1548 está en el mapa (la cubrimos) pero no se ha visto -> inactiva
    expect(document.querySelector('[data-tecnica="T1548"]')).toHaveAttribute("data-activa", "false")
  })

  it("una técnica desconocida no rompe la matriz y cae a 'Otras' con su id", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T9999", n: 3 }]} />)
    expect(screen.getByText("Otras")).toBeInTheDocument()
    const celda = document.querySelector('[data-tecnica="T9999"]')
    expect(celda).toHaveTextContent("T9999")
    expect(celda).toHaveTextContent("3")
  })

  it("sin técnicas desconocidas no aparece la columna 'Otras'", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T1595", n: 1 }]} />)
    expect(screen.queryByText("Otras")).not.toBeInTheDocument()
  })

  it("cubre las familias nuevas bajo Impacto: FIM (T1565) y DoS (T1498/T1499), no en 'Otras'", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T1565", n: 2 }, { tecnica: "T1498", n: 1 }, { tecnica: "T1499", n: 1 }]} />)
    expect(screen.getByText("Impacto")).toBeInTheDocument()
    expect(screen.queryByText("Otras")).not.toBeInTheDocument()
    expect(document.querySelector('[data-tecnica="T1565"]')).toHaveAttribute("data-activa", "true")
    expect(document.querySelector('[data-tecnica="T1498"]')).toHaveAttribute("data-activa", "true")
  })

  it("cubre la familia abuso de cuenta (T1548 escalada, T1136/T1098 persistencia), no en 'Otras'", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T1548", n: 3 }, { tecnica: "T1136", n: 2 }, { tecnica: "T1098", n: 1 }]} />)
    expect(screen.getByText("Persistencia")).toBeInTheDocument()
    expect(screen.queryByText("Otras")).not.toBeInTheDocument()
    expect(document.querySelector('[data-tecnica="T1548"]')).toHaveAttribute("data-activa", "true")
    expect(document.querySelector('[data-tecnica="T1136"]')).toHaveAttribute("data-activa", "true")
    expect(document.querySelector('[data-tecnica="T1098"]')).toHaveAttribute("data-activa", "true")
  })

  it("cubre acceso consumado (T1078/T1021) en Movimiento lateral / Acceso inicial, no en 'Otras'", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T1078", n: 2 }, { tecnica: "T1021", n: 2 }]} />)
    expect(screen.getByText("Movimiento lateral")).toBeInTheDocument()
    expect(screen.queryByText("Otras")).not.toBeInTheDocument()
    expect(document.querySelector('[data-tecnica="T1021"]')).toHaveAttribute("data-activa", "true")
  })

  it("con cobertura de las 8 familias, TODAS las celdas de la matriz quedan activas (se llena entera)", () => {
    // Cobertura por familia: un ataque por familia enciende todas las técnicas de familias.yml.
    const todas = Object.keys(TECNICAS).map((t) => ({ tecnica: t, n: 1 }))
    render(<MatrizAttack tecnicas={todas} />)
    expect(screen.queryByText("Otras")).not.toBeInTheDocument()   // nada fuera del mapa
    const celdas = Array.from(document.querySelectorAll("[data-tecnica]"))
    expect(celdas.length).toBe(Object.keys(TECNICAS).length)
    expect(celdas.every((c) => c.getAttribute("data-activa") === "true")).toBe(true)
  })

  it("muestra las tácticas fuera de alcance (por diseño), no como huecos", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T1110", n: 1 }]} />)
    expect(screen.getByText("Recolección")).toBeInTheDocument()            // táctica no cubierta
    expect(screen.getByText("Desarrollo de recursos")).toBeInTheDocument()
    expect(screen.getAllByText("fuera de alcance").length).toBeGreaterThan(0)
    expect(screen.getByText(/12 de 14/)).toBeInTheDocument()               // cobertura honesta
  })
})
