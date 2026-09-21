# 07 · Roadmap del pipeline y latencia medida (qué pasa detrás de cada incidente)

Recorre el camino completo de una alerta, **de la ingesta a la acción**, dice **qué ocurre detrás** de cada
etapa y **cuánto tarda** en cada perfil de hardware. Complementa a [06 · Rendimiento y hardware](06-rendimiento-y-hardware.md)
(que se centra en los modos y el hardware objetivo): aquí el foco es el **flujo por etapas** y una **medición
nueva en el Acer Aspire 3** (la máquina de trabajo de hoy), tomada el 14/09/2026.

## Las tres máquinas de referencia

| Perfil | CPU / RAM / GPU | Modelos que sostiene | Papel |
|---|---|---|---|
| **Acer Aspire 3 (hoy)** | CPU móvil, **8 GB** (11 GiB en WSL2), **sin GPU** | **1B + `bge-m3` residentes** (los dos caben, ~2 GB); el 8B no | desarrollo e iteración; test de arquitectura |
| **Portátil 16 GB (histórico)** | CPU sin GPU, 16 GB | 1B por subproceso, `bge-m3` por subproceso | mediciones de la Fase 6 |
| **Objetivo (9800X3D + RTX 5070)** | Zen5, **12 GB VRAM** | **8B residente + `bge-m3` residente** | producción / demos cómodas |

