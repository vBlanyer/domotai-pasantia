import { useState } from "react"
import { rotarClave, type Conectividad as Datos } from "@/api"
import { AlertDialog } from "@/components/ui/alert-dialog"
import { useToast } from "@/components/ui/use-toast"
import { Boton, Capa } from "./ConectividadUi"

// Rotación de la clave del conector en tres fases, sin credenciales de administrador: el usuario del
// conector es dueño de su propio authorized_keys. Mientras dura, el conector ofrece las dos claves.

const PILL = { si: "bg-ok/15 text-ok", no: "bg-critico/15 text-critico", pend: "bg-enrutado/15 text-enrutado" }

export function RotacionClave({ d, onCerrar, onCambio }: { d: Datos; onCerrar: () => void; onCambio: () => void }) {
  const toast = useToast()
  const [ocupado, setOcupado] = useState<string | null>(null)
  const [confirmar, setConfirmar] = useState(false)
  const r = d.rotacion
  const filas = Object.entries(r?.equipos ?? {})
  const listos = filas.filter(([, f]) => f.probada && !f.retirada).length
  const retiradas = filas.filter(([, f]) => f.retirada).length
  const todas = filas.length > 0 && retiradas === filas.length

  async function hacer(accion: Parameters<typeof rotarClave>[0], ok: string) {
    setOcupado(accion)
    const res = await rotarClave(accion)
    setOcupado(null)
    onCambio()
    if (res.status === 200) toast({ type: "success", title: ok })
    else toast({ type: "error", title: "No se pudo", description: String(res.datos.error ?? `HTTP ${res.status}`) + (Array.isArray(res.datos.faltan) ? `: ${(res.datos.faltan as string[]).join(", ")}` : "") })
  }
  const pill = (v: boolean | undefined, si: string, no: string, err?: string | null) =>
    <span className={`rounded px-1.5 text-[11px] font-medium ${v ? PILL.si : err ? PILL.no : PILL.pend}`}>{v ? si : err ?? no}</span>

  return (
    <Capa titulo="Rotar la clave del conector" onCerrar={onCerrar} ancho="max-w-3xl">
      <div className="grid border-b border-border text-[12.5px] sm:grid-cols-3">
        {[["1 · Añadir la nueva", "Se genera el par nuevo en el nodo del conector y su clave pública se añade en cada equipo, junto a la vieja."],
          ["2 · Probar con la nueva", "Cada equipo se prueba entrando solo con la clave nueva."],
          ["3 · Retirar la vieja", "Solo en los equipos que pasaron. Al finalizar, la nueva sustituye a la vieja en el conector."]].map(([t, x]) => (
          <div key={t} className="border-b border-border px-4 py-3 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0"><b className="mb-0.5 block text-[13px]">{t}</b>{x}</div>
        ))}
      </div>
      {!r ? (
        <div className="space-y-3 px-5 py-4 text-[13px]">
          <p>Clave actual del conector: <span className="font-mono text-xs">{d.clave?.huella ?? "—"}</span>.</p>
          <p className="text-muted-foreground">Mientras dura la rotación el conector ofrece las dos claves, así que ningún equipo pierde el acceso. Puedes cancelarla hasta que se retire la vieja en algún equipo.</p>
          <Boton tono="pri" onClick={() => hacer("iniciar", "Par nuevo generado")} disabled={!!ocupado}>{ocupado ? "Generando…" : "Iniciar: generar el par nuevo"}</Boton>
        </div>
      ) : (
        <>
          <p className="px-5 pt-3 text-xs text-muted-foreground">Iniciada {r.iniciada_por ? `por ${r.iniciada_por} ` : ""}· clave nueva <span className="font-mono">{r.huella_nueva}</span></p>
          <table className="mt-2 w-full text-[13px]">
            <thead><tr className="border-y border-border bg-muted text-left text-[11.5px] text-muted-foreground">
              <th className="px-4 py-1.5 font-medium">Equipo</th><th className="px-4 py-1.5 font-medium">Nueva añadida</th>
              <th className="px-4 py-1.5 font-medium">Probada</th><th className="px-4 py-1.5 font-medium">Vieja retirada</th></tr></thead>
            <tbody>{filas.map(([n, f]) => (
              <tr key={n} className="border-b border-border"><td className="px-4 py-1.5">{n}</td>
                <td className="px-4 py-1.5">{pill(f.anadida, "sí", "pendiente", f.anadida === false ? f.error : null)}</td>
                <td className="px-4 py-1.5">{pill(f.probada, "pasa", "pendiente", f.anadida && f.probada === false ? f.error : null)}</td>
                <td className="px-4 py-1.5">{pill(f.retirada, "sí", "pendiente", f.probada && f.retirada === false ? f.error : null)}</td></tr>))}</tbody>
          </table>
          <div className="flex flex-wrap items-center gap-2 px-5 py-3">
            <Boton onClick={() => hacer("preparar", "Clave nueva añadida y probada")} disabled={!!ocupado}>{ocupado === "preparar" ? "Preparando…" : "Añadir y probar en todos"}</Boton>
            <Boton tono="dan" onClick={() => setConfirmar(true)} disabled={!!ocupado || listos === 0}>Retirar la clave vieja en {listos} equipo{listos === 1 ? "" : "s"}…</Boton>
            <Boton tono="pri" onClick={() => hacer("finalizar", "Rotación terminada")} disabled={!!ocupado || !todas}>Finalizar</Boton>
            <span className="ml-auto" />
            <Boton onClick={() => hacer("cancelar", "Rotación cancelada")} disabled={!!ocupado || retiradas > 0}>Cancelar la rotación</Boton>
          </div>
          <p className="px-5 pb-4 text-xs text-muted-foreground">{todas ? "Todos los equipos tienen solo la clave nueva: finaliza para que el conector deje de ofrecer la vieja."
            : `${retiradas} de ${filas.length} equipos ya solo aceptan la nueva. Los que no respondan siguen con la vieja y quedan señalados.`}</p>
        </>
      )}
      <AlertDialog open={confirmar} onOpenChange={(o) => { if (!o) setConfirmar(false) }}
        title={`¿Retirar la clave vieja en ${listos} equipo${listos === 1 ? "" : "s"}?`}
        description="Solo en los que ya entran con la nueva. Después no se podrá cancelar la rotación: habrá que terminarla."
        confirmLabel="Retirar la clave vieja" onConfirm={() => hacer("retirar", "Clave vieja retirada")} />
    </Capa>
  )
}
