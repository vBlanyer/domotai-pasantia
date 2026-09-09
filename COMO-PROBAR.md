# Cómo probar el prototipo

Guía práctica para ejecutar y validar el motor de triaje. Está ordenada por **niveles de dependencia**:
del **Nivel 0** (solo Python, sin nada más) al **Nivel 3** (demo en vivo contra el laboratorio con el
LLM). Todos los comandos se ejecutan **desde la raíz del repositorio**.

> Resumen de un vistazo: si solo quieres comprobar que todo funciona, haz el **Nivel 0**. Si quieres ver
> el prototipo decidir sobre datos reales, el **Nivel 1**. El RAG y la demo en vivo (Niveles 2–3) piden el
> modelo local y/o el laboratorio.

---

## Requisitos

| Para… | Necesitas |
|-------|-----------|
| Niveles 0 y 1 (tests, CLI, evaluación sin LLM) | **Python 3** (probado en 3.14) + **pyyaml**. Sin `pip`, sin `venv`, sin `pytest`. |
| Nivel 2 (RAG y justificador LLM) | El entorno conda de 5C: `~/miniforge3/envs/triaje-ml` (Python 3.12 + `llama.cpp`) y el modelo `modelos/llama-3.2-1b-q4.gguf` (~808 MB, no versionado). Instalación en [`prototipo/README.md`](prototipo/README.md). |
| Nivel 3 (demo en vivo) | Lo anterior **+ Docker + Containerlab** (el laboratorio). |

No hace falta el laboratorio ni el modelo para los Niveles 0–1: el dataset etiquetado y los hallazgos
del auditor ya están en el repo (`lab/dataset/`, `lab/campañas/`).

---

## Nivel 0 · Comprobar que todo funciona (sin dependencias, segundos)

Corre las tres baterías de tests (stdlib `unittest`):

```bash
python3 -m unittest discover -s prototipo/tests      # el motor (116 tests)
python3 -m unittest discover -s lab/dataset/tests     # el pipeline del dataset (33)
python3 -m unittest discover -s evaluacion/tests      # el marco de evaluación (22)
```

Esperado: `OK` en las tres. Si las tres dan verde, el prototipo está sano.

---

## Nivel 1 · Ver el motor decidir sobre datos reales (sin dependencias)

### 1.1 Triaje sobre el dataset

Corre el motor completo (clasifica → política → perfil → traza) sobre las 410 alertas reales, con el
perfil empresarial y los hallazgos del auditor:

```bash
python3 -m prototipo.triaje \
    lab/dataset/etiquetado.jsonl \
    prototipo/perfiles/empresarial.yml \
    lab/campañas/2026-08-31-evaluacion/hallazgos.json \
    salida.jsonl
```

Esperado: `410 decisiones -> salida.jsonl`. Cada línea de `salida.jsonl` es una traza auditable: `clase`,
`prioridad`, `confianza`, `justificacion`, `justificacion_estructurada`, `accion_propuesta`,
`resultado_filtro`, `accion_final`, `requiere_humano`, `version_justificador`… Míralo con:

```bash
grep vp_intento_acceso salida.jsonl | head -1 | python3 -m json.tool
```

Prueba el otro perfil (`prototipo/perfiles/residencial.yml`) para ver cómo cambia el filtro de continuidad.

### 1.2 Ingesta desde Wazuh crudo (RF-01)

Normaliza alertas crudas de Wazuh al esquema del motor (agnóstico de fuente):

```bash
python3 -m prototipo.ingesta <alerts.json de Wazuh> normalizado.jsonl wazuh
```

(Un `alerts.json` de ejemplo: `lab/campañas/2026-08-31-evaluacion/alerts.json`.)
Avisa de las alertas con campos críticos ausentes sin inventarlos (RNF-07).

### 1.3 Agrupación por incidente (RF-11)

Colapsa las ráfagas de alertas casi idénticas en incidentes:

```bash
python3 -m prototipo.agrupacion normalizado.jsonl incidentes.jsonl 300
```

Esperado: `N alertas -> M incidentes (ventana 300s)`. Sobre las 205 alertas de evaluación da **4
incidentes**; sobre las 18 soportadas, **2** (el ataque y el admin legítimo).

---

