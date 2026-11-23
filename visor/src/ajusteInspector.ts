// El panel derecho de cada vista (`.inspector`) acaba siempre en el borde de abajo del área visible: su
// altura máxima es lo que queda visible desde donde EMPIEZA (debajo de las cifras y los filtros, o ya pegado
// arriba tras bajar la página). Así su final se alcanza con su propio scroll, sin bajar la página entera.
import { useEffect, type RefObject } from "react"

export const MARGEN = 12            // px: el `top` del sticky y el respiro de abajo
const MINIMO = 160                  // px: nunca un panel inservible en una ventana muy baja

export function alturaMaxima(topPanel: number, area: { top: number; bottom: number }): number {
  const inicio = Math.max(topPanel, area.top + MARGEN)   // pegado (sticky) no sube más que el margen
  return Math.max(MINIMO, Math.round(area.bottom - inicio - MARGEN))
}

// Solo en pantallas anchas (en móvil el panel va debajo de la lista, sin sticky): ≥ 64rem, como `.inspector`.
const ancho = () => typeof window.matchMedia !== "function" || window.matchMedia("(min-width: 64rem)").matches

export function useAjusteInspectores(area: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const main = area.current
    if (!main) return
    const ajustar = () => {
      const rect = main.getBoundingClientRect()
      for (const el of main.querySelectorAll<HTMLElement>(".inspector")) {
        el.style.maxHeight = ancho() ? `${alturaMaxima(el.getBoundingClientRect().top, rect)}px` : ""
      }
    }
    ajustar()
    main.addEventListener("scroll", ajustar, { passive: true })
    window.addEventListener("resize", ajustar)
    // Al cambiar de vista o de selección aparece otro panel: se ajusta también (solo hijos, no estilos: sin bucle).
    const obs = new MutationObserver(ajustar)
    obs.observe(main, { childList: true, subtree: true })
    return () => { main.removeEventListener("scroll", ajustar); window.removeEventListener("resize", ajustar); obs.disconnect() }
  }, [area])
}
