import { TriangleAlert } from "lucide-react"
import { useSondeo, getPendientes, aprobar, parsearPendiente, type Pendiente, type Opcion } from "@/api"
import { Button } from "@/components/ui/button"
import { Cargando, SinConexion, Vacio, Punto } from "./bits"

const CLASE_LEGIBLE: Record<string, string> = {
  vp_intento_acceso: "Intento de acceso",
  vp_acceso_consumado: "Acceso consumado",
  fp_actividad_legitima: "Falso positivo (legítimo)",
  fp_exposicion_inexistente: "Falso positivo (exposición)",
  no_soportada: "No soportada",
  amenaza_enrutada: "Enrutada a un equipo",
}

// Botón a partir de una opción del menú: veredicto (aprobar/rechazar/reclasificar) o una clase.
function boton(op: Opcion): { etiqueta: string; variante: "default" | "destructive" | "outline" } {
  const base = op.etiqueta.split("—")[0].trim().toLowerCase()
  if (base === "aprobar") return { etiqueta: "Aprobar", variante: "default" }
  if (base === "rechazar") return { etiqueta: "Rechazar", variante: "destructive" }
  if (base === "reclasificar") return { etiqueta: "Reclasificar", variante: "outline" }
  return { etiqueta: CLASE_LEGIBLE[base] ?? op.etiqueta, variante: "outline" }   // submenú de clases
}

function LineaInfo({ t }: { t: string }) {
  const i = t.indexOf(": ")
  if (i === -1) return <div className="text-sm">{t}</div>
  return (
    <div className="text-sm">
      <span className="text-muted-foreground">{t.slice(0, i)}:</span> {t.slice(i + 2)}
    </div>
  )
}

function Tarjeta({ p }: { p: Pendiente }) {
  const v = parsearPendiente(p)
  const escalada = p.tipo === "escalada"
  const conCascada = !!v.consecuencia && /cascada/.test(v.consecuencia)
  const clasificando = (v.titulo ?? "").startsWith("Nueva clase")

  return (
    <div className="overflow-hidden rounded-lg border border-amber-500/40 bg-amber-500/[0.04]">
      <div className="flex items-center gap-2 border-b border-amber-500/20 px-4 py-2.5">
        <Punto estado="pendiente" />
        <span className="text-sm font-medium text-amber-700 dark:text-amber-300">Espera tu decisión</span>
        {v.incidente && <span className="ml-1 truncate text-xs text-muted-foreground">· {v.incidente}</span>}
      </div>

      <div className="space-y-3 p-4">
        {v.info.length > 0 && (
          <div className="space-y-1">
            {v.info.map((t, i) => <LineaInfo key={i} t={t} />)}
          </div>
        )}

        {v.consecuencia && (
          <div className={`flex items-start gap-2 rounded-md border p-2.5 text-sm ${
            conCascada ? "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300" : "border-border bg-muted"
          }`}>
            {conCascada && <TriangleAlert className="mt-0.5 size-4 shrink-0" />}
            <div><span className="font-medium">Consecuencia:</span> {v.consecuencia}</div>
          </div>
        )}

        {clasificando && <div className="pt-1 text-sm font-medium">Elige la clase correcta:</div>}

        <div className="flex flex-wrap gap-2">
          {escalada ? (
            <>
              <Button onClick={() => aprobar(p.id, "s")}>Aprobar</Button>
              <Button variant="destructive" onClick={() => aprobar(p.id, "")}>Rechazar</Button>
            </>
          ) : v.opciones.length > 0 ? (
            v.opciones.map((op) => {
              const b = boton(op)
              return (
                <Button key={op.n} variant={b.variante} onClick={() => aprobar(p.id, op.n)}>
                  {b.etiqueta}
                </Button>
              )
            })
          ) : (
            // fallback: el prompt no trajo el menú (p. ej. daemon sin la última versión)
            <>
              <Button onClick={() => aprobar(p.id, "1")}>Aprobar</Button>
              <Button variant="destructive" onClick={() => aprobar(p.id, "2")}>Rechazar</Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export function Aprobaciones() {
  const p = useSondeo(getPendientes)
  if (!p) return <Cargando />
  if ("error" in p) return <SinConexion />
  if (p.length === 0)
    return <Vacio>Nada que aprobar ahora mismo. Cuando una decisión necesite un humano, aparecerá aquí.</Vacio>
  return (
    <div className="space-y-4">
      {p.map((x) => <Tarjeta key={x.id} p={x} />)}
    </div>
  )
}