## Nivel 2 · La evaluación y el RAG (necesita el modelo local para el LLM)

### 2.1 La evaluación contra el baseline (Fase 6)

**Sin LLM** (rápido, solo métricas de clasificación/priorización/continuidad):

```bash
python3 -m evaluacion.campana --particion evaluacion --sin-llm
```

Esperado: una tabla comparativa prototipo vs baseline de Wazuh. Resultado principal: el prototipo da
**precisión 1.000, tasa de FP 0.000** frente al baseline (0.154 / 0.282). Escribe
`evaluacion/resultados/tabla.md` y `campana-<fecha>.json`.

**Con RAG** (lento, ~5 min: corre el 1B sobre las 18 soportadas para el anclaje):

```bash
python3 -m evaluacion.campana --particion evaluacion --con-rag
```

Otros flags: `--perfil residencial`, `--particion todas`, `--salida-dir <dir>`.

### 2.2 El RAG por separado (5D)

Genera el índice del corpus (una vez; usa el modelo, ~40 s):

```bash
python3 -m prototipo.rag --indexar
```

Consulta el corpus (qué recupera para una alerta):

```bash
python3 -m prototipo.rag --consulta "regla 5760 tecnicas MITRE T1110.001 servicio ssh"
```

Esperado: los pasajes más cercanos por coseno (fichas de las reglas SSH / técnicas MITRE).

El corpus incluye ahora contramedidas **D3FEND** y fichas de mapeo *técnica → contramedida → acción* (RAG
agéntico, Opción C). Pruébalo con una consulta orientada a la defensa:

```bash
python3 -m prototipo.rag --consulta "contramedida defensiva D3FEND filtrado de trafico ante fuerza bruta SSH"
```

La **consulta agéntica** (el 1B decide qué añadir a la búsqueda, aumentando la consulta fija) se ejerce
al justificar con `rag.recuperar_fn_agentico(...)`; la traza registra `consulta_rag` y
`recuperacion_agentica` (RNF-03). Si el modelo no está, degrada a la consulta fija sin romper.

---

## Nivel 3 · La demo en vivo, de punta a punta (laboratorio + modelo)

Reproduce el lazo completo contra el laboratorio: un ataque real → Wazuh alerta → el triaje clasifica y
**justifica con RAG** → validación humana → el conector **bloquea por SSH** → verificación.

### 3.1 Levantar el laboratorio

```bash
sh lab/lab.sh up          # despliega la red + Wazuh + aprovisiona el auditor
sh lab/lab.sh status      # comprobar: nodos arriba, plano de datos OK
```

(Para verlo/limpiarlo: `sh lab/lab.sh test`, `sh lab/lab.sh down`.)

Asegúrate de tener el índice RAG (Nivel 2.2, `python3 -m prototipo.rag --indexar`).

### 3.2 Demo del lazo completo (víctima / atacante / triaje)

```bash
python3 lab/scripts/demo-lazo-vivo.py
```

Lanza una fuerza bruta SSH real desde el atacante (`puesto`, .10) contra la víctima (`objetivo-vuln`, .30),
deja que Wazuh alerte, corre el motor con RAG y el conector SSH real, y narra las tres vistas: el bloqueo
`iptables` aparece en la víctima y el atacante deja de alcanzar el puerto 22.

### 3.3 Demo de validación humana real

```bash
python3 lab/scripts/demo-validacion-humana.py
```

Provoca una acción que alcanza el servicio (con confianza baja): el perfil la **degrada** a una acción
segura **y exige aprobación**. Corre el mismo punto de decisión dos veces —**rechazar** (no ejecuta nada)
y **aprobar** (ejecuta por SSH)— para mostrar que la decisión humana gobierna la ejecución.

> Deja el laboratorio neutro tras la demo:
> `docker exec clab-red-cliente-objetivo-vuln iptables -D INPUT -s 192.168.1.10 -j DROP`

---

## Nivel 3.bis · Modo tiempo real continuo (daemon / listener MDR)

A diferencia de las demos de un solo tiro (`demo-lazo-vivo.py`, que lee `alerts.json` una vez y sale),
el runner **se queda escuchando** alertas sin cerrarse, como en producción. Reutiliza el motor completo
(`lazo.procesar_lazo`): por cada ráfaga colapsa el incidente (RF-11), lo clasifica, lo justifica (con RAG
si `--con-llm`), abre el prompt **[Aprobar/Rechazar/Reclasificar]** cuando la decisión requiere humano,
ejecuta la mitigación, escribe la traza línea a línea y vuelve a escuchar. CLI:

