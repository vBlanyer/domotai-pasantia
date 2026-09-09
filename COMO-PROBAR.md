# Cómo probar el prototipo

Guía práctica ordenada por **niveles de dependencia**: del **Nivel 0** (solo Python) al **Nivel 3** (lab +
modelo). Para cada comando tienes su **Sinopsis** (sintaxis) y un **Ejemplo** listo para pegar en consola.

**Todos los comandos se ejecutan desde la raíz del repositorio.**

**Convención de sintaxis:** `<obligatorio>` · `[opcional]` · `a | b` (alternativas) · `-` como ruta = leer de *stdin*.

---

## Requisitos por nivel

| Para… | Necesitas |
|-------|-----------|
| Niveles 0–1 (tests, CLI del motor) | **Python 3** (probado en 3.14) + **pyyaml**. Sin `pip`/`venv`/`pytest`. |
| Nivel 2 (RAG, LLM, evaluación con modelo) | Entorno conda `~/miniforge3/envs/triaje-ml` (Python 3.12 + `llama.cpp`) y el modelo `modelos/llama-3.2-1b-q4.gguf` (~808 MB, no versionado). Instalación en [`prototipo/README.md`](prototipo/README.md). |
| Nivel 3 (demos en vivo, daemon) | Lo anterior **+ Docker + Containerlab** (el laboratorio). |

Los Niveles 0–1 no necesitan lab ni modelo: el dataset etiquetado y los hallazgos ya están en el repo.

---

## Arranque rápido (copia-pega)

```bash
# 0) Sanidad (segundos, sin dependencias)
python3 -m unittest discover -s prototipo/tests

# 1) El motor decide sobre 410 alertas reales (sin dependencias)
python3 -m prototipo.triaje lab/dataset/etiquetado.jsonl prototipo/perfiles/empresarial.yml \
    lab/campañas/2026-08-31-evaluacion/hallazgos.json salida.jsonl

# 2) Evaluación contra el baseline (sin modelo, rápido)
python3 -m evaluacion.campana --particion evaluacion --sin-llm

# 3) Lab en vivo (necesita Docker + Containerlab + modelo)
sh lab/lab.sh up && python3 lab/scripts/demo-agente-escalado.py --autonomo
```

---

# Nivel 0 · Sanidad (sin dependencias, segundos)

**Sinopsis**
```
python3 -m unittest discover -s <directorio_de_tests>
```

**Ejemplo**
```bash
python3 -m unittest discover -s prototipo/tests      # el motor
python3 -m unittest discover -s lab/dataset/tests     # el pipeline del dataset
python3 -m unittest discover -s evaluacion/tests      # el marco de evaluación
```

**Esperado:** `OK` en las tres (≈169 + 33 + 28 tests). Si las tres dan verde, el prototipo está sano.

---

# Nivel 1 · El motor sobre datos reales (sin dependencias)

## 1.1 · Triaje sobre el dataset

Corre el lazo completo: clasifica → política → perfil → traza.

**Sinopsis**
```
python3 -m prototipo.triaje <alertas.jsonl> <perfil.yml> <hallazgos.json> <salida.jsonl>
```

**Ejemplo**
```bash
python3 -m prototipo.triaje lab/dataset/etiquetado.jsonl prototipo/perfiles/empresarial.yml \
    lab/campañas/2026-08-31-evaluacion/hallazgos.json salida.jsonl
```

**Esperado:** `410 decisiones -> salida.jsonl`. Cada línea es una traza auditable (`clase`, `prioridad`,
`confianza`, `justificacion`, `accion_propuesta`, `resultado_filtro`, `accion_final`, `requiere_humano`,
`version_justificador`…). Inspecciona una:
```bash
grep vp_intento_acceso salida.jsonl | head -1 | python3 -m json.tool
```
Prueba `prototipo/perfiles/residencial.yml` para ver cómo cambia el filtro de continuidad.

## 1.2 · Ingesta desde Wazuh crudo (RF-01)

Normaliza alertas crudas de Wazuh al esquema del motor (agnóstico de fuente).

**Sinopsis**
```
python3 -m prototipo.ingesta <cruda.json> <salida.jsonl> [fuente=wazuh] [campaña]
```

**Ejemplo**
```bash
python3 -m prototipo.ingesta lab/campañas/2026-08-31-evaluacion/alerts.json normalizado.jsonl wazuh
```

**Esperado:** `N alertas normalizadas -> normalizado.jsonl`. Avisa de las alertas con campos críticos
ausentes sin inventarlos (RNF-07).

## 1.3 · Agrupación por incidente (RF-11)

Colapsa las ráfagas casi idénticas en incidentes.

**Sinopsis**
```
python3 -m prototipo.agrupacion <normalizado.jsonl> <salida.jsonl> [ventana_seg=300]
```

