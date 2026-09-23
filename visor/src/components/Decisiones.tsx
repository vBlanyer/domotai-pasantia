import { useEffect, useState, type ReactNode } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { useSondeo, getDecisiones, getTrazaDetalle, type Decision, type Detalle, type Pasaje } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Cargando, SinConexion, Vacio, ClaseBadge, Dato } from "./bits"

const COLS = 7

// De dónde viene la justificación: plantilla (baseline, sin modelo) o el LLM 1B.
function esLLM(v?: string | null) {
  return !!v && !v.startsWith("plantilla")
}

function Pildora({ children, tono }: { children: ReactNode; tono: string }) {
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${tono}`}>{children}</span>
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

function Detalles({ id }: { id: string }) {
  const [det, setDet] = useState<Detalle | { error: string }>()
  useEffect(() => {
    let vivo = true
    getTrazaDetalle(id).then((d) => { if (vivo) setDet(d) })
    return () => { vivo = false }
  }, [id])

  if (!det) return <p className="text-sm text-muted-foreground">cargando detalle…</p>
  if ("error" in det) return <p className="text-sm text-muted-foreground">no se pudo cargar el detalle de esta decisión.</p>

  const ev = det.justificacion_estructurada?.evidencia ?? {}
  const mitre = det.justificacion_estructurada?.tecnica_mitre ?? []
  const motivo = det.impacto_determinado?.motivo
  const pasajes = det.pasajes ?? []

  return (
    <div className="space-y-4">
      <Campo etiqueta="Justificación">
        <p className="leading-relaxed">{det.justificacion ?? "—"}</p>
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
      {motivo && <Campo etiqueta="Impacto"><span className="text-muted-foreground">{motivo}</span></Campo>}
      <Campo etiqueta="Conocimiento recuperado (RAG)">
        <Pasajes pasajes={pasajes} consulta={det.consulta_rag} />
      </Campo>
    </div>
  )
}

export function FilaDecision({ d, abierto, onToggle }: { d: Decision; abierto: boolean; onToggle: () => void }) {
  if (d.tipo === "actividad_suprimida")
    return (
      <TableRow className="text-muted-foreground">
        <TableCell colSpan={COLS} className="italic">
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
        <TableCell><Dato>{d.timestamp}</Dato></TableCell>
        <TableCell className="font-medium">{d.activo}</TableCell>
        <TableCell>
          <ClaseBadge clase={d.clase} />
          <Aporte d={d} />
        </TableCell>
        <TableCell className="tabular-nums">{d.confianza != null ? d.confianza.toFixed(2) : "—"}</TableCell>
        <TableCell>{d.accion_final ?? <span className="text-muted-foreground">—</span>}</TableCell>
        <TableCell>
          {d.requiere_humano
            ? <span className="text-amber-600 dark:text-amber-400">humano</span>
            : <span className="text-muted-foreground">auto</span>}
        </TableCell>
      </TableRow>
      {abierto && d.id_decision && (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={COLS} className="bg-muted/30 p-4">
            <Detalles id={d.id_decision} />
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

export function Decisiones() {
  const d = useSondeo(getDecisiones)
  const [abierto, setAbierto] = useState<string | null>(null)
  if (!d) return <Cargando />
  if ("error" in d) return <SinConexion />
  if (d.length === 0) return <Vacio>Aún no hay decisiones. Lanza un ataque para verlas aquí.</Vacio>
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-6" />
            <TableHead>Cuándo</TableHead><TableHead>Activo</TableHead><TableHead>Clase</TableHead>
            <TableHead>Confianza</TableHead><TableHead>Acción</TableHead><TableHead>Decisión</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {d.map((x, i) => (
            <FilaDecision
              key={x.id_decision ?? i}
              d={x}
              abierto={!!x.id_decision && abierto === x.id_decision}
              onToggle={() => setAbierto((a) => (a === x.id_decision ? null : x.id_decision ?? null))}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
