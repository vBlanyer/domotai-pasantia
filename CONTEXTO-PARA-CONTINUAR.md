# Contexto para continuar (handoff a otro Claude)

> **Para quién es esto:** un agente Claude Code que retoma este proyecto en otra máquina.
> Las memorias del Claude anterior viven en `~/.claude/` (local, **no** viajan por git),
> así que este archivo las suple. Léelo entero antes de tocar nada.

## Qué es el proyecto

Prototipo de **MDR** (Managed Detection & Response) de una pasantía. El MDR **refina** las
alertas de un SIEM (aquí **Wazuh emula el SIEM del cliente**): decide cuáles alertas son
amenazas reales, reduce falsos positivos, **justifica** cada decisión y en las críticas pide
**validación humana**. **NO hace detección primaria** — nunca digas "no detecta"; lo que hace es
triaje inteligente sobre lo que el SIEM ya levantó. Las alertas entran en JSON (podrían venir en
CEF, aún no adaptado). Hay un módulo de **RAG local** y un **justificador LLM** (llama 3.2 1B).

## Estado del repo

- Rama de trabajo: **`main`** (todo el trabajo vive aquí; recién subido a GitHub
  `github.com/vBlanyer/domotai-pasantia`).
- Núcleo del motor: `prototipo/` (Python 3 **solo stdlib** + PyYAML; **sin pip/venv/pytest**,
  se testea con `unittest`). **`prototipo/` NO importa `lab/`** (independencia; respétalo).
- Laboratorio: `lab/` (Containerlab, red del banco de 14 nodos). El escenario insignia es el
  **banco** (`lab/banco/`, `lab/topologias/banco.clab.yml`).
- Visor web: `visor/` (**Vite + React + TypeScript + shadcn-ui + Tailwind v4 + Zod + Vitest +
  Recharts**). Lo sirve el propio daemon con `--web` (lee `visor/dist` por petición).
- Runbook operativo completo: **`COMO-ARRANCAR.md`** (léelo; tiene arranque, pantallas, flags,
  apagado y solución de problemas).

## Lo hecho en la última sesión (ya en `main`)

1. **Rediseño comercial del visor** (sidebar navy, KPIs, gráficos Recharts) + **tema claro/oscuro**
   (interruptor sol/luna, persiste) + fuentes **Inter** (UI) y **Roboto** (títulos).
2. **Panel Equipos = inventario de dispositivos** (`/api/equipos`): los 11 activos que el MDR
   conoce **desde el perfil** (`bancario.yml` `activos:` + `topologia:`), agrupados por categoría
   (servidor/endpoint/gestión/cortafuegos), con criticidad, IP, estado (cruzado con salud) y
   postura de seguridad (incidentes recibidos, amenazas, ataques originados) cruzando la traza.
   Distinto de *Estado de servicios* (las 7 apps de negocio con salud+dependencias). Los 3 nodos
   restantes de los 14 del lab (`internet` sim-exterior, `sw-soc` switch) no son activos del cliente.
3. **Panel Decisiones enriquecido**: filas expandibles que muestran justificación, evidencia,
   **técnicas MITRE**, motivo de impacto y **pasajes del RAG** (traídos de `/api/traza/<id>`, con
   los IDs de pasaje resueltos contra `prototipo/corpus/corpus.jsonl`).
4. **Arreglo del "hay que clicar varias veces"**: `useSondeo` solo re-renderiza si el dato cambió,
   y los gráficos Recharts no se animan en cada sondeo (el reflow se comía los clics).
5. **IP de origen rotativa** en el lanzador de ataques: tecla **`r`** en `sh lab/banco/banco.sh
   atacar`. Cada ataque sale desde una IP nueva de la subred del atacante (alias en `eth1` + `ssh
   -b`), para repetir el mismo caso (p. ej. D1) **sin** chocar con la supresión del MDR ni con el
   bloqueo `iptables` previo, y sin esperar los 60 s.

## Pendientes / cosas a saber para la demo LLM+RAG

