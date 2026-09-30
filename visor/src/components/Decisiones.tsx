import { useEffect, useState, type ReactNode } from "react"
import { ChevronDown, ChevronRight, Shield, ShieldCheck, ShieldX, TriangleAlert } from "lucide-react"
import { useSondeo, getDecisiones, getTrazaDetalle, type Decision, type Detalle, type Pasaje } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Cargando, SinConexion, Vacio, ClaseBadge, Dato, BarraFiltros, Prioridad } from "./bits"
import { filtrarDecisiones, clasesDe, claveDe, contencionDe, filtroLegible, type Contencion, type EstadoContencion, type Filtro } from "@/datos"

const COLS = 8

// Desenlace del veredicto humano, en la columna Decisión.
const DESENLACE: Record<string, string> = { aprobar: "aprobada", rechazar: "rechazada", reclasificar: "reclasificada" }

// De dónde viene la justificación: plantilla (baseline, sin modelo) o el LLM 1B.
function esLLM(v?: string | null) {
  return !!v && !v.startsWith("plantilla")
}

function Pildora({ children, tono, title }: { children: ReactNode; tono: string; title?: string }) {
  return <span title={title} className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${tono}`}>{children}</span>
}

// Chips MITRE + insignia del justificador + señal de RAG, para ver el aporte del LLM/RAG de un vistazo.
function Aporte({ d }: { d: Decision }) {
  const mitre = d.tecnica_mitre ?? []
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1">
      {esLLM(d.version_justificador)
        ? <Pildora tono="bg-violet-500/15 text-violet-600 dark:text-violet-300">LLM</Pildora>
        : <Pildora tono="bg-slate-500/15 text-slate-600 dark:text-slate-300">plantilla</Pildora>}
      {d.con_rag && <Pildora tono="bg-emerald-500/15 text-emerald-600 dark:text-emerald-300">RAG</Pildora>}
      {mitre.map((t) => (
        <span key={t} className="rounded bg-sky-500/15 px-1.5 py-0.5 font-mono text-[10px] text-sky-600 dark:text-sky-300">{t}</span>
      ))}
    </div>
  )
}

function Campo({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{etiqueta}</div>
      <div className="mt-0.5 text-sm">{children}</div>
    </div>
  )
}

function Pasajes({ pasajes, consulta }: { pasajes: Pasaje[]; consulta?: string | null }) {
  if (pasajes.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        Esta decisión no consultó el RAG (la recuperación de conocimiento se activa en los accesos a
        credenciales). Requiere el daemon con{" "}
        <code className="rounded bg-foreground/10 px-1 font-mono text-xs">--con-llm</code>.
      </p>
    )
  return (
    <div className="space-y-2">
      {consulta && <Dato>consulta: {consulta}</Dato>}
      <ul className="space-y-2">
        {pasajes.map((p, i) => (
          <li key={i} className="rounded-md border border-border bg-muted/40 p-2.5 text-sm">
            {p.titulo && <div className="font-medium">{p.titulo}</div>}
            <div className="text-muted-foreground">{p.texto}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}

// Qué pasó con la contención: la pregunta que el operador se hace primero al abrir una decisión.
const FRASE: Record<EstadoContencion, (c: Contencion) => string> = {
  contenida: (c) => `Contenida en ${c.dispositivo ?? "—"}` + (c.escalada && c.desde ? ` · escaló desde ${c.desde}` : ""),
  fallida: (c) => c.desde ? "No se pudo contener: ni el activo ni la escalada lo lograron"
    : "No se pudo contener en el activo (no hay a dónde escalar)",
  retenida: () => "Retenida por el analista: no se ejecutó ninguna acción",
  cancelada: () => "Escalada cancelada por el analista",
  degradada: () => "El agente no respondió: se degradó al motor determinista",
  enrutada: (c) => `Enrutada a ${c.destino ?? "—"}: se deriva al equipo, sin contención (por diseño)`,
  sin_accion: () => "Sin acción de contención",
}

function BloqueContencion({ c }: { c: Contencion }) {
  const Icono = c.estado === "contenida" ? ShieldCheck : c.estado === "fallida" ? ShieldX : Shield
  const tono = c.estado === "contenida" ? "text-emerald-600 dark:text-emerald-400"
    : c.estado === "fallida" ? "text-rose-600 dark:text-rose-400" : "text-muted-foreground"
  const siNo = (b?: boolean) => (b ? "sí" : "no")
  return (
    <Campo etiqueta="Contención">
      <div className={`flex items-center gap-1.5 font-medium ${tono}`}>
        <Icono className="size-4 shrink-0" aria-hidden /> <span>{FRASE[c.estado](c)}</span>
      </div>
      {c.accion && (
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
          <span>{c.accion}</span>
          <span>ejecutada: {siNo(c.ejecutada)}</span>
          <span>verificada: {siNo(c.verificada)}</span>
          {c.comando && <Dato>{c.comando}</Dato>}
        </div>
      )}
      {c.intento && (
        <div className="mt-0.5 text-xs text-muted-foreground">
          intento en {c.intento.nodo ?? "el activo"}: {c.intento.ejecutada ? "se ejecutó pero no se verificó" : "no respondió"}
        </div>
      )}
    </Campo>
  )
}

function Detalles({ id, indice }: { id: string; indice?: number | null }) {
  const [det, setDet] = useState<Detalle | { error: string }>()
  useEffect(() => {
    let vivo = true
    getTrazaDetalle(id, indice).then((d) => { if (vivo) setDet(d) })
    return () => { vivo = false }
  }, [id, indice])

  if (!det) return <p className="text-sm text-muted-foreground">cargando detalle…</p>
  if ("error" in det) return <p className="text-sm text-muted-foreground">no se pudo cargar el detalle de esta decisión.</p>

  const ev = det.justificacion_estructurada?.evidencia ?? {}
  const mitre = det.justificacion_estructurada?.tecnica_mitre ?? []
  // Si la contención escaló, lo que se aplicó fue el bloqueo en el dispositivo que contuvo: su
  // impacto (todo lo que enruta) sustituye al del bloqueo en el activo, que no llegó a aplicarse.
  const efectivo = det.escalada?.resultado === "mitigado" ? det.escalada.impacto_efectivo?.motivo : null
  const motivo = efectivo ?? det.impacto_determinado?.motivo
  const cascada = det.impacto_determinado?.activos_afectados_en_cascada ?? []
  const pasajes = det.pasajes ?? []
  const filtro = filtroLegible(det)

  return (
    <div className="space-y-4">
      {cascada.length > 0 && (
        <div className="rounded-md border border-rose-500/40 bg-rose-500/10 p-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-rose-600 dark:text-rose-400">
            <TriangleAlert className="size-4 shrink-0" /> Riesgo de cascada al aprobar
          </div>
          <p className="mt-1 text-sm">
            Bloquear esta IP aísla un activo del que otros dependen: caerían en cascada{" "}
            <span className="font-medium">{cascada.join(", ")}</span>.
          </p>
        </div>
      )}
      <BloqueContencion c={contencionDe(det)} />
      <Campo etiqueta="Justificación">
        <p className="leading-relaxed">{det.justificacion ?? "—"}</p>
        {det.justificacion_descartada && (
          <div className="mt-2 rounded-md border border-dashed p-2 text-xs text-muted-foreground">
            <p>El modelo respondió, pero su texto se descartó: {det.justificacion_descartada.motivo}</p>
            {det.justificacion_descartada.texto && (
              <p className="mt-1 italic">«{det.justificacion_descartada.texto}»</p>
            )}
          </div>
        )}
      </Campo>
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.keys(ev).length > 0 && (
          <Campo etiqueta="Evidencia">
            <ul className="space-y-0.5">
              {Object.entries(ev).map(([k, v]) => (
                <li key={k}><span className="text-muted-foreground">{k}:</span> <span className="font-mono text-xs">{String(v)}</span></li>
              ))}
            </ul>
          </Campo>
        )}
        {mitre.length > 0 && (
          <Campo etiqueta="Técnicas MITRE ATT&CK">
            <div className="flex flex-wrap gap-1">
              {mitre.map((t) => (
                <span key={t} className="rounded bg-sky-500/15 px-1.5 py-0.5 font-mono text-xs text-sky-600 dark:text-sky-300">{t}</span>
              ))}
            </div>
          </Campo>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {(det.accion_propuesta || filtro) && (
          <Campo etiqueta="Política del perfil">
            <div className="font-mono text-xs">
              {det.accion_propuesta && det.accion_propuesta !== det.accion_final
                ? `${det.accion_propuesta} → ${det.accion_final ?? "ninguna"}`
                : det.accion_propuesta ?? det.accion_final ?? "—"}
            </div>
            {filtro && <div className="mt-0.5 text-muted-foreground">{filtro}</div>}
            {det.veredicto_escalada && (
              <div className="mt-0.5 text-muted-foreground">
                escalada {det.veredicto_escalada === "aprobar" ? "aprobada" : "rechazada"} por el analista
              </div>
            )}
          </Campo>
        )}
        {motivo && <Campo etiqueta="Impacto"><span className="text-muted-foreground">{motivo}</span></Campo>}
      </div>
      <Campo etiqueta="Conocimiento recuperado (RAG)">
        <Pasajes pasajes={pasajes} consulta={det.consulta_rag} />
      </Campo>
    </div>
  )
}

// Las filas de ancho completo (detalle, supresión, reversión, error) llevan texto largo: sin partir
// líneas (TableCell es whitespace-nowrap) estiraban toda la tabla y obligaban a desplazarse en
// horizontal. overflow-wrap parte también lo que no tiene espacios (hashes, comandos, URLs).
const FILA_ANCHA = "whitespace-normal [overflow-wrap:anywhere]"

export function FilaDecision({ d, abierto, onToggle }: { d: Decision; abierto: boolean; onToggle: () => void }) {
  if (d.tipo === "actividad_propia")
    return (
      <TableRow className="text-muted-foreground">
        <TableCell colSpan={COLS} className={`${FILA_ANCHA} italic`}>
          ↺ actividad propia del MDR en {d.activo}: login de gestión al aplicar o verificar una contención (no es un ataque)
        </TableCell>
      </TableRow>
    )
  if (d.tipo === "reversion")
    return (
      <TableRow className="text-muted-foreground">
        <TableCell colSpan={COLS} className={`${FILA_ANCHA} italic`}>
          ↶ reversión de {d.id_decision_revertida ?? "—"} en {d.nodo ?? "—"}: {d.exito ? "aplicada" : "falló"}
          {d.accion_id ? ` (${d.accion_id})` : ""}
        </TableCell>
      </TableRow>
    )
  if (d.tipo === "error")
    return (
      <TableRow className="text-rose-600 dark:text-rose-400">
        <TableCell colSpan={COLS} className={FILA_ANCHA}>
          ✗ {d.id_decision}: error al procesar el incidente de {d.origen_ip ?? "—"} → {d.activo ?? "—"}: {d.error}
        </TableCell>
      </TableRow>
    )
  if (d.tipo === "actividad_suprimida")
    return (
      <TableRow className="text-muted-foreground">
        <TableCell colSpan={COLS} className={`${FILA_ANCHA} italic`}>
          ↩ el ataque continúa · {d.alertas_suprimidas} alerta(s) suprimida(s) (ya decidido)
        </TableCell>
      </TableRow>
    )
  return (
    <>
      <TableRow className="cursor-pointer" onClick={onToggle}>
        <TableCell className="w-6 text-muted-foreground">
          {abierto ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </TableCell>
        <TableCell><Prioridad n={d.prioridad} /></TableCell>
        <TableCell><Dato>{d.timestamp}</Dato></TableCell>
        <TableCell className="font-medium">{d.activo}</TableCell>
        <TableCell>
          <ClaseBadge clase={d.clase} />
          <Aporte d={d} />
          {d.cascada && d.cascada.length > 0 && (
            <div className="mt-1.5 inline-flex items-center gap-1 rounded bg-rose-500/15 px-1.5 py-0.5 text-xs font-medium text-rose-600 dark:text-rose-400">
              <TriangleAlert className="size-3 shrink-0" /> tumba en cascada: {d.cascada.join(", ")}
            </div>
          )}
          {d.clase_reclasificada && (
            <div className="mt-1.5 rounded bg-amber-500/15 px-1.5 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-300">
              reclasificada: {d.clase} → {d.clase_reclasificada}
            </div>
          )}
        </TableCell>
        <TableCell className="tabular-nums">{d.confianza != null ? d.confianza.toFixed(2) : "—"}</TableCell>
        <TableCell>
          {d.accion_final
            ?? (d.resultado_filtro === "veta" && d.accion_propuesta
              ? <s className="text-muted-foreground">{d.accion_propuesta}</s>
              : <span className="text-muted-foreground">—</span>)}
          {d.resultado_filtro === "degrada" && (
            <> <Pildora tono="bg-amber-500/15 text-amber-700 dark:text-amber-300" title={`propuesta: ${d.accion_propuesta ?? "—"}`}>degradada</Pildora></>
          )}
          {d.resultado_filtro === "veta" && !d.accion_final && (
            <> <Pildora tono="bg-rose-500/15 text-rose-700 dark:text-rose-300">vetada</Pildora></>
          )}
        </TableCell>
        <TableCell>
          {d.requiere_humano
            ? <span className="text-amber-600 dark:text-amber-400">humano</span>
            : <span className="text-muted-foreground">auto</span>}
          {d.veredicto_humano && (
            <div className="text-xs text-muted-foreground">{DESENLACE[d.veredicto_humano] ?? d.veredicto_humano}</div>
          )}
        </TableCell>
      </TableRow>
      {abierto && d.id_decision && (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={COLS} className={`${FILA_ANCHA} bg-muted/30 p-4`}>
            <Detalles id={d.id_decision} indice={d.indice} />
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

export function Decisiones() {
  const d = useSondeo(getDecisiones)
  const [abierto, setAbierto] = useState<string | null>(null)
  const [filtro, setFiltro] = useState<Filtro>({ texto: "", clase: "" })
  if (!d) return <Cargando />
  if ("error" in d) return <SinConexion />
  if (d.length === 0) return <Vacio>Aún no hay decisiones. Lanza un ataque para verlas aquí.</Vacio>
  const filtradas = filtrarDecisiones(d, filtro)
  return (
    <div className="space-y-3">
      <BarraFiltros f={filtro} set={setFiltro} clases={clasesDe(d)} cuenta={filtradas.length} />
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-6" />
              <TableHead>Prioridad</TableHead><TableHead>Cuándo</TableHead><TableHead>Activo</TableHead><TableHead>Clase</TableHead>
              <TableHead>Confianza</TableHead><TableHead>Acción</TableHead><TableHead>Decisión</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtradas.map((x, i) => {
              const clave = claveDe(x, i)
              return (
                <FilaDecision
                  key={clave}
                  d={x}
                  abierto={abierto === clave}
                  onToggle={() => setAbierto((a) => (a === clave ? null : clave))}
                />
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
