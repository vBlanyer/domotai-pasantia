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
            <span className={cadena.ok ? "text-emerald-600" : "text-rose-600"}>{cadena.texto}</span>
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
                <TableHead>Cuándo</TableHead><TableHead>Activo</TableHead><TableHead>Clase</TableHead>
                <TableHead>Acción</TableHead><TableHead>Decisión</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>{t.map((x, i) => <FilaDecision key={i} d={x} />)}</TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