- **El texto del LLM no sale por defecto**: `--con-llm` habla con un `llama-server` en
  `127.0.0.1:8080`. Si no está levantado, el generador devuelve `""` y **toda justificación
  degrada a plantilla** (`version_justificador: plantilla-0`). El **RAG sí recupera** igual
  (embeddings aparte). Para texto real del modelo:
  - Rápido para demo: levantar `llama-server -m modelos/llama-3.2-1b-q4.gguf --port 8080` (entorno
    conda `triaje-ml`, binarios en `~/miniforge3/envs/triaje-ml/bin/`).
  - O `export LLAMA_MODO=subproceso` antes de lanzar el daemon (usa `llama-simple` por decisión;
    más lento). Modelos en `modelos/*.gguf` (gitignored; deben existir en la máquina).
- **El RAG solo se consulta en accesos a credenciales** (fuerza bruta SSH); en un FP o
  `no_soportada` el panel dirá, correctamente, "no consultó el RAG". Para verlo, lanza **D1/A1/K1**.
- **Usa una `--salida` nueva por sesión** (p. ej. `--salida trazas-$(date +%F-%H%M).jsonl`): si
  reusas el mismo fichero, los `id_decision` se repiten entre corridas y se ve "cadena rota".

## Gotchas críticos (te van a morder si no los sabes)

- **"No veo nada / no llegan los ataques"**: al reusar/reiniciar contenedores se pierde el
  direccionamiento 10.x del plano de datos. Solución: `sh lab/lab.sh down banco && sh lab/lab.sh
  up banco && sh lab/banco/banco.sh aprovisionar`. Hay que correr **`aprovisionar` tras cada
  `up`** y `export TRIAJE_NODO_GESTION=clab-banco-mdr-siem` antes del daemon.
- **Cambios en `prototipo/*.py` (API, motor) requieren reiniciar el daemon** (el proceso tiene el
  código en memoria). El `visor/dist` en cambio se sirve fresco por petición: basta
  `cd visor && npm run build` y recargar el navegador.
- **Regla 5763 de Wazuh**: se silencia ~60 s tras dispararse. El lanzador `atacar` lo respeta; la
  rotación de IP (`r`) lo esquiva.
- **Supresión**: repetir el mismo `(IP, familia)` no re-pregunta (sale `↩ … ya decidido`);
  desactivable con `--sin-supresion`. Por eso repetir D1 desde la misma IP "no hace nada".
- **El daemon es de un solo hilo**: mientras hay un menú de aprobación abierto, no consume stdin;
  no lances ataques con un prompt pendiente.

## Convenciones del proyecto (respétalas)

- **`main` es local + este repo**. No hagas `push --force`. Fusiona con `--no-ff` solo si te lo piden.
- **No toques**: el plan de trabajo/roadmap, los `.tex` del informe, `informe-evaluacion.md`, ni los
  docs de Fase 1–4 sin pedirlo. La info nueva va al detalle de fases / `estado-y-riesgos`.
- Ataques **solo** en el laboratorio Containerlab aislado (RNF-01). Nunca fuera.
- Commits terminan con: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Tienes las skills de **superpowers** (brainstorming, writing-plans, executing-plans, TDD,
  subagent-driven-development, systematic-debugging) + **frontend-design** + **dataviz**. Úsalas.
  Para el visor, valida paletas con la skill dataviz; el core sigue Python stdlib + TDD `unittest`.

## Cómo verificar que todo está sano (antes de fusionar cualquier cosa)

```bash
# Núcleo Python (motor, banco, dataset, evaluación)
for d in prototipo/tests lab/banco/tests lab/dataset/tests evaluacion/tests; do \
  PYTHONPATH=. python3 -m unittest discover -s "$d" -t . 2>&1 | tail -1; done
# Visor
cd visor && npm install && npx tsc --noEmit && npx vitest run && npm run build
```
En la última corrida verde: Python ~646 tests OK; visor tsc limpio, 11 tests, build OK.
