// Lógica pura de la vista «Conectividad»: el estado que se enseña de cada equipo y el resumen.
import type { EquipoConectividad } from "@/api"

export type Tono = "ok" | "aviso" | "critico" | "neutro"
export type EstadoEquipo = { id: string; texto: string; sub: string; tono: Tono }

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

export function estadoEquipo(e: EquipoConectividad): EstadoEquipo {
  if (e.protegido) return { id: "protegido", texto: "no se contiene", sub: "protegido: canal de gestión del MDR", tono: "neutro" }
  const p = e.ultima_prueba
  if (p) return { id: p.estado, ...(POR_PRUEBA[p.estado] ?? POR_PRUEBA.fallo) }
  if (!e.huella_fijada) return { id: "sin_aprovisionar", texto: "sin aprovisionar", sub: "clave del host sin fijar", tono: "aviso" }
  return { id: "sin_probar", texto: "sin probar", sub: "aún no se ha probado en esta sesión", tono: "neutro" }
}

export function resumenConectividad(equipos: EquipoConectividad[]) {
  const est = equipos.filter((e) => !e.protegido).map(estadoEquipo)
  return {
    contenibles: est.length,
    verificadas: est.filter((e) => e.id === "verificada").length,
    hostCambiada: est.filter((e) => e.id === "host_cambiada").length,
    sinAprovisionar: est.filter((e) => e.id === "sin_aprovisionar").length,
    sinProbar: est.filter((e) => e.id === "sin_probar").length,
  }
}
