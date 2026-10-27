import { useState } from "react"
import { useSondeo, getWatchlist, watchlistAgregar, watchlistQuitar, type WatchEntrada } from "@/api"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Cargando, SinConexion, Vacio } from "./bits"

// Vista «Watchlist / IoC»: lista local de indicadores (IP o CIDR) que el analista marca como malos.
// Es una ANOTACIÓN (no toca el motor ni las métricas); el visor la usa para marcar los orígenes.
export function Watchlist() {
  const w = useSondeo(getWatchlist)
  const [indicador, setIndicador] = useState("")
  const [nota, setNota] = useState("")
  const [msg, setMsg] = useState<string | null>(null)
  if (!w) return <Cargando />
  const fallo = "error" in w ? w : null
  const lista: WatchEntrada[] = fallo ? (fallo.datos ?? []) : (w as WatchEntrada[])
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />

  const anadir = async () => {
    const ind = indicador.trim()
    if (!ind) return
    const r = await watchlistAgregar(ind, nota.trim())
    if (r) { setIndicador(""); setNota(""); setMsg(null) }
    else setMsg("No se pudo añadir (¿indicador válido? IP o CIDR).")
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Indicadores (IP o CIDR) marcados como maliciosos. Es una anotación del analista: el visor marca
        los orígenes que coincidan con un <span title="watchlist">⚑</span>. No cambia ninguna decisión del motor.
      </p>
      <div className="flex flex-wrap items-end gap-2 rounded-lg border border-border bg-card p-3">
        <input value={indicador} onChange={(e) => setIndicador(e.target.value)} placeholder="IP o CIDR (p. ej. 203.0.113.9 o 198.51.100.0/24)"
          className="min-w-[16rem] flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm" />
        <input value={nota} onChange={(e) => setNota(e.target.value)} placeholder="nota (opcional)"
          className="min-w-[10rem] flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm" />
        <Button size="sm" onClick={anadir}>Añadir</Button>
      </div>
      {msg && <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">{msg}</div>}
      {lista.length === 0 ? <Vacio>La watchlist está vacía.</Vacio> : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Indicador</TableHead><TableHead>Nota</TableHead><TableHead>Añadido</TableHead><TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {lista.map((e) => (
                <TableRow key={e.indicador}>
                  <TableCell className="font-mono text-xs">⚑ {e.indicador}</TableCell>
                  <TableCell className="text-xs">{e.nota || "—"}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{e.operador ? `${e.operador} · ` : ""}{e.agregado_en ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    <button onClick={() => watchlistQuitar(e.indicador)}
                      className="rounded-md border border-border px-2 py-0.5 text-xs hover:bg-muted">Quitar</button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
