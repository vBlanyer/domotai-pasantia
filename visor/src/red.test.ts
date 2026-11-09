import { describe, it, expect } from "vitest"
import { disposicion, DIM } from "./red"
import type { Red } from "./api"

const nodo = (nombre: string, tipo = "servidor", zona: string | null = null) => ({
  nombre, tipo, zona, actividad: { objetivo: 0, origen: 0, contuvo_aqui: 0, pendientes: 0, estado: "sin_actividad" },
})
const BANCO: Red = {
  nodos: [nodo("internet", "externo"), nodo("fw-edge", "cortafuegos"), nodo("fw-core", "cortafuegos"),
          nodo("web-banking", "servidor", "DMZ"), nodo("api-movil", "servidor", "DMZ"),
          nodo("core-db", "servidor", "Core"), nodo("mdr-siem", "gestion", "SOC")],
  enlaces: [["fw-edge", "internet"], ["fw-core", "fw-edge"], ["web-banking", "fw-core"], ["api-movil", "fw-core"],
            ["core-db", "fw-core"], ["mdr-siem", "fw-core"]],
  dependencias: [], zonas: [{ nombre: "DMZ", nodos: ["web-banking", "api-movil"] },
                            { nombre: "Core", nodos: ["core-db"] }, { nombre: "SOC", nodos: ["mdr-siem"] }],
}

describe("disposicion", () => {
  it("coloca la cadena desde internet de arriba abajo, centrada", () => {
    const d = disposicion(BANCO)
    expect(d.nodos["internet"].y).toBeLessThan(d.nodos["fw-edge"].y)
    expect(d.nodos["fw-edge"].y).toBeLessThan(d.nodos["fw-core"].y)
    expect(d.nodos["fw-core"].x).toBe(d.ancho / 2)
  })
  it("las zonas van bajo la cadena, en el orden declarado, y sus nodos en columna", () => {
    const d = disposicion(BANCO)
    expect(d.zonas.map((z) => z.nombre)).toEqual(["DMZ", "Core", "SOC"])
    expect(d.zonas[0].x).toBeLessThan(d.zonas[1].x)
    expect(d.zonas[0].y).toBeGreaterThan(d.nodos["fw-core"].y)
    expect(d.nodos["web-banking"].x).toBe(d.nodos["api-movil"].x)
    expect(d.nodos["api-movil"].y).toBeGreaterThan(d.nodos["web-banking"].y)
    expect(d.alto).toBeGreaterThan(d.zonas[0].y + d.zonas[0].h)
  })
  it("es determinista", () => {
    expect(disposicion(BANCO)).toEqual(disposicion(BANCO))
  })
  it("con más de 4 zonas pasa a una segunda fila", () => {
    const zonas = ["A", "B", "C", "D", "E"].map((z) => ({ nombre: z, nodos: [`n${z}`] }))
    const red: Red = { nodos: zonas.map((z) => nodo(z.nodos[0], "servidor", z.nombre)), enlaces: [], dependencias: [], zonas }
    const d = disposicion(red)
    expect(d.zonas[4].y).toBeGreaterThan(d.zonas[0].y)
    expect(d.nodos["nE"].y).toBeGreaterThan(d.nodos["nA"].y + DIM.nodoAlto)
  })
  it("una red vacía no rompe", () => {
    const d = disposicion({ nodos: [], enlaces: [], dependencias: [], zonas: [] })
    expect(d.ancho).toBeGreaterThan(0)
  })
})

// ---- árbol: carril, ramas plegables, orígenes y cascada ----------------------------------------
import { origenesDe, cascadaDe, trazoDependencia } from "./red"
import type { Decision } from "./api"

