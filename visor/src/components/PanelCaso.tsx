import { useCallback, useEffect, useState } from "react"
import { getCaso, actualizarCaso, operadorActual, type Caso } from "@/api"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"

export const ESTADO_CASO: Record<string, { texto: string; clase: string }> = {
  nuevo: { texto: "Nuevo", clase: "bg-enrutado/15 text-enrutado" },
  en_revision: { texto: "En revisión", clase: "bg-aviso/15 text-aviso" },
  resuelto: { texto: "Resuelto", clase: "bg-ok/15 text-ok" },
}
const ESTADOS = ["nuevo", "en_revision", "resuelto"] as const

const cuando = (iso?: string | null) => {
  const t = iso ? new Date(iso) : null
  return t && !isNaN(t.getTime()) ? t.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : ""
}

// Ciclo de vida del caso: estado, responsable y notas del analista. Cada cambio se añade a la traza
// como registro `actualizacion_caso` encadenado (no muta la decisión); el estado actual se pliega de
// ellos. El `operador` lo sella el backend (del token, no repudio). `idDecision` es la clave del caso:
// `sN`/`dN` para un caso por decisión, o `inc:<prefijo/24>` para un caso a nivel INCIDENTE (misma API).
export function PanelCaso({ idDecision, sinMarco = false }: { idDecision: string; sinMarco?: boolean }) {
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
  const [estado, setEstado] = useState("")          // el elegido y aún sin guardar ("" = sin cambio)
  const [asignado, setAsignado] = useState("")
  const [nota, setNota] = useState("")
  const [guardando, setGuardando] = useState(false)
  const toast = useToast()
  const yo = operadorActual().trim()
  const hayCambio = (!!estado && estado !== estadoActual) || !!asignado.trim() || !!nota.trim()

  async function guardar(extra: { estado?: string } = {}) {
    const est = extra.estado ?? (estado && estado !== estadoActual ? estado : "")
    if ((!est && !asignado.trim() && !nota.trim()) || guardando) return
    setGuardando(true)
    const ok = await actualizarCaso(idDecision, {
      ...(est ? { estado: est } : {}),
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
  const elegido = estado || estadoActual
  const campo = "rounded-[7px] border border-border bg-card px-2.5 py-1 text-[13px] text-foreground outline-none focus:border-ring"
  const notas = [...(caso?.notas ?? [])].reverse()          // la más reciente arriba
  return (
    <div className={cn("space-y-3 text-sm", !sinMarco && "rounded-lg border border-border bg-card p-4")}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-heading text-sm font-semibold">Caso</span>
        <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium", badge.clase)}>{badge.texto}</span>
        <span className="text-xs text-muted-foreground">{caso?.asignado ? `· lo lleva ${caso.asignado}` : "· sin asignar"}</span>
      </div>

      <div className="grid grid-cols-[92px_1fr] items-center gap-x-2.5 gap-y-2">
        <span className="text-muted-foreground">Estado</span>
        <div role="group" aria-label="Cambiar estado del caso" className="inline-flex w-fit gap-0.5 rounded-[8px] border border-border bg-muted p-0.5">
          {ESTADOS.map((e) => (
            <button key={e} type="button" aria-pressed={elegido === e} onClick={() => setEstado(e === estadoActual ? "" : e)}
              className={cn("rounded-[6px] px-2.5 py-0.5 text-[12.5px]", elegido === e ? "bg-card font-medium shadow-sm" : "text-muted-foreground hover:text-foreground",
                elegido === e && ESTADO_CASO[e].clase.split(" ").find((c) => c.startsWith("text-")))}>
              {ESTADO_CASO[e].texto}
            </button>
          ))}
        </div>
        <span className="text-muted-foreground">Responsable</span>
        <div className="flex flex-wrap items-center gap-2">
          <input value={asignado} onChange={(e) => setAsignado(e.target.value)} placeholder={caso?.asignado ?? "asignar a…"}
            className={cn(campo, "w-40")} aria-label="Asignar el caso a un analista" />
          {yo && caso?.asignado !== yo && (
            <button type="button" onClick={() => setAsignado(yo)} className="text-xs font-medium text-info hover:underline">asignarme</button>
          )}
        </div>
        <span className="self-start pt-1 text-muted-foreground">Nota</span>
        <textarea value={nota} onChange={(e) => setNota(e.target.value)} rows={2} placeholder="Añadir una nota al caso…"
          className={cn(campo, "w-full resize-y")} aria-label="Nota del analista" />
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => guardar()} disabled={!hayCambio || guardando}
          className="inline-flex h-8 items-center rounded-[8px] border border-primary bg-primary px-3 text-[13px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-45">
          {guardando ? "Guardando…" : "Guardar en el caso"}
        </button>
        {estadoActual !== "resuelto" && (
          <button type="button" onClick={() => guardar({ estado: "resuelto" })} disabled={!nota.trim() || guardando}
            title={nota.trim() ? undefined : "Escribe en la nota el motivo del cierre"}
            className="inline-flex h-8 items-center rounded-[8px] border border-border bg-card px-3 text-[13px] font-medium hover:bg-muted disabled:opacity-45">
            Resolver con esta nota
          </button>
        )}
      </div>

      {notas.length > 0 && (
        <ul className="space-y-1.5">
          {notas.map((n, i) => (
            <li key={i} className="rounded-r-md border-l-[3px] border-border bg-muted px-2.5 py-1.5 text-[12.5px]">
              {n.texto}
              <div className="text-[11px] text-muted-foreground">{n.operador || "—"}{n.decidido_en ? ` · ${cuando(n.decidido_en)}` : ""}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
