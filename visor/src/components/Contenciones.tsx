import { useEffect, useState } from "react"
import { useSondeo, getContenciones, getPausa, setPausa, revertirTodo } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Cargando, SinConexion, Vacio, Dato } from "./bits"

// #8 kill switch: contenciones activas (reconstruidas de la traza) + los dos interruptores de
// seguridad — pausa global de la automatización y des-bloqueo en masa.
export function Contenciones() {
  const c = useSondeo(getContenciones)
  const p = useSondeo(getPausa)
  const pausadaServidor = !!(p && !("error" in p) && p.pausada)
  const [pausaLocal, setPausaLocal] = useState<boolean | null>(null)   // optimista hasta que el sondeo confirma
  const pausada = pausaLocal ?? pausadaServidor
  useEffect(() => { if (pausaLocal !== null && pausaLocal === pausadaServidor) setPausaLocal(null) },
    [pausaLocal, pausadaServidor])
  const activas = c && !("error" in c) ? c : []
  const [confirmar, setConfirmar] = useState(false)
  const [revirtiendo, setRevirtiendo] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const alternarPausa = async () => { const nuevo = !pausada; if (await setPausa(nuevo)) setPausaLocal(nuevo) }
  const desbloquear = async () => {
    setConfirmar(false); setMsg(null); setRevirtiendo(true)
    const r = await revertirTodo()
    setRevirtiendo(false)
    setMsg(r ? `Revertidas ${r.revertidas}${r.fallidas ? ` · ${r.fallidas} fallidas` : ""}.` : "No se pudo revertir.")
  }

  return (
    <div className="space-y-4">
      {/* interruptores de seguridad */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3">
        <button onClick={alternarPausa}
          className={`rounded-md px-4 py-2 text-sm font-medium ${pausada
            ? "bg-emerald-600 text-white hover:bg-emerald-700"
            : "bg-rose-600 text-white hover:bg-rose-700"}`}>
          {pausada ? "Reanudar automatización" : "Pausar automatización"}
        </button>
        <span className="text-sm text-muted-foreground">
          {pausada
            ? "En pausa: toda contención automática espera aprobación humana."
            : "Automatización activa."}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {revirtiendo ? (
            <span className="text-sm text-muted-foreground">Revirtiendo…</span>
          ) : !confirmar ? (
            <button onClick={() => { setMsg(null); setConfirmar(true) }} disabled={!activas.length}
              className="rounded-md border border-border px-3 py-2 text-sm text-foreground enabled:hover:bg-muted disabled:opacity-40">
              Revertir todo
            </button>
          ) : (
            <span className="flex items-center gap-2 text-sm">
              ¿Revertir {activas.length} contención(es)?
              <button onClick={desbloquear} className="rounded-md bg-rose-600 px-3 py-1.5 font-medium text-white hover:bg-rose-700">Sí, revertir</button>
              <button onClick={() => setConfirmar(false)} className="rounded-md border border-border px-3 py-1.5 hover:bg-muted">No</button>
            </span>
          )}
        </div>
      </div>
      {msg && <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">{msg}</div>}

      {/* lista de contenciones activas */}
      {!c ? <Cargando /> : "error" in c ? <SinConexion /> : !c.length ? (
        <Vacio>No hay contenciones activas. Nada bloqueado ahora mismo.</Vacio>
      ) : (
        <div className="rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <span className="text-sm font-medium">
              {c.length} {c.length === 1 ? "contención activa" : "contenciones activas"}
            </span>
            <Dato>reconstruidas de la traza</Dato>
          </div>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Objetivo bloqueado</TableHead><TableHead>Activo</TableHead>
                <TableHead>Dónde</TableHead><TableHead>Acción</TableHead><TableHead>Decisión</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {c.map((x) => (
                <TableRow key={`${x.id_decision}:${x.objetivo}:${x.nodo}`}>
                  <TableCell className="font-mono text-xs">{x.objetivo ?? x.ip ?? "—"}</TableCell>
                  <TableCell>{x.activo ?? "—"}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {x.nodo ?? "—"}{x.via_escalada ? " (escalada)" : ""}
                  </TableCell>
                  <TableCell className="font-mono text-xs">{x.accion_id}</TableCell>
                  <TableCell className="text-muted-foreground">{x.id_decision}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