**Ejemplo**
```bash
python3 -m prototipo.agrupacion normalizado.jsonl incidentes.jsonl 300
```

**Esperado:** `N alertas -> M incidentes (ventana 300s)`. Sobre las 205 de evaluación da **4 incidentes**;
sobre las 18 soportadas, **2** (el ataque y el admin legítimo).

---

# Nivel 2 · RAG, LLM y evaluación (necesita el modelo local)

## 2.1 · Evaluación contra el baseline (Fase 6)

**Sinopsis**
```
python3 -m evaluacion.campana [--particion evaluacion|todas] [--perfil empresarial|residencial] \
                              [--sin-llm] [--con-rag] [--salida-dir DIR] [--hallazgos RUTA]
```

**Ejemplo** (sin LLM, rápido — solo métricas de clasificación/priorización)
```bash
python3 -m evaluacion.campana --particion evaluacion --sin-llm
```

**Ejemplo** (con RAG, lento ~5 min — corre el 1B para el anclaje)
```bash
python3 -m evaluacion.campana --particion evaluacion --con-rag
```

**Esperado:** tabla prototipo vs baseline. Resultado principal: **precisión 1.000, tasa de FP 0.000** frente
al baseline (0.154 / 0.282). Escribe `evaluacion/resultados/tabla.md` y `campana-<fecha>.json`.

## 2.2 · Compilar el corpus del RAG desde MITRE ATT&CK

Destila las técnicas del perímetro del bundle STIX oficial y las compone con las fichas curadas.

**Sinopsis**
```
python3 -m prototipo.extraer_attack [bundle.json] [curado.jsonl] [corpus.jsonl]
```

**Ejemplo**
```bash
# requiere prototipo/corpus/fuentes/enterprise-attack.json (ver prototipo/corpus/fuentes/README.md)
python3 -m prototipo.extraer_attack
```

**Esperado:** `15 tecnicas extraidas + 14 curadas -> 29 fichas -> prototipo/corpus/corpus.jsonl`.

## 2.3 · Indexar y consultar el RAG (5D)

**Sinopsis**
```
python3 -m prototipo.rag ( --indexar | --consulta "<texto>" )
```

**Ejemplo** (generar el índice de embeddings; una vez, ~40 s)
```bash
python3 -m prototipo.rag --indexar
```

**Ejemplo** (ver qué recupera para una consulta defensiva)
```bash
python3 -m prototipo.rag --consulta "contramedida defensiva D3FEND filtrado de trafico ante fuerza bruta SSH"
```

**Esperado:** los pasajes más cercanos por coseno (fichas ATT&CK / D3FEND / mapeos). El corpus encadena
*técnica → contramedida D3FEND → acción del catálogo*.

## 2.4 · Banco de simulación y evaluación del RAG

Calibra la recuperación (**fija vs agéntica**) sobre 12 alertas sintéticas etiquetadas, con **Hit Rate@K,
Precision@K y MRR** (K=1,3,5).

**Sinopsis**
```
python3 -m evaluacion.simular_ataques_rag [--con-sintesis] [--salida-dir DIR]
```

**Ejemplo** (recuperación; usa el 1B para la consulta agéntica, ~6 min)
```bash
python3 -m evaluacion.simular_ataques_rag
```

**Ejemplo** (+ tasa de anclaje de la síntesis del 1B, más lento)
```bash
python3 -m evaluacion.simular_ataques_rag --con-sintesis
```

**Esperado:** tabla comparativa en `evaluacion/resultados/rag-simulacion-<fecha>.md`. Referencia actual:
**MRR 0.50 (agéntica)**, Hit@5 0.75; 3/4 familias al 100 % (servicio_expuesto residual).

---

# Nivel 3 · En vivo, de punta a punta (lab + modelo)

## 3.0 · Levantar el laboratorio (imprescindible para el resto del Nivel 3)

**Sinopsis**
```
sh lab/lab.sh ( up | down | status | test )
```

**Ejemplo**
```bash
sh lab/lab.sh up          # despliega la red + Wazuh + aprovisiona el auditor (~2 min)
sh lab/lab.sh status      # comprobar: 8 nodos arriba, plano de datos OK
```

Asegúrate de tener el índice RAG (`python3 -m prototipo.rag --indexar`, Nivel 2.3).

## 3.1 · Demo del lazo completo (víctima / atacante / triaje)

Ataque real → Wazuh alerta → triaje justifica con RAG → validación → bloqueo por SSH → verificación.

**Sinopsis**
```
python3 lab/scripts/demo-lazo-vivo.py
```

**Ejemplo**
```bash
python3 lab/scripts/demo-lazo-vivo.py
```

**Esperado:** narra las 3 vistas; el bloqueo `iptables` aparece en la víctima y el atacante deja de
alcanzar el puerto 22.

## 3.2 · Demo de validación humana real