describe("disposicion en árbol", () => {
  it("los externos van al carril de arriba y el tronco empieza debajo, centrado", () => {
    const d = disposicion(BANCO)
    expect(d.carril).not.toBeNull()
    expect(d.nodos["internet"].y).toBeLessThan(d.carril!.y + d.carril!.h)
    expect(d.nodos["fw-edge"].y).toBeGreaterThan(d.carril!.y + d.carril!.h)
    expect(d.nodos["fw-core"].x).toBe(d.ancho / 2)
  })
  it("cada zona es una rama con sus hojas colgando en columna bajo la píldora", () => {
    const d = disposicion(BANCO)
    const dmz = d.ramas.find((r) => r.nombre === "DMZ")!
    expect(dmz.plegada).toBe(false)
    expect(dmz.hojas.map((h) => h.nombre)).toEqual(["web-banking", "api-movil"])
    expect(d.nodos["web-banking"].y).toBeGreaterThan(dmz.y + dmz.h_pildora)
    expect(d.nodos["web-banking"].x).toBe(d.nodos["api-movil"].x)
    expect(dmz.espinaX).toBeLessThan(d.nodos["web-banking"].x - DIM.hojaAncho / 2)
  })
  it("una rama plegada no coloca sus hojas y ocupa solo la píldora", () => {
    const d = disposicion(BANCO, { plegadas: new Set(["DMZ"]) })
    const dmz = d.ramas.find((r) => r.nombre === "DMZ")!
    expect(dmz.plegada).toBe(true)
    expect(dmz.hojas).toEqual([])
    expect(d.nodos["web-banking"]).toBeUndefined()
    expect(dmz.h).toBe(dmz.h_pildora)
    expect(d.alto).toBeLessThan(disposicion(BANCO).alto)
  })
  it("el bus une las ramas y cuelga del último nodo del tronco", () => {
    const d = disposicion(BANCO)
    expect(d.bus).not.toBeNull()
    expect(d.bus!.y).toBeGreaterThan(d.nodos["fw-core"].y)
    expect(d.bus!.y).toBeLessThan(d.ramas[0].y)
    expect(d.bus!.x1).toBeLessThan(d.bus!.x2)
  })
  it("sin externos ni orígenes no hay carril", () => {
    const red: Red = { ...BANCO, nodos: BANCO.nodos.filter((n) => n.tipo !== "externo"), enlaces: [] }
    expect(disposicion(red).carril).toBeNull()
    expect(disposicion(red, { carril: true }).carril).not.toBeNull()
  })
})

const dec = (x: Partial<Decision>): Decision => x as Decision
const T: Decision[] = [
  dec({ origen_ip: "203.0.113.7", activo: "web-banking", relaciones: { "web-banking": ["objetivo"], "fw-core": ["contuvo_aqui"] }, enriquecimiento_origen: { geo: { codigo: "RU", pais: "Rusia" }, alcance: "externo" } as never }),
  dec({ origen_ip: "203.0.113.7", activo: "web-banking", relaciones: { "web-banking": ["objetivo"] } }),
  dec({ origen_ip: "203.0.113.7", activo: "api-movil", relaciones: { "api-movil": ["objetivo"] } }),
  dec({ origen_ip: "198.51.100.23", activo: "api-movil", relaciones: { "api-movil": ["objetivo"] } }),
  dec({ origen_ip: "192.0.2.55", activo: "ssh-bastion", relaciones: { "ssh-bastion": ["objetivo"] } }),
  dec({ origen_ip: "10.0.40.12", activo: "ssh-bastion", relaciones: { "ssh-bastion": ["objetivo"] } }),
  dec({ tipo: "actividad_suprimida", origen_ip: "203.0.113.7", alertas_suprimidas: 14 }),   // sistema: no cuenta
  dec({ tipo: "actividad_propia", activo: "fw-core" }),
]

describe("origenesDe: los orígenes que más atacan, para el carril", () => {
  it("ordena por ataques, trae país y objetivos, y pliega el resto", () => {
    const o = origenesDe(T, 2)
    expect(o.total).toBe(4)
    expect(o.top.map((x) => [x.ip, x.n])).toEqual([["203.0.113.7", 3], ["198.51.100.23", 1]])
    expect(o.top[0].codigo).toBe("RU")
    expect(o.top[0].objetivos).toEqual({ "web-banking": 2, "api-movil": 1 })
    expect(o.resto).toBe(2)
  })
  it("sin trazas, nada", () => {
    expect(origenesDe([], 4)).toEqual({ top: [], resto: 0, total: 0 })
  })
})

describe("cascadaDe: qué arrastra un equipo caído, siguiendo las dependencias", () => {
  const red: Red = {
    nodos: [nodo("db-core"), nodo("api-movil"), nodo("web-banking"), nodo("smb-files")].map((n, i) =>
      i === 0 ? { ...n, salud: "caido", actividad: { ...n.actividad, estado: "caido" } } : n),
    enlaces: [], zonas: [],
    dependencias: [["api-movil", "db-core"], ["web-banking", "db-core"], ["smb-files", "web-banking"]],
  }
  it("del caído a cada dependiente, también transitivo, sin repetir", () => {
    expect(cascadaDe(red).sort()).toEqual([["db-core", "api-movil"], ["db-core", "smb-files"], ["db-core", "web-banking"]].sort())
  })
  it("sin caídos no hay cascada", () => {
    expect(cascadaDe({ ...red, nodos: red.nodos.map((n) => ({ ...n, salud: null, actividad: { ...n.actividad, estado: "sin_actividad" } })) })).toEqual([])
  })
})

