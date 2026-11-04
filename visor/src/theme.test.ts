/// <reference types="node" />   // tsconfig.app.json solo trae vite/client; este test lee index.css con fs
import { describe, it, expect } from "vitest"
import { readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { semantico, ejes, tooltipEstilos } from "./theme"

// theme.ts lleva los hex en TS porque Recharts no acepta var() en atributos SVG. Este test es el
// candado: si alguien retoca un token en index.css y no en theme.ts (o al revés), rompe aquí.
// Se lee con fs (no `?raw` ni `new URL(…, import.meta.url)`: Vitest deja el CSS vacío y Vite
// reescribe ese `new URL` como asset).
const css = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "index.css"), "utf8")

// Variables con valor hex declaradas en TODOS los bloques `selector { … }` de index.css
// (`:root, .dark {` de impresión no cuenta: el selector debe abrir la línea o ir tras `{`/`}`).
function tokens(selector: string): Record<string, string> {
  const out: Record<string, string> = {}
  const re = new RegExp(`(?:^|[{}])\\s*${selector.replace(".", "\\.")}\\s*\\{([^}]*)\\}`, "gm")
  for (const m of css.matchAll(re))
    for (const t of m[1].matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\b/g)) out[t[1]] = t[2].toLowerCase()
  return out
}
const claro = tokens(":root"), oscuro = tokens(".dark")
const SEM = ["ok", "aviso", "grave", "critico", "enrutado", "violeta"] as const

describe("theme.ts lee de la misma paleta que index.css", () => {
  it("cada token semántico existe en ambos modos", () => {
    for (const k of SEM) {
      expect(claro[k], `--${k} (claro)`).toMatch(/^#/)
      expect(oscuro[k], `--${k} (oscuro)`).toMatch(/^#/)
    }
  })
  it("los colores semánticos de los gráficos son los tokens --ok/--aviso/… en claro y en oscuro", () => {
    for (const k of SEM) {
      expect(semantico(false)[k], `--${k} claro`).toBe(claro[k])
      expect(semantico(true)[k], `--${k} oscuro`).toBe(oscuro[k])
    }
  })
  it("rejilla, texto de ejes, relleno, serie y tooltip usan borde, texto atenuado, acento, primario y tarjeta del tema", () => {
    for (const [osc, t] of [[false, claro], [true, oscuro]] as const) {
      const e = ejes(osc)
      expect(e.grid).toBe(t.border)
      expect(e.texto).toBe(t["muted-foreground"])
      expect(e.relleno).toBe(t.accent)
      expect(e.serie).toBe(t.primary)
      expect(tooltipEstilos(osc).contentStyle.backgroundColor).toBe(t.card)
    }
  })
})
