# 07 · Roadmap del pipeline y latencia medida (qué pasa detrás de cada incidente)

Recorre el camino completo de una alerta, **de la ingesta a la acción**, dice **qué ocurre detrás** de cada
etapa y **cuánto tarda** en cada perfil de hardware. Complementa a [06 · Rendimiento y hardware](06-rendimiento-y-hardware.md)
(que se centra en los modos y el hardware objetivo): aquí el foco es el **flujo por etapas** y una **medición
nueva en el Acer Aspire 3** (la máquina de trabajo de hoy), tomada el 14/09/2026.

## Las tres máquinas de referencia

| Perfil | CPU / RAM / GPU | Modelos que sostiene | Papel |
|---|---|---|---|
| **Acer Aspire 3 (hoy)** | CPU móvil, **8 GB** (11 GiB en WSL2), **sin GPU** | solo el **1B por subproceso**; sin `bge-m3`, sin 8B | desarrollo e iteración deterministas |
| **Portátil 16 GB (histórico)** | CPU sin GPU, 16 GB | 1B por subproceso, `bge-m3` por subproceso | mediciones de la Fase 6 |
| **Objetivo (9800X3D + RTX 5070)** | Zen5, **12 GB VRAM** | **8B residente + `bge-m3` residente** | producción / demos cómodas |

**El stack de producción íntegro** (generador 8B residente + embedder `bge-m3` residente + índice vectorial
+ orquestador) **solo corre en la máquina objetivo**. En el Acer de hoy corre el **perfil degradado**
(RNF-09): el 1B por subproceso genera la justificación y, al **faltar el modelo `bge-m3`**, la recuperación
RAG devuelve `[]` sin romper (guardia de dimensión y degradación limpia), así que la justificación se produce
**sin pasajes**. La decisión de seguridad es idéntica en las tres máquinas.

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
3. **El RAG no está disponible aquí, y degrada limpio.** Sin el modelo `bge-m3` en `modelos/`, el embedder
   devuelve `[]` en 0,1 s y el justificador sigue **sin pasajes** (RNF-09) en vez de romper. La guardia de
   dimensión de `recuperar()` (índice a 1024-d) evita cualquier recuperación con vectores incompatibles.
4. **Aun degradado, el 1B ancla.** La justificación generada supera la verificación de anclaje (RNF-02): la
   traza registra `justificador=llm-6:llama-3.2-1b-q4.gguf`, no la plantilla. La calidad es pobre (es un 1B
   sin RAG), pero está anclada a los datos de la alerta.

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

## Conclusión operativa por máquina

- **Acer Aspire 3 (hoy):** trabaja en **`--sin-llm`**. La decisión, la política, el perfil y la traza —lo que
  importa— son instantáneos y completos. El LLM aquí es un 1B degradado a ~75 s/incidente y sin RAG: sirve
  para verificar que la tubería LLM enchufa, no para juzgar la calidad de la explicación.
- **Máquina objetivo:** deja **`--con-llm` siempre activo** (8B + `bge-m3` residentes, ~2,8 s/incidente). Es
  donde la justificación enriquecida y el RAG rinden como el diseño previó.
