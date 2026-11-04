// Lógica pura de «Decisiones»: en qué acabó cada decisión, el resumen de resultados, los filtros por
// desenlace y el recorrido de la decisión en seis pasos (alerta → clasificación → propuesta → política
// → analista → ejecución). La vista Trazas es la de la integridad; esta, la de cómo razonó el motor.
import type { Decision, Detalle } from "@/api"
import { contencionDe, etiquetaClase, filtroLegible, type EstadoContencion, quienDecidio, esperaTexto, VERBO_VEREDICTO } from "@/datos"

const horaLocal = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : null)

export type Tono = "ok" | "aviso" | "critico" | "neutro" | "violeta"
export type Desenlace = { id: string; texto: string; tono: Tono; degradada: boolean }

const esDecision = (d: Decision) => !d.tipo || d.tipo === "decision"

export function desenlaceDe(d: Decision): Desenlace {
  const degradada = d.resultado_filtro === "degrada"
  const r = (id: string, texto: string, tono: Tono): Desenlace => ({ id, texto, tono, degradada })
  if (!esDecision(d)) return r("sistema", d.tipo ?? "registro", "neutro")
  if (d.contencion === "fallida") return r("fallida", "fallida", "critico")
  if (d.veredicto_humano === "reclasificar" || d.clase_reclasificada) return r("reclasificada", "reclasificada", "violeta")
  if (d.veredicto_humano === "rechazar") return r("rechazada", "rechazada", "aviso")
  if (d.resultado_filtro === "veta" && !d.accion_final) return r("vetada", "vetada", "critico")
  if (d.requiere_humano && !d.veredicto_humano) return r("pendiente", "pendiente", "aviso")
  if (d.contencion === "contenida") return r("contenida", "contenida", "ok")
  if (degradada) return r("degradada", "degradada", "aviso")
  if (d.contencion === "enrutada") return r("enrutada", "enrutada", "neutro")
  if ((d.clase ?? "").startsWith("fp_")) return r("falso_positivo", "falso positivo", "neutro")
  if (d.clase === "no_soportada") return r("no_soportada", "no soportada", "neutro")
  return r("sin_accion", d.accion_final ? "sin verificar" : "sin acción", "neutro")
}

export function resumenDecisiones(ds: Decision[]) {
  const dec = ds.filter(esDecision)
  const v = (x: string) => dec.filter((d) => d.veredicto_humano === x).length
  const rechazadas = v("rechazar"), reclasificadas = v("reclasificar")
  const degradadas = dec.filter((d) => d.resultado_filtro === "degrada").length
  const vetadas = dec.filter((d) => d.resultado_filtro === "veta" && !d.accion_final).length
  return {
    total: dec.length,
    autoContenidas: dec.filter((d) => d.contencion === "contenida" && !d.requiere_humano).length,
    humano: dec.filter((d) => d.requiere_humano).length,
    aprobadas: v("aprobar"),
    corregidas: rechazadas + reclasificadas, rechazadas, reclasificadas,
    frenadas: degradadas + vetadas, degradadas, vetadas,
    fallidas: dec.filter((d) => d.contencion === "fallida").length,
  }
}

export type FiltroDecision = "todas" | "contenidas" | "pendientes" | "frenadas" | "corregidas" | "fallidas" | "falsos" | "decididas_por_mi"
export const FILTROS_DECISION: { id: FiltroDecision; nombre: string }[] = [
  { id: "todas", nombre: "Todas" }, { id: "contenidas", nombre: "Contenidas" }, { id: "pendientes", nombre: "Pendientes" },
  { id: "frenadas", nombre: "Frenadas por la política" }, { id: "corregidas", nombre: "Corregidas por el analista" },
  { id: "fallidas", nombre: "Fallidas" }, { id: "falsos", nombre: "Falsos positivos" },
  { id: "decididas_por_mi", nombre: "Decididas por mí" },
]
// `yo`: el operador de la sesión, para «Decididas por mí» (las que firmó con su veredicto).
export function pasaFiltro(d: Decision, f: FiltroDecision, yo = ""): boolean {
  if (f === "todas") return true
  if (!esDecision(d)) return false
  switch (f) {
    case "contenidas": return d.contencion === "contenida"
    case "pendientes": return !!d.requiere_humano && !d.veredicto_humano
    case "frenadas": return d.resultado_filtro === "degrada" || (d.resultado_filtro === "veta" && !d.accion_final)
    case "corregidas": return d.veredicto_humano === "rechazar" || d.veredicto_humano === "reclasificar"
    case "fallidas": return d.contencion === "fallida"
    case "falsos": return (d.clase ?? "").startsWith("fp_") || (d.clase_reclasificada ?? "").startsWith("fp_")
    case "decididas_por_mi": return !!yo && !!d.veredicto_humano && d.veredicto_por === yo
  }
}

