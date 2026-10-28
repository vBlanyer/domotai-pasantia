import { useCallback, useEffect, useState } from "react"
import { getCaso, actualizarCaso, type Caso } from "@/api"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"

export const ESTADO_CASO: Record<string, { texto: string; clase: string }> = {
  nuevo: { texto: "Nuevo", clase: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  en_revision: { texto: "En revisión", clase: "bg-sky-500/15 text-sky-700 dark:text-sky-300" },
  resuelto: { texto: "Resuelto", clase: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
}

// Ciclo de vida del caso: estado, responsable y notas del analista. Cada cambio se añade a la traza
// como registro `actualizacion_caso` encadenado (no muta la decisión); el estado actual se pliega de
// ellos. El `operador` lo sella el backend (del token, no repudio). `idDecision` es la clave del caso:
// `sN`/`dN` para un caso por decisión, o `inc:<prefijo/24>` para un caso a nivel INCIDENTE (misma API).
export function PanelCaso({ idDecision }: { idDecision: string }) {
  // El caso llega YA plegado del servidor (GET /api/caso/<id>, sobre el fichero completo): no
  // «rejuvenece» al salir de la ventana de /api/trazas ni descarga la traza entera (A4). Se recarga
  // al guardar, para que el analista vea su cambio al instante, y cada 10 s por si otro lo cambia.
  const [caso, setCaso] = useState<Caso | null>(null)
  const recargar = useCallback(async () => {
    const r = await getCaso(idDecision)
    if (!("error" in r)) setCaso(r)
  }, [idDecision])
  useEffect(() => {
    setCaso(null)
    recargar()
    const t = setInterval(recargar, 10000)
    return () => clearInterval(t)
  }, [recargar])
  const estadoActual = caso?.estado ?? "nuevo"
  const [estado, setEstado] = useState("")
  const [asignado, setAsignado] = useState("")
  const [nota, setNota] = useState("")
  const [guardando, setGuardando] = useState(false)
  const toast = useToast()
  const hayCambio = !!estado || !!asignado.trim() || !!nota.trim()

  async function guardar() {
    if (!hayCambio || guardando) return
    setGuardando(true)
    const ok = await actualizarCaso(idDecision, {
      ...(estado ? { estado } : {}),
      ...(asignado.trim() ? { asignado: asignado.trim() } : {}),
      ...(nota.trim() ? { nota: nota.trim() } : {}),
    })
    setGuardando(false)
    if (ok) {
      setEstado(""); setAsignado(""); setNota("")
      recargar()   // el panel refleja el cambio al instante (sin esperar al sondeo: parecería fallido)
      toast({ type: "success", title: "Caso actualizado", description: "Queda anotado en la traza." })
    }
    else toast({ type: "error", title: "No se pudo actualizar el caso", description: "Revisa la conexión o el token de la consola." })
  }

  const badge = ESTADO_CASO[estadoActual] ?? ESTADO_CASO.nuevo
  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-heading text-sm font-semibold">Caso</span>
        <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${badge.clase}`}>{badge.texto}</span>
        {caso?.asignado && <span className="text-xs text-muted-foreground">· asignado a {caso.asignado}</span>}
      </div>

      {!!caso?.notas?.length && (
        <ul className="space-y-1.5">
          {caso.notas.map((n, i) => (
            <li key={i} className="rounded-md border border-border bg-muted px-2.5 py-1.5 text-xs">
              <span className="text-muted-foreground">{n.operador || "—"}{n.decidido_en ? ` · ${n.decidido_en.slice(0, 16).replace("T", " ")}` : ""}:</span>{" "}
              {n.texto}
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2 border-t border-border pt-3">
        <div className="flex flex-wrap items-center gap-2">
          <select value={estado} onChange={(e) => setEstado(e.target.value)}
            className="rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground"
            aria-label="Cambiar estado del caso">
            <option value="">— estado —</option>
            <option value="en_revision">En revisión</option>
            <option value="resuelto">Resuelto</option>
            <option value="nuevo">Reabrir (nuevo)</option>
          </select>
          <input value={asignado} onChange={(e) => setAsignado(e.target.value)} placeholder="asignar a…"
            className="w-36 rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground"
            aria-label="Asignar el caso a un analista" />
        </div>
        <textarea value={nota} onChange={(e) => setNota(e.target.value)} rows={2} placeholder="Añadir una nota…"
          className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground"
          aria-label="Nota del analista" />
        <Button onClick={guardar} disabled={!hayCambio || guardando}>
          {guardando ? "Guardando…" : "Guardar en el caso"}
        </Button>
      </div>
    </div>
  )
}
