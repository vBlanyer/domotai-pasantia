import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
  useSondeo, getSalud, getPendientes, getVerificacion, getLatido, getConectividad, getMetricas, getMetricasHoy, getTrazasPanel,
  LIMITE_TRAZAS_PANEL, listaConocida, operadorActual, actualizarCaso, ahoraServidor, type Pendiente, type Decision,
} from "@/api"
import { DatosCongelados } from "./bits"
import { etiquetaClase, SIN_NOMBRE } from "@/datos"
import { edadTexto } from "@/alertas"
import { resumenConectividad } from "@/conectividad"
import { incidentesDe, type IncidenteVista } from "@/incidentes"
import { desenlaceDe, type Tono as TonoDesenlace } from "@/decisiones"
import {
  saludPlataforma, urgentes, conActividadDeCola, textoSla, colaResumen, incidentesSinResponsable, fallidasRecientes, actividadPorHora,
  cobertura, comparaConAyer, llegadasUltimaHora, variacion, atacadoEn24h, ultimasDecisiones, type Tono, type Hora, type Urgente,
} from "@/panel"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"

// Panel: lo primero al empezar el turno. Responde «¿funciona todo?» en una línea y dedica el resto a
// lo que le toca al analista y a lo que está pasando ahora. Cada bloque resume y lleva a su vista.

type Saltos = {
  onVerAprobaciones?: (id?: string) => void; onVerIncidente?: (clave: string, cidr: string) => void
  onVerDecisiones?: (texto: string) => void; onVerSalud?: () => void; onVerInforme?: () => void; onVerRed?: () => void
}

const PUNTO: Record<Tono, string> = { ok: "bg-ok", aviso: "bg-aviso", critico: "bg-critico", neutro: "bg-muted-foreground/50" }
const PILDORA: Record<TonoDesenlace, string> = {
  ok: "bg-ok/15 text-ok", aviso: "bg-aviso/15 text-aviso", critico: "bg-critico/15 text-critico",
  neutro: "bg-enrutado/15 text-enrutado", violeta: "bg-violeta/15 text-violeta",
}
const BOTON = "inline-flex h-7 shrink-0 items-center rounded-lg border px-2.5 text-xs font-medium transition-colors"
const hora = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" }) : "—")
const num = (x: number) => x.toLocaleString("es")
const decisiones = (n: number) => `${num(n)} ${n === 1 ? "decisión" : "decisiones"}`

function useAhora(ms: number): number {
  const [ahora, setAhora] = useState(() => ahoraServidor())
  useEffect(() => { const t = setInterval(() => setAhora(ahoraServidor()), ms); return () => clearInterval(t) }, [ms])
  return ahora
}