export type Paso = { titulo: string; estado: Tono | "humano"; etiqueta?: string; texto: string }

const EJECUCION: Record<EstadoContencion, { estado: Paso["estado"]; texto: string }> = {
  contenida: { estado: "ok", texto: "contenida" }, fallida: { estado: "critico", texto: "fallida" },
  retenida: { estado: "neutro", texto: "no se ejecutó" }, cancelada: { estado: "aviso", texto: "escalada cancelada" },
  degradada: { estado: "aviso", texto: "degradada" }, enrutada: { estado: "neutro", texto: "enrutada" },
  sin_accion: { estado: "neutro", texto: "sin acción" },
}

export function pasosDe(d: Decision, det: Detalle | null): Paso[] {
  const ev = (det?.justificacion_estructurada?.evidencia ?? {}) as Record<string, unknown>
  const mitre = det?.justificacion_estructurada?.tecnica_mitre ?? d.tecnica_mitre ?? []
  const origen = (ev.origen_ip as string | undefined) ?? d.origen_ip
  const activo = (ev.activo as string | undefined) ?? d.activo
  const regla = ev.regla ?? ev.regla_id ?? ev.rule_id
  const propuesta = det?.accion_propuesta ?? d.accion_propuesta ?? d.accion_final ?? null
  const final = det ? det.accion_final : d.accion_final
  const cascada = det?.impacto_determinado?.activos_afectados_en_cascada ?? d.cascada ?? []
  const filtro = det?.resultado_filtro ?? d.resultado_filtro
  const veredicto = det?.veredicto_humano ?? d.veredicto_humano
  const humano = det?.requiere_humano ?? d.requiere_humano
  const c = det ? contencionDe(det) : null
  const estadoC = (c?.estado ?? (d.contencion as EstadoContencion | undefined) ?? "sin_accion") as EstadoContencion
  const ej = EJECUCION[estadoC] ?? EJECUCION.sin_accion
  return [
    { titulo: "Alerta del SIEM", estado: "ok", etiqueta: regla != null ? `regla ${regla}` : undefined,
      texto: `${origen ? `de ${origen} ` : ""}contra ${activo ?? "—"}${mitre.length ? ` · ATT&CK ${mitre.join(", ")}` : ""}` },
    { titulo: "Clasificación", estado: d.clase_reclasificada ? "aviso" : "ok",
      etiqueta: d.confianza != null ? `confianza ${d.confianza}` : undefined,
      texto: `${d.clase ? etiquetaClase(d.clase) : "—"}${d.prioridad ? ` · prioridad P${d.prioridad}` : ""}`
        + (d.clase_reclasificada ? ` · el analista la corrigió a ${etiquetaClase(d.clase_reclasificada)}` : "") },
    { titulo: "Propuesta del motor", estado: cascada.length ? "aviso" : propuesta ? "ok" : "neutro",
      texto: `${propuesta ?? "ninguna acción"}${det?.impacto_determinado?.nivel ? ` · impacto ${det.impacto_determinado.nivel}` : ""}`
        + (cascada.length ? ` · tumba en cascada: ${cascada.join(", ")}` : "") },
    { titulo: "Política del cliente", estado: filtro === "veta" && !final ? "critico" : filtro === "veta" || filtro === "degrada" ? "aviso" : filtro === "permite" ? "ok" : "neutro",
      etiqueta: filtro ?? undefined,
      texto: filtroLegible({ resultado_filtro: filtro, accion_final: final, requiere_humano: humano, veredicto_humano: veredicto }) ?? "sin acción que filtrar" },
    veredicto
      ? { titulo: "Analista", estado: "humano", etiqueta: quienDecidio(d) ?? undefined,
          texto: [veredicto === "reclasificar" && d.clase_reclasificada ? `corrigió la clase a ${etiquetaClase(d.clase_reclasificada)}` : `${VERBO_VEREDICTO[veredicto] ?? veredicto} la propuesta`,
            horaLocal(d.decidido_en), esperaTexto(d.espera_humana_s)].filter(Boolean).join(" · ") }
      : humano
        ? { titulo: "Analista", estado: "aviso", etiqueta: "pendiente", texto: "espera la decisión de un analista (ver Aprobaciones)" }
        : { titulo: "Analista", estado: "neutro", etiqueta: "no hizo falta", texto: "la política permitía decidir sin humano" },
    { titulo: "Ejecución", estado: ej.estado, etiqueta: ej.texto,
      // con el detalle cargado, el inspector cuenta la contención con su propia frase: aquí no se repite
      texto: c ? ""
        : estadoC === "fallida" ? "no se pudo contener ni verificar"
        : estadoC === "contenida" ? `aplicada en ${d.dispositivo ?? "—"} y comprobada después`
        : "no se ejecutó ninguna acción" },
  ]
}
