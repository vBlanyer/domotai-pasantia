# Visor web React (núcleo) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un SPA React (stack de la empresa) que muestra los 4 paneles del MDR y aprueba contenciones consumiendo la API Python del daemon.

**Architecture:** El núcleo sigue Python; `prototipo/tablero.py` (API stdlib + `LectorWeb`) gana CORS y sirve el build de React. Un proyecto Vite/React/TS en `visor/` consume esa API por sondeo y reemplaza el frontend vanilla. Sin backend Node.

**Tech Stack:** Python 3 stdlib (API), Vite + TypeScript + React + shadcn-ui + Tailwind CSS + Zod + Vitest (visor).

**Spec:** `docs/superpowers/specs/2026-09-23-visor-react-nucleo-design.md`

## Global Constraints

- El **núcleo del prototipo sigue en Python stdlib**; el visor es una pieza aparte en `visor/`. **`prototipo/tablero.py` no importa `lab/`** ni gana dependencias nuevas.
- Sin backend Node, sin Prisma/Postgres, sin OAuth/JWT, sin S3, sin Winston.
- La API liga solo a `127.0.0.1`, **sin auth**. CORS: `Access-Control-Allow-Origin: *` (aceptable por ligar a localhost).
- Commits terminan exactamente en `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Rama `feature/pulido-mdr` (ya creada). **Nunca push.**
- Suites Python que siguen verdes: `prototipo/tests`, `evaluacion/tests`, `lab/dataset/tests`, `lab/banco/tests`. Tests Python con `unittest` (sin pytest).
- `visor/node_modules` y `visor/dist` van a `.gitignore` (no se versionan).
- No se modifican el plan de trabajo, el roadmap, el informe `.tex`, los documentos de Fases 1–4 ni `informe-evaluacion.md`.

## Review Focus

- **API caída / error de red** (spec §7): el cliente `fetch` de `api.ts` debe resolver a un estado de error, no lanzar sin capturar → test en Task 3.
- **Respuesta malformada del API** (spec §5): los esquemas Zod rechazan JSON inválido → test en Task 3.
- **Preflight `OPTIONS`** de `POST /api/aprobar` (spec §4): responde `204` con cabeceras CORS → test en Task 1.
- **`visor/dist` ausente** cuando el daemon sirve (spec R1): `GET /` da `404` claro, no una excepción → test en Task 1.
- **Aprobar un `id` de pendiente caduco/desconocido** (API actual): `409`; el cliente lo trata como no-fatal → test en Task 3 (cliente) sobre el contrato del API.

---

### Task 1: API — CORS, preflight OPTIONS y estáticos por defecto → `visor/dist`

**Files:**
- Modify: `prototipo/tablero.py`
- Test: `prototipo/tests/test_tablero.py`

**Interfaces:**
- Consumes: el `_Manejador`/`crear_servidor` existentes.
- Produces: cada respuesta lleva cabeceras CORS; `OPTIONS <cualquier ruta>` → `204` con CORS; `_DIR_ESTATICOS` por defecto = `<repo>/visor/dist`.

- [ ] **Step 1: Write the failing tests**

```python
# añadir a prototipo/tests/test_tablero.py (dentro de TestServidor o una clase nueva TestCORS)
class TestCORS(unittest.TestCase):
    def _srv(self):
        srv = tablero.crear_servidor(tablero.EstadoTablero(), "/no/existe.jsonl", puerto=0,
                                     estaticos=tempfile.mkdtemp())
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv.server_address[1]

    def test_get_lleva_cabecera_cors(self):
        puerto = self._srv()
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", "/api/pendientes"); r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "*")

    def test_options_preflight_devuelve_204_con_cors(self):
        puerto = self._srv()
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("OPTIONS", "/api/aprobar"); r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 204)
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", r.getheader("Access-Control-Allow-Methods") or "")

    def test_dist_ausente_da_404_claro(self):
        # estáticos apuntando a un dir sin index.html -> GET / responde 404, no una excepción
        srv = tablero.crear_servidor(tablero.EstadoTablero(), "/no/existe.jsonl", puerto=0,
                                     estaticos="/directorio/que/no/existe")
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=3)
        c.request("GET", "/"); r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 404)
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero.TestCORS -v`
Expected: FAIL (sin cabecera CORS; `OPTIONS` no manejado → 501).

- [ ] **Step 3: Implement CORS + OPTIONS + default estáticos**

En `prototipo/tablero.py`:

1) Cambia el default de estáticos (arriba, donde está `_DIR_ESTATICOS`):

```python
_DIR_ESTATICOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "visor", "dist")
```

2) Añade una cabecera CORS a cada respuesta. En `_Manejador`, factoriza el envío de cabeceras añadiendo un helper y llamándolo en `_responder` y `_estatico`:

```python
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()
```

En `_responder`, tras `self.send_response(codigo)` añade `self._cors()`. En `_estatico`, tras `self.send_response(200)` añade `self._cors()` (y en su rama de error, `_responder` ya lo lleva).

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero -v`
Expected: PASS. **Nota:** el test existente `TestEstaticosReales` sirve `prototipo/tablero/`; en la Task 5 se elimina el frontend vanilla y ese test se reapunta a un dir temporal. Por ahora, si `TestEstaticosReales` falla porque cambió el default de estáticos, **ajústalo para pasar `estaticos=` explícito a un dir temporal con un `index.html`** (no dependas del default).

