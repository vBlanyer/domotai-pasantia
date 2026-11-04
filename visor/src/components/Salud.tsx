import { useEffect, useState } from "react"
import { useSondeo, getSalud, getLatido, ahoraServidor } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Punto, Cargando, SinConexion, Vacio } from "./bits"
import { clasificar, edadMuestraMs, MUESTRA_VIEJA_MS, type Fila } from "@/salud"
import { edadTexto } from "@/alertas"
import { cn } from "@/lib/utils"

const seg = (s: number) => (s < 1 ? `${Math.round(s * 10) / 10} s` : s < 60 ? `${Math.round(s)} s` : edadTexto(s * 1000).replace("hace ", ""))
const horaLocal = (iso: string) => {
  const t = new Date(iso)
  return isNaN(t.getTime()) ? iso : t.toLocaleTimeString()
}

// Franja del propio MDR: lo que el daemon cuenta de sí mismo en /healthz. Sin ella, el único rastro
// del estado del MDR en el visor era el punto verde del menú.
function FranjaMdr() {
  const l = useSondeo(getLatido, 5000)
  if (!l || "error" in l) return null
  const celda = "px-4 py-3 border-l border-border"
  return (
    <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-border bg-card text-sm sm:grid-cols-[auto_1fr_1fr_1fr]">
      <div className="flex items-center gap-2 bg-muted px-4 py-3 font-semibold">
        <Punto estado={l.ok ? "ok" : "caido"} />MDR <span className="text-xs font-normal text-muted-foreground">propio</span>
      </div>
      <div className={celda}>
        <div className="text-[11px] text-muted-foreground">Lazo de decisión</div>
        <div className={cn("font-semibold tabular-nums", l.ok ? "text-ok" : "text-critico")}>
          {l.ok ? "vivo" : "parado"} <span className="text-xs font-normal text-muted-foreground">último tick hace {seg(l.lazo_quietud_s)}</span>
        </div>
      </div>
      <div className={celda}>
        <div className="text-[11px] text-muted-foreground">Ingesta del SIEM</div>
        <div className="font-semibold tabular-nums">
          {l.ingesta_silencio_s == null ? <span className="text-muted-foreground">sin alertas aún</span> : <>hace {seg(l.ingesta_silencio_s)} <span className="text-xs font-normal text-muted-foreground">última alerta</span></>}
        </div>
      </div>
      <div className={celda}>
        <div className="text-[11px] text-muted-foreground">Alertas procesadas</div>
        <div className="font-semibold tabular-nums">
          {l.alertas.toLocaleString()} {l.desde && <span className="text-xs font-normal text-muted-foreground">desde las {horaLocal(l.desde)}</span>}
        </div>
      </div>
    </div>
  )
}

const NOMBRES = (xs: string[]) => xs.map((x, i) => <span key={x}>{i > 0 && ", "}<b className="font-medium text-foreground">{x}</b></span>)

function Relacion({ f }: { f: Fila }) {
  if (f.estado === "caido") return f.afecta.length ? <>afecta a {NOMBRES(f.afecta)}</> : <>—</>
  if (f.estado === "degradado") return <>responde, pero {NOMBRES(f.causas)} {f.causas.length > 1 ? "están caídos" : "está caído"}</>
  if (f.sostiene.length) return <>sostiene a {NOMBRES(f.sostiene)}</>
  if (f.depende_de.length) return <>depende de {f.depende_de.join(", ")}</>
  return <>—</>
}

export function Salud() {
  const s = useSondeo(getSalud)
  // El sondeo no re-renderiza si la muestra no cambia (monitor muerto = muestra congelada), así que
  // la edad «hace X» y el aviso de muestra vieja necesitan su propio tic.
  const [, setTic] = useState(0)
  useEffect(() => { const id = setInterval(() => setTic((n) => n + 1), 5000); return () => clearInterval(id) }, [])

  if (!s) return <Cargando />
  if ("error" in s) return <SinConexion causa={s.causa} />
  if ("sin_datos" in s) return <Vacio>Sin datos del monitor de servicios.</Vacio>

  const filas = clasificar(s.servicios)
  const degradados = filas.filter((f) => f.estado === "degradado").length
  const edad = edadMuestraMs(s.t, ahoraServidor())
  const vieja = edad != null && edad > MUESTRA_VIEJA_MS

  return (
    <div className="space-y-4">
      <FranjaMdr />
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <div className={cn("flex flex-wrap items-center gap-x-2 gap-y-1 border-b px-4 py-3 text-sm",
          vieja ? "border-aviso/40 bg-aviso/10" : "border-border")}>
          {vieja ? (
            <>
              <Punto estado="pendiente" />
              <span className="font-medium text-aviso">Sin muestra del monitor desde {edadTexto(edad!)}</span>
              <span className="text-muted-foreground">· lo de abajo es lo último que se supo</span>
              {s.t && <span className="ml-auto text-xs text-muted-foreground">última muestra {horaLocal(s.t)}</span>}
            </>
          ) : (
            <>
              <Punto estado={s.caidos === 0 ? "ok" : "caido"} />
              {s.caidos === 0
                ? <span className="font-medium text-ok">Todos los servicios operativos</span>
                : <span className="font-medium text-critico">{s.caidos} de {s.total} {s.caidos === 1 ? "caído" : "caídos"}</span>}
              {degradados > 0 && <span className="text-muted-foreground">· afecta a {degradados} {degradados === 1 ? "servicio" : "servicios"}</span>}
              <span className="ml-auto text-xs text-muted-foreground">
                {edad == null ? "muestra del monitor sin hora" : `muestra del monitor ${edadTexto(edad)}`}
              </span>
            </>
          )}
        </div>
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Servicio</TableHead><TableHead>Estado</TableHead><TableHead>Relación</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filas.map((f) => (
              <TableRow key={f.nombre} className={cn(f.estado === "caido" && "bg-critico/5")}>
                <TableCell className={cn("font-medium border-l-[3px]",
                  f.estado === "caido" ? "border-l-critico" : f.estado === "degradado" ? "border-l-aviso" : "border-l-transparent")}>
                  {f.nombre}
                </TableCell>
                <TableCell>
                  <span className="inline-flex items-center gap-2">
                    {f.estado === "degradado"
                      ? <span className="inline-block size-2 shrink-0 rounded-full bg-aviso" />
                      : <Punto estado={f.estado === "ok" ? "ok" : "caido"} />}
                    <span className={f.estado === "ok" ? "text-ok" : f.estado === "caido" ? "text-critico" : "text-aviso"}>
                      {f.estado === "ok" ? "operativo" : f.estado === "caido" ? "caído" : "depende de un servicio caído"}
                    </span>
                  </span>
                </TableCell>
                <TableCell className="text-muted-foreground"><Relacion f={f} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
