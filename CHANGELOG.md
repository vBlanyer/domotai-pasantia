# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Las **cifras canónicas de la evaluación** (clasificación, priorización, continuidad de v1.0) **no
se mueven** entre versiones: todo lo posterior a v1.0 se diseñó para no alterarlas (ver el informe,
capítulo de resultados, y `evaluacion/resultados/`).

## [No publicado] — sobre v1.1 (2026-10-14 → 2026-10-20)

Extensiones de cobertura y de consola posteriores a v1.1, en `main` pero **sin etiquetar**. No
tocan el motor de decisión evaluado, así que el canónico sigue intacto.

### Añadido
- **Familias 6 a 10** (de 5 a **10**), cada una con su patrón de respuesta del catálogo cerrado:
  - integridad de ficheros / FIM → `AISLAR_NODO` (cuarentena en el borde).
  - denegación de servicio / DoS → `LIMITAR_BANDA` (contención gradual).
  - acceso consumado (login tras fuerza bruta) → `MATAR_CONEXION` (cortar la sesión viva).
  - exfiltración / C2 → `BLOQUEAR_DESTINO` (bloquear el egreso al destino en el borde).
  - malware / rootkit → `AISLAR_NODO`.
- **Consola MDR**: aviso al analista (notificación del navegador + distintivo en la pestaña + SLA
  «pendiente desde hace X» en la cola) y **ciclo de vida del caso** (estado nuevo→en revisión→
  resuelto, responsable y notas, como registros `actualizacion_caso` encadenados).
- **Matriz ATT&CK por cobertura de familia** en el visor; el lanzador del banco cubre las 10 familias.
- Escalada a **revisión humana de un `no_soportada` grave** (opt-in del perfil).
- **Barrido del umbral de confianza (RF-07)**: curva escalado↔bloqueos indebidos y su lectura
  (`evaluacion/resultados/barrido-umbral.md`).
- Documentación: `STRUCTURE.md`, cuadro de alcance (§8 de estado-y-riesgos), este `CHANGELOG.md`.

### Cambiado
- Limpieza de estructura: `documentacion/archivo/` → `documentacion/material-superado/`; archivo de
  proceso reubicado; `README`/informe al día (10 familias y cifras de tests actuales).
- Agente ReAct: optimalidad validada con un modelo capaz y reproducibilidad probada (documentado).

### Corregido
- Hallazgos de revisión adversarial (Opus) por familia: verificación invertida de acciones
  transitorias; `AISLAR_NODO` que no se ejecutaba; veto de gestión/anti-self-DoS en
  `BLOQUEAR_DESTINO`; `/api/trazas` ahora arrastra los campos del ciclo de caso.
- **Dos caídas del daemon** (auditoría 20/10): una línea de JSON con anidamiento hostil (bajo el
  tope de 1 MiB) lanzaba `RecursionError` fuera del `except`, y un lote con timestamps de zona
  mixta (aware+naive) rompía la agrupación fuera de la barrera. El parseo tolerante de línea JSONL
  vive ahora en un solo sitio (`ingesta.parsear_linea`, usado por todas las fronteras) y la
  agrupación normaliza la zona con el mismo patrón que la ráfaga (`rafaga._instante`).

### Seguridad / Robustez
- **Receptor de red**: cierre de la conexión ociosa (15 min sin datos: una conexión muda ya no
  retiene su slot), tope de conexiones **por IP** (8: un emisor comprometido no monopoliza los 64
  slots), rechazos y cierres **con rastro** en el log (frenado: uno por minuto y motivo),
  `--permitir` **obligatorio al escuchar fuera de loopback** (fail-closed) y **mTLS opcional**
  (`--tls-ca`: exige certificado de cliente — autentica al emisor, no solo cifra).
- **Cola de pendientes acotada** (tope 500): un atacante que fabrique claves infinitas (un `srcip`
  distinto por alerta) ya no agota la memoria; al tope se desaloja la tarjeta menos severa y más
  vieja (nunca una en curso), contado y con aviso.

## [1.1] — 2026-10-14 · Endurecimiento, robustez y congruencia

Sobre v1.0, **sin mover las cifras canónicas** (V1.1 no re-basa v1.0).

### Añadido
- Autenticación **opcional** de la consola por token (`TRIAJE_CONSOLA_TOKEN`) y **no repudio** del
  operador en la traza.
- Señal de vigilancia *low-and-slow* (asesora; adaptación B de la recomendación #1 del informe).
- Recomendaciones del informe: **#2** (clase propia del reconocimiento, versión segura) y **#3**
  (invariante de cobertura del corpus de descarte).

### Seguridad / Robustez
- Pool de hilos acotado del modo agente, entorno filtrado al conector, HMAC opcional de la cadena de
  la traza, conector *fail-closed*, frontera de `stdin` segura (del pentest del propio MDR, 19
  hallazgos; se cerraron los de severidad crítica/alta/media).

## [1.0] — 2026-10-13 · Entrega final de la pasantía

Hito funcional y de evaluación.

### Añadido
- **Motor de triaje**: ingesta → clasificación → política determinista → filtro del perfil de
  cliente → traza encadenada → acción con validación humana. **El LLM justifica, no decide.** 5 familias.
- **Justificador LLM + RAG local** (1B por defecto; 8B en GPU como objetivo), **daemon en vivo**,
  **visor web** (consola SOC), **laboratorio Containerlab** con Wazuh, **dataset etiquetado** (600
  alertas) y **marco de evaluación** frente al baseline de reglas.
- Traza auditable (cadena de hashes, RF-09), kill switch, reversión, `/healthz`, kit de despliegue
  systemd.

### Limitaciones conocidas
- **Clasificador con ajuste fino bloqueado** por falta de un dataset suficientemente variado (la
  empresa no lo aportó): el clasificador es un árbol de decisión, no un codificador entrenado.
- Ejecutar el **LLM 8B** como justificador exige una máquina con **GPU** (el portátil de desarrollo
  no puede): `EVALUAR-LLM-EN-GPU.md`.