**El stack de producción íntegro** (generador 8B residente + embedder `bge-m3` residente + índice vectorial
+ orquestador) rinde a su velocidad **solo en la máquina objetivo**, pero su **arquitectura se reproduce en el
Acer** (con el 1B en vez del 8B): ver [«Probar como en la máquina objetivo, desde el Acer»](#probar-como-en-la-máquina-objetivo-desde-el-acer-14092026).
Si no se arrancan los servidores residentes, el Acer cae al **perfil degradado** (RNF-09): 1B por subproceso y,
si además falta el modelo `bge-m3`, la recuperación RAG devuelve `[]` sin romper (guardia de dimensión y
degradación limpia) y la justificación se produce **sin pasajes**. La decisión de seguridad es idéntica en las
tres máquinas y en los dos perfiles.

## El roadmap del incidente, etapa por etapa

```
  syslog del atacante
        │
        ▼
 ┌─────────────┐   Wazuh (SIEM del cliente, emulado): correlaciona y escribe alerts.json
 │  1. FUENTE  │   → NO es nuestro; es la capa de arriba. Coste: pocos s (fuera del daemon).
 └─────────────┘
        │  alerta cruda
        ▼
 ┌─────────────┐   ingesta.py: adaptador por fuente → esquema común, tolerante a campos ausentes
 │ 2. INGESTA  │   (RNF-06/07). Resuelve el activo aunque el equipo no tenga agente (RF-16).
 └─────────────┘   Detrás: parseo puro Python. Coste: microsegundos.
        │  alerta normalizada
        ▼
 ┌─────────────┐   agrupacion.py: junta la ráfaga del mismo origen en UN incidente (RF-11).
 │3. AGRUPACIÓN│   Detrás: ventana temporal (--ventana-agrupacion N). Coste: la espera de la ventana.
 └─────────────┘
        │  incidente
        ▼
 ┌─────────────┐   analisis.enriquecer: añade postura del activo (auditor) + criticidad del perfil.
 │4. ENRIQUECER│   Detrás: lectura de hallazgos e inventario. Coste: microsegundos.
 └─────────────┘
        │
        ▼
 ┌─────────────┐   analisis.clasificar: REGLAS deterministas (6, la 6ª descubierta por el árbol).
 │5. CLASIFICAR│   → clase / prioridad / confianza. Detrás: comparaciones, sin modelo.
 └─────────────┘   Coste: microsegundos.  ◄── ESTA es la decisión de seguridad.
        │
        ▼
 ┌─────────────┐   politica.proponer + perfil.filtrar: propone la acción y el perfil de cliente la
 │6. POLÍTICA  │   permite / degrada / veta (continuidad del servicio). Detrás: reglas + catálogo
 │  + PERFIL   │   cerrado (RF-15). Coste: microsegundos.
 └─────────────┘
        │
        ▼
 ┌─────────────┐   El LLM SOLO explica; no decide (RF-15). Dos sub-pasos, ambos con el generador:
 │7. JUSTIFICAR│     7a. consulta agéntica: el modelo formula UNA línea de búsqueda (1 generación)
 │  (LLM+RAG)  │     7b. RAG: embedder vectoriza la consulta → coseno contra el índice → top-k pasajes
 └─────────────┘     7c. justificación: el modelo explica citando datos + pasajes (1 generación)
        │            Detrás: 2 generaciones + 1 embedding. Verificación de anclaje (RNF-02);
        │            si falla o el modelo no responde → plantilla determinista (RNF-09).
        ▼            ◄── AQUÍ vive casi toda la latencia del incidente.
 ┌─────────────┐   traza.construir: traza encadenada por hash (RF-09), verificable y anclada.
 │  8. TRAZA   │   Detrás: hash de la cadena. Coste: microsegundos.
 └─────────────┘
        │
        ▼
 ┌─────────────┐   validacion → conector SSH (o agente ReAct que escala host→firewall). El bloqueo
 │  9. ACCIÓN  │   determinista es instantáneo; la aprobación humana la marca el analista.
 └─────────────┘   Detrás: orden sobre el catálogo cerrado + reescaneo de verificación.
```

**La lectura clave:** las etapas 2–6 y 8 (la **decisión de seguridad** y su traza) son **deterministas e
instantáneas en cualquier máquina**. Toda la latencia sensible al hardware está en la **etapa 7** (el LLM que
*explica*), y por eso el coste del modelo **no retrasa la respuesta de seguridad**, solo la explicación.

## Latencia medida por etapa

Medido el **14/09/2026** en el Acer (`LLAMA_MODO=subproceso`, 1B q4, 64 tokens); columnas de producción
tomadas de las mediciones de [06 · Rendimiento](06-rendimiento-y-hardware.md).

| Etapa | Acer 8 GB (hoy, medido) | Objetivo 8B+bge-m3 residentes (medido) |
|---|---|---|
| **2–6 · decisión determinista** (600 alertas) | **3,7 ms** total → **0,006 ms/alerta** | igual (no usa LLM) |
| **7a · consulta agéntica** (1 gen 1B/8B) | ~14 s en frío → **~35 s** con throttling | ~0,4 s (8B) |
| **7b · embedder + coseno** | **no corre**: falta `bge-m3` → degrada a `[]` en **0,1 s** | **ms** (residente) |
| **7c · justificación** (1 gen 1B/8B) | ~14 s en frío → **~40 s** con throttling | ~0,4 s (8B) |
| **Incidente `--con-llm` completo** (7a+7b+7c) | **~73–75 s** | daemon en vivo **2,8 s** |

### Lo que enseña la medición del Acer

1. **La decisión es gratis.** 600 alertas clasificadas y filtradas en **3,7 ms**. El motor de seguridad no
   depende del hardware; corre igual en el Acer que en la máquina objetivo.
2. **Throttling térmico real.** Las **primeras** generaciones del 1B salen a ~14 s (≈4,4 t/s), pero bajo
   **carga sostenida** el Acer, de refrigeración pasiva, cae a **~35–40 s por generación** (≈1,7 t/s). El
   estado estable de un incidente se asienta en **~75 s**, no en los ~28 s que sugerirían las primeras
   generaciones. Es el número honesto para operar.
3. **Esta medición se tomó sin `bge-m3` (degrada limpio).** En ese momento el embedder no estaba en
   `modelos/`, así que devolvía `[]` en 0,1 s y el justificador seguía **sin pasajes** (RNF-09) en vez de
   romper. La guardia de dimensión de `recuperar()` (índice a 1024-d) evita cualquier recuperación con
   vectores incompatibles. *(Después se bajó `bge-m3` y el RAG sí corre en vivo — ver la sección de abajo.)*
4. **Sin pasajes, el 1B ancla; con pasajes, no.** En esta medición (sin RAG) la justificación supera la
   verificación de anclaje (RNF-02) y la traza registra `justificador=llm-6:llama-3.2-1b-q4.gguf`. Con RAG en
   vivo (sección siguiente) el 1B narra técnicas de los pasajes como propias, **falla el anclaje y degrada a
   plantilla** — la razón por la que el objetivo usa el 8B.

## Qué pasa detrás de cada llamada al LLM (y por qué el servidor residente)

En el Acer, cada `generador_llama` es un **subproceso nuevo** (`llama-simple`) que **recarga los 771 MB del
modelo desde disco** antes de generar un solo token. Un incidente `--con-llm` son **dos** generaciones, así
que se paga **dos recargas** más la presión de 8 GB de RAM. Ése es el grueso del coste — y es exactamente lo
que el **servidor residente** elimina en la máquina objetivo:

| | Subproceso (Acer hoy) | Servidor residente (objetivo) |
|---|---|---|
| Modelo en memoria | se recarga **en cada llamada** | cargado **una vez** (en RAM/VRAM) |
| Plantilla de chat | no se aplica | la aplica el servidor |
| Temperatura / esquema | flag en la línea | campo JSON (RF-15 por muestreo) |
| Embedder `bge-m3` | subproceso (~5 s/llamada en el de 16 GB) | residente (**ms**) |
| Coste por incidente | **~75 s** (1B, degradado) | **~2,8 s** (8B + RAG) |

Por eso la recomendación operativa (06) es: en el Acer, **`--sin-llm`** (plantilla determinista,
instantánea) para iterar; el `--con-llm` real, con su calidad, es cosa de la máquina objetivo.

## Cómo reproducir la medición

```bash
# decisión determinista sobre el dataset (instantánea, cualquier máquina)
python3 -m prototipo.triaje lab/dataset/etiquetado.jsonl prototipo/perfiles/empresarial.yml \
    lab/campañas/2026-08-31-evaluacion/hallazgos.json /tmp/salida.jsonl

# una generación real del 1B por subproceso (fuerza el camino sin servidor)
LLAMA_MODO=subproceso python3 -c "from prototipo import justificador_llm as j; \
    import time; t=time.time(); print(j.generador_llama('Eres un analista. Explica: regla 5760 ssh')); \
    print(f'{time.time()-t:.1f} s')"
```

## Probar como en la máquina objetivo, desde el Acer (14/09/2026)

Se puede reproducir la **arquitectura** de producción en el Acer —servidores residentes + RAG en vivo— aunque
no su velocidad (GPU) ni la calidad del 8B (RAM). Son **dos palancas**:

**Palanca 1 — servidores residentes** (en vez del subproceso). El script arranca el 1B como generador (no hay
8B) y `bge-m3` como embedder; el código pasa a `generador_servidor`/`embedder_servidor`, la ruta **exacta** de
producción (plantilla de chat, temperatura por JSON, json-schema del agente, modelo cargado entre llamadas).

```bash
sh lab/scripts/llm-server.sh --embedder   # bge-m3 residente en :8082
sh lab/scripts/llm-server.sh              # 1B residente en :8080
```

**Palanca 2 — el modelo `bge-m3`** (para el RAG en vivo). No se versiona (`modelos/` es pesado); se baja una
vez (~606 MB) a `modelos/bge-m3-q8.gguf`. Se verificó que el modelo público de `gpustack/bge-m3-GGUF` (Q8_0)
**coincide con el índice versionado**: re-embeber una ficha y compararla con su vector guardado da coseno
**0,999485**, así que la recuperación es fiel **sin reindexar** (la diferencia es el ruido de cuantización que
`rag.py` ya documenta). Cabe en RAM junto al 1B (~2 GB de los 8).

### Qué demostró la prueba (y qué no)

Con las dos palancas activas se pasó un incidente real (fuerza bruta SSH, regla 5760) por la ruta de producción:

- **El RAG recupera en vivo los pasajes correctos.** La consulta agéntica del 1B + el embedder `bge-m3`
  residente + el coseno devolvieron las tres fichas defensivas pertinentes: `mitre-T1110` (Brute Force),
  `mapeo-acceso_credenciales` y `d3fend-D3-NTF` (Network Traffic Filtering). Comportamiento idéntico al de
  producción.
- **El 1B con RAG no sabe usar ese conocimiento sin alucinar, y el salvaguarda lo atrapa.** La justificación
  generada **falló la verificación de anclaje** (RNF-02) —los pasajes traen identificadores de técnicas
  vecinas y el 1B los narra como propios— y el sistema **degradó a la plantilla anclada** (RNF-09). Es decir:
  la tubería y las defensas funcionan; la pieza que falta es la **calidad del modelo**. Exactamente el motivo
  por el que la máquina objetivo usa el **8B** (con él la justificación con RAG sí ancla; medido en Fase 6).
- **El throttling térmico domina el tiempo.** Con el CPU ya caliente de la batería de pruebas, cada generación
  del 1B residente subió a ~60 s, así que la recuperación tardó **61,6 s** y el incidente completo **135,6 s**
  — más que el subproceso en frío (~75 s). La ventaja del servidor residente (10 s/generación con el CPU frío,
  medida antes) **se la come la refrigeración pasiva** bajo carga sostenida.

| Ruta en el Acer | 1 generación | Incidente `--con-llm` | RAG |
|---|---|---|---|
| Subproceso, CPU frío | ~14 s | ~75 s | sin pasajes (sin `bge-m3`) |
| **Residente, CPU frío** | **~10 s** | ~20–30 s (est.) | — |
| **Residente, CPU caliente (medido)** | **~60 s** | **135,6 s** | **3 pasajes en vivo** |
| Objetivo (8B+GPU, medido) | 0,4 s | 2,8 s | 3 pasajes en vivo |

**Conclusión del experimento:** el Acer sirve para **validar el flujo de producción de extremo a extremo**
(RAG real, anclaje, degradación, agente con salida restringida) — comportamiento y corrección, no tiempos ni
calidad de prosa. Para lo segundo hace falta la máquina objetivo (8B + GPU).

## El lazo humano de validación (etapa 9: aprobar / rechazar / reclasificar)

Cuando un incidente **requiere criterio humano** (RF-08), el daemon para y pregunta al analista con un
**menú cerrado numerado** (sin texto libre: sólo números, para que no entren typos ni clases inexistentes al
feedback — misma filosofía de catálogo cerrado que RF-15):

```
── Validación humana requerida ──
Activo: objetivo-vuln  ·  Origen: 192.168.1.10  ·  Servicio: ssh
Clase: vp_intento_acceso  ·  Prioridad: 3  ·  Confianza: 0.6
Justificación: Ráfaga de autenticaciones SSH fallidas desde 192.168.1.10 ...
Acción sugerida: BLOQUEAR_IP  ·  Impacto: localizado  ·  Filtro: retenida — espera tu aprobación
¿Qué hacer con este incidente?
  1) aprobar       — ejecuta la acción propuesta
  2) rechazar      — retiene sin ejecutar
  3) reclasificar  — corrige la clase
Elige [1-3]: 3
Nueva clase:
  1) fp_actividad_legitima
  2) fp_exposicion_inexistente
  3) no_soportada
Elige [1-3]: 1
```

Entrada inválida → repregunta; Enter en blanco → `rechazar` (seguro). El submenú de clase muestra las de
`analisis.CLASES` **menos la actual** del incidente (reclasificar es cambiarla, no repetirla). Qué hace cada
veredicto:

| Veredicto | ¿Ejecuta acción? | ¿Corrige la clase? | Nota |
|---|---|---|---|
| **1 · aprobar** | **Sí** (`accion_final`; aquí BLOQUEAR_IP = corta la IP de origen) | no | única que actúa sobre la red |
| **2 · rechazar** | no | no | veta la acción, deja la clase como está |
| **3 · reclasificar** | no | **sí** (feedback RF-12) | guarda `clase_reclasificada` en la traza; **NO** alimenta el RAG ni reentrena |

Los tres quedan en la traza encadenada por hash (RF-09), se ejecute o no. La reclasificación es feedback
auditable **sin reentrenamiento**: la misma alerta al día siguiente se clasifica igual y vuelve a preguntar —
la recurrencia se corta con un cambio de **configuración** (dar postura al auditor, añadir un origen a
`origenes_legitimos`, recalibrar umbrales), no con el motor mutándose solo (RNF-03, reproducibilidad).

### Provocar el lazo para probarlo

El lazo humano **se dispara con el perfil real**: en la campaña vigente, el **29,7 %** de las alertas (89 de
300) van al analista. Son las **20 ráfagas desde el origen de administración** (`192.168.1.1`), que la 6ª regla
clasifica como VP con confianza 0,6 para que un humano confirme antes de bloquear al admin, y las **69 cuyo
bloqueo recaería sobre el puesto de un empleado** (`192.168.1.10`, activo interno: el perfil exige humano para
bloquear lo propio, D16). Cualquier fuerza bruta desde el puesto abre el menú:

```bash
# una alerta (fuerza bruta SSH desde el puesto) por el daemon; --sin-llm lo hace instantáneo, el menú es idéntico
sed -n '188p' lab/campañas/2026-08-31-evaluacion/alerts.json | \
  python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml \
    lab/campañas/2026-08-31-evaluacion/hallazgos.json \
    --sin-llm --sin-lab --ventana-agrupacion 2 --salida /tmp/traza-menu.jsonl
```

El teclado responde por `/dev/tty` aunque la alerta entre por la tubería. Con `--con-llm` (y los servidores
residentes) se ve además la justificación LLM+RAG real, asumiendo ~2 min por incidente en el Acer.

## Conclusión operativa por máquina

- **Acer Aspire 3 (hoy):** para **trabajar**, `--sin-llm` (decisión completa e instantánea). Para **validar el
  flujo de producción**, arranca los servidores residentes + `bge-m3` y usa `--con-llm`: verás el RAG real y
  las defensas actuar, asumiendo ~1–2 min por incidente por el throttling y que el 1B degradará a plantilla.
- **Máquina objetivo:** deja **`--con-llm` siempre activo** (8B + `bge-m3` residentes, ~2,8 s/incidente). Es
  donde la justificación enriquecida y el RAG rinden como el diseño previó.
