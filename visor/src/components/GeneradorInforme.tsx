import { useState } from "react"
import { FileText } from "lucide-react"
import type { Metricas } from "@/api"
import { etiquetaPeriodo, nombreArchivo } from "@/informe"
import { SECCIONES, datosInforme, type DatosInforme, type Seccion } from "@/informeDatos"
import { VistaPreviaInforme } from "./InformeDocumento"

// Generador del informe en PDF: elige qué entra, para quién va y abre la vista previa paginada.
// En vivo no se exporta: un informe es de un periodo cerrado. Los datos extra (periodo anterior,
// verificación de la cadena y la traza del periodo) se piden solo al abrir la vista previa.

const PARA_KEY = "mdr.informe.para"
const leerPara = () => { try { return localStorage.getItem(PARA_KEY) ?? "" } catch { return "" } }
const guardarPara = (v: string) => { try { localStorage.setItem(PARA_KEY, v) } catch { /* modo privado */ } }

export function GeneradorInforme({ m, desde, hasta, enVivo }: { m: Metricas | null; desde: string; hasta: string; enVivo: boolean }) {
  const [secciones, setSecciones] = useState(() => new Set(SECCIONES.filter((s) => s.defecto).map((s) => s.id)))
  const [para, setPara] = useState(leerPara)
  const [cargando, setCargando] = useState(false)
  const [doc, setDoc] = useState<DatosInforme | null>(null)
  const alternar = (id: Seccion) => setSecciones((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const listo = !enVivo && !!m && secciones.size > 0
  const abrir = async () => {
    if (!m || !listo) return
    setCargando(true)
    try { setDoc(await datosInforme(m, desde, hasta, para.trim(), secciones)) } finally { setCargando(false) }
  }
  return (
    <section aria-label="Informe en PDF" className="grid gap-5 rounded-xl border border-border bg-card p-4 md:grid-cols-[1fr_1.4fr_1fr] print:hidden">
      <div className="space-y-1.5">
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Informe en PDF</div>
        <p className="text-sm">{enVivo ? "Elige «Este mes», «Este año» o un rango para exportarlo." : <>{etiquetaPeriodo(desde, hasta)}{m && <> · {m.total.toLocaleString("es")} decisiones</>}</>}</p>
        <p className="text-xs text-muted-foreground">El modo en vivo no se exporta: un informe es de un periodo cerrado.</p>
      </div>
      <fieldset className="space-y-1.5">
        <legend className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">Qué incluir</legend>
        <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
          {SECCIONES.map((s) => (
            <label key={s.id} className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="accent-primary" checked={secciones.has(s.id)} onChange={() => alternar(s.id)} />{s.nombre}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="space-y-1.5">
        <label className="block text-xs font-medium uppercase tracking-wide text-muted-foreground" htmlFor="informe-para">Para</label>
        <input id="informe-para" value={para} placeholder="Cliente · área destinataria"
          onChange={(e) => { setPara(e.target.value); guardarPara(e.target.value) }}
          className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm" />
        <div className="pt-1 text-xs text-muted-foreground">Se guardará como</div>
        <div className="font-mono text-xs">{enVivo ? "—" : `${nombreArchivo(desde, hasta)}.pdf`}</div>
        <button type="button" onClick={abrir} disabled={!listo || cargando}
          className="mt-1.5 flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50">
          <FileText className="size-4" /> {cargando ? "Preparando…" : "Vista previa del PDF"}
        </button>
      </div>
      {doc && <VistaPreviaInforme d={doc} onCerrar={() => setDoc(null)} />}
    </section>
  )
}
