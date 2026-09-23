import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

type Tema = { oscuro: boolean; alternar: () => void }
const Ctx = createContext<Tema>({ oscuro: false, alternar: () => {} })

function inicial(): boolean {
  try {
    const g = localStorage.getItem("tema")
    if (g) return g === "oscuro"
  } catch { /* almacenamiento bloqueado */ }
  return typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches
}

export function TemaProvider({ children }: { children: ReactNode }) {
  const [oscuro, setOscuro] = useState(inicial)
  useEffect(() => {
    document.documentElement.classList.toggle("dark", oscuro)
    try { localStorage.setItem("tema", oscuro ? "oscuro" : "claro") } catch { /* sin persistencia */ }
  }, [oscuro])
  return <Ctx.Provider value={{ oscuro, alternar: () => setOscuro((v) => !v) }}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useTema = () => useContext(Ctx)
