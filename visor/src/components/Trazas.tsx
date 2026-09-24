import { useState } from "react"
import { useSondeo, getTrazas, getVerificacion, type Decision } from "@/api"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Cargando, SinConexion, Vacio, Punto, BarraFiltros } from "./bits"
import { filtrarDecisiones, clasesDe, type Filtro } from "@/datos"

type Estado = { texto: string; ok: boolean; roto?: number | null } | null

const GENESIS = "0".repeat(64)

// Muestra un hash abreviado (o "génesis" para el eslabón inicial); el título lleva el completo.
function Hash({ h, previo }: { h?: string | null; previo?: boolean }) {
  if (!h) return <span className="text-muted-foreground">—</span>
  if (previo && h === GENESIS) return <span className="text-xs text-muted-foreground">génesis</span>
  return <span className="font-mono text-xs" title={h}>{h.slice(0, 10)}…</span>
}

export function Trazas() {
  const t = useSondeo(getTrazas)
  const [cadena, setCadena] = useState<Estado>(null)
  const [filtro, setFiltro] = useState<Filtro>({ texto: "", clase: "" })
  const verificar = async () => {
    const r = await getVerificacion()
    if ("error" in r) return setCadena({ texto: "sin conexión", ok: false })
    setCadena(r.ok
      ? { texto: "cadena íntegra: nada fue alterado", ok: true }
      : { texto: `cadena rota en el registro #${(r.roto_en ?? 0) + 1}: ${r.motivo}`, ok: false, roto: r.roto_en })
  }
  if (!t) return <Cargando />
  if ("error" in t) return <SinConexion />
  const regs: Decision[] = t
  // Se filtra preservando el índice real de la cadena (para el # y el resaltado de "roto"):
  // filtrarDecisiones conserva las referencias, así que basta un Set por identidad.
  const enFiltro = new Set(filtrarDecisiones(regs, filtro))
  const filas = regs.map((r, i) => ({ r, i })).filter(({ r }) => enFiltro.has(r))

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-heading text-sm font-semibold">Registro auditable · cadena de hashes (SHA-256)</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Cada decisión se encadena con la anterior (<span className="font-mono">hash_previo → hash</span>);
              si algún registro se altera, la verificación detecta dónde se rompe la cadena.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button size="sm" variant="secondary" onClick={verificar}>Verificar la cadena</Button>
            {cadena && (
              <span className="inline-flex items-center gap-2 text-sm">
                <Punto estado={cadena.ok ? "ok" : "caido"} />
                <span className={cadena.ok ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}>{cadena.texto}</span>
              </span>
            )}
          </div>
        </div>
      </div>

      {regs.length === 0 ? (
        <Vacio>La traza está vacía. Cada decisión aparecerá aquí, encadenada por hash.</Vacio>
      ) : (
        <>
        <BarraFiltros f={filtro} set={setFiltro} clases={clasesDe(regs)} cuenta={filas.length} />
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-10">#</TableHead>
                <TableHead>Decisión</TableHead><TableHead>Cuándo</TableHead><TableHead>Registro</TableHead>
                <TableHead>hash_previo</TableHead><TableHead className="w-6" />
                <TableHead>hash</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filas.map(({ r, i }) => {
                const roto = cadena?.roto === i
                const suprimida = r.tipo === "actividad_suprimida"
                return (
                  <TableRow key={r.id_decision ?? i} className={roto ? "bg-rose-500/10" : undefined}>
                    <TableCell className="tabular-nums text-muted-foreground">{i + 1}</TableCell>
                    <TableCell className="font-mono text-xs">{r.id_decision ?? "—"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.timestamp}</TableCell>
                    <TableCell className="text-xs">
                      {suprimida
                        ? <span className="text-muted-foreground italic">actividad suprimida (+{r.alertas_suprimidas})</span>
                        : <span>{r.clase ?? "—"}</span>}
                    </TableCell>
                    <TableCell><Hash h={r.hash_previo} previo /></TableCell>
                    <TableCell className="text-muted-foreground">→</TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-2">
                        <Hash h={r.hash} />
                        {roto && <span className="text-xs font-medium text-rose-600 dark:text-rose-400">alterado</span>}
                      </span>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
        </>
      )}
    </div>
  )
}
