import { z } from "zod"
import { useEffect, useState } from "react"

// Base de la API: relativa (mismo origen) en el build que sirve el daemon --web (funciona en
// cualquier puerto); en desarrollo (Vite en :5173) apunta al daemon en :8787; VITE_API lo sobreescribe.
export function baseApi(env: { VITE_API?: string; DEV?: boolean }): string {
  return env.VITE_API ?? (env.DEV ? "http://127.0.0.1:8787" : "")
}
const BASE = baseApi(import.meta.env)

export const ServicioSchema = z.object({ nombre: z.string(), estado: z.string(), depende_de: z.array(z.string()) })
export const SaludSchema = z.union([
  z.object({ sin_datos: z.literal(true) }),
  z.object({ t: z.string().nullable(), servicios: z.array(ServicioSchema), caidos: z.number(), total: z.number() }),
])
export const DecisionSchema = z.object({
  id_decision: z.string().nullable().optional(), timestamp: z.string().nullable().optional(),
  activo: z.string().nullable().optional(), clase: z.string().nullable().optional(),
  accion_final: z.string().nullable().optional(), requiere_humano: z.boolean().nullable().optional(),
  tipo: z.string().optional(), alertas_suprimidas: z.number().optional(),
})
export const PendienteSchema = z.object({
  id: z.string(), tipo: z.string(), prompt: z.string(), lineas: z.array(z.string()),
})
export const VerificacionSchema = z.object({
  ok: z.boolean(), roto_en: z.number().nullable().optional(), motivo: z.string().optional(),
})

export type Salud = z.infer<typeof SaludSchema>
export type Decision = z.infer<typeof DecisionSchema>
export type Pendiente = z.infer<typeof PendienteSchema>
export type Verificacion = z.infer<typeof VerificacionSchema>

async function pedir<T>(ruta: string, esquema: z.ZodType<T>): Promise<T | { error: string }> {
  try {
    const r = await fetch(BASE + ruta)
    return esquema.parse(await r.json())
  } catch (e) {
    return { error: String(e) }
  }
}

export const getSalud = () => pedir("/api/salud", SaludSchema)
export const getDecisiones = () => pedir("/api/decisiones", z.array(DecisionSchema))
export const getPendientes = () => pedir("/api/pendientes", z.array(PendienteSchema))
export const getTrazas = () => pedir("/api/trazas", z.array(DecisionSchema))
export const getVerificacion = () => pedir("/api/verificar", VerificacionSchema)

export async function aprobar(id: string, respuesta: string): Promise<boolean> {
  try {
    const r = await fetch(BASE + "/api/aprobar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, respuesta }),
    })
    return r.ok            // 200 -> true; 409 (pendiente caduca) -> false, no lanza
  } catch {
    return false
  }
}

export function controlesDePendiente(p: Pendiente): { etiqueta: string; respuesta: string; variante: "aprobar" | "rechazar" }[] {
  return p.tipo === "escalada"
    ? [{ etiqueta: "Aprobar", respuesta: "s", variante: "aprobar" }, { etiqueta: "Rechazar", respuesta: "", variante: "rechazar" }]
    : [{ etiqueta: "Aprobar (1)", respuesta: "1", variante: "aprobar" }, { etiqueta: "Rechazar (2)", respuesta: "2", variante: "rechazar" }]
}

export function useSondeo<T>(fn: () => Promise<T>, ms = 2000): T | undefined {
  const [v, setV] = useState<T>()
  useEffect(() => {
    let vivo = true
    const tick = async () => { const r = await fn(); if (vivo) setV(r) }
    tick()
    const id = setInterval(tick, ms)
    return () => { vivo = false; clearInterval(id) }
  }, [])
  return v
}
