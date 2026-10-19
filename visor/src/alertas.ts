// Aviso al analista de que hay decisiones esperando: lógica PURA (testeable) separada de los efectos
// de navegador (título de la pestaña, Notification, sonido), que viven en un hook fino en App.
// Todo se queda en el navegador del analista: no sale nada a ningún servicio externo (RNF-01).
import type { Pendiente } from "@/api"

export const TITULO_BASE = "MDR — consola de triaje"

// Antepone el número de pendientes al título de la pestaña, para que se vea aunque el analista esté
// en otra pestaña del navegador. Sin pendientes, el título base.
export function tituloConPendientes(n: number, base = TITULO_BASE): string {
  return n > 0 ? `(${n}) ${base}` : base
}

// Los pendientes que NO estaban en la vuelta anterior del sondeo: así se notifica una sola vez por
// incidente, no en cada refresco.
export function nuevosPendientes(prev: Iterable<string>, actuales: Pendiente[]): Pendiente[] {
  const vistos = new Set(prev)
  return actuales.filter((p) => !vistos.has(p.id))
}

// Texto de la notificación del sistema. Una sola decisión nombra el activo y el origen; varias, el
// recuento. Null si no hay novedades (no se emite notificación vacía).
export function textoAviso(nuevos: Pendiente[]): { titulo: string; cuerpo: string } | null {
  if (nuevos.length === 0) return null
  if (nuevos.length === 1) {
    const p = nuevos[0]
    const quien = [p.activo, p.origen_ip].filter(Boolean).join(" · ")
    return { titulo: "MDR: decisión pendiente",
             cuerpo: quien ? `${quien} — espera tu aprobación` : "Una decisión espera tu aprobación" }
  }
  return { titulo: "MDR: decisiones pendientes",
           cuerpo: `${nuevos.length} decisiones esperan tu aprobación` }
}

// «pendiente desde hace X» a partir de los milisegundos transcurridos. Nunca negativo (reloj del
// cliente / primera observación en la sesión).
export function edadTexto(msTranscurridos: number): string {
  const s = Math.max(0, Math.floor(msTranscurridos / 1000))
  if (s < 60) return "hace unos segundos"
  const m = Math.floor(s / 60)
  if (m < 60) return `hace ${m} min`
  const h = Math.floor(m / 60)
  return `hace ${h} h ${m % 60} min`
}

// Una decisión que lleva esperando más de `umbralMs` se resalta en la cola (SLA del analista).
export function envejecido(msTranscurridos: number, umbralMs = 5 * 60_000): boolean {
  return msTranscurridos >= umbralMs
}

// Milisegundos desde una marca ISO (la hora de encolado del servidor) hasta `ahora`. 0 si falta o no
// parsea (daemon antiguo sin el campo, o reloj raro): así la cola nunca muestra una edad absurda.
export function msDesde(iso: string | null | undefined, ahora: number): number {
  if (!iso) return 0
  const t = Date.parse(iso)
  return Number.isNaN(t) ? 0 : Math.max(0, ahora - t)
}
