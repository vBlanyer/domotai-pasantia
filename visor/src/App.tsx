import { useSondeo, getSalud, getPendientes, getDecisiones } from "@/api"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Salud } from "@/components/Salud"
import { Decisiones } from "@/components/Decisiones"
import { Aprobaciones } from "@/components/Aprobaciones"
import { Trazas } from "@/components/Trazas"
import { Punto } from "@/components/bits"

function Stat({ etiqueta, valor, tono }: { etiqueta: string; valor: string; tono?: string }) {
  return (
    <div className="flex flex-col leading-none">
      <span className={`text-xl font-semibold tabular-nums ${tono ?? ""}`}>{valor}</span>
      <span className="mt-1 text-[11px] text-muted-foreground">{etiqueta}</span>
    </div>
  )
}

export default function App() {
  const salud = useSondeo(getSalud)
  const pend = useSondeo(getPendientes)
  const dec = useSondeo(getDecisiones)

  const conectado = salud !== undefined && !("error" in salud)
  const nPend = Array.isArray(pend) ? pend.length : 0
  const nDec = Array.isArray(dec) ? dec.filter((d) => d.tipo !== "actividad_suprimida").length : 0
  const conSalud = salud && "servicios" in salud
  const sanos = conSalud ? `${salud.total - salud.caidos}/${salud.total}` : "—"
  const saludTono = conSalud ? (salud.caidos ? "text-rose-400" : "text-emerald-400") : ""

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-10 gap-y-4 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="grid size-9 place-items-center rounded-md bg-cyan-500/15 font-bold text-cyan-400">M</div>
            <div>
              <div className="text-sm font-semibold leading-tight">Consola de triaje MDR</div>
              <div className="text-xs text-muted-foreground">refina y contiene las alertas del SIEM</div>
            </div>
          </div>
          <div className="flex items-center gap-10">
            <Stat etiqueta="servicios sanos" valor={sanos} tono={saludTono} />
            <Stat etiqueta="decisiones" valor={String(nDec)} />
            <Stat etiqueta="pendientes" valor={String(nPend)} tono={nPend ? "text-amber-400" : "text-muted-foreground"} />
          </div>
          <div className="ml-auto flex items-center gap-2 text-sm">
            <Punto estado={conectado ? "ok" : "caido"} />
            <span className={conectado ? "text-emerald-400" : "text-rose-400"}>
              {conectado ? "en vivo" : "sin conexión"}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-6">
        <Tabs defaultValue="salud">
          <TabsList>
            <TabsTrigger value="salud">Salud</TabsTrigger>
            <TabsTrigger value="decisiones">Decisiones</TabsTrigger>
            <TabsTrigger value="aprobaciones">
              Aprobaciones
              {nPend > 0 && (
                <span className="ml-1.5 rounded bg-amber-400/20 px-1.5 text-xs font-medium text-amber-300">{nPend}</span>
              )}
            </TabsTrigger>
            <TabsTrigger value="trazas">Trazas</TabsTrigger>
          </TabsList>
          <div className="mt-5">
            <TabsContent value="salud"><Salud /></TabsContent>
            <TabsContent value="decisiones"><Decisiones /></TabsContent>
            <TabsContent value="aprobaciones"><Aprobaciones /></TabsContent>
            <TabsContent value="trazas"><Trazas /></TabsContent>
          </div>
        </Tabs>
      </main>
    </div>
  )
}
