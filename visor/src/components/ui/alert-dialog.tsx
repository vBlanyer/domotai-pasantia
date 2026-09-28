import { useRef, type ReactNode } from "react"
import { AlertDialog as AlertDialogPrimitive } from "@base-ui/react/alert-dialog"
import { buttonVariants } from "@/components/ui/button"

// Confirmación de una acción con consecuencias: el foco arranca en «Cancelar» para que un Enter
// apresurado no confirme; confirmar ejecuta `onConfirm` y cierra.
export function AlertDialog({
  open, onOpenChange, title, description, children, confirmLabel, cancelLabel = "Cancelar",
  onConfirm, destructive = true,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children?: ReactNode
  confirmLabel: string
  cancelLabel?: string
  onConfirm: () => void
  destructive?: boolean
}) {
  const cancelar = useRef<HTMLButtonElement>(null)
  return (
    <AlertDialogPrimitive.Root open={open} onOpenChange={(o) => onOpenChange(o)}>
      <AlertDialogPrimitive.Portal>
        <AlertDialogPrimitive.Backdrop className="fixed inset-0 z-50 bg-black/50" />
        <AlertDialogPrimitive.Popup initialFocus={cancelar}
          className="fixed top-1/2 left-1/2 z-50 w-[28rem] max-w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-card p-5 text-card-foreground shadow-xl">
          <AlertDialogPrimitive.Title className="text-base font-semibold">{title}</AlertDialogPrimitive.Title>
          {description && (
            <AlertDialogPrimitive.Description className="mt-1.5 text-sm text-muted-foreground">
              {description}
            </AlertDialogPrimitive.Description>
          )}
          {children && <div className="mt-3 text-sm">{children}</div>}
          <div className="mt-5 flex justify-end gap-2">
            <AlertDialogPrimitive.Close ref={cancelar} className={buttonVariants({ variant: "outline" })}>
              {cancelLabel}
            </AlertDialogPrimitive.Close>
            <button type="button" className={buttonVariants({ variant: destructive ? "destructive" : "default" })}
              onClick={() => { onConfirm(); onOpenChange(false) }}>
              {confirmLabel}
            </button>
          </div>
        </AlertDialogPrimitive.Popup>
      </AlertDialogPrimitive.Portal>
    </AlertDialogPrimitive.Root>
  )
}
