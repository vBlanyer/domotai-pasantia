// Lógica pura de la vista «Conectividad»: el estado que se enseña de cada equipo y el resumen.
import type { EquipoConectividad, ModoSesion } from "@/api"

export type Tono = "ok" | "aviso" | "critico" | "neutro"
// `aviso`: la última contención real en el equipo falló. Va ENCIMA del estado de la prueba, que no se
// toca: solo resta confianza (nunca pone nada en verde).
export type AvisoOperativo = { texto: string; sub: string; tono: Tono; ataque: boolean }
export type EstadoEquipo = { id: string; texto: string; sub: string; tono: Tono; aviso?: AvisoOperativo }

export const MODOS = [
  { id: "clave", nombre: "Clave · vía nodo de gestión" },
  { id: "directo", nombre: "Clave · desde este host" },
  { id: "password", nombre: "Contraseña (laboratorio)" },
] as const

const POR_PRUEBA: Record<string, Omit<EstadoEquipo, "id">> = {
  verificada: { texto: "verificada", sub: "la prueba pasó", tono: "ok" },
  host_cambiada: { texto: "bloqueada", sub: "la clave del host cambió", tono: "critico" },
  privilegio_de_mas: { texto: "privilegio de más", sub: "sudo permite un comando fuera del catálogo", tono: "aviso" },
  sin_aprovisionar: { texto: "sin aprovisionar", sub: "no acepta la clave del conector o falta la clave del host", tono: "aviso" },
  sin_acceso: { texto: "sin acceso", sub: "puerto cerrado, sin ruta o sin respuesta", tono: "critico" },
  fallo: { texto: "fallo", sub: "el comando del catálogo falló", tono: "critico" },
}

export const DIA_MS = 24 * 3600_000

// «hace 2 h» / «hace 3 días» desde la hora de la prueba.
export function edadTexto(iso: string | null | undefined, ahora: number): string | null {
  const t = iso ? Date.parse(iso) : NaN
  if (Number.isNaN(t)) return null
  const min = Math.max(0, Math.round((ahora - t) / 60_000))
  if (min < 1) return "hace un momento"
  if (min < 60) return `hace ${min} min`
  const h = Math.round(min / 60)
  return h < 48 ? `hace ${h} h` : `hace ${Math.round(h / 24)} días`
}

// «hh:mm» local de una hora ISO.
export const horaCorta = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })

export function avisoOperativo(e: EquipoConectividad, ahora = Date.now()): AvisoOperativo | undefined {
  if (e.protegido) return undefined
  const sa = e.sin_acceso
  if (sa) {                     // memoria de fallos: manda sobre el último fallo suelto
    const ataque = !!sa.regresion
    return { texto: "sin acceso", tono: "critico", ataque,
      sub: [`el MDR no entra desde las ${horaCorta(sa.desde)}`, sa.fallos ? `${sa.fallos} fallos` : null, "se reprueba cada 60 s"].filter(Boolean).join(" · ") }
  }
  const o = e.operativo
  if (!o) return undefined
  const ataque = !!o.posible_ataque
  return { texto: ataque ? "posible ataque" : "la última contención falló", tono: "critico", ataque,
    sub: [o.descripcion ?? o.clase, edadTexto(o.en, ahora)].filter(Boolean).join(" · ") }
}

export function estadoEquipo(e: EquipoConectividad, ahora = Date.now()): EstadoEquipo {
  const est = estadoPorPrueba(e, ahora)
  const aviso = avisoOperativo(e, ahora)
  return aviso ? { ...est, aviso } : est
}

function estadoPorPrueba(e: EquipoConectividad, ahora: number): EstadoEquipo {
  if (e.protegido) return { id: "protegido", texto: "no se contiene", sub: "protegido: canal de gestión del MDR", tono: "neutro" }
  if (e.alta === "pendiente") return { id: "alta_pendiente", texto: "alta pendiente", sub: "esperando el paquete en el equipo", tono: "neutro" }
  const p = e.ultima_prueba
  if (p) {
    const base = { id: p.estado, ...(POR_PRUEBA[p.estado] ?? POR_PRUEBA.fallo) }
    const edad = edadTexto(p.en, ahora)
    const vieja = p.en ? ahora - Date.parse(p.en) > DIA_MS : false
    if (p.estado === "verificada" && vieja) return { ...base, id: "verificada_vieja", texto: edad ?? "verificada", sub: "conviene volver a probar", tono: "aviso" }
    return { ...base, sub: [edad, p.por].filter(Boolean).join(" · ") || base.sub }
  }
  if (!e.huella_fijada) return { id: "sin_aprovisionar", texto: "sin aprovisionar", sub: "clave del host sin fijar", tono: "aviso" }
  return { id: "sin_probar", texto: "sin probar", sub: "aún no se ha probado", tono: "neutro" }
}

