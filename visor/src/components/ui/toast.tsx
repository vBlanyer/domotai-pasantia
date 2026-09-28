import type { ReactNode } from "react"
import { Toast } from "@base-ui/react/toast"
import { cva } from "class-variance-authority"
import { CircleAlert, CircleCheck, Info, X } from "lucide-react"
import { cn } from "cn"

export type Tono = "success" | "error" | "info"

const toastVariants = cva(
  "pointer-events-auto flex w-full items-start gap-2.5 rounded-lg border bg-card p-3 text-sm text-card-foreground shadow-lg",
  {
    variants: {
      tono: {
        success: "border-emerald-500/40",
        error: "border-rose-500/50",
        info: "border-border",
      },
    },
    defaultVariants: { tono: "info" },
  },
)

const ICONO = { success: CircleCheck, error: CircleAlert, info: Info }
const COLOR_ICONO = { success: "text-emerald-500", error: "text-rose-500", info: "text-muted-foreground" }

function tonoDe(type?: string): Tono {
  return type === "success" || type === "error" ? type : "info"
}

// Los avisos vivos: cada uno con su icono de tono (no solo color) y un botón para descartarlo.
function ListaAvisos() {
  const { toasts } = Toast.useToastManager()
  return toasts.map((t) => {
    const tono = tonoDe(t.type)
    const Icono = ICONO[tono]
    return (
      <Toast.Root key={t.id} toast={t} data-tono={tono} className={toastVariants({ tono })}>
        <Icono className={cn("mt-0.5 size-4 shrink-0", COLOR_ICONO[tono])} aria-hidden />
        <Toast.Content className="min-w-0 flex-1">
          <Toast.Title className="font-medium" />
          <Toast.Description className="mt-0.5 text-muted-foreground" />
        </Toast.Content>
        <Toast.Close aria-label="Cerrar aviso"
          className="shrink-0 rounded p-0.5 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50">
          <X className="size-4" />
        </Toast.Close>
      </Toast.Root>
    )
  })
}

// Proveedor de avisos: envuelve la app y pinta la pila abajo a la derecha. Los avisos se lanzan
// con `useToast()` (use-toast.ts).
export function Toaster({ children }: { children: ReactNode }) {
  return (
    <Toast.Provider timeout={5000} limit={4}>
      {children}
      <Toast.Portal>
        <Toast.Viewport aria-label="Avisos"
          className="fixed right-4 bottom-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
          <ListaAvisos />
        </Toast.Viewport>
      </Toast.Portal>
    </Toast.Provider>
  )
}
