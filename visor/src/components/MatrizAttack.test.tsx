import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { MatrizAttack } from "./MatrizAttack"

describe("MatrizAttack", () => {
  it("agrupa cada técnica observada bajo su táctica y muestra el conteo", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T1110.001", n: 161 }, { tecnica: "T1021.004", n: 137 }]} />)
    // columnas por táctica (nuestra taxonomía, no las 14 de enterprise)
    expect(screen.getByText("Acceso a credenciales")).toBeInTheDocument()   // T1110.*
    expect(screen.getByText("Movimiento lateral")).toBeInTheDocument()      // T1021.*
    const celda = document.querySelector('[data-tecnica="T1110.001"]')
    expect(celda).toHaveAttribute("data-activa", "true")
    expect(celda).toHaveTextContent("161")
  })

  it("una técnica cubierta pero no vista aparece inactiva (tenue)", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T1110.001", n: 10 }]} />)
    expect(document.querySelector('[data-tecnica="T1110.001"]')).toHaveAttribute("data-activa", "true")
    // T1110.002 está en el mapa (la cubrimos) pero no se ha visto -> inactiva
    expect(document.querySelector('[data-tecnica="T1110.002"]')).toHaveAttribute("data-activa", "false")
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

  it("cubre T1055 (aparece en trazas reales) bajo Evasión de defensas, no en 'Otras'", () => {
    render(<MatrizAttack tecnicas={[{ tecnica: "T1055", n: 17 }]} />)
    expect(screen.getByText("Evasión de defensas")).toBeInTheDocument()
    expect(screen.queryByText("Otras")).not.toBeInTheDocument()
    expect(document.querySelector('[data-tecnica="T1055"]')).toHaveAttribute("data-activa", "true")
  })
})
