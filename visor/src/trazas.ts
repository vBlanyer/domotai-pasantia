// Lógica pura de la vista «Trazas»: qué es cada registro, los chips de tipo, el hash abreviado, la hora
// local con agrupación por día y el texto de los registros de sistema. Sin React: se prueba en seco.
import type { Decision } from "@/api"

export type TipoFila = "decision" | "humano" | "sistema" | "error"
export type Chip = "todo" | "decisiones" | "humano" | "sistema"
export const CHIPS: { id: Chip; nombre: string }[] = [
  { id: "todo", nombre: "Todo" }, { id: "decisiones", nombre: "Decisiones" },
  { id: "humano", nombre: "Humano" }, { id: "sistema", nombre: "Sistema" },
]
const SISTEMA = new Set(["actividad_suprimida", "actividad_propia", "reversion", "actualizacion_caso"])
const GENESIS = "0".repeat(64)

export function tipoDe(r: Decision): TipoFila {
  if (r.tipo === "error") return "error"
  if (r.tipo && SISTEMA.has(r.tipo)) return "sistema"
  return r.requiere_humano || r.veredicto_humano ? "humano" : "decision"
}

export function filtrarTipo(regs: Decision[], chip: Chip): Decision[] {
  if (chip === "todo") return regs
  return regs.filter((r) => {
    const t = tipoDe(r)
    return chip === "decisiones" ? t === "decision" || t === "humano"
      : chip === "humano" ? t === "humano"
      : t === "sistema" || t === "error"
  })
}

// «a3f9…00»; el eslabón inicial se nombra; sin hash, null (la fila pinta «—»).
export function hashCorto(h?: string | null): string | null {
  if (!h) return null
  if (h === GENESIS) return "génesis"
  return `${h.slice(0, 4)}…${h.slice(-2)}`
}

export function horaLocal(ts?: string | null): string {
  if (!ts) return "—"
  const t = new Date(ts)
  return isNaN(t.getTime()) ? ts : t.toLocaleTimeString()
}

// Fecha LOCAL YYYY-MM-DD, para agrupar filas por día (la traza va en UTC con Z).
export function claveDia(ts?: string | null): string {
  if (!ts) return ""
  const t = new Date(ts)
  if (isNaN(t.getTime())) return ""
  const p = (n: number) => String(n).padStart(2, "0")
  return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}`
}

export function etiquetaDia(clave: string, hoy: string): string {
  const [a, m, d] = clave.split("-").map(Number)
  const nombre = new Intl.DateTimeFormat("es", { weekday: "long", day: "numeric", month: "long" }).format(new Date(a, m - 1, d))
  const [ha, hm, hd] = hoy.split("-").map(Number)
  const claveAyer = claveDia(new Date(ha, hm - 1, hd - 1).toISOString())
  return clave === hoy ? `Hoy · ${nombre}` : clave === claveAyer ? `Ayer · ${nombre}` : nombre
}

const ESTADO_CASO: Record<string, string> = { nuevo: "nuevo", en_revision: "en revisión", resuelto: "resuelto" }

// Los registros de sistema dicen qué pasó, en una línea de título y otra de detalle.
export function describirSistema(r: Decision): { titulo: string; detalle: string } {
  switch (r.tipo) {
    case "actividad_suprimida":
      return { titulo: "Ruido suprimido",
        detalle: `${r.alertas_suprimidas ?? 0} alertas más${r.origen_ip ? ` de ${r.origen_ip}` : ""}${r.activo ? ` contra ${r.activo}` : ""}` }
    case "actividad_propia":
      return { titulo: "Actividad propia del MDR", detalle: `login de gestión${r.activo ? ` en ${r.activo}` : ""}, no es amenaza` }
    case "reversion":
      return { titulo: `Reversión de ${r.id_decision_revertida ?? "—"}`, detalle: `${r.exito ? "aplicada" : "falló"}${r.nodo ? ` en ${r.nodo}` : ""}` }
    case "actualizacion_caso":
      return { titulo: "Caso actualizado",
        detalle: [r.estado ? (ESTADO_CASO[r.estado] ?? r.estado) : null, r.asignado ? `asignado a ${r.asignado}` : null, r.operador ? `por ${r.operador}` : null]
          .filter(Boolean).join(" · ") }
    case "error":
      return { titulo: "Error al procesar", detalle: r.error ?? "" }
    default:
      return { titulo: r.tipo ?? "registro", detalle: "" }
  }
}

// ---- integridad por registro (propuesta «inspector») --------------------------------------------
export type Marca = "ok" | "roto" | "tras"
export type CadenaMin = { ok: boolean; roto: number | null } | null

// La verificación del servidor recalcula los hashes del fichero entero y dice el PRIMER eslabón que
// no cuadra. De ahí sale la marca de cada registro: antes, verificado; en él, alterado; después,
// coherente entre sí pero colgando de un eslabón alterado.
export function marcaDe(i: number, cadena: CadenaMin): Marca | null {
  if (!cadena) return null
  if (cadena.ok || cadena.roto == null) return "ok"
  return i < cadena.roto ? "ok" : i === cadena.roto ? "roto" : "tras"
}

// Las tres líneas de la prueba: hash_previo, el hash del registro anterior (si está en la ventana) y
// el hash guardado. `enlaza` compara las dos primeras; null = no hay con qué comparar aquí.
export function pruebaDe(r: Decision, anterior: Decision | undefined) {
  const previo = r.hash_previo ?? null
  const hashAnterior = anterior?.hash ?? null
  const enlaza = previo === GENESIS && (r.indice ?? 0) === 0 ? true
    : hashAnterior == null || previo == null ? null
    : previo === hashAnterior
  return { previo, hashAnterior, enlaza, guardado: r.hash ?? null }
}

// Incidente (campaña /24) del origen, con la misma clave que usa la vista Incidentes (`inc:<prefijo>`).
export function campanaDe(ip?: string | null): { prefijo: string; clave: string; cidr: string } | null {
  const m = ip?.match(/^(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}$/)
  if (!m) return null
  return { prefijo: `${m[1]}.`, clave: `inc:${m[1]}`, cidr: `${m[1]}.0/24` }
}