- [ ] **Step 5: Commit**

```bash
git add prototipo/tablero.py prototipo/tests/test_tablero.py
git commit -m "feat(tablero): CORS y preflight OPTIONS; estaticos por defecto a visor/dist

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Andamiaje del proyecto `visor/` (Vite + React + TS + Tailwind + shadcn)

**Files:**
- Create: el proyecto `visor/` (config + `src/` mínimo).
- Modify: `.gitignore`.

**Interfaces:**
- Produces: `cd visor && npm run dev` sirve un SPA; `npm run build` genera `visor/dist/`; `npx tsc --noEmit` limpio; `npx vitest run` disponible.

- [ ] **Step 1: Andamiaje Vite React-TS**

```bash
cd /home/pc/pasantias/domotai-pasantia
npm create vite@latest visor -- --template react-ts
cd visor && npm install
```

- [ ] **Step 2: Tailwind + PostCSS**

```bash
cd /home/pc/pasantias/domotai-pasantia/visor
npm install -D tailwindcss@3 postcss autoprefixer
npx tailwindcss init -p
```

Escribe `visor/tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

Sustituye `visor/src/index.css` por las directivas de Tailwind:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3: shadcn-ui (alias de rutas + init + componentes)**

Añade el alias `@` en `visor/tsconfig.json` (`compilerOptions.baseUrl: "."`, `paths: {"@/*": ["./src/*"]}`) y en `visor/vite.config.ts` (`resolve.alias` con `@` → `./src`, importando `path`). Luego:

```bash
cd /home/pc/pasantias/domotai-pasantia/visor
npx shadcn@latest init -d
npx shadcn@latest add button card table tabs badge
```

Si `init -d` pide algo interactivo, acepta los valores por defecto (estilo "new-york", color base "neutral", CSS variables sí). Verifica que se creó `src/lib/utils.ts` (con `cn`) y `src/components/ui/*`.

- [ ] **Step 4: Vitest**

```bash
cd /home/pc/pasantias/domotai-pasantia/visor
npm install -D vitest
```

Añade a `visor/package.json` los scripts: `"test": "vitest run"`, `"typecheck": "tsc --noEmit"`.

- [ ] **Step 5: Placeholder App + verificación**

Sustituye `visor/src/App.tsx` por un placeholder mínimo que compile y use Tailwind:

```tsx
export default function App() {
  return <div className="p-6 text-lg font-semibold">Tablero MDR (visor)</div>
}
```

Run: `cd visor && npx tsc --noEmit && npm run build`
Expected: `tsc` sin errores y `dist/` generado.

- [ ] **Step 6: .gitignore + commit**

Añade a `.gitignore` (raíz del repo):

```
visor/node_modules
visor/dist
```

