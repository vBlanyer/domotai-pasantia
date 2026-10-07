import { TACTICAS, TECNICAS, tecnicasDe } from "@/attack"
import { useTema } from "@/tema"

type Tecnica = { tecnica: string; n: number }

// Intensidad del heat en escala log (los conteos están muy sesgados: 161 vs 1). 0 = sin actividad.
function intensidad(n: number, max: number): number {
  if (n <= 0 || max <= 0) return 0
  return 0.28 + 0.72 * (Math.log(n + 1) / Math.log(max + 1))
}

function Celda({ id, n, max, serie }: { id: string; n: number; max: number; serie: string }) {
  const activa = n > 0
  const k = intensidad(n, max)
  const nombre = TECNICAS[id]?.nombre
  const title = activa
    ? `${id}${nombre ? ` · ${nombre}` : ""} · ${n} ${n === 1 ? "detección" : "detecciones"}`
    : `${id}${nombre ? ` · ${nombre}` : ""} · cubierta, sin actividad`
  return (
    <div
      data-tecnica={id}
      data-activa={activa ? "true" : "false"}
      title={title}
      className={`rounded-md border px-2 py-1.5 text-xs leading-tight ${
        activa ? "border-transparent font-medium" : "border-dashed border-border text-muted-foreground"
      }`}
      style={activa ? { backgroundColor: `rgb(${serie} / ${k})`, color: k > 0.55 ? "#fff" : undefined } : undefined}
    >
      <div className="font-mono tabular-nums">{id}</div>
      {activa && <div className="tabular-nums">{n}</div>}
    </div>
  )
}

export function MatrizAttack({ tecnicas }: { tecnicas: Tecnica[] }) {
  const serie = useTema().oscuro ? "57 135 229" : "42 120 214"
  const conteo: Record<string, number> = {}
  for (const t of tecnicas) conteo[t.tecnica] = (conteo[t.tecnica] ?? 0) + t.n
  const max = Math.max(1, ...tecnicas.map((t) => t.n))
  // Técnicas observadas que no están en nuestro mapa de referencia: no se pierden, van a «Otras».
  const desconocidas = tecnicas.filter((t) => !TECNICAS[t.tecnica]).map((t) => t.tecnica)

  const columnas = TACTICAS.map((tac) => ({ nombre: tac.nombre, ids: tecnicasDe(tac.id) }))
  if (desconocidas.length) columnas.push({ nombre: "Otras", ids: [...new Set(desconocidas)].sort() })

  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
        <span>cobertura: la reconocemos</span>
        <span className="h-3 w-3 rounded-sm border border-dashed border-border" />
        <span className="ml-2">actividad:</span>
        <span className="flex overflow-hidden rounded-sm">
          {[0.2, 0.45, 0.7, 1].map((k) => (
            <span key={k} className="h-3 w-4" style={{ backgroundColor: `rgb(${serie} / ${k})` }} />
          ))}
        </span>
        <span>más</span>
      </div>
      <div className="overflow-x-auto">
        <div className="flex gap-3">
          {columnas.map((col) => {
            const total = col.ids.reduce((s, id) => s + (conteo[id] ?? 0), 0)
            return (
              <div key={col.nombre} className="min-w-[8.5rem] flex-1">
                <div className="mb-2 border-b border-border pb-1.5">
                  <div className="text-xs font-medium">{col.nombre}</div>
                  <div className="text-[10px] tabular-nums text-muted-foreground">{total} det.</div>
                </div>
                <div className="space-y-1.5">
                  {col.ids.map((id) => (
                    <Celda key={id} id={id} n={conteo[id] ?? 0} max={max} serie={serie} />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