function Enlace({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  if (!onClick) return null
  return <button type="button" onClick={onClick} className="whitespace-nowrap text-xs font-medium text-info hover:underline">{children} ›</button>
}

function Bloque({ titulo, extra, children, className }: { titulo: string; extra?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section aria-label={titulo} className={cn("min-w-0 overflow-hidden rounded-xl border border-border bg-card", className)}>
      <div className="flex items-baseline justify-between gap-3 px-4 pb-2 pt-3">
        <h2 className="text-sm font-semibold">{titulo}</h2>{extra}
      </div>
      {children}
    </section>
  )
}

function Cifra({ k, v, sub, tono, onClick, className }: { k: string; v: string; sub?: ReactNode; tono?: string; onClick?: () => void; className?: string }) {
  const cuerpo = (
    <>
      <div className="text-xs text-muted-foreground">{k}</div>
      <div className={cn("font-heading text-2xl font-semibold tabular-nums leading-tight", tono)}>{v}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </>
  )
  const caja = cn("min-w-0 bg-card px-4 py-3 text-left", className)
  return onClick ? <button type="button" onClick={onClick} className={cn(caja, "transition-colors hover:bg-muted/50")}>{cuerpo}</button> : <div className={caja}>{cuerpo}</div>
}

function Tarea({ tono, letra, claseLetra, l1, l2, children }: { tono: string; letra: string; claseLetra: string; l1: ReactNode; l2: ReactNode; children: ReactNode }) {
  return (
    <li className="grid grid-cols-[4px_22px_minmax(0,1fr)_auto] items-center gap-2.5 border-t border-border py-2.5 pl-2.5 pr-4 text-sm">
      <span className={cn("self-stretch rounded-sm", tono)} />
      <span className={cn("grid size-[22px] place-items-center rounded-md text-xs font-semibold", claseLetra)}>{letra}</span>
      <div className="min-w-0"><div className="truncate font-medium">{l1}</div><div className="truncate text-xs text-muted-foreground">{l2}</div></div>
      <div className="flex items-center gap-2.5">{children}</div>
    </li>
  )
}

function Grupo({ children }: { children: ReactNode }) {
  return <li className="border-t border-border bg-muted/40 px-4 py-1.5 text-[11px] font-medium text-muted-foreground">{children}</li>
}

function FilaAprobacion({ u, primera, onAbrir }: { u: Urgente; primera: boolean; onAbrir?: (id: string) => void }) {
  const { p } = u
  const tono = u.restanteMs <= 5 * 60_000 ? "critico" : u.restanteMs <= 10 * 60_000 ? "aviso" : "primary"
  const barra = { critico: "bg-critico", aviso: "bg-aviso", primary: "bg-primary" }[tono]
  return (
    <Tarea tono={barra} letra="A" claseLetra="bg-aviso/15 text-aviso"
      l1={<>{p.clase ? etiquetaClase(p.clase) : "Decisión"} en <span className="font-mono text-[13px]">{p.activo ?? "—"}</span>
        {p.accion_final && <span className="text-muted-foreground"> · <span className="font-mono text-xs">{p.accion_final}</span></span>}</>}
      l2={<><span className={cn("sm:hidden", u.restanteMs <= 5 * 60_000 && "font-medium text-critico")}>{textoSla(u.restanteMs)} · </span>
        {[p.confianza != null ? `confianza ${Math.round(p.confianza * 100)} %` : null, p.origen_ip ? `desde ${p.origen_ip}` : null,
          p.encolado_en ? `llegó ${edadTexto(u.edadMs)}` : null].filter(Boolean).join(" · ")}</>}>
      <div className="hidden w-24 sm:block" title="SLA de 15 min">
        <div className="h-1.5 overflow-hidden rounded-full bg-muted"><i className={cn("block h-full", barra)} style={{ width: `${u.fraccion * 100}%` }} /></div>
        <div className="mt-0.5 whitespace-nowrap text-right text-[10.5px] tabular-nums text-muted-foreground">{textoSla(u.restanteMs)}</div>
      </div>
      {onAbrir && <button type="button" onClick={() => onAbrir(p.id)}
        className={cn(BOTON, primera ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90" : "border-border bg-card hover:bg-muted")}>Revisar</button>}
    </Tarea>
  )
}

function TeToca({ pend, ahora, incidentes, fallidas, s }: {
  pend: Pendiente[] | null; ahora: number; incidentes: IncidenteVista[]; fallidas: { d: Decision; veces: number }[]; s: Saltos
}) {
  const toast = useToast()
  const yo = operadorActual().trim()
  const [asignados, setAsignados] = useState<Set<string>>(new Set())
  const urg = pend ? urgentes(pend, ahora, 3) : []
  const cola = pend ? colaResumen(pend, ahora) : null
  const sinDueno = incidentesSinResponsable(incidentes.filter((e) => !asignados.has(e.clave)), 2)
  const asignarme = async (e: IncidenteVista) => {
    if (await actualizarCaso(e.clave, { asignado: yo })) {
      setAsignados((p) => new Set(p).add(e.clave))
      toast({ type: "success", title: "Caso asignado", description: `${e.cidr} queda a nombre de ${yo}.` })
    } else toast({ type: "error", title: "No se pudo asignar", description: "El daemon no anotó el cambio." })
  }
  const nada = pend !== null && !urg.length && !sinDueno.length && !fallidas.length
  return (
    <Bloque titulo="Te toca" extra={<Enlace onClick={s.onVerAprobaciones && (() => s.onVerAprobaciones!())}>Ir a Aprobaciones</Enlace>}>
      <ul>
        {pend === null && <li className="border-t border-border px-4 py-6 text-center text-sm text-muted-foreground">No se pudo leer la cola de aprobaciones.</li>}
        {nada && <li className="border-t border-border px-4 py-8 text-center text-sm text-muted-foreground">Nada pendiente ahora mismo.</li>}
        {urg.length > 0 && <Grupo>Aprobaciones más urgentes · por tiempo que queda de SLA</Grupo>}
        {urg.map((u, i) => <FilaAprobacion key={u.p.id} u={u} primera={i === 0} onAbrir={s.onVerAprobaciones} />)}
        {(sinDueno.length > 0 || fallidas.length > 0) && <Grupo>Incidentes y contención</Grupo>}
        {sinDueno.map((e) => (
          <Tarea key={e.clave} tono={e.activo ? "bg-critico" : "bg-aviso"} letra="I" claseLetra="bg-critico/15 text-critico"
            l1={<>Campaña <span className="font-mono text-[13px]">{e.cidr}</span> sin responsable</>}
            l2={<>{e.activo ? <span className="font-medium text-critico">activa ahora</span> : `última actividad ${edadTexto(ahora - Date.parse(e.ultima ?? ""))}`}
              {` · ${decisiones(e.n)} contra ${e.objetivos.slice(0, 2).map((o) => o.equipo).join(" y ") || "la red"}`}</>}>
            {yo ? <button type="button" onClick={() => asignarme(e)} className={cn(BOTON, "border-border bg-card hover:bg-muted")}>Asignarme</button>
              : s.onVerIncidente && <button type="button" onClick={() => s.onVerIncidente!(e.clave, e.cidr)} className={cn(BOTON, "border-border bg-card hover:bg-muted")}>Abrir</button>}
          </Tarea>
        ))}
        {fallidas.map(({ d, veces }) => (
          <Tarea key={d.activo ?? d.id_decision ?? "f"} tono="bg-critico" letra="C" claseLetra="bg-enrutado/15 text-enrutado"
            l1={<>{veces === 1 ? "Una contención falló" : `${veces} contenciones fallaron`} en <span className="font-mono text-[13px]">{d.activo ?? "—"}</span></>}
            l2={`${d.accion_final ?? "acción"} · ${edadTexto(ahora - Date.parse(d.timestamp ?? ""))} · revisar el conector con ese equipo`}>
            {s.onVerDecisiones && d.id_decision && <button type="button" onClick={() => s.onVerDecisiones!(d.id_decision!)} className={cn(BOTON, "border-border bg-card hover:bg-muted")}>Ver</button>}
          </Tarea>
        ))}
      </ul>
      {cola && cola.total > urg.length && (
        <div className="flex items-center justify-between gap-3 border-t border-border bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
          <span>{num(cola.total - urg.length)} aprobaciones más · {cola.fueraSla ? <span className="font-medium text-critico">{cola.fueraSla} fuera de SLA</span> : "ninguna fuera de SLA"}</span>
          <Enlace onClick={s.onVerAprobaciones && (() => s.onVerAprobaciones!())}>Ver todas</Enlace>
        </div>
      )}
    </Bloque>
  )
}

function Horas({ horas }: { horas: Hora[] }) {
  const W = 560, H = 120, bw = W / 24
  const max = Math.max(1, ...horas.map((h) => h.auto + h.humano + h.descartadas))
  return (
    <svg viewBox={`0 -2 ${W} ${H + 16}`} className="block h-auto w-full" role="img" aria-label="Decisiones por hora en las últimas 24 horas">
      {horas.map((h, i) => {
        let y = H - 2
        const partes = ([[h.auto, "fill-primary"], [h.humano, "fill-aviso"], [h.descartadas, "fill-muted-foreground/45"]] as const).map(([v, c], k) => {
          const alto = (v / max) * (H - 12)
          if (alto <= 0) return null
          y -= alto
          return <rect key={k} x={i * bw + bw * 0.18} y={y} width={bw * 0.64} height={alto} rx={1} className={c} />
        })
        const etq = new Date(h.inicio).getHours().toString().padStart(2, "0")
        return (
          <g key={h.inicio}>
            <title>{`${etq}:00 · ${h.auto} en automático, ${h.humano} a un analista, ${h.descartadas} descartadas`}</title>
            <rect x={i * bw} y={0} width={bw} height={H} fill="transparent" />
            {partes}
            {i % 3 === 0 && <text x={i * bw + bw / 2} y={H + 12} textAnchor="middle" className="fill-muted-foreground text-[10px]">{etq}</text>}
          </g>
        )
      })}
      <line x1={0} y1={H - 1.5} x2={W} y2={H - 1.5} className="stroke-border" />
    </svg>
  )
}

function Barras({ filas }: { filas: { nombre: ReactNode; clave: string; n: number; verde?: number }[] }) {
  const max = Math.max(1, ...filas.map((f) => f.n))
  return (
    <div className="flex flex-col gap-2 px-4 pb-4 pt-1">
      {filas.map((f) => (
        <div key={f.clave} className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-2 text-xs">
          <span className="truncate">{f.nombre}</span>
          <span className="flex h-2 overflow-hidden rounded-sm bg-muted">
            {f.verde == null ? <i className="block h-full bg-primary" style={{ width: `${(f.n / max) * 100}%` }} /> : <>
              <i className="block h-full bg-ok" style={{ width: `${(f.verde / max) * 100}%` }} />
              <i className="block h-full bg-critico" style={{ width: `${((f.n - f.verde) / max) * 100}%` }} /></>}
          </span>
          <span className="text-right font-medium tabular-nums">{num(f.n)}</span>
        </div>
      ))}
      {!filas.length && <p className="py-6 text-center text-sm text-muted-foreground">Sin ataques en las últimas 24 h.</p>}
    </div>
  )
}

export function Dashboard({ conectado, ...s }: { conectado: boolean } & Saltos) {
  const salud = useSondeo(getSalud)
  const latido = useSondeo(getLatido, 5000)
  const verif = useSondeo(getVerificacion, 30000)       // recorre todo el fichero en el servidor: cada 30 s basta
  const conect = useSondeo(getConectividad, 30000)
  const pendR = useSondeo(getPendientes)
  const mhR = useSondeo(getMetricasHoy, 10000)
  // el ruido evitado sale de la sesión: los resúmenes de supresión no llevan fecha y el filtro por día no los ve
  const msR = useSondeo(getMetricas, 10000)
  const trR = useSondeo(getTrazasPanel, 10000)
  const ahora = useAhora(5000)

  // Un fallo CON datos previos conserva lo último bueno bajo el aviso (no vacía el panel ni pinta ceros).
  const mh = mhR && !("error" in mhR) ? mhR : mhR?.datos ?? null
  const fallo = mhR && "error" in mhR ? mhR : null
  const ms = msR && !("error" in msR) ? msR : msR?.datos ?? null
  const pend = listaConocida(pendR)
  const conTrazas = listaConocida(trR) !== null      // sin traza legible, sus cifras son «—», nunca un 0
  const regs = useMemo(() => listaConocida(trR) ?? [], [trR])
  const minuto = Math.floor(ahora / 60_000)
  const incidentes = useMemo(() => conActividadDeCola(incidentesDe(regs, minuto * 60_000), pend ?? [], minuto * 60_000), [regs, pend, minuto])

  const sv = salud && "servicios" in salud ? salud : null
  const r = conect && !("error" in conect) ? resumenConectividad(conect.equipos) : null
  const linea = saludPlataforma({
    conectado,
    servicios: sv ? { total: sv.total, caidos: sv.caidos, caidosNombres: sv.servicios.filter((x) => x.estado !== "ok").map((x) => x.nombre).slice(0, 3) } : null,
    ingestaSilencioS: latido && !("error" in latido) ? latido.ingesta_silencio_s : undefined,
    trazaOk: verif && !("error" in verif) ? verif.ok : null,
    conector: conect && !("error" in conect) && r ? { modo: conect.modo, problemas: r.hostCambiada + r.sinAprovisionar, verificados: r.verificadas, contenibles: r.contenibles } : null,
  })

  const completa = regs.length < LIMITE_TRAZAS_PANEL
  const cmp = comparaConAyer(regs, ahora, completa)
  const delta = variacion(cmp.hoy, cmp.ayer)
  const cola = pend ? colaResumen(pend, ahora) : null
  const abiertos = incidentes.filter((e) => e.caso.estado !== "resuelto")
  const activos = abiertos.filter((e) => e.activo)
  const sinDueno = abiertos.filter((e) => !e.caso.asignado)
  const horas = actividadPorHora(regs, ahora, pend ?? [])
  const llegadas = llegadasUltimaHora(regs, pend ?? [], ahora)
  const desde = cobertura(regs)
  const parcial = !completa && desde != null && desde > ahora - 24 * 3600_000
  const atacado = atacadoEn24h(regs, ahora)
  const ultimas = ultimasDecisiones(regs, 6)
  const ahoraMismo = [...abiertos].sort((a, b) => Number(b.activo) - Number(a.activo) || (b.ultima ?? "").localeCompare(a.ultima ?? "")).slice(0, 3)

  return (
    <div className="space-y-4">
      {fallo?.datos && <DatosCongelados fallo={fallo} />}

      <section aria-label="Salud de la plataforma" className={cn("flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border bg-card px-4 py-2.5 text-sm",
        linea.tono === "critico" ? "border-critico/50 bg-critico/10" : "border-border")}>
        <span className={cn("flex items-center gap-2 font-semibold", linea.tono === "critico" && "text-critico")}>
          <span className={cn("size-2 rounded-full", PUNTO[linea.tono])} />{linea.titulo}
        </span>
        {linea.indicadores.map((i) => (
          <span key={i.nombre} className="inline-flex items-center gap-1.5 text-muted-foreground">
            <span className={cn("size-2 rounded-full", PUNTO[i.tono])} />{i.nombre} <b className="font-medium text-foreground">{i.valor}</b>
          </span>
        ))}
        <span className="ml-auto"><Enlace onClick={s.onVerSalud}>Estado de servicios</Enlace></span>
      </section>

      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border lg:grid-cols-5">
        <Cifra k="Decisiones hoy" v={mh ? num(mh.total) : "—"}
          sub={delta ? <span className={delta.sube ? "text-aviso" : "text-ok"}>{delta.texto}</span> : conTrazas ? `${num(llegadas)} llegaron en la última hora` : undefined} />
        <Cifra k="Contenidas en automático" v={mh ? `${Math.round(mh.pct_auto * 100)} %` : "—"}
          sub={mh ? `falsos positivos ${(Math.round(mh.tasa_fp * 1000) / 10).toLocaleString("es")} %` : undefined} />
        <Cifra k="Esperan a un humano" v={cola ? num(cola.total) : "—"} tono={cola?.total ? "text-aviso" : undefined}
          onClick={s.onVerAprobaciones && (() => s.onVerAprobaciones!())}
          sub={!cola ? "no se pudo leer la cola" : cola.fueraSla ? <span className="font-medium text-critico">{cola.fueraSla} fuera de SLA · 15 min</span>
            : cola.porVencer ? <span className="font-medium text-critico">{cola.porVencer} vencen en &lt; 5 min</span> : "ninguna cerca del SLA"} />
        <Cifra k="Incidentes abiertos" v={conTrazas ? num(abiertos.length) : "—"}
          onClick={s.onVerIncidente && abiertos[0] ? () => s.onVerIncidente!(abiertos[0].clave, abiertos[0].cidr) : undefined}
          sub={!conTrazas ? "no se pudo leer la traza" : abiertos.length ? <>{activos.length ? <span className="font-medium text-critico">{activos.length} activo{activos.length > 1 ? "s" : ""} ahora</span> : "ninguno activo"}{sinDueno.length ? ` · ${sinDueno.length} sin responsable` : ""}</> : "ninguno abierto"} />
        <Cifra k="Ruido evitado" v={ms ? num(ms.suprimidas) : "—"} sub="alertas repetidas en esta sesión" className="col-span-2 lg:col-span-1" />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <TeToca pend={pend} ahora={ahora} incidentes={incidentes} fallidas={fallidasRecientes(regs, ahora)} s={s} />
        <Bloque titulo="Actividad · últimas 24 h" extra={<span className="text-xs text-muted-foreground">por hora</span>}>
          <div className="px-4 pb-4">
            <Horas horas={horas} />
            <div className="mt-2 flex flex-wrap gap-x-3 text-[11px] text-muted-foreground">
              <span><i className="mr-1 inline-block size-2 rounded-sm bg-primary" />en automático</span>
              <span><i className="mr-1 inline-block size-2 rounded-sm bg-aviso" />a un analista</span>
              <span><i className="mr-1 inline-block size-2 rounded-sm bg-muted-foreground/45" />descartadas</span>
              {parcial && <span className="ml-auto">la ventana cargada empieza a las {hora(new Date(desde!).toISOString())}</span>}
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              {([[conTrazas ? num(llegadas) : "—", "llegaron en la última hora", ""],
                [mh?.mttr_mediano_seg != null ? `${Math.round(mh.mttr_mediano_seg)} s` : "—", "respuesta humana mediana", ""],
                [mh?.sla_pct != null && mh.escalado_humano ? `${Math.round(mh.sla_pct * 100)} %` : "—", "resueltas en SLA hoy", mh?.sla_pct != null && mh.sla_pct < 0.9 ? "text-critico" : "text-ok"]] as const).map(([v, t, c]) => (
                <div key={t} className="rounded-lg border border-border px-2.5 py-1.5">
                  <div className={cn("text-base font-semibold tabular-nums", v !== "—" && c)}>{v}</div><div className="text-[11px] text-muted-foreground">{t}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 space-y-1.5 border-t border-border pt-3">
              <div className="text-xs text-muted-foreground">Ahora mismo</div>
              {ahoraMismo.map((e) => (
                <button key={e.clave} type="button" onClick={s.onVerIncidente && (() => s.onVerIncidente!(e.clave, e.cidr))}
                  className="grid w-full grid-cols-[10px_minmax(0,1fr)_auto] items-center gap-2 rounded text-left text-[13px] hover:bg-muted/50">
                  <span className={cn("size-2 rounded-full", e.activo ? "animate-pulse bg-critico motion-reduce:animate-none" : "bg-muted-foreground/50")} />
                  <span className="truncate"><span className="font-mono font-semibold">{e.cidr}</span> · {decisiones(e.n)} contra {e.objetivos[0]?.equipo ?? "la red"}</span>
                  <span className={cn("rounded px-1.5 text-[11px] font-medium", e.activo ? PILDORA.critico : PILDORA.neutro)}>{e.activo ? "activa" : "en calma"}</span>
                </button>
              ))}
              {!ahoraMismo.length && <p className="text-[13px] text-muted-foreground">{conTrazas ? "Ninguna campaña abierta." : "No se pudo leer la traza."}</p>}
            </div>
          </div>
        </Bloque>
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
        <Bloque titulo="Qué se está atacando · 24 h" extra={<Enlace onClick={s.onVerInforme}>Informe</Enlace>}>
          <Barras filas={atacado.clases.slice(0, 6).map((c) => ({ clave: c.clase, nombre: etiquetaClase(c.clase), n: c.n }))} />
        </Bloque>
        <Bloque titulo="Equipos más atacados · 24 h" extra={<Enlace onClick={s.onVerRed}>Red</Enlace>}>
          <Barras filas={atacado.equipos.slice(0, 5).map((e) => ({ clave: e.equipo, nombre: <span className="font-mono">{e.equipo}</span>, n: e.n, verde: e.contenidas }))} />
          {atacado.equipos.length > 0 && <div className="-mt-2 flex gap-3 px-4 pb-3 text-[11px] text-muted-foreground">
            <span><i className="mr-1 inline-block size-2 rounded-sm bg-ok" />contenido</span><span><i className="mr-1 inline-block size-2 rounded-sm bg-critico" />sin contener</span></div>}
        </Bloque>
        <Bloque titulo="Últimas decisiones" extra={<Enlace onClick={s.onVerDecisiones && (() => s.onVerDecisiones!(""))}>Decisiones</Enlace>}>
          <ul className="px-4 pb-2">
            {ultimas.map((d, i) => {
              const des = desenlaceDe(d)
              return (
                <li key={`${d.id_decision}-${i}`}>
                  <button type="button" onClick={s.onVerDecisiones && d.id_decision ? () => s.onVerDecisiones!(d.id_decision!) : undefined}
                    className="grid w-full grid-cols-[2.6rem_minmax(0,1fr)_auto] items-center gap-2 border-b border-border py-1.5 text-left text-[13px] last:border-0 hover:bg-muted/40">
                    <span className="font-mono text-[11px] text-muted-foreground">{hora(d.timestamp)}</span>
                    <span className="truncate"><span className="font-mono text-xs">{d.activo ?? "—"}</span> · {d.clase ? etiquetaClase(d.clase) : "—"}
                      {d.veredicto_humano && <span className="text-muted-foreground"> · {d.veredicto_por ?? SIN_NOMBRE}</span>}</span>
                    <span className={cn("rounded px-1.5 text-[11px] font-medium", PILDORA[des.tono])}>{des.texto}</span>
                  </button>
                </li>
              )
            })}
            {!ultimas.length && <li className="py-6 text-center text-sm text-muted-foreground">Aún no hay decisiones.</li>}
          </ul>
        </Bloque>
      </div>
    </div>
  )
}