```bash
cd /home/pc/pasantias/domotai-pasantia
git add visor .gitignore
git commit -m "feat(visor): andamiaje Vite+React+TS+Tailwind+shadcn

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

(Confirma que `git status` NO incluye `visor/node_modules` ni `visor/dist`.)

---

### Task 3: Cliente API + esquemas Zod + hook de sondeo (`src/api.ts`)

**Files:**
- Create: `visor/src/api.ts`, `visor/src/api.test.ts`

**Interfaces:**
- Consumes: la API Python (`/api/salud`, `/api/decisiones`, `/api/pendientes`, `/api/trazas`, `/api/verificar`, `POST /api/aprobar`).
- Produces: tipos `Salud`, `Decision`, `Pendiente`, `Verificacion`; funciones `getSalud/getDecisiones/getPendientes/getTrazas/verificar/aprobar`; hook `useSondeo`. Todas validan con Zod y devuelven un resultado tolerante a error de red.

- [ ] **Step 1: Write the failing tests** (`visor/src/api.test.ts`)

```ts
import { describe, it, expect } from "vitest"
import { SaludSchema, PendienteSchema, controlesDePendiente } from "./api"

describe("esquemas Zod", () => {
  it("acepta una salud válida", () => {
    const ok = SaludSchema.parse({ t: "x", servicios: [{ nombre: "a", estado: "ok", depende_de: [] }], caidos: 0, total: 1 })
    expect(ok.total).toBe(1)
  })
  it("acepta salud sin datos", () => {
    expect(SaludSchema.parse({ sin_datos: true })).toEqual({ sin_datos: true })
  })
  it("rechaza una salud malformada", () => {
    expect(() => SaludSchema.parse({ servicios: "no-es-lista" })).toThrow()
  })
})

describe("controlesDePendiente", () => {
  it("escalada ofrece aprobar='s' y rechazar=''", () => {
    const c = controlesDePendiente({ id: "1", tipo: "escalada", prompt: "[s/N]", lineas: [] })
    expect(c.map((x) => x.respuesta)).toEqual(["s", ""])
  })
  it("menú ofrece 1 y 2", () => {
    const c = controlesDePendiente({ id: "1", tipo: "menu", prompt: "Elige", lineas: [] })
    expect(c.map((x) => x.respuesta)).toEqual(["1", "2"])
  })
})
```

- [ ] **Step 2: Run to verify fail**

Run: `cd visor && npx vitest run`
Expected: FAIL (no existe `./api`).

- [ ] **Step 3: Implement** (`visor/src/api.ts`)

```ts
import { z } from "zod"
import { useEffect, useState } from "react"

const BASE = (import.meta.env.VITE_API as string) ?? "http://127.0.0.1:8787"

export const ServicioSchema = z.object({ nombre: z.string(), estado: z.string(), depende_de: z.array(z.string()) })
export const SaludSchema = z.union([
  z.object({ sin_datos: z.literal(true) }),
  z.object({ t: z.string().nullable(), servicios: z.array(ServicioSchema), caidos: z.number(), total: z.number() }),
])
export const DecisionSchema = z.object({
  id_decision: z.string().nullable().optional(), timestamp: z.string().nullable().optional(),
  activo: z.string().nullable().optional(), clase: z.string().nullable().optional(),
  accion_final: z.string().nullable().optional(), requiere_humano: z.boolean().nullable().optional(),
  tipo: z.string().optional(), alertas_suprimidas: z.number().optional(),
})
export const PendienteSchema = z.object({
  id: z.string(), tipo: z.string(), prompt: z.string(), lineas: z.array(z.string()),
})
export const VerificacionSchema = z.object({
  ok: z.boolean(), roto_en: z.number().nullable().optional(), motivo: z.string().optional(),
})

export type Salud = z.infer<typeof SaludSchema>
export type Decision = z.infer<typeof DecisionSchema>
export type Pendiente = z.infer<typeof PendienteSchema>
export type Verificacion = z.infer<typeof VerificacionSchema>

async function pedir<T>(ruta: string, esquema: z.ZodType<T>): Promise<T | { error: string }> {
  try {
    const r = await fetch(BASE + ruta)
    return esquema.parse(await r.json())
  } catch (e) {
    return { error: String(e) }
  }
}

