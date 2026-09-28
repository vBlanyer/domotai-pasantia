# Matriz de trazabilidad — requisito ↔ origen ↔ implementación

Vista de un vistazo para la entrega. Complementa a [`requisitos.md`](./requisitos.md) (que lleva el
enunciado, el origen y el estado de cada requisito) con dos cosas que allí están dispersas: **en qué
módulo del prototipo se implementa cada requisito**, y el **mapeo inverso** desde las limitaciones
(L1–L5) y restricciones (C1–C6) del [modelo de cliente genérico](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md)
hacia los requisitos que las materializan.

**Estado:** ✔ cumplido · ~ cumplido con matiz · **+** añadido tras el análisis original · ⏳ trabajo futuro.

---

## 1. Requisitos funcionales → implementación

| RF | Implementa en | Estado |
|----|---------------|--------|
| RF-01 | `prototipo/ingesta.py` (+ `adaptador_wazuh.py`) | ✔ |
| RF-02 | `analisis.enriquecer` + `prototipo/postura.py` | ~ (sin histórico de SOC) |
| RF-03 | `prototipo/analisis.py` + `familias.yml` + `arbol.py` | ~ (4/6 clases; límite de datos) |
| RF-04 | `analisis._priorizar` (criticidad, V4) | ~ (granularidad a afinar) |
| RF-05 | `traza.py` (`justificacion_estructurada`) + `justificador_llm.py` + `rag.py` | ✔ |
| RF-06 | `prototipo/analisis.py` (confianza) | ✔ |
| RF-07 | `prototipo/perfil.py` (`continuidad.umbral_confianza`) | ~ (calibración pendiente) |
| RF-08 | `prototipo/lazo.py` (aprobar / rechazar / reclasificar) | ✔ |
| RF-09 | `prototipo/traza.py` (`version_justificador`, cadena de hashes) | ✔ |
| RF-10 | `prototipo/familias.py` + perímetro (`no_soportada`) | ✔ |
| RF-11 | `prototipo/agrupacion.py` | ✔ |
| RF-12 | `traza.py` (feedback persistido) → [bucle de feedback](../00-general/bucle-de-feedback-rf12.md) | ✔ |
| RF-13 | `prototipo/stream.py` + `traza.py` (traza JSONL = interfaz de salida) | ~ (push a producción = futuro) |
| RF-14 | `evaluacion/` (campaña vs baseline) | ✔ |
| RF-15 | `prototipo/catalogo.py` + conector (catálogo cerrado) | **+** |
| RF-16 | `ingesta.py` / `adaptador_wazuh.py` (activo sin agente) | **+** |
| RF-17 | `prototipo/impacto.py` (`impacto.determinar`) + `actores.py` | **+** |
| RF-18 | catálogo (reversibilidad) + `prototipo/revertir.py` | **+** |
| RF-19 | `perfil.filtrar` (veto duro sobre `ip_gestion`) | **+** |
| RF-20 | `evaluacion/` (métricas de continuidad) | **+** |

## 2. Requisitos no funcionales → implementación

