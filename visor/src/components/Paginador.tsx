// Control de paginación reutilizable para las listas largas (Trazas, Decisiones). No renderiza nada
// si hay una sola página. La página la gobierna el componente padre (useState), separada del dato
// sondeado para que no se reinicie en cada poll.
export function Paginador({ pagina, paginas, onPagina }: {
  pagina: number; paginas: number; onPagina: (p: number) => void
}) {
  if (paginas <= 1) return null
  return (
    <div className="flex items-center justify-end gap-2 text-sm">
      <button onClick={() => onPagina(pagina - 1)} disabled={pagina <= 1}
        className="rounded-md border border-border px-2.5 py-1 text-foreground enabled:hover:bg-muted disabled:opacity-40">
        Anterior
      </button>
      <span className="tabular-nums text-muted-foreground">Página {pagina} de {paginas}</span>
      <button onClick={() => onPagina(pagina + 1)} disabled={pagina >= paginas}
        className="rounded-md border border-border px-2.5 py-1 text-foreground enabled:hover:bg-muted disabled:opacity-40">
        Siguiente
      </button>
    </div>
  )
}