**Sinopsis**
```
python3 lab/scripts/demo-validacion-humana.py
```

**Ejemplo**
```bash
python3 lab/scripts/demo-validacion-humana.py
```

**Esperado:** una acción que alcanza el servicio se **degrada** y **exige aprobación**; se corre el mismo
punto de decisión **rechazar** (no ejecuta) y **aprobar** (ejecuta por SSH).

> Deja el lab neutro tras las demos:
> `docker exec clab-red-cliente-objetivo-vuln iptables -D INPUT -s 192.168.1.10 -j DROP`

## 3.3 · Modo tiempo real continuo (daemon / listener MDR)

Se **queda escuchando** `alerts.json` sin cerrarse (como en producción): colapsa la ráfaga (RF-11),
clasifica, justifica (con RAG si `--con-llm`), abre el prompt **[Aprobar/Rechazar/Reclasificar]** cuando hace
falta humano, ejecuta, escribe la traza línea a línea y vuelve a escuchar. `Ctrl+C` cierra con resumen.

**Sinopsis**
```
python3 -m prototipo.stream <alerts.json | -> [perfil.yml] [hallazgos.json] \
        [--con-llm | --sin-llm] [--ventana-agrupacion N] [--sin-lab] [--salida trazas.jsonl]
```
(`--ventana-agrupacion N`: acumula la ráfaga N s antes de emitir el incidente; `N=0` = al instante. Default 5.)

**Ejemplo** (en el lab: el `alerts.json` vive dentro del contenedor de Wazuh → canaliza su `tail -F`)
```bash
docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --con-llm --ventana-agrupacion 10
```
(en otra terminal, lanza el ataque; p. ej. corre `demo-lazo-vivo.py` o la fuerza bruta a mano)

**Ejemplo** (en producción: Wazuh escribe a un fichero del host montado)
```bash
python3 -m prototipo.stream /var/ossec/logs/alerts/alerts.json prototipo/perfiles/empresarial.yml --con-llm
```

**Ejemplo** (prueba de humo sin lab ni modelo: alerta cruda por *stdin*, ejecutor simulado)
```bash
printf '%s\n' '{"id":"z1","rule":{"id":"5760","level":10,"groups":["sshd","authentication_failed"],"mitre":{"id":["T1110.001"]}},"predecoder":{"hostname":"objetivo-vuln","program_name":"sshd"},"data":{"srcip":"192.168.1.10"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Failed password for root from 192.168.1.10"}' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
```

## 3.4 · Agente de mitigación (escalado multi-nodo host → firewall)

El LLM actúa como **agente ReAct**: decide la estrategia y **escala de dispositivo** (host → firewall)
reaccionando a los errores, pero **elige acciones de un catálogo cerrado** (el código renderiza el
`iptables`, RF-15), valida (RF-19), pide aprobación (RF-08) y ejecuta reversible (RF-18). Consulta el
conocimiento **ATT&CK/D3FEND** del RAG. Si falla, **degrada** al motor determinista (RNF-09).

**Sinopsis**
```
python3 lab/scripts/demo-agente-escalado.py [--lab] [--autonomo] [--con-llm]
```
(`--lab`: conector SSH real · `--autonomo`: sin pausas de aprobación · `--con-llm`: el 1B real como agente)

**Ejemplo** (simulado, sin interacción — el más rápido para ver el escalado)
```bash
python3 lab/scripts/demo-agente-escalado.py --autonomo
```

**Esperado:** consulta el conocimiento → intenta el bloqueo local (falla: *Connection refused*) → **escala
al firewall** (`BLOQUEAR_IP_FIREWALL`) → verifica el corte → registra ambas reversiones; `escalado: True`,
`dispositivo ejecutor: gateway`.

---

## Qué mirar en cada prueba

- **La traza** es la evidencia auditable: clase, prioridad, confianza, justificación (texto **y**
  estructurada), acción propuesta/final, filtro del perfil, veredicto humano, `version_justificador`,
  y (con RAG) `consulta_rag`/`recuperacion_agentica`/`pasajes_usados`.
- **La decisión NO la toma el modelo**: la política determinista propone y el perfil de cliente filtra
  (permite / degrada / veta). El LLM **justifica** y, en el agente, **elige de un catálogo cerrado** — nunca
  redacta comandos libres.
- **Todo es local** (RNF-01): ninguna alerta sale a servicios externos; el LLM corre por subprocess a un
  binario local.

## Más detalle

- [`README.md`](README.md) — qué es el proyecto y qué hay construido.
- [`prototipo/README.md`](prototipo/README.md) — el motor por dentro (5A–5D, RAG agéntico, agente de mitigación).
- [`documentacion/`](documentacion/) — el diseño por fases; el
  [informe de evaluación](documentacion/06-fase6-evaluacion-del-prototipo/informe-evaluacion.md) tiene los números.
