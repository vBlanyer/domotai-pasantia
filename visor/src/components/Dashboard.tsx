import type { ReactNode } from "react"
import { useSondeo, getSalud, getMetricas, getPendientes, getVerificacion } from "@/api"
import { SinConexion } from "./bits"
import { Donut, Gauge, Tendencia, type Segmento } from "./charts"
import { CATEGORICO_LIGHT, CATEGORICO_DARK, ESTADO } from "@/theme"
import { useTema } from "@/tema"

function Tarjeta({ titulo, children, className = "" }: { titulo: string; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-xl border border-border bg-card p-5 shadow-sm ${className}`}>
      <h2 className="mb-4 text-sm font-medium text-muted-foreground">{titulo}</h2>
      {children}
    </section>
  )
}

function Kpi({ valor, etiqueta, tono }: { valor: string; etiqueta: string; tono?: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-border bg-card px-5 py-4 shadow-sm">
      <div className={`font-heading text-4xl font-semibold tabular-nums ${tono ?? ""}`}>{valor}</div>
      <div className="mt-1 text-sm text-muted-foreground">{etiqueta}</div>
    </div>
  )
}

function Check({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <li className="flex items-center justify-between py-2 text-sm">
      <span>{children}</span>
      {ok
        ? <span className="font-semibold" style={{ color: ESTADO.good }}>✓</span>
        : <span className="font-semibold" style={{ color: ESTADO.critical }}>✗</span>}
    </li>
  )
}

const ETIQUETA_CLASE: Record<string, string> = {
  vp_intento_acceso: "Intento de acceso",
  vp_acceso_consumado: "Acceso consumado",
  fp_actividad_legitima: "Falso positivo (legítimo)",
  fp_exposicion_inexistente: "Falso positivo (exposición)",
  no_soportada: "No soportada",
  amenaza_enrutada: "Enrutada a un equipo",
}

export function Dashboard({ conectado }: { conectado: boolean }) {
  const CAT = useTema().oscuro ? CATEGORICO_DARK : CATEGORICO_LIGHT
  const salud = useSondeo(getSalud)
  const metricas = useSondeo(getMetricas)
  const pend = useSondeo(getPendientes)
  const verif = useSondeo(getVerificacion)

  const conSalud = salud && "servicios" in salud
  const total = conSalud ? salud.total : 0
  const caidos = conSalud ? salud.caidos : 0
  const sanos = total - caidos
  const pctSanos = total ? Math.round((sanos / total) * 100) : 0

  // Totales del periodo: /api/metricas agrega la traza completa (el listado de trazas va acotado a
  // los últimos registros). Sin datos se pinta «—», nunca un 0 que se lea como «todo tranquilo».
  const m = metricas && !("error" in metricas) ? metricas : null
  const sinConexion = !!metricas && "error" in metricas
  const nPend = Array.isArray(pend) ? pend.length : null
  const sinDatos = sinConexion ? "sin datos: no hay conexión con el daemon" : null

  // Donut por clase: color estable por clase (orden alfabético), nunca por rango.
  const clases = m ? Object.keys(m.por_clase).sort() : []
  const porClase: Segmento[] = clases.map((c, i) => ({
    name: ETIQUETA_CLASE[c] ?? c, value: m?.por_clase[c] ?? 0, fill: CAT[i % CAT.length],
  }))

  const saludSeg: Segmento[] = [
    { name: "Operativos", value: sanos, fill: ESTADO.good },
    { name: "Caídos", value: caidos, fill: ESTADO.critical },
  ]

  // Tendencia: decisiones por día (ya ordenadas y en MM-DD desde el backend).
  const tendencia = m ? m.por_dia : []

  const cadenaOk = !!verif && !("error" in verif) && verif.ok

  return (
    <div className="space-y-6">
      {sinConexion && <SinConexion />}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi valor={conSalud ? `${sanos}/${total}` : "—"} etiqueta="servicios operativos"
          tono={caidos ? "text-[color:#d03b3b]" : ""} />
        <Kpi valor={m ? String(m.total) : "—"} etiqueta="decisiones tomadas" />
        <Kpi valor={nPend != null ? String(nPend) : "—"} etiqueta="esperando aprobación" tono={nPend ? "text-[color:#eda100]" : ""} />
        <Kpi valor={m ? String(m.suprimidas) : "—"} etiqueta="alertas suprimidas" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Tarjeta titulo="Estado de los servicios">
          <Donut data={saludSeg} total={total} unidad="servicios" />
        </Tarjeta>
        <Tarjeta titulo="Decisiones por clase">
          {porClase.length
            ? <Donut data={porClase} total={m?.total ?? 0} unidad="decisiones" />
            : <p className="py-14 text-center text-sm text-muted-foreground">{sinDatos ?? "aún no hay decisiones"}</p>}
        </Tarjeta>
        <Tarjeta titulo="Servicios monitoreados">
          <Gauge pct={pctSanos} color={pctSanos >= 100 ? ESTADO.good : pctSanos >= 50 ? ESTADO.warning : ESTADO.critical}
            etiqueta="operativos ahora" />
        </Tarjeta>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Tarjeta titulo="Decisiones por día" className="lg:col-span-2">
          {tendencia.length
            ? <Tendencia data={tendencia} />
            : <p className="py-16 text-center text-sm text-muted-foreground">{sinDatos ?? "sin histórico todavía"}</p>}
        </Tarjeta>
        <Tarjeta titulo="Estado del despliegue">
          <ul className="divide-y divide-border">
            <Check ok={conectado}>Conexión con el daemon</Check>
            <Check ok={total > 0 && caidos === 0}>Todos los servicios operativos</Check>
            <Check ok={cadenaOk}>Cadena de traza íntegra</Check>
            <Check ok={nPend === 0}>Sin decisiones pendientes</Check>
          </ul>
        </Tarjeta>
      </div>
    </div>
  )
}
