import { useState } from "react"
import { useSondeo, getTrazas, getVerificacion } from "@/api"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { FilaDecision } from "./Decisiones"

export function Trazas() {
  const t = useSondeo(getTrazas)
  const [v, setV] = useState<string>("")
  const verificar = async () => {
    const r = await getVerificacion()
    setV("error" in r ? "sin conexión" : r.ok ? "cadena íntegra" : `rota en ${r.roto_en}: ${r.motivo}`)
  }
  if (!t || "error" in t) return <p>{t && "error" in t ? "sin conexión" : "cargando…"}</p>
  return (
    <div>
      <p className="mb-2">{v} <Button size="sm" onClick={verificar}>verificar cadena</Button></p>
      <Table>
        <TableHeader><TableRow><TableHead>Cuándo</TableHead><TableHead>Activo</TableHead><TableHead>Clase</TableHead><TableHead>Acción</TableHead></TableRow></TableHeader>
        <TableBody>{t.map((x, i) => <FilaDecision key={i} d={x} />)}</TableBody>
      </Table>
    </div>
  )
}
