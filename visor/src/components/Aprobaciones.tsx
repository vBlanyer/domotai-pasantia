import { useSondeo, getPendientes, aprobar, controlesDePendiente } from "@/api"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function Aprobaciones() {
  const p = useSondeo(getPendientes)
  if (!p || "error" in p) return <p>{p && "error" in p ? "sin conexión" : "cargando…"}</p>
  if (p.length === 0) return <p>ninguna decisión esperando</p>
  return (
    <div className="space-y-3">{p.map((x) => (
      <Card key={x.id}>
        <CardContent className="pt-4">
          <pre className="bg-muted p-2 rounded text-sm whitespace-pre-wrap">{x.lineas.join("\n")}</pre>
          <p className="my-2">{x.prompt}</p>
          <div className="flex gap-2">{controlesDePendiente(x).map((c) => (
            <Button key={c.etiqueta} variant={c.variante === "rechazar" ? "destructive" : "default"}
              onClick={() => aprobar(x.id, c.respuesta)}>{c.etiqueta}</Button>))}</div>
        </CardContent>
      </Card>))}
    </div>
  )
}
