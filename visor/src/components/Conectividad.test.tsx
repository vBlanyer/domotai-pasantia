import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { Toaster } from "@/components/ui/toast"

const h = vi.hoisted(() => ({
  datos: {} as unknown,
  probar: vi.fn(), guardar: vi.fn(), defecto: vi.fn(), leer: vi.fn(), aceptar: vi.fn(),
  inventario: vi.fn(), alta: vi.fn(), paquete: vi.fn(), rotar: vi.fn(), probarEquipo: vi.fn(), generar: vi.fn(),
  sesion: { modo: "identificado", operador: "ana", desde: 0 } as unknown,
}))
vi.mock("@/api", async (orig) => ({
  ...(await orig<typeof import("@/api")>()),
  getConectividad: async () => h.datos,
  probarConexion: h.probar, guardarConexion: h.guardar, guardarUsuarioDefecto: h.defecto,
  leerClaveHost: h.leer, aceptarClaveHost: h.aceptar,
  guardarInventario: h.inventario, darDeAlta: h.alta, getPaquete: h.paquete, rotarClave: h.rotar, probarEquipo: h.probarEquipo,
  generarClaveConector: h.generar,
  sesionActual: () => h.sesion, operadorActual: () => "ana",
}))
import { Conectividad } from "./Conectividad"

const PRUEBA_OK = { ok: true, estado: "verificada", en: "2026-11-04T10:00:00Z", puerto: 2222, usuario: "triaje",
  pasos: [{ paso: "entra y ejecuta un comando del catálogo", ok: true, detalle: "correctos" }, { paso: "sudo deniega lo que está fuera del catálogo", ok: true, detalle: "denegado" }] }
const equipo = (x: object) => ({ nombre: "fw-core", ip: "10.0.0.1", zona: "Borde", tipo: "cortafuegos", funcion: null, protegido: false,
  puerto: 22, usuario: "triaje", ajustado: false, huella_fijada: "SHA256:FWFIJADA", ultima_prueba: null, ...x })
const base = (x: object = {}) => ({
  modo: "clave", nodo_gestion: "clab-banco-mdr-siem", editable: true, motivo_no_editable: null,
  usuario_defecto: null, usuario_entorno: "triaje", ruta_clave: "/root/.ssh/triaje", known_hosts: "/root/.ssh/known_hosts_triaje",
  clave: { huella: "SHA256:CONECTOR", tipo: "ED25519", publica: "ssh-ed25519 AAAA conector" },
  equipos: [equipo({}), equipo({ nombre: "db-core", ip: "10.0.20.10", huella_fijada: "SHA256:DBVIEJA", ultima_prueba: { ok: false, estado: "host_cambiada", pasos: [] } }),
            equipo({ nombre: "monitor", ip: "10.0.30.3", protegido: true })],
  cambios: [], permisos: { probar: true, editar: true, motivo: null },
  papeles: [{ id: "servidor", nombre: "Servidor", descripcion: "Observar, bloquear…", acciones: ["OBS_CONEXIONES", "BLOQUEAR_IP", "CERRAR_SERVICIO"] },
            { id: "puesto", nombre: "Puesto", descripcion: "Observar y cortar…", acciones: ["OBS_CONEXIONES", "MATAR_CONEXION"] }],
  acciones: [{ id: "OBS_CONEXIONES", comando: "ss -tunap", nunca_automatica: false, lista: null },
             { id: "BLOQUEAR_IP", comando: "iptables -A INPUT -s {ip} -j DROP", nunca_automatica: false, lista: null },
             { id: "MATAR_CONEXION", comando: "ss -K dst {ip}", nunca_automatica: false, lista: null },
             { id: "CERRAR_SERVICIO", comando: "service {servicio} stop", nunca_automatica: false, lista: "servicios" }],
  zonas: ["Borde", "Servidores"], activos: ["fw-core", "db-core"], criticidades: ["baja", "media", "alta"], rotacion: null, ...x,
})
const vista = () => <Toaster><Conectividad /></Toaster>
const region = () => within(screen.getByRole("region", { name: "Equipo" }))

