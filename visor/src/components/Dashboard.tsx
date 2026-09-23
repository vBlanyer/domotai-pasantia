import type { ReactNode } from "react"
import { useSondeo, getSalud, getTrazas, getPendientes, getVerificacion, type Decision } from "@/api"
import { Donut, Gauge, Tendencia, type Segmento } from "./charts"
import { CATEGORICO_LIGHT, CATEGORICO_DARK, ESTADO } from "@/theme"
import { useTema } from "@/tema"

function Tarjeta({ titulo, children, className = "" }: { titulo: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-border bg-card p-5 shadow-sm ${className}`}>
      <h2 className="mb-4 text-sm font-medium text-muted-foreground">{titulo}</h2>
      {children}
    </section>
  )
}

function Kpi({ valor, etiqueta, tono }: { valor: string; etiqueta: string; tono?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card px-5 py-4 shadow-sm">
      <div className={`text-4xl font-semibold tabular-nums ${tono ?? ""}`}>{valor}</div>
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
  const trazas = useSondeo(getTrazas)
  const pend = useSondeo(getPendientes)
  const verif = useSondeo(getVerificacion)

  const conSalud = salud && "servicios" in salud
  const total = conSalud ? salud.total : 0
  const caidos = conSalud ? salud.caidos : 0
  const sanos = total - caidos
  const pctSanos = total ? Math.round((sanos / total) * 100) : 0

  const regs: Decision[] = Array.isArray(trazas) ? trazas : []
  const decisiones = regs.filter((d) => d.tipo !== "actividad_suprimida")
  const suprimidas = regs
    .filter((d) => d.tipo === "actividad_suprimida")
    .reduce((a, d) => a + (d.alertas_suprimidas ?? 0), 0)
  const nPend = Array.isArray(pend) ? pend.length : 0

  // Donut por clase: color estable por clase (orden alfabético), nunca por rango.
  const cuentas = new Map<string, number>()
  for (const d of decisiones) {
    const c = d.clase ?? "otra"
    cuentas.set(c, (cuentas.get(c) ?? 0) + 1)
  }
  const clases = [...cuentas.keys()].sort()
  const porClase: Segmento[] = clases.map((c, i) => ({
    name: ETIQUETA_CLASE[c] ?? c, value: cuentas.get(c) ?? 0, fill: CAT[i % CAT.length],
  }))

  const saludSeg: Segmento[] = [
    { name: "Operativos", value: sanos, fill: ESTADO.good },
    { name: "Caídos", value: caidos, fill: ESTADO.critical },
  ]

  // Tendencia: decisiones por día.
  const porDia = new Map<string, number>()
  for (const d of decisiones) {
    const dia = (d.timestamp ?? "").slice(0, 10)
    if (dia) porDia.set(dia, (porDia.get(dia) ?? 0) + 1)
  }
  const tendencia = [...porDia.entries()].sort().map(([dia, n]) => ({ dia: dia.slice(5), n }))

  const cadenaOk = !!verif && !("error" in verif) && verif.ok

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi valor={conSalud ? `${sanos}/${total}` : "—"} etiqueta="servicios operativos"
          tono={caidos ? "text-[color:#d03b3b]" : ""} />
        <Kpi valor={String(decisiones.length)} etiqueta="decisiones tomadas" />
        <Kpi valor={String(nPend)} etiqueta="esperando aprobación" tono={nPend ? "text-[color:#eda100]" : ""} />
        <Kpi valor={String(suprimidas)} etiqueta="alertas suprimidas" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Tarjeta titulo="Salud de los servicios">
          <Donut data={saludSeg} total={total} unidad="servicios" />
        </Tarjeta>
        <Tarjeta titulo="Decisiones por clase">
          {porClase.length
            ? <Donut data={porClase} total={decisiones.length} unidad="decisiones" />
            : <p className="py-14 text-center text-sm text-muted-foreground">aún no hay decisiones</p>}
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
            : <p className="py-16 text-center text-sm text-muted-foreground">sin histórico todavía</p>}
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