export function resumenConectividad(equipos: EquipoConectividad[]) {
  const est = equipos.filter((e) => !e.protegido && e.alta !== "pendiente").map((e) => estadoEquipo(e))
  return {
    contenibles: est.length,
    // con una contención fallida encima, la prueba verde ya no basta para contarlo como verificado
    verificadas: est.filter((e) => (e.id === "verificada" || e.id === "verificada_vieja") && !e.aviso).length,
    conFallos: est.filter((e) => e.aviso).length,         // fallo reciente o sin acceso (memoria de fallos)
    hostCambiada: est.filter((e) => e.id === "host_cambiada").length,
    sinAprovisionar: est.filter((e) => e.id === "sin_aprovisionar").length,
    sinProbar: est.filter((e) => e.id === "sin_probar").length,
  }
}


// Lo que permite el sudoers del equipo frente a su papel (de la última prueba).
export function reglasDe(e: EquipoConectividad): { texto: string; sub: string; tono: Tono } {
  const r = e.ultima_prueba?.reglas
  if (e.protegido || e.alta === "pendiente") return { texto: "—", sub: "", tono: "neutro" }
  if (!r) return { texto: "sin comprobar", sub: "", tono: "neutro" }
  if (r.estado === "coinciden") return { texto: "coinciden", sub: "", tono: "ok" }
  if (r.estado === "sobran") return { texto: "no coinciden", sub: "sudo permite de más", tono: "critico" }
  if (r.estado === "faltan") return { texto: "incompletas", sub: `faltan ${r.faltan.length}`, tono: "aviso" }
  return { texto: "sin comprobar", sub: "sudo pide contraseña para listar", tono: "neutro" }
}

export const papelTexto = (e: EquipoConectividad, papeles: { id: string; nombre: string }[] = []) =>
  e.papel ? (papeles.find((p) => p.id === e.papel)?.nombre ?? e.papel) : null

// La franja de arriba: qué puede hacer esta sesión en la vista, en una frase.
export function franjaPermisos(puede: boolean, motivo: string | null | undefined, modo: ModoSesion | null, nombre: string, puedeGenerar = false):
  { tono: "ok" | "aviso"; titulo: string; texto: string } {
  if (puede && modo === "identificado")
    return { tono: "ok", titulo: `Firmas como ${nombre}, verificado por tu token.`,
      texto: "Puedes ver, probar, dar de alta equipos, cambiar puerto y usuario, aceptar claves del host y rotar la clave del conector. Cada acción queda registrada con tu nombre." }
  if (puede)
    return { tono: "aviso", titulo: "Consola abierta, opción de laboratorio activa.",
      texto: `Puedes hacerlo todo, firmado con un nombre sin verificar${nombre ? ` (${nombre})` : ""}. Solo para el laboratorio.` }
  if (motivo?.startsWith("falta la clave del conector"))
    return { tono: "aviso", titulo: "Falta la clave del conector.",
      texto: puedeGenerar ? "Genérala aquí abajo para empezar: sin ella el MDR no puede entrar en ningún equipo ni contener."
        : "Sin ella el MDR no puede entrar en ningún equipo. Generarla exige tu token de operador, o la opción de conectividad abierta del laboratorio." }
  if (motivo && !motivo.includes("operador"))
    return { tono: "aviso", titulo: "Solo lectura.", texto: `Puedes ver la configuración: ${motivo}.` }
  if (modo === "compartido")
    return { tono: "aviso", titulo: "Con el token compartido.", texto: "Puedes ver la configuración. Probar, dar de alta y cambiar ajustes exige entrar con tu token de operador." }
  if (modo === "abierta")
    return { tono: "aviso", titulo: "Consola abierta.", texto: "Puedes ver la configuración. Probar y cambiar exige un token de operador, o arrancar el laboratorio con la opción de conectividad abierta: TRIAJE_CONECTIVIDAD_ABIERTA=1 sh reiniciar.sh" }
  return { tono: "aviso", titulo: "Solo lectura.", texto: "Puedes ver la configuración. Probar y cambiar exige tu token de operador." }
}