| RNF | Implementa en | Estado |
|-----|---------------|--------|
| RNF-01 | ejecución local (`justificador_llm.py` por subprocess; sin salida externa) | ✔ |
| RNF-02 | `rag.py` / `justificador_llm.py` (anclaje: `verificar_anclaje`) | ✔ |
| RNF-03 | temperatura 0 + `version_justificador` en `traza.py` | ✔ |
| RNF-04 | `llama-server` residente (`justificador_llm.py`) | ~ (subproceso ~14–36 s; residente lo elimina) |
| RNF-05 | verificado (hardware; `lab/docs/mediciones.md`) | ✔ |
| RNF-06 | `ingesta.py` + adaptador (esquema agnóstico de fabricante) | ✔ |
| RNF-07 | `analisis.py` / `postura.py` (baja confianza ante telemetría incompleta) | ✔ |
| RNF-08 | `evento_crudo` tratado como **dato inerte, nunca instrucción** | ~ (superficie crítica: el log lo escribe quien ataca) |
| RNF-09 | `prototipo/lazo.py` (fallo del modelo → cola manual, RNF-09) | ✔ |
| RNF-10 | perfiles YAML (reglas/umbrales); **prompts en código** (`construir_prompt`) | ~ (externalizar prompts = futuro) |
| RNF-11 | salida legible (`traza.py` / tablero) | ✔ |
| RNF-12 | política documentada ([protocolos §8](../04-fase4-diseno-de-arquitectura/protocolos-comunicacion-sandbox.md)); **no implementada** | ~ (anonimización/retención = config de despliegue) |
| RNF-13 | `evaluacion/` (procesamiento por lotes) | ✔ |
| RNF-14 | perfil + adaptador (V1/V3/V4/V5); **V2 (canal/ejecutor) = código** | **+** |

## 3. Mapeo inverso — el modelo de cliente (Fase 1) → requisito

### Limitaciones del sistema base (L1–L5): las brechas que el prototipo **cubre**

| L | Limitación | Requisitos que la cubren | Cómo |
|---|------------|--------------------------|------|
| L1 | Clasifica por regla sin contexto del activo | RF-02, RF-03, RF-16 | contexto de activo/postura + orígenes legítimos |
| L2 | Severidad fija por regla | RF-04, RF-06, RF-14 | prioridad calculada + confianza contra el baseline |
| L3 | Sin justificación explicable | RF-05, RNF-02, RF-09 | justificador LLM+RAG anclado, registrado en la traza |
| L4 | Sin noción de coste operativo | RF-17, RF-18, RF-19, RF-20 | conciencia de impacto + reversibilidad + métricas de continuidad |
| L5 | Correlación multicapa limitada | RF-11 (parcial: agrupa ráfagas en incidentes) | ⏳ la correlación multicapa (XDR) es **trabajo futuro** |

### Restricciones operativas del cliente (C1–C6): lo que el prototipo **respeta**

| C | Restricción | Requisitos que la honran | Cómo |
|---|-------------|--------------------------|------|
| C1 | Continuidad | RF-07, RF-17, RF-19 | política de continuidad; `actores` = `humano_siempre` (D16) |
| C2 | Sin ventana de mantenimiento | *(por diseño)* | no difiere acciones; el impacto nunca se subestima (`impacto.py`) |
| C3 | Sin manos en el equipo | RF-18 | reversibilidad verificable (`revertir.py`) |
| C4 | Privacidad | RNF-01 (+ RNF-12) | análisis 100 % local |
| C5 | Parque heterogéneo | RF-15, RNF-06 | acciones abstractas del catálogo + conector (V2) |
| C6 | Plano de gestión = objetivo | RF-19 | veto duro: no cortar el canal de respuesta (`perfil.filtrar`) |

### Puntos de variabilidad (V1–V5)

El mapeo V→requisito ya vive en [`requisitos.md` §"Los cinco puntos de variabilidad"](./requisitos.md#los-cinco-puntos-de-variabilidad).
Resumen: V1→RF-01/RNF-06 · V2→RF-15 · V3→RF-07/17/18/19 · V4→RF-02/04 · V5→RF-14/20.

---

## 4. Huecos honestos (no ocultos)

- **L5 · correlación multicapa** — declarada trabajo futuro; el prototipo mejora el triaje de la alerta que recibe, no la correlación que la produjo.
- **RNF-12 · retención/anonimización** — política documentada, **no implementada** (config de despliegue por normativa del cliente).
- **RNF-14 · V2 (canal/ejecutor)** — un canal de respuesta nuevo exige **código** (ejecutor por back-end), no es pura configuración del perfil.
- **RF-07 · umbral de confianza** — calibración por barrido **pendiente**.
