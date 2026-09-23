# Visor web React (núcleo) — diseño

**Fecha:** 23/09/2026 · **Estado:** diseño; pendiente de revisión antes del plan.

**Contexto.** El prototipo tiene hoy un visor web mínimo embebido (`prototipo/tablero.py` sirve HTML/JS/CSS
vanilla + una API JSON stdlib; el daemon lo levanta con `stream.py --web`). Se decidió (sesión 23/09) que el
**visor debe ser una pieza modular aparte**, con la **stack web de la empresa**, fácil de integrar a una web
local — mientras el **núcleo del prototipo sigue siendo Python** y expone su salida por una API. Esta es la
primera iteración, **B-núcleo**: reemplazar el frontend vanilla por un SPA React que consume la **misma API
Python** (ampliada con CORS). La concurrencia (doble canal web+terminal, contador en vivo) queda para una
iteración posterior, porque exige reestructurar el lazo de un solo hilo del daemon.

**Objetivo.** Un SPA **React** (stack de la empresa) que muestra los cuatro paneles —salud de servicios, feed
de decisiones, cola de aprobaciones y explorador de trazas con verificación— y permite **aprobar/rechazar**
una contención, **consumiendo la API Python del daemon** (`prototipo/tablero.py`), sin backend Node.

## 1. Alcance

**Dentro (B-núcleo):**
- SPA en `visor/`: **Vite + TypeScript + React + shadcn-ui + Tailwind CSS + Zod**.
- Los cuatro paneles, consumiendo la API existente por sondeo (~2 s).
- **Aprobación por web** reusando el puente actual (`LectorWeb` bloqueante) vía `POST /api/aprobar`.
- La API Python gana **CORS** (y respuesta a *preflight* `OPTIONS`) para que el SPA la consuma en desarrollo.
- **Modo demo/producción:** `npm run build` genera `visor/dist/`; el daemon `--web` **sirve ese build** (el
  servidor apunta sus estáticos a `visor/dist`), jubilando el frontend vanilla `prototipo/tablero/`.

**Fuera (iteración siguiente, documentado):**
- **Doble canal (web + terminal)** y **contador en vivo** sobre una decisión pendiente — exigen un hilo lector
  concurrente en el daemon (hoy de un solo hilo). Se anota como trabajo futuro.
- Cola de pendientes con priorización *fina* más allá del **orden que A ya impone** (el daemon procesa los
  incidentes por severidad, así que las pendientes ya se registran en ese orden; el visor las muestra en ese
  orden sin lógica extra).
- Autenticación/OAuth, Postgres/Prisma, S3, Winston, backend Node — **descartados** para este caso.

## 2. Decisiones fijadas (de la sesión)

- **Frontend:** Vite + TS + React + shadcn-ui + Tailwind + Zod. **Sin** Prisma/Postgres, OAuth/JWT, S3, Winston,
  ni backend Node.
- **Backend = el prototipo Python.** El SPA habla **directo** con la API del daemon (`prototipo/tablero.py`),
  ampliada con CORS. No se añade servicio Node.
- **Seguridad:** la API sigue ligada a `127.0.0.1`, **sin auth** (etapa inicial). CORS abierto a localhost.
- **El SPA reemplaza el frontend vanilla**, pero **conserva** la API `tablero.py` y el puente `LectorWeb`.

## 3. Arquitectura

```
 navegador ──HTTP/JSON──> prototipo/tablero.py (ThreadingHTTPServer 127.0.0.1:8787, API + CORS)
   (visor/ React)              └── EstadoTablero (pendientes) · lee salud.jsonl · lee la traza
 stream.py --web ── embebe el servidor en un hilo del daemon (LectorWeb = aprobación web)
```

- **`visor/`** (nuevo, raíz): la app React. En **desarrollo** corre con `npm run dev` (Vite en `:5173`) y llama
  a la API en `127.0.0.1:8787` (CORS lo permite). En **demo**, `npm run build` → `visor/dist/`, y el daemon
  `--web` sirve ese `dist/` (mismo servidor, misma API), así que la demo no necesita Node corriendo.
- **`prototipo/tablero.py`** (modificado): (a) añade cabeceras **CORS** a cada respuesta (`Access-Control-Allow-
  Origin`, `-Methods`, `-Headers`) y responde a **`OPTIONS`** (preflight de `POST /api/aprobar`); (b) el
  `_DIR_ESTATICOS` por defecto pasa a `visor/dist` (con reserva clara si no existe el build); (c) sin cambios en
  los endpoints ni en `EstadoTablero`/`LectorWeb`.
- **`prototipo/tablero/` (vanilla)** se elimina; su API y el puente de aprobación permanecen en `tablero.py`.

## 4. API (sin endpoints nuevos; solo CORS)

Los endpoints ya existen y bastan: `GET /api/salud`, `/api/decisiones`, `/api/pendientes`, `/api/trazas`,
`/api/traza/<id>`, `/api/verificar`, `POST /api/aprobar`. El feed y las trazas ya incluyen los registros
`actividad_suprimida` de la memoria de decisiones (A), así que el visor muestra la supresión sin trabajo extra.

