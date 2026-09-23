import { useState } from "react"
import { useSondeo, getTrazas, getVerificacion } from "@/api"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { FilaDecision } from "./Decisiones"
import { Cargando, SinConexion, Vacio, Punto } from "./bits"

type Estado = { texto: string; ok: boolean } | null

export function Trazas() {
  const t = useSondeo(getTrazas)
  const [cadena, setCadena] = useState<Estado>(null)
  const [abierto, setAbierto] = useState<string | null>(null)
  const verificar = async () => {
    const r = await getVerificacion()
    if ("error" in r) return setCadena({ texto: "sin conexión", ok: false })
    setCadena(r.ok ? { texto: "cadena íntegra", ok: true } : { texto: `rota en ${r.roto_en}: ${r.motivo}`, ok: false })
  }
  if (!t) return <Cargando />
  if ("error" in t) return <SinConexion />
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <Button size="sm" variant="secondary" onClick={verificar}>Verificar la cadena de hashes</Button>
        {cadena && (
          <span className="inline-flex items-center gap-2 text-sm">
            <Punto estado={cadena.ok ? "ok" : "caido"} />
            <span className={cadena.ok ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}>{cadena.texto}</span>
          </span>
        )}
      </div>
      {t.length === 0 ? (
        <Vacio>La traza está vacía. Las decisiones aparecerán aquí, encadenadas por hash.</Vacio>
      ) : (
        <div className="rounded-lg border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-6" />
                <TableHead>Cuándo</TableHead><TableHead>Activo</TableHead><TableHead>Clase</TableHead>
                <TableHead>Confianza</TableHead><TableHead>Acción</TableHead><TableHead>Decisión</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {t.map((x, i) => (
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
      )}
    </div>
  )
}