describe("trazoDependencia", () => {
  it("en la misma columna, un arco por la derecha que no atraviesa las cajas", () => {
    const d = trazoDependencia({ x: 100, y: 50 }, { x: 100, y: 130 }, 120, 120)
    expect(d).toBe("M160,50 C180,50 180,130 160,130")      // borde derecho (100 + 60), comba 10 + 80/8
    expect(trazoDependencia({ x: 100, y: 50 }, { x: 100, y: 900 }, 120, 120)).toContain("C190,50")   // comba máxima 30
  })
  it("en columnas distintas, de borde a borde", () => {
    expect(trazoDependencia({ x: 100, y: 50 }, { x: 300, y: 90 }, 120, 120)).toBe("M160,50 C200,50 200,90 240,90")
    expect(trazoDependencia({ x: 300, y: 90 }, { x: 100, y: 50 }, 120, 120)).toBe("M240,90 C200,90 200,50 160,50")
  })
})


describe("disposicion con una red ramificada", () => {
  // el banco con Tiendas detrás de su propio cortafuegos, que cuelga de fw-core
  const TIENDAS: Red = {
    ...BANCO,
    nodos: [...BANCO.nodos, nodo("fw-tiendas", "cortafuegos"), nodo("pos-1", "puesto", "Tiendas"), nodo("pos-2", "puesto", "Tiendas")],
    enlaces: [...BANCO.enlaces, ["fw-tiendas", "fw-core"], ["pos-1", "fw-tiendas"], ["pos-2", "fw-tiendas"]],
    zonas: [...BANCO.zonas, { nombre: "Tiendas", nodos: ["pos-1", "pos-2"] }],
  }

  it("en cadena se dispone igual que siempre", () => {
    const d = disposicion(BANCO)
    expect(d.buses).toEqual([{ desde: "fw-core", ...d.bus! }])
    expect(d.troncoPadre).toEqual({ "fw-edge": null, "fw-core": "fw-edge" })
    expect(d.ramas.every((r) => r.desde === "fw-core")).toBe(true)
  })

  it("cada zona cuelga de su cortafuegos real, con un bus por cortafuegos", () => {
    const d = disposicion(TIENDAS)
    expect(Object.fromEntries(d.ramas.map((r) => [r.nombre, r.desde]))).toEqual({ DMZ: "fw-core", Core: "fw-core", SOC: "fw-core", Tiendas: "fw-tiendas" })
    expect(d.buses.map((b) => b.desde)).toEqual(["fw-core", "fw-tiendas"])
    expect(d.troncoPadre["fw-tiendas"]).toBe("fw-core")
    const tiendas = d.ramas.find((r) => r.nombre === "Tiendas")!
    expect(d.nodos["fw-tiendas"].x).toBeCloseTo(tiendas.cx)                       // encima de su zona
    expect(Math.abs(d.nodos["fw-core"].x - tiendas.cx)).toBeGreaterThan(DIM.colAncho) // y no encima de ella
    expect(new Set(d.ramas.map((r) => r.y)).size).toBe(1)                         // las filas empiezan a la par
  })

  it("nada se solapa ni se sale del lienzo", () => {
    const d = disposicion(TIENDAS)
    const ps = Object.entries(d.nodos)
    for (const [n, p] of ps) {
      expect(p.x - DIM.nodoAncho / 2, n).toBeGreaterThanOrEqual(0)
      expect(p.x + DIM.nodoAncho / 2, n).toBeLessThanOrEqual(d.ancho)
    }
    for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++)
      expect(Math.abs(ps[i][1].x - ps[j][1].x) >= DIM.nodoAncho - 2 || Math.abs(ps[i][1].y - ps[j][1].y) >= DIM.hojaAlto - 2, `${ps[i][0]}/${ps[j][0]}`).toBe(true)
  })

  it("una zona sin enlaces cuelga del último cortafuegos, como siempre", () => {
    const d = disposicion({ ...TIENDAS, zonas: [...TIENDAS.zonas, { nombre: "Suelta", nodos: [] }] })
    expect(d.ramas.find((r) => r.nombre === "Suelta")!.desde).toBe("fw-tiendas")
  })
})