**CORS (lo único nuevo en la API):**
- Cada respuesta lleva `Access-Control-Allow-Origin: *` (aceptable: liga solo a `127.0.0.1`), `Access-Control-
  Allow-Methods: GET, POST, OPTIONS`, `Access-Control-Allow-Headers: Content-Type`.
- `OPTIONS` en cualquier ruta responde `204` con esas cabeceras (preflight).

## 5. Frontend (`visor/`)

- **Estructura:** proyecto Vite React-TS estándar: `package.json`, `vite.config.ts`, `tsconfig*.json`,
  `index.html`, `tailwind.config.js`, `postcss.config.js`, `components.json` (shadcn), `src/`.
- **`src/api.ts`:** un cliente `fetch` con la base configurable (`VITE_API` con defecto `http://127.0.0.1:8787`)
  y **esquemas Zod** que validan cada respuesta (salud, decisión/traza, pendiente, verificación). Un hook
  `useSondeo(fn, ms=2000)` que refresca.
- **Componentes (shadcn + Tailwind):** un layout con pestañas/tarjetas:
  - `Salud`: tabla de servicios verde/rojo con dependencias y «caídos/total».
  - `Decisiones`: tabla del feed (incluye filas `actividad_suprimida`, marcadas).
  - `Aprobaciones`: una `Card` por pendiente con las líneas capturadas (`<pre>`) y botones **Aprobar/Rechazar**
    (escalada `[s/N]` → `s`/``; menú → opciones), que hacen `POST /api/aprobar`.
  - `Trazas`: lista → detalle (registro completo) + botón **verificar cadena**.
- **shadcn-ui:** se inicializa con su CLI; se usan componentes básicos (Card, Table, Button, Tabs, Badge). Tema
  con soporte claro/oscuro por defecto de shadcn.

## 6. Pruebas

- **Frontend:** *typecheck* con `tsc --noEmit` como puerta mínima; **Vitest** para lo puro y frágil: los
  **esquemas Zod** (parsean una respuesta válida, rechazan una inválida) y el mapeo pendiente→controles
  (escalada vs menú). Sin tests de render pesados (YAGNI para la v1).
- **API (Python):** ampliar `prototipo/tests/test_tablero.py` — una petición `OPTIONS` devuelve `204` con
  cabeceras CORS; una respuesta `GET` lleva `Access-Control-Allow-Origin`. Las suites Python siguen verdes.
- **Extremo a extremo (manual):** `npm run dev` + daemon `--web`; lanzar un ataque (con `banco.sh atacar`), ver
  la decisión en Aprobaciones, aprobar/rechazar, verla pasar al feed y a la traza; y `npm run build` + `--web`
  sirviendo `dist/`.

## 7. Errores y seguridad

- Sin daemon / API caída: el SPA muestra un estado «sin conexión con el daemon», no rompe.
- Endpoints que degradan a vacío/`sin_datos` (ya en la API) se muestran como estados vacíos.
- `127.0.0.1` + sin auth por diseño (igual que hoy); CORS abierto es aceptable porque el servidor no escucha
  fuera de localhost. Un clic de aprobación ejecuta `iptables` real (igual que hoy) — auditable en la traza.

## 8. Riesgos y notas honestas

- **R1 · Toolchain Node/npm** entra en el proyecto (antes Python puro). Solo afecta a `visor/` (pieza aparte);
  el núcleo sigue Python. `visor/dist` es artefacto de build (git-ignored); el daemon sirve `dist/` si existe y,
  si no, avisa de correr `npm run build`.
- **R2 · Sin concurrencia:** la aprobación por web sigue **bloqueando** el lazo (un hilo). El doble canal y el
  contador en vivo quedan para la iteración de concurrencia (documentado).
- **R3 · CORS `*`** es seguro aquí solo porque el servidor liga a `127.0.0.1`; si algún día se expone en red,
  hay que cerrar CORS y añadir auth (ya listado como futuro).

## 9. Ficheros

- **Crear:** el proyecto `visor/` (config Vite/TS/Tailwind/shadcn + `src/` con `api.ts`, esquemas Zod,
  componentes y `App.tsx`), y sus pruebas Vitest.
- **Modificar:** `prototipo/tablero.py` (CORS + `OPTIONS` + `_DIR_ESTATICOS` → `visor/dist`);
  `prototipo/tests/test_tablero.py` (CORS). `.gitignore` (`visor/dist`, `visor/node_modules`).
- **Eliminar:** `prototipo/tablero/` (frontend vanilla) — la API y `LectorWeb` se quedan en `tablero.py`.
- **Docs:** `docs/pruebas/09-tablero-web.md` (actualizar a la app React y cómo correrla/construirla); nota en
  `estado-y-riesgos` de que la UI v1 pasó a React y que la concurrencia (doble canal/contador en vivo) es futuro.

## 10. Criterios de éxito

- `cd visor && npm install && npm run dev` levanta el SPA; con el daemon `--web` y el banco arriba, los cuatro
  paneles muestran datos reales y una aprobación desde React ejecuta la contención y pasa a feed/traza.
- `npm run build` + `stream.py --web` sirve `visor/dist/` sin Node corriendo.
- `tsc --noEmit` limpio; Vitest de esquemas en verde; las suites Python en verde (incluida la de CORS).
- Sin backend Node, sin Postgres/OAuth/S3/Winston. El núcleo sigue Python.
