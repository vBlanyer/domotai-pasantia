import { TAMANOS } from "@/datos"

// Control de paginación reutilizable para las listas largas (Trazas, Decisiones). Deja elegir el
// tamaño de página (TAMANOS) y pasa de página. La página y el tamaño los gobierna el componente
// padre (useState), separados del dato sondeado para que no se reinicien en cada poll. No muestra
// nada si la lista cabe en la página más pequeña; el prev/siguiente solo aparece con más de una.
export function Paginador({ pagina, paginas, total, tam, onPagina, onTam }: {
  pagina: number; paginas: number; total: number; tam: number
  onPagina: (p: number) => void; onTam: (t: number) => void
}) {
  if (total <= TAMANOS[0]) return null
  return (
    <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-2 text-sm">
      <label className="flex items-center gap-1.5 text-muted-foreground">
        Filas por página
        <select aria-label="Filas por página" value={tam} onChange={(e) => onTam(Number(e.target.value))}
          className="rounded-md border border-border bg-background px-1.5 py-1 text-foreground">
          {TAMANOS.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
      {paginas > 1 && (
        <span className="flex items-center gap-2">
          <button onClick={() => onPagina(pagina - 1)} disabled={pagina <= 1}
            className="rounded-md border border-border px-2.5 py-1 text-foreground enabled:hover:bg-muted disabled:opacity-40">
            Anterior
          </button>
          <span className="tabular-nums text-muted-foreground">Página {pagina} de {paginas}</span>
          <button onClick={() => onPagina(pagina + 1)} disabled={pagina >= paginas}
            className="rounded-md border border-border px-2.5 py-1 text-foreground enabled:hover:bg-muted disabled:opacity-40">
            Siguiente
          </button>
        </span>
      )}
    </div>
  )
}
