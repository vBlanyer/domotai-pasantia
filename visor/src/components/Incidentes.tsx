import { useSondeo, getTrazas, type Decision } from "@/api"
import { Prioridad, Cargando, SinConexion, Vacio } from "@/components/bits"
import { campanasDe, estadoDeCasos } from "@/datos"
import { ESTADO_CASO } from "@/components/PanelCaso"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

const hora = (ts?: string | null) => {
  if (!ts) return "—"
  const t = new Date(ts)
  return isNaN(t.getTime()) ? ts : new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(t)
}

// La clave de incidente (caso a nivel campaña /24) a partir del prefijo de `campanasDe` ("203.0.113.").
const claveDeCampana = (prefijo: string) => "inc:" + prefijo.replace(/\.$/, "")

// Vista «Incidentes»: trabaja por INCIDENTE (= una campaña de origen /24, colapsa las IPs rotadas en
// una historia de ataque) en vez de por alerta suelta. Cada incidente tiene su propio estado de caso
// (reutiliza la maquinaria de casos con la clave `inc:<prefijo>`). Al pulsarlo se abre su detalle.
export function Incidentes({ onVerIncidente }: { onVerIncidente: (clave: string, cidr: string) => void }) {
  const t = useSondeo(getTrazas)
  if (!t) return <Cargando />
  const fallo = "error" in t ? t : null
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />
  const regs: Decision[] = fallo ? (fallo.datos ?? []) : (t as Decision[])
  const campanas = campanasDe(regs)
  if (campanas.length === 0) return <Vacio>Sin incidentes: no hay ataques agrupables por campaña todavía.</Vacio>
  const casos = estadoDeCasos(regs)   // incluye los casos de incidente (clave `inc:…`), de la ventana
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Cada <strong>incidente</strong> agrupa una <strong>campaña de origen /24</strong> (las IPs rotadas de un
        mismo atacante = una sola historia). Pulsa un incidente para ver su cronología y gestionar su caso
        (estado, responsable, notas) a nivel incidente.
      </p>
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Incidente (campaña)</TableHead><TableHead>Caso</TableHead><TableHead>Gravedad</TableHead>
              <TableHead>IPs</TableHead><TableHead>Decisiones</TableHead>
              <TableHead>Objetivos</TableHead><TableHead>Ventana</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {campanas.map((c) => {
              const clave = claveDeCampana(c.prefijo)
              const est = ESTADO_CASO[casos[clave]?.estado ?? "nuevo"] ?? ESTADO_CASO.nuevo
              return (
                <TableRow key={c.cidr} className="cursor-pointer" onClick={() => onVerIncidente(clave, c.cidr)}
                  title="Ver el detalle del incidente">
                  <TableCell>
                    <span className="font-mono text-xs">{c.cidr}</span>
                    {c.alcance && <span className="ml-1 text-xs text-muted-foreground">· {c.alcance}</span>}
                  </TableCell>
                  <TableCell><span className={`rounded px-1.5 py-0.5 text-xs font-medium ${est.clase}`}>{est.texto}</span></TableCell>
                  <TableCell><Prioridad n={c.prioridad || null} /></TableCell>
                  <TableCell className="tabular-nums whitespace-nowrap">{c.ips} IP{c.ips === 1 ? "" : "s"}</TableCell>
                  <TableCell className="tabular-nums">×{c.n}</TableCell>
                  <TableCell className="text-xs">
                    <span title={c.objetivos.map((o) => `${o.equipo} ×${o.n}`).join(", ")}>
                      {c.objetivos.slice(0, 2).map((o) => o.equipo).join(", ")}
                      {c.objetivos.length > 2 ? ` +${c.objetivos.length - 2}` : ""}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{hora(c.primera)} → {hora(c.ultima)}</TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