```bash
python3 -m prototipo.stream <ruta_alerts.json | -> [perfil.yml] [hallazgos.json] \
    [--con-llm | --sin-llm] [--ventana-agrupacion N] [--sin-lab] [--salida trazas.jsonl]
```

**En producción** (Wazuh escribe a un fichero del host, p. ej. montado): apúntalo al fichero y lo sigue
estilo `tail -f`, tolerando incluso que aún no exista:

```bash
python3 -m prototipo.stream /var/ossec/logs/alerts/alerts.json prototipo/perfiles/empresarial.yml --con-llm
```

**En el laboratorio** (el `alerts.json` vive **dentro** del contenedor de Wazuh): canaliza el `tail -F`
del contenedor a la entrada estándar del runner (fuente `-`):

```bash
docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --con-llm --ventana-agrupacion 10
```

En otra terminal lanza el ataque (la fuerza bruta de `demo-lazo-vivo.py`, o a mano desde el atacante) y
observa el runner reaccionar en vivo. `Ctrl+C` cierra e imprime el resumen de la sesión (alertas vistas,
incidentes, aprobadas/rechazadas/ejecutadas). Con **`--sin-lab`** usa un ejecutor **simulado** (sin
Containerlab), útil para ensayar la UX; y una **prueba de humo sin nada** (canalizando una alerta cruda):

```bash
printf '%s\n' '<una alerta cruda de Wazuh en JSON>' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
```

> La ventana de agrupación (`--ventana-agrupacion N`, por defecto 5 s) acumula la ráfaga N segundos antes
> de emitir el incidente; `N=0` procesa cada alerta al instante.

## Nivel 3.ter · Agente de mitigación (escalado multi-nodo host → firewall)

El LLM actúa como **agente ReAct**: decide la estrategia y **escala de dispositivo** (del host al
firewall) reaccionando a los errores — pero **elige acciones de un catálogo cerrado** (no redacta shell:
el código renderiza el `iptables`, RF-15), valida (RF-19), exige aprobación humana (RF-08) y ejecuta de
forma reversible (RF-18). Consulta el conocimiento **ATT&CK/D3FEND** del RAG para fundamentar la
contramedida. Si no produce una acción válida, **degrada** al motor determinista (RNF-09).

```bash
python3 lab/scripts/demo-agente-escalado.py [--lab] [--autonomo] [--con-llm]
```

Por defecto usa **ejecutores simulados** (host caído / firewall ok) — el firewall `borde` del laboratorio
no trae sshd por defecto — y **pide aprobación por cada acción** (usa `--autonomo` para verlo sin
interacción). Esperado: el agente consulta el conocimiento, intenta el bloqueo local (falla: *Connection
refused*), **escala al firewall** (`BLOQUEAR_IP_FIREWALL`), verifica el corte, y registra ambas
reversiones. Con `--con-llm` usa el 1B real como agente (puede degradar); con `--lab`, el conector SSH real.

## Qué mirar en cada prueba

- **La traza** (`salida.jsonl`, o el retorno de `triaje.procesar`) es la evidencia auditable: clase,
  prioridad, confianza, justificación (texto **y** estructurada), acción propuesta/final, filtro del perfil,
  veredicto humano, y `version_justificador` (versión+modelo del que justificó).
- **La decisión NO la toma el modelo**: la política determinista propone y el perfil de cliente filtra
  (permite / degrada / veta). El LLM solo justifica.
- **Todo es local**: ninguna alerta sale a servicios externos (RNF-01); el LLM corre por subprocess a un
  binario local.

## Más detalle

- [`README.md`](README.md) — qué es el proyecto y qué hay construido.
- [`prototipo/README.md`](prototipo/README.md) — el motor por dentro (5A–5D), instalación del entorno LLM.
- [`documentacion/`](documentacion/) — el diseño completo por fases; el
  [informe de evaluación](documentacion/06-fase6-evaluacion-del-prototipo/informe-evaluacion.md) tiene los números.
