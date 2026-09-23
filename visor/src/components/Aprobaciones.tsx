import { useSondeo, getPendientes, aprobar, controlesDePendiente } from "@/api"
import { Button } from "@/components/ui/button"
import { Cargando, SinConexion, Vacio, Punto } from "./bits"

export function Aprobaciones() {
  const p = useSondeo(getPendientes)
  if (!p) return <Cargando />
  if ("error" in p) return <SinConexion />
  if (p.length === 0)
    return <Vacio>Nada que aprobar ahora mismo. Cuando una decisión necesite un humano, aparecerá aquí.</Vacio>
  return (
    <div className="space-y-4">
      {p.map((x) => (
        <div key={x.id} className="overflow-hidden rounded-lg border border-amber-500/40 bg-amber-500/[0.04]">
          <div className="flex items-center gap-2 border-b border-amber-500/20 px-4 py-2.5">
            <Punto estado="pendiente" />
            <span className="text-sm font-medium text-amber-700 dark:text-amber-300">Espera tu decisión</span>
          </div>
          <div className="p-4">
            <pre className="mb-3 overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed text-foreground/90 whitespace-pre-wrap">
              {x.lineas.join("\n") || x.prompt}
            </pre>
            <div className="flex flex-wrap gap-2">
              {controlesDePendiente(x).map((c) => (
                <Button
                  key={c.etiqueta}
                  variant={c.variante === "rechazar" ? "destructive" : "default"}
                  onClick={() => aprobar(x.id, c.respuesta)}
                >
                  {c.etiqueta}
                </Button>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