export const getSalud = () => pedir("/api/salud", SaludSchema)
export const getDecisiones = () => pedir("/api/decisiones", z.array(DecisionSchema))
export const getPendientes = () => pedir("/api/pendientes", z.array(PendienteSchema))
export const getTrazas = () => pedir("/api/trazas", z.array(DecisionSchema))
export const getVerificacion = () => pedir("/api/verificar", VerificacionSchema)

export async function aprobar(id: string, respuesta: string): Promise<boolean> {
  try {
    const r = await fetch(BASE + "/api/aprobar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, respuesta }),
    })
    return r.ok            // 200 -> true; 409 (pendiente caduca) -> false, no lanza
  } catch { return false }
}

export function controlesDePendiente(p: Pendiente): { etiqueta: string; respuesta: string; variante: "aprobar" | "rechazar" }[] {
  return p.tipo === "escalada"
    ? [{ etiqueta: "Aprobar", respuesta: "s", variante: "aprobar" }, { etiqueta: "Rechazar", respuesta: "", variante: "rechazar" }]
    : [{ etiqueta: "Aprobar (1)", respuesta: "1", variante: "aprobar" }, { etiqueta: "Rechazar (2)", respuesta: "2", variante: "rechazar" }]
}

export function useSondeo<T>(fn: () => Promise<T>, ms = 2000): T | undefined {
  const [v, setV] = useState<T>()
  useEffect(() => {
    let vivo = true
    const tick = async () => { const r = await fn(); if (vivo) setV(r) }
    tick(); const id = setInterval(tick, ms)
    return () => { vivo = false; clearInterval(id) }
  }, [])
  return v
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd visor && npx vitest run && npx tsc --noEmit`
Expected: PASS y typecheck limpio.

- [ ] **Step 5: Commit**

```bash
git add visor/src/api.ts visor/src/api.test.ts
git commit -m "feat(visor): cliente API con esquemas Zod, sondeo y aprobacion

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Los cuatro paneles y el `App`

**Files:**
- Create: `visor/src/components/Salud.tsx`, `Decisiones.tsx`, `Aprobaciones.tsx`, `Trazas.tsx`
- Modify: `visor/src/App.tsx`

**Interfaces:**
- Consumes: `api.ts` (Task 3) y los componentes shadcn en `src/components/ui/*` (Task 2).
- Produces: un SPA con pestañas (Salud/Decisiones/Aprobaciones/Trazas) que sondea y aprueba.

- [ ] **Step 1: Componentes de panel**

`visor/src/components/Salud.tsx` (usa `Table`, `Badge` de shadcn):

```tsx
import { useSondeo, getSalud } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

export function Salud() {
  const s = useSondeo(getSalud)
  if (!s) return <p>cargando…</p>
  if ("error" in s) return <p className="text-red-600">sin conexión con el daemon</p>
  if ("sin_datos" in s) return <p>sin datos del monitor (¿banco levantado?)</p>
  return (
    <div>
      <p className="mb-2">{s.caidos} de {s.total} servicios caídos</p>
      <Table><TableHeader><TableRow><TableHead>Servicio</TableHead><TableHead>Estado</TableHead><TableHead>Depende de</TableHead></TableRow></TableHeader>
        <TableBody>{s.servicios.map((x) => (
          <TableRow key={x.nombre}><TableCell>{x.nombre}</TableCell>
            <TableCell><Badge variant={x.estado === "ok" ? "default" : "destructive"}>{x.estado === "ok" ? "OK" : "CAÍDO"}</Badge></TableCell>
            <TableCell>{x.depende_de.join(", ") || "—"}</TableCell></TableRow>))}
        </TableBody></Table>
    </div>
  )
}
```

`visor/src/components/Decisiones.tsx` y `Trazas.tsx` comparten una tabla del feed. Escribe `Decisiones.tsx`:

```tsx
import { useSondeo, getDecisiones, type Decision } from "@/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export function FilaDecision({ d }: { d: Decision }) {
  if (d.tipo === "actividad_suprimida")
    return <TableRow className="opacity-60"><TableCell colSpan={4}>↩ actividad suprimida (+{d.alertas_suprimidas})</TableCell></TableRow>
  return <TableRow><TableCell>{d.timestamp}</TableCell><TableCell>{d.activo}</TableCell><TableCell>{d.clase}</TableCell><TableCell>{d.accion_final ?? "—"}</TableCell></TableRow>
}

export function Decisiones() {
  const d = useSondeo(getDecisiones)
  if (!d || "error" in d) return <p>{d && "error" in d ? "sin conexión" : "cargando…"}</p>
  if (d.length === 0) return <p>sin decisiones todavía</p>
  return <Table><TableHeader><TableRow><TableHead>Cuándo</TableHead><TableHead>Activo</TableHead><TableHead>Clase</TableHead><TableHead>Acción</TableHead></TableRow></TableHeader>
    <TableBody>{d.map((x, i) => <FilaDecision key={i} d={x} />)}</TableBody></Table>
}
```

`visor/src/components/Trazas.tsx`:

```tsx
import { useState } from "react"
import { useSondeo, getTrazas, getVerificacion } from "@/api"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { FilaDecision } from "./Decisiones"

export function Trazas() {
  const t = useSondeo(getTrazas)
  const [v, setV] = useState<string>("")
  const verificar = async () => { const r = await getVerificacion(); setV("error" in r ? "sin conexión" : r.ok ? "cadena íntegra" : `rota en ${r.roto_en}: ${r.motivo}`) }
  if (!t || "error" in t) return <p>{t && "error" in t ? "sin conexión" : "cargando…"}</p>
  return (<div>
    <p className="mb-2">{v} <Button size="sm" onClick={verificar}>verificar cadena</Button></p>
    <Table><TableHeader><TableRow><TableHead>Cuándo</TableHead><TableHead>Activo</TableHead><TableHead>Clase</TableHead><TableHead>Acción</TableHead></TableRow></TableHeader>
      <TableBody>{t.map((x, i) => <FilaDecision key={i} d={x} />)}</TableBody></Table></div>)
}
```

`visor/src/components/Aprobaciones.tsx`:

```tsx
import { useSondeo, getPendientes, aprobar, controlesDePendiente } from "@/api"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function Aprobaciones() {
  const p = useSondeo(getPendientes)
  if (!p || "error" in p) return <p>{p && "error" in p ? "sin conexión" : "cargando…"}</p>
  if (p.length === 0) return <p>ninguna decisión esperando</p>
  return <div className="space-y-3">{p.map((x) => (
    <Card key={x.id}><CardContent className="pt-4">
      <pre className="bg-muted p-2 rounded text-sm whitespace-pre-wrap">{x.lineas.join("\n")}</pre>
      <p className="my-2">{x.prompt}</p>
      <div className="flex gap-2">{controlesDePendiente(x).map((c) => (
        <Button key={c.etiqueta} variant={c.variante === "rechazar" ? "destructive" : "default"}
          onClick={() => aprobar(x.id, c.respuesta)}>{c.etiqueta}</Button>))}</div>
    </CardContent></Card>))}</div>
}
```

- [ ] **Step 2: `App.tsx` con pestañas**

```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Salud } from "@/components/Salud"
import { Decisiones } from "@/components/Decisiones"
import { Aprobaciones } from "@/components/Aprobaciones"
import { Trazas } from "@/components/Trazas"

export default function App() {
  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-xl font-bold mb-4">Tablero MDR</h1>
      <Tabs defaultValue="salud">
        <TabsList><TabsTrigger value="salud">Salud</TabsTrigger><TabsTrigger value="decisiones">Decisiones</TabsTrigger>
          <TabsTrigger value="aprobaciones">Aprobaciones</TabsTrigger><TabsTrigger value="trazas">Trazas</TabsTrigger></TabsList>
        <TabsContent value="salud"><Salud /></TabsContent>
        <TabsContent value="decisiones"><Decisiones /></TabsContent>
        <TabsContent value="aprobaciones"><Aprobaciones /></TabsContent>
        <TabsContent value="trazas"><Trazas /></TabsContent>
      </Tabs>
    </div>
  )
}
```

- [ ] **Step 3: Verificar typecheck y build**

Run: `cd visor && npx tsc --noEmit && npm run test && npm run build`
Expected: typecheck limpio, Vitest verde, `dist/` generado. Si algún import de shadcn no resuelve, revisa el alias `@` (Task 2, Step 3).

- [ ] **Step 4: Commit**

```bash
git add visor/src
git commit -m "feat(visor): cuatro paneles (salud, decisiones, aprobaciones, trazas)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Integración (servir el build), jubilar el vanilla y docs

**Files:**
- Delete: `prototipo/tablero/` (frontend vanilla)
- Modify: `prototipo/tests/test_tablero.py` (el test de estáticos), `docs/pruebas/09-tablero-web.md`, `documentacion/00-general/estado-y-riesgos.md`

- [ ] **Step 1: Jubilar el frontend vanilla y ajustar su test**

```bash
git rm -r prototipo/tablero
```

En `prototipo/tests/test_tablero.py`, el test `TestEstaticosReales` servía `prototipo/tablero/`. Reapúntalo a un dir temporal con un `index.html` mínimo (ya no depende del frontend vanilla):

```python
def test_sirve_estaticos_de_un_directorio(self):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
        f.write("<html>Tablero MDR</html>")
    srv = tablero.crear_servidor(tablero.EstadoTablero(), "/no/existe.jsonl", puerto=0, estaticos=d)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=3)
    c.request("GET", "/"); r = c.getresponse(); html = r.read(); c.close()
    self.assertEqual(r.status, 200); self.assertIn(b"Tablero", html)
