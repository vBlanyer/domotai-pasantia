# Arreglos de la revisión del 15/11 — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Estado (16/11/2026): pendiente.** Alcance acordado con el usuario: #13, los arreglos rápidos (#17, #14,
> #15, #22, #4), #1 y #2 de [`OBSERVACIONES-REVISION.md`](../../OBSERVACIONES-REVISION.md). El resto queda
> como recomendación o para la fase de AWS. Commits locales en `main`, sin push.

**Goal:** Cerrar la escalada a root del conector (#13), dejar la CI en verde y quitar los fallos pequeños de la consola, no perder en silencio las aprobaciones pendientes al reiniciar (#1) y reindexar el RAG (#2).

**Architecture:** #13 sustituye las reglas `sudo` con comodines por **un envoltorio** `/usr/local/sbin/mdr-accion` (sh POSIX, generado desde el catálogo) que valida cada argumento por tipo y ejecuta el comando exacto; el sudoers solo permite ese envoltorio. La deriva se mide preguntando al envoltorio (`--reglas`). #1 encadena un registro `pendiente` al encolar y avisa al arrancar de los que quedaron sin resolver.

**Tech Stack:** Python 3 (stdlib + PyYAML), sh POSIX, unittest; React/TS + vitest; Containerlab para la validación en vivo.

**Spec:** [`OBSERVACIONES-REVISION.md`](../../OBSERVACIONES-REVISION.md) (puntos 1, 2, 4, 13, 14, 15, 17, 22).

## Global Constraints

- El motor de decisión no cambia: `evaluacion/tests` debe dar las mismas cifras.
- La frontera de privilegio en el equipo es **exactamente** el catálogo: ningún argumento fuera de las plantillas, ningún token de más, ninguna cuenta del sistema (`perfil.CUENTAS_DEL_SISTEMA`).
- El envoltorio funciona con cualquier sudo (también 1.6.9 de Metasploitable): nada de expresiones regulares de sudo ≥ 1.9.10.
- El modo contraseña del laboratorio (`ejecutor_ssh_lab`, Metasploitable con sudo completo) no cambia.
- Fail-closed: un argumento que no encaja → código 126 y nada ejecutado.
- Contrato de capas (`test_arquitectura`). Commits locales en `main`, sin push.

## Review Focus

1. **Inyección por un argumento con espacios** (`1.2.3.4 --modprobe=/tmp/x`): el envoltorio recibe argv separados por `sudo`; un argumento con espacio o un token de más se rechaza. → `test_envoltorio_rechaza_tokens_de_mas`, `test_envoltorio_rechaza_argumento_con_espacio` (tarea 3).
2. **Cuentas del sistema y servicios fuera de la lista del papel**: `passwd -l root` y `service sshd stop` sin lista se rechazan. → `test_envoltorio_cuentas_y_servicios` (tarea 3).
3. **Equipo dado de alta con el sudoers antiguo** (antes de este cambio): la prueba de Conectividad lo marca como deriva («falta el envoltorio») y el recorte «acción no ejecutable» no intenta acciones en él. → `test_deriva_sin_envoltorio` (tarea 4).
4. **Reinicio con varias tarjetas pendientes y alguna ya resuelta**: solo las no resueltas se avisan como perdidas. → `test_pendientes_perdidas_al_arrancar` (tarea 2).
5. **Cuerpo POST que no es un objeto** en cualquier ruta: 400, nunca 500. → `test_post_cuerpo_no_objeto` (tarea 1).

---

### Tarea 1: arreglos rápidos (#17, #14, #15, #22, #4)

**Files:** `prototipo/tests/test_receptor.py`, `prototipo/servicio/tablero.py`, `prototipo/servicio/stream.py`, `visor/src/attack.ts`; Test: `prototipo/tests/test_tablero.py` (o uno nuevo `test_revision_15_11.py`)

- [ ] **#17:** `test_una_ip_no_monopoliza_los_slots` reintenta el envío de la segunda conexión hasta un plazo (p. ej. 2 s) en lugar de suponer la liberación inmediata. Verificar con 20 ejecuciones seguidas en una máquina cargada (la suite completa en paralelo).
- [ ] **#14:** `test_cabeceras_anti_clickjacking`: toda respuesta (API, estáticos, 404) lleva `X-Frame-Options: DENY` y `Content-Security-Policy: frame-ancestors 'none'`. Implementar en el único punto de salida de cabeceras del manejador.
- [ ] **#15:** `test_banner_avisa_consola_abierta`: sin `TRIAJE_CONSOLA_TOKEN` ni `TRIAJE_CONSOLA_OPERADORES`, el arranque con `--web` imprime `[inicio] consola SIN autenticación: …`.
- [ ] **#22:** `test_post_cuerpo_no_objeto`: `POST /api/pausa`, `/api/aprobar`, `/api/caso`, `/api/watchlist` con `[]` → 400. Comprobar `isinstance(cuerpo, dict)` una vez tras el `json.loads` del POST (y JSON inválido → 400).
- [ ] **#4:** comentario de `visor/src/attack.ts:4` («8 familias» → 10).
- [ ] Suite del prototipo y del visor; commit `fix: arreglos rápidos de la revisión del 15/11`.

### Tarea 2: aprobaciones pendientes en la traza (#1)

**Files:** `prototipo/servicio/stream.py`, `prototipo/servicio/tablero.py` (`_NO_DECISIONES`), `visor/src/datos.ts`, `visor/src/trazas.ts`, `visor/src/aprobaciones.ts`; Test: `prototipo/tests/test_pendientes_en_traza.py`, vitest

**Interfaces:** registro `{"tipo": "pendiente", "id_decision", "timestamp", "id_cola", "activo", "origen_ip", "clase", "accion_final", "prioridad"}` al encolar (decisión y escalada diferida); al arrancar, por cada `pendiente` sin un registro posterior con el mismo `id_decision` que no sea `pendiente` (la decisión resuelta, un descarte), un registro `{"tipo": "pendiente_perdida", "id_decision", "timestamp", "motivo": "el servicio se reinició antes de resolverla"}` y la línea `[inicio] N aprobación(es) pendiente(s) se perdieron al reiniciar: …`. Función pura `pendientes_sin_resolver(registros) -> list[dict]`.

- [ ] Tests: `test_al_encolar_queda_en_la_traza`, `test_pendientes_perdidas_al_arrancar` (una resuelta, una descartada y dos sin resolver → dos avisos), `test_no_cuentan_como_decision`, y vitest: `pendiente`/`pendiente_perdida` son de sistema con su descripción.
- [ ] Implementar; las cifras de la evaluación no cambian (`evaluacion/tests`).
- [ ] Commit `fix(traza): las aprobaciones pendientes quedan en la traza y se avisan si se pierden (#1)`.

### Tarea 3: el envoltorio `mdr-accion` (#13)

**Files:** `prototipo/accion/catalogo.py` (`envoltorio(catalogo, allowlist=None) -> str`, `sudoers_envoltorio(usuario) -> str`, CLI `--envoltorio`), Test: `prototipo/tests/test_envoltorio.py`

Tipos de argumento por parámetro del catálogo: `{ip}`, `{ip_nodo}` → IPv4 o IPv4/prefijo; `{puerto}` → 1–65535; `{if}` → `[A-Za-z0-9._-]{1,15}`; `{rate}` → número + `bit|kbit|mbit|gbit`; `{servicio}` → nombre, y si hay lista del papel, de la lista; `{usuario}` → nombre, nunca una cuenta del sistema, y si hay lista, de la lista; `{respaldo}`/`{respaldo_previo}` → nombre. Literales, iguales. Uso: `mdr-accion --reglas` (imprime las plantillas, una por línea, en el formato de `catalogo.reglas`) y `mdr-accion <binario> <args…>` (`exec` del binario con `PATH=/usr/sbin:/usr/bin:/sbin:/bin`). Sudoers: `triaje ALL=(root) NOPASSWD: /usr/local/sbin/mdr-accion`.

- [ ] Tests (ejecutan el envoltorio con `sh` y un `PATH` de binarios falsos que registran su argv): `test_envoltorio_permite_lo_legitimo` (cada acción del catálogo con parámetros válidos), `test_envoltorio_rechaza_tokens_de_mas` (`--modprobe=/tmp/x`, `-j ACCEPT -j DROP`), `test_envoltorio_rechaza_argumento_con_espacio`, `test_envoltorio_cuentas_y_servicios` (`passwd -l root`, `daemon`, servicio fuera de la lista), `test_reglas_coinciden_con_el_catalogo`, `test_sudoers_solo_permite_el_envoltorio`, y que pase `shellcheck` si está disponible.
- [ ] Implementar; commit `feat(conector): envoltorio mdr-accion: la frontera de privilegio es exactamente el catálogo (#13)`.

### Tarea 4: el conector, la prueba de Conectividad y el alta usan el envoltorio

**Files:** `prototipo/accion/conector.py` (modos clave y directo: `sudo -S /usr/local/sbin/mdr-accion <comando>`), `prototipo/accion/conectividad.py` (`reglas_de_envoltorio(texto)`, la prueba compara `--reglas` y exige que `sudo -l` solo permita el envoltorio; paquete de alta script/ansible/sudoers instala el envoltorio), `prototipo/servicio/conectividad_web.py`, `prototipo/accion/fallos.py` (recorte acción no ejecutable), `lab/scripts/aprovisionar-minimo-privilegio.sh`; Tests existentes de conector, conectividad, fallos y aprovisionamiento ajustados + nuevos

- [ ] Tests: `test_comando_con_envoltorio` (clave y directo; contraseña sin cambios), `test_deriva_sin_envoltorio`, `test_deriva_envoltorio_con_reglas_de_mas`, `test_paquete_instala_el_envoltorio` (los tres formatos; idempotente; 0755 root), `test_aprovisionar_instala_el_envoltorio`.
- [ ] Implementar.
- [ ] **Verificación en vivo** (preguntar antes al usuario: hay que bajar el banco si está en uso): en la oficina, alta de un equipo con el paquete nuevo, `sudo -n -l` como `triaje` muestra solo el envoltorio, `sudo mdr-accion iptables -A INPUT -s 1.2.3.4 --modprobe=/tmp/x -j DROP` → 126, y `oficina.sh atacar` acaba en una contención verificada. En el banco, `banco.sh aprovisionar` + `banco.sh test` + un ataque contenido.
- [ ] Commit `feat(conector): el conector, la prueba y el alta usan el envoltorio`.

### Tarea 5: el índice del RAG (#2)

**Files:** `prototipo/corpus/indice.json`; Test: `prototipo/tests/test_rag_indice.py`

- [ ] `test_indice_cubre_el_corpus`: los `id` de `corpus.jsonl` y de `indice.json` coinciden (sin modelo). Verla fallar (faltan 3).
- [ ] Reindexar con `python3 -m prototipo.explicacion.rag --indexar` (embedder local `bge-m3`). Verla pasar. El banco de recuperación (`sec:mrr`) se vuelve a medir y se anota si cambia.
- [ ] Commit `fix(rag): reindexar el corpus (35 fichas) y una prueba que lo vigila (#2)`.

### Tarea 6: documentación

- [ ] `OBSERVACIONES-REVISION.md`: estado de cada punto (hecho, con commit, o recomendación).
- [ ] Manual de producción y de usuario (Conectividad: el paquete instala el envoltorio; la prueba muestra la deriva), `integracion-en-produccion.md` (frontera de privilegio), `CHANGELOG.md`, `RUNBOOK.md` si cambia el aprovisionamiento.
- [ ] Commit `docs: revisión del 15/11 aplicada`.

## Fuera de este plan

AWS (#6–#12, #18, #19), #3 (fichas nuevas del RAG), #5 y #16 (rotación de la traza), #20 (systemd), #21 (copias y sondas), #23 (CI). Quedan como recomendación con su análisis en `OBSERVACIONES-REVISION.md`. El informe se actualiza solo si el usuario lo pide.