describe("Conectividad", () => {
  beforeEach(() => {
    for (const f of [h.probar, h.guardar, h.defecto, h.leer, h.aceptar, h.inventario, h.alta, h.paquete, h.rotar, h.probarEquipo, h.generar]) f.mockReset()
    h.datos = base(); h.sesion = { modo: "identificado", operador: "ana", desde: 0 }
  })

  it("enseña el conector, su huella, el resumen y cada equipo; nunca una clave privada", async () => {
    render(vista())
    expect(await screen.findByText("SHA256:CONECTOR")).toBeInTheDocument()
    expect(screen.getByText("Clave · vía nodo de gestión").tagName).toBe("B")              // el modo es información, no un selector
    expect(screen.getByRole("status")).toHaveTextContent("Firmas como ana, verificado por tu token.")
    expect(screen.getByText(/Canal de gestión del MDR: no se contiene/)).toBeInTheDocument()   // monitor protegido
    expect(screen.getByText("bloqueada")).toBeInTheDocument()                          // db-core
    expect(region().getByText("fw-core")).toBeInTheDocument()                          // el primero contenible
    expect(document.body.textContent).not.toMatch(/PRIVATE KEY/)
  })

  it("sin operador es solo lectura y dice por qué", async () => {
    h.sesion = { modo: "abierta", operador: "", desde: 0 }
    h.datos = base({ editable: false, permisos: { probar: false, editar: false, motivo: "probar y cambiar exigen un operador identificado por su token" } })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    expect(screen.getByRole("status")).toHaveTextContent("Consola abierta. Puedes ver la configuración. Probar y cambiar exige un token de operador")
    expect(screen.getByLabelText("Puerto")).toBeDisabled()
    for (const b of ["Probar y guardar", "Probar sin guardar", "+ Añadir equipo", "Probar todos", "Volver a leer del equipo"])
      expect(screen.queryByRole("button", { name: b })).not.toBeInTheDocument()
    expect(screen.getByText(/Probar y cambiar ajustes · exige tu token de operador/)).toBeInTheDocument()   // candado con motivo
  })

  it("«Probar y guardar» manda el ajuste y, si la prueba falla, enseña por qué y no guarda", async () => {
    h.guardar.mockResolvedValue({ status: 409, datos: { guardado: false, prueba: { ok: false, estado: "sin_aprovisionar",
      pasos: [{ paso: "entra y ejecuta un comando del catálogo", ok: false, detalle: "el equipo no acepta la clave del conector" }] } } })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    fireEvent.change(screen.getByLabelText("Puerto"), { target: { value: "2222" } })
    fireEvent.click(screen.getByRole("button", { name: "Probar y guardar" }))
    await waitFor(() => expect(h.guardar).toHaveBeenCalledWith("fw-core", { puerto: 2222, usuario: null }))
    expect(await screen.findByText("el equipo no acepta la clave del conector")).toBeInTheDocument()
    expect(await screen.findByText("No se guardó: la prueba falló")).toBeInTheDocument()
  })

  it("«Probar sin guardar» enseña los pasos", async () => {
    h.probar.mockResolvedValue({ status: 200, datos: PRUEBA_OK })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    fireEvent.click(screen.getByRole("button", { name: "Probar sin guardar" }))
    expect(await screen.findByText("sudo deniega lo que está fuera del catálogo")).toBeInTheDocument()
    expect(h.probar).toHaveBeenCalledWith("fw-core", { puerto: null, usuario: null })
  })

  it("la deriva del sudoers se enseña con lo que sobra y lo que falta", async () => {
    h.datos = base({ equipos: [equipo({ papel: "puesto", ultima_prueba: { ok: false, estado: "privilegio_de_mas", pasos: [],
      reglas: { estado: "sobran", sobran: ["cat *"], faltan: ["ss -K dst *"] } } })] })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    expect(screen.getAllByText("no coinciden").length).toBeGreaterThan(0)
    expect(region().getByText("+ cat *")).toBeInTheDocument()
    expect(region().getByText("− ss -K dst *")).toBeInTheDocument()
    expect(region().getByRole("button", { name: "Generar paquete de corrección" })).toBeInTheDocument()
  })

  it("añadir un equipo: inventario, papel, paquete y alta con la huella confirmada", async () => {
    h.inventario.mockResolvedValue({ status: 200, datos: { equipo: "pagos-qr", alta: "pendiente" } })
    h.paquete.mockResolvedValue({ nombre: "alta-pagos-qr.sh", contenido: "#!/bin/sh\nregla 'service' 'nginx stop'", formato: "script" })
    h.leer.mockResolvedValue({ status: 200, datos: { fijada: null, presentada: "SHA256:QRNUEVA", coincide: false } })
    h.aceptar.mockResolvedValue({ status: 200, datos: { huella: "SHA256:QRNUEVA" } })
    h.alta.mockResolvedValue({ status: 200, datos: { alta: "activo", prueba: PRUEBA_OK } })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    fireEvent.click(screen.getByRole("button", { name: "+ Añadir equipo" }))
    const capa = within(screen.getByRole("dialog", { name: "Añadir equipo" }))
    fireEvent.change(capa.getByLabelText("Nombre"), { target: { value: "pagos-qr" } })
    fireEvent.change(capa.getByLabelText("IP"), { target: { value: "10.0.20.20" } })
    fireEvent.click(capa.getByRole("button", { name: "Siguiente: papel y reglas" }))
    fireEvent.change(capa.getByLabelText("Servicios que se pueden parar"), { target: { value: "nginx" } })
    fireEvent.click(capa.getByRole("button", { name: "Generar el paquete de alta" }))
    await waitFor(() => expect(h.inventario).toHaveBeenCalledWith(expect.objectContaining({
      nombre: "pagos-qr", ip: "10.0.20.20", zona: "Borde", papel: "servidor", servicios: ["nginx"],
      acciones: ["OBS_CONEXIONES", "BLOQUEAR_IP", "CERRAR_SERVICIO"] })))
    expect(await capa.findByText(/regla 'service' 'nginx stop'/)).toBeInTheDocument()
    fireEvent.click(capa.getByRole("button", { name: "Ya está ejecutado" }))
    fireEvent.click(capa.getByRole("button", { name: "Leer la clave del equipo" }))
    expect(await capa.findByText("SHA256:QRNUEVA")).toBeInTheDocument()
    expect(capa.getByRole("button", { name: "Dar de alta pagos-qr" })).toBeDisabled()       // sin confirmar la huella, no
    fireEvent.click(capa.getByRole("checkbox", { name: "Coincide con la que imprimió el equipo" }))
    fireEvent.click(capa.getByRole("button", { name: "Dar de alta pagos-qr" }))
    await waitFor(() => expect(h.alta).toHaveBeenCalledWith("pagos-qr", "SHA256:QRNUEVA"))
    expect(h.aceptar).toHaveBeenCalledWith("pagos-qr", "SHA256:QRNUEVA")
  })

  it("sin clave del conector lo dice y se genera desde la vista", async () => {
    h.generar.mockResolvedValue({ status: 200, datos: { clave: { huella: "SHA256:NUEVA" } } })
    h.datos = base({ modo: "sin_configurar", clave: null, falta_clave: true,
      permisos: { probar: false, editar: false, generar_clave: true, motivo: "falta la clave del conector: genérala para empezar" } })
    render(vista())
    expect(await screen.findByText("No hay clave del conector: sin ella no entra en ningún equipo ni contiene.")).toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent("Falta la clave del conector.")
    fireEvent.click(screen.getByRole("radio", { name: /RSA 3072/ }))
    fireEvent.click(screen.getByRole("button", { name: "Generar la clave del conector" }))
    await waitFor(() => expect(h.generar).toHaveBeenCalledWith("rsa"))
  })

  it("la primera clave del host se fija sin el aviso de «cambiada» y solo confirmando la huella", async () => {
    h.leer.mockResolvedValue({ status: 200, datos: { fijada: null, presentada: "SHA256:PRIMERA", coincide: false } })
    h.aceptar.mockResolvedValue({ status: 200, datos: { huella: "SHA256:PRIMERA" } })
    h.datos = base({ equipos: [equipo({ huella_fijada: null })] })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    fireEvent.click(region().getByRole("button", { name: "Leer la clave del equipo" }))
    expect(await region().findByText("SHA256:PRIMERA")).toBeInTheDocument()
    expect(region().queryByText(/presenta una clave distinta de la fijada/)).not.toBeInTheDocument()
    expect(region().getByRole("button", { name: "Fijar esta clave" })).toBeDisabled()
    fireEvent.click(region().getByRole("checkbox", { name: "Coincide con la que imprimió el equipo" }))
    fireEvent.click(region().getByRole("button", { name: "Fijar esta clave" }))
    await waitFor(() => expect(h.aceptar).toHaveBeenCalledWith("fw-core", "SHA256:PRIMERA"))
  })

  it("el asistente manda «cualquier cuenta salvo las del sistema»", async () => {
    h.inventario.mockResolvedValue({ status: 200, datos: { equipo: "fw-core", alta: null } })
    h.paquete.mockResolvedValue({ nombre: "alta-fw-core.sh", contenido: "#!/bin/sh", formato: "script" })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    fireEvent.click(region().getByRole("button", { name: "Editar" }))
    const capa = within(screen.getByRole("dialog"))
    fireEvent.click(capa.getByRole("checkbox", { name: /Cualquier cuenta salvo las del sistema/ }))
    expect(capa.getByLabelText("Cuentas que se pueden bloquear")).toBeDisabled()
    fireEvent.click(capa.getByRole("button", { name: "Guardar y generar el paquete de corrección" }))
    await waitFor(() => expect(h.inventario).toHaveBeenCalledWith(expect.objectContaining({ nombre: "fw-core", cuentas_cualquiera: true, cuentas: [] })))
  })

  it("la rotación se inicia y la retirada de la vieja pide confirmación", async () => {
    h.rotar.mockResolvedValue({ status: 200, datos: {} })
    h.datos = base({ rotacion: { iniciada_por: "ana", en: "2026-11-04T10:00:00Z", huella_nueva: "SHA256:NUEVA",
      equipos: { "fw-core": { anadida: true, probada: true }, "db-core": { anadida: false, error: "no se pudo añadir la clave nueva" } } } })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    fireEvent.click(screen.getByRole("button", { name: "Rotación de la clave en curso…" }))
    const capa = within(screen.getByRole("dialog", { name: "Rotar la clave del conector" }))
    expect(capa.getByText("no se pudo añadir la clave nueva")).toBeInTheDocument()
    expect(capa.getByRole("button", { name: "Finalizar" })).toBeDisabled()
    fireEvent.click(capa.getByRole("button", { name: "Retirar la clave vieja en 1 equipo…" }))
    expect(h.rotar).not.toHaveBeenCalled()
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Retirar la clave vieja" }))
    await waitFor(() => expect(h.rotar).toHaveBeenCalledWith("retirar"))
  })

  it("una clave del host cambiada se lee, se compara y solo se acepta confirmando", async () => {
    h.leer.mockResolvedValue({ status: 200, datos: { fijada: "SHA256:DBVIEJA", presentada: "SHA256:DBNUEVA", coincide: false } })
    h.aceptar.mockResolvedValue({ status: 200, datos: { huella: "SHA256:DBNUEVA" } })
    render(vista())
    await screen.findByText("SHA256:CONECTOR")
    fireEvent.click(screen.getByRole("button", { name: "Ver db-core" }))
    fireEvent.click(region().getByRole("button", { name: "Leer la clave que presenta" }))
    expect(await region().findByText("SHA256:DBNUEVA")).toBeInTheDocument()
    fireEvent.click(region().getByRole("button", { name: "Aceptar la nueva clave…" }))
    expect(h.aceptar).not.toHaveBeenCalled()
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Aceptar la nueva clave" }))
    await waitFor(() => expect(h.aceptar).toHaveBeenCalledWith("db-core", "SHA256:DBNUEVA"))
  })
})