```

- [ ] **Step 2: Verificar suites Python**

Run: `for d in prototipo/tests evaluacion/tests lab/dataset/tests lab/banco/tests; do PYTHONPATH=. python3 -m unittest discover -s $d -t . 2>&1 | tail -1; done`
Expected: `OK` en las cuatro.

- [ ] **Step 3: Verificación de extremo a extremo (manual)**

Con el banco levantado y aprovisionado:
1. `cd visor && npm run build` (genera `dist/`).
2. `docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' | TRIAJE_NODO_GESTION=clab-banco-mdr-siem python3 -m prototipo.stream - prototipo/perfiles/bancario.yml lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --web`
3. Abre `http://127.0.0.1:8787` → el SPA React sirve los 4 paneles; lanza un ataque con `sh lab/banco/banco.sh atacar`, apruébalo/recházalo en **Aprobaciones**, y ve la decisión pasar a **Decisiones** y **Trazas**.
4. (Desarrollo) alternativamente `cd visor && npm run dev` (Vite en :5173) contra el daemon `--web` en :8787 (CORS).

- [ ] **Step 4: Docs**

- `docs/pruebas/09-tablero-web.md`: actualiza a la app React — cómo correrla (`npm run dev` o `npm run build` + `--web`), que la API es la misma, y la nota de que el frontend vanilla se jubiló.
- `documentacion/00-general/estado-y-riesgos.md` (nota D11): la UI v1 pasó a **React** (visor modular con la stack de la empresa contra la API Python); el **doble canal (web+terminal) y el contador en vivo** quedan como iteración de concurrencia futura.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(visor): el daemon sirve el build React; jubila el frontend vanilla; docs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Verificación (plan completo)

1. **Suites Python verdes** (con CORS y el test de estáticos reapuntado), cero regresión.
2. **`visor`:** `npx tsc --noEmit` limpio, `npm run test` (Vitest) verde, `npm run build` genera `dist/`.
3. **Sin dependencias nuevas en el núcleo Python; `tablero.py` no importa `lab/`.** Sin backend Node/Postgres/OAuth/S3/Winston.
4. **Extremo a extremo (manual):** el SPA React muestra los 4 paneles reales y una aprobación desde React ejecuta la contención y pasa a feed/traza, tanto en `npm run dev` como sirviendo `dist/` por `--web`.
5. **Frontend vanilla eliminado**, API y `LectorWeb` conservados.
