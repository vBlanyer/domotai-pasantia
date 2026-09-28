import { useCallback } from "react"
import { Toast } from "@base-ui/react/toast"
import type { Tono } from "./toast"

export type Aviso = { title: string; description?: string; type?: Tono }

// Lanza un aviso en la pila del <Toaster>. Va en su propio fichero para que toast.tsx solo
// exporte componentes (fast refresh).
export function useToast() {
  const { add } = Toast.useToastManager()
  return useCallback(
    (a: Aviso) => { add({ title: a.title, description: a.description, type: a.type ?? "info" }) },
    [add],
  )
}
