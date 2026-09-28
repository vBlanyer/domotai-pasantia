# Banco de pruebas manual (docs + escenarios) y topología de firewall — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dividir la guía de pruebas en `docs/pruebas/`, añadir un catálogo categorizado de escenarios de ataque por familia y por comportamiento del sistema, y añadir una topología con firewall gestionable por SSH para ejercer la escalada real.

**Architecture:** Trabajo de **documentación + datos**, sin tocar el motor (`prototipo/*`). Los escenarios se disparan en **híbrido**: en vivo donde el lab lo permite (fuerza bruta SSH, telnet al IoT) e **inyección de alertas crudas** al daemon (`prototipo.stream -`) para los comportamientos controlados. Una topología nueva (`red-cliente-firewall`) clona la actual con el `borde` corriendo `sshd`+`msfadmin`, y `lab.sh` gana selector de topología.

**Tech Stack:** Markdown, Containerlab (`.clab.yml`), `sh` (lab.sh), Python CLIs ya existentes (`prototipo.stream`, `lab/scripts/*`). Verificación con corridas reales (no `unittest`, salvo la regresión de no-regresión).

**Spec:** `docs/superpowers/specs/2026-09-09-banco-pruebas-manual-y-topologias-design.md`

## Global Constraints

- **No se toca el motor** (`prototipo/*.py`): solo docs, un `.clab.yml` y `lab.sh`. La suite `unittest` debe seguir en verde (169+/33/28) — es red de no-regresión, no el objeto de prueba aquí.
- **Comportamientos reales del motor** (verificados en `analisis.clasificar` + `politica.proponer` + `perfil.filtrar` + `empresarial.yml`): la única acción propuesta hoy es `BLOQUEAR_IP` (localizado). Comportamientos alcanzables: **auto-bloqueo** (`permite`, conf 1.0), **confirmación humana** (`veta`+`requiere_humano`, conf 0.5), **FP** (`fp_actividad_legitima`/`fp_exposicion_inexistente`, sin acción), **`no_soportada`** (familia fuera de las 4). La **escalada a firewall** es del **agente** (`agente_mitigacion`), no del motor base. **No documentar "degradación"** como comportamiento del flujo base (no es alcanzable sin excepción de perfil).
- **Todo local** (RNF-01); las alertas de inyección usan solo campos que el adaptador Wazuh mapea.
- **Cada escenario del catálogo se verifica** ejecutándolo y pegando la salida real en el "Esperado".
- Commits terminan con `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## File Structure

- **Create** `docs/pruebas/README.md` — índice + convención + requisitos + arranque rápido (migrado de COMO-PROBAR).
- **Create** `docs/pruebas/01-motor.md` — Niveles 0–1 (migrado).
- **Create** `docs/pruebas/02-rag-evaluacion.md` — Nivel 2 (migrado).
- **Create** `docs/pruebas/03-lab-en-vivo.md` — Nivel 3 (migrado: lab, demos, daemon, multi-terminal).
- **Create** `docs/pruebas/04-escenarios-de-ataque.md` — **nuevo** catálogo por comportamiento.
- **Create** `docs/pruebas/05-topologias.md` — **nuevo** topologías.
- **Modify** `COMO-PROBAR.md` — reducir a índice corto que enlaza a `docs/pruebas/`.
- **Create** `lab/topologias/red-cliente-firewall.clab.yml` — clon con `borde` SSH-gestionable.
- **Modify** `lab/lab.sh` — selector de topología `up|down|status|test [topologia]`.
- **Modify** `README.md`, `prototipo/README.md` — actualizar enlaces a la guía.

---

## Task 1: Dividir la guía en `docs/pruebas/`

Migra el contenido actual de `COMO-PROBAR.md` a ficheros por categoría y deja `COMO-PROBAR.md` como índice.

**Files:** Create `docs/pruebas/{README,01-motor,02-rag-evaluacion,03-lab-en-vivo}.md`; Modify `COMO-PROBAR.md`.

- [ ] **Step 1: Crear `docs/pruebas/README.md`** con: título, la nota de convención (`<oblig>`/`[opc]`/`a|b`/`-`=stdin), la tabla "Requisitos por nivel" y el bloque "Arranque rápido" (copiados del COMO-PROBAR actual), y un índice:
  ```markdown
  - [01 · Motor sin dependencias](01-motor.md)
  - [02 · RAG y evaluación](02-rag-evaluacion.md)
  - [03 · Lab en vivo](03-lab-en-vivo.md)
  - [04 · Escenarios de ataque](04-escenarios-de-ataque.md)
  - [05 · Topologías del laboratorio](05-topologias.md)
  ```

- [ ] **Step 2: Mover** el bloque "Nivel 0" + "Nivel 1" del COMO-PROBAR actual a `docs/pruebas/01-motor.md` (con su encabezado y los bloques Sinopsis/Ejemplo/Esperado tal cual).

- [ ] **Step 3: Mover** el bloque "Nivel 2" (2.1 campana, 2.2 extractor, 2.3 rag, 2.4 banco) a `docs/pruebas/02-rag-evaluacion.md`.

- [ ] **Step 4: Mover** el bloque "Nivel 3" completo (3.0 lab up, 3.1–3.4 demos/daemon/agente, 3.5 multi-terminal) a `docs/pruebas/03-lab-en-vivo.md`. Ajusta las rutas relativas de enlaces (`../../README.md`, etc.) para que resuelvan desde `docs/pruebas/`.

- [ ] **Step 5: Reducir `COMO-PROBAR.md`** a un índice corto: una intro de 2 líneas + la lista de enlaces a `docs/pruebas/*` + el bloque "Arranque rápido". (No dupliques el contenido — vive en `docs/pruebas/`.)

- [ ] **Step 6: Verificar enlaces**
  Run: `for f in docs/pruebas/*.md COMO-PROBAR.md; do echo "== $f =="; grep -oE '\]\([^)]+\.md[^)]*\)' "$f"; done`
  Expected: los enlaces apuntan a ficheros existentes (revisar a ojo que las rutas relativas resuelven).

- [ ] **Step 7: Commit**
  ```bash
  git add COMO-PROBAR.md docs/pruebas/README.md docs/pruebas/01-motor.md docs/pruebas/02-rag-evaluacion.md docs/pruebas/03-lab-en-vivo.md
  git commit -m "docs(pruebas): dividir COMO-PROBAR en docs/pruebas/ por categoria + indice"
  ```

---

## Task 2: Catálogo de escenarios de ataque (`04-escenarios-de-ataque.md`)

El fichero nuevo, organizado **por comportamiento del sistema**, con cada escenario **verificado**.

**Files:** Create `docs/pruebas/04-escenarios-de-ataque.md`.

**Interfaces (comportamientos y disparadores — verificados contra el motor):**
- **A. Auto-bloqueo** — `vp_intento_acceso`, conf 1.0 (activo con postura expuesta), `BLOQUEAR_IP` → `permite`, `requiere_humano=false`.
- **B. Confirmación humana** — `vp_intento_acceso`, conf 0.5 (activo sin postura) → `veta`, `requiere_humano=true` → el daemon abre `[aprobar/rechazar/reclasificar]`.
- **C. Escalada a firewall** — vía **agente** (`demo-agente-escalado.py` o topología `red-cliente-firewall`): host inalcanzable → `BLOQUEAR_IP_FIREWALL`.
- **D. Falso positivo** — origen en `origenes_legitimos` (192.168.1.1) → `fp_actividad_legitima`, sin acción.
- **E. `no_soportada`** — familia fuera de las 4 (p. ej. `rootcheck`→`plataforma`) → `no_soportada`, sin acción.

- [ ] **Step 1: Verificar A (auto-bloqueo)** — inyección de credenciales contra activo con postura:
  ```bash
  printf '%s\n' '{"id":"A1","rule":{"id":"5760","level":10,"groups":["sshd","authentication_failed"],"mitre":{"id":["T1110.001"]}},"predecoder":{"hostname":"objetivo-vuln","program_name":"sshd"},"data":{"srcip":"192.168.1.10"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Failed password for root from 192.168.1.10"}' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
  ```
  Expected: `Clase: vp_intento_acceso … filtro permite … Ejecutadas: 1`. Anota la línea de decisión real en el doc.

- [ ] **Step 2: Verificar B (confirmación humana)** — activo desconocido (sin postura) → conf 0.5 → veta+humano; se pipea el veredicto para no colgar:
  ```bash
  printf '%s\nrechazar\n' '{"id":"B1","rule":{"id":"5760","level":10,"groups":["sshd","authentication_failed"],"mitre":{"id":["T1110.001"]}},"predecoder":{"hostname":"camara-desconocida","program_name":"sshd"},"data":{"srcip":"192.168.1.55"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Failed password for admin from 192.168.1.55"}' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
  ```
  Expected: aparece `── Validación humana requerida ──` y `filtro veta`; con `rechazar` → `Rechazadas: 1`, `Ejecutadas: 0`.

- [ ] **Step 3: Verificar D (FP admin legítimo)** — origen 192.168.1.1:
  ```bash
  printf '%s\n' '{"id":"D1","rule":{"id":"5760","level":10,"groups":["sshd","authentication_failed"],"mitre":{"id":["T1110.001"]}},"predecoder":{"hostname":"objetivo-vuln","program_name":"sshd"},"data":{"srcip":"192.168.1.1"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Failed password for root from 192.168.1.1"}' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
  ```
  Expected: `Clase: fp_actividad_legitima … accion None`; `Ejecutadas: 0`.

- [ ] **Step 4: Verificar E (`no_soportada`)** — familia fuera de perímetro (rootcheck):
  ```bash
  printf '%s\n' '{"id":"E1","rule":{"id":"510","level":7,"groups":["rootcheck"]},"predecoder":{"hostname":"objetivo-vuln","program_name":"rootcheck"},"data":{"srcip":"192.168.1.60"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Rootcheck: file integrity change"}' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
  ```
  Expected: `Clase: no_soportada … accion None`.

- [ ] **Step 5: Verificar C (escalada a firewall)** — el agente, sin lab:
  ```bash
  python3 lab/scripts/demo-agente-escalado.py --autonomo
  ```
  Expected: `escalado: True · dispositivo ejecutor: gateway` (host cae → `BLOQUEAR_IP_FIREWALL`).

- [ ] **Step 6: Escribir `04-escenarios-de-ataque.md`** con:
  - Una **matriz** (Comportamiento · Familia/técnica · Disparo · Qué observar).
  - Un bloque por comportamiento **A–E**, cada uno con: para qué sirve, el **comando de disparo** (los de arriba, más los **en vivo**: fuerza bruta SSH multi-terminal para A, y telnet al IoT `docker exec clab-red-cliente-puesto sh -c "nc -w3 192.168.1.20 23"` como servicio_expuesto), y el **Esperado** con la **salida real** capturada en los pasos 1–5.
  - Nota honesta: la escalada a firewall es del **agente** (no del daemon); la "degradación" del perfil no se alcanza en el flujo base actual (documentada como capacidad de config, no como escenario).

- [ ] **Step 7: Commit**
  ```bash
  git add docs/pruebas/04-escenarios-de-ataque.md
  git commit -m "docs(pruebas): catalogo de escenarios de ataque por comportamiento (A-E, verificados)"
  ```

---

## Task 3: Topología `red-cliente-firewall` + selector en `lab.sh`

Una topología con el `borde` gestionable por SSH (para escalada real) y `lab.sh` capaz de elegirla.

**Files:** Create `lab/topologias/red-cliente-firewall.clab.yml`; Modify `lab/lab.sh`.

- [ ] **Step 1: Crear `lab/topologias/red-cliente-firewall.clab.yml`** — copia de `red-cliente.clab.yml` con `name: red-cliente` **igual** (mismo prefijo de contenedores) y el nodo `borde` con `exec` ampliado:
  ```yaml
  # (idéntico a red-cliente salvo el nodo borde:)
    borde:
      labels: {graph-icon: router, graph-group: "Red del cliente", graph-level: 2}
      mgmt-ipv4: 172.20.20.100
      sysctls: {net.ipv4.ip_forward: 1}
      exec:
        - ip addr add 10.0.1.2/24 dev eth1
        - ip addr add 192.168.1.1/24 dev eth2
        # firewall gestionable: sshd + msfadmin (para el ejecutor del conector -> escalada real)
        - apk add --no-cache openssh sshpass
        - sh -c 'adduser -D msfadmin 2>/dev/null; echo msfadmin:msfadmin | chpasswd'
        - sh -c 'echo "msfadmin ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers'
        - ssh-keygen -A
        - sh -c '/usr/sbin/sshd'
  ```
  (El resto de nodos y `links`, idénticos a `red-cliente.clab.yml`.)

- [ ] **Step 2: Añadir selector de topología a `lab.sh`** — cambiar la línea fija por un argumento. Localiza:
  ```sh
  TOPO="$HERE/topologias/red-cliente.clab.yml"
  ```
  y sustitúyela por resolución del 2º argumento (default `red-cliente`), colocada tras leer `$1`:
  ```sh
  CMD="${1:-}"
  TOPOLOGIA="${2:-red-cliente}"
  TOPO="$HERE/topologias/${TOPOLOGIA}.clab.yml"
  ```
  Ajusta el `case` para usar `$CMD` en vez de `$1` si hiciera falta. `up)` sigue haciendo `containerlab deploy -t "$TOPO"`.

- [ ] **Step 3: Verificar sintaxis del `.clab.yml`**
  Run: `python3 -c "import yaml,sys; yaml.safe_load(open('lab/topologias/red-cliente-firewall.clab.yml')); print('YAML OK')"`
  Expected: `YAML OK`.

- [ ] **Step 4: Verificar arranque + borde gestionable** (si hay Docker/Containerlab; es el paso caro)
  ```bash
  sh lab/lab.sh down 2>/dev/null; sh lab/lab.sh up red-cliente-firewall
  docker exec clab-red-cliente-auditor sh -c 'sshpass -p msfadmin ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password msfadmin@192.168.1.1 "echo msfadmin | sudo -S iptables -L FORWARD -n"' && echo "✓ borde SSH+iptables OK"
  ```
  Expected: el `borde` acepta SSH y ejecuta `iptables -L FORWARD`. Si el entorno no está, anota que la verificación queda pendiente y continúa con la doc.

- [ ] **Step 5: Commit**
  ```bash
  git add lab/topologias/red-cliente-firewall.clab.yml lab/lab.sh
  git commit -m "feat(lab): topologia red-cliente-firewall (borde SSH-gestionable) + selector en lab.sh"
  ```

---

## Task 4: `05-topologias.md` + enlaces + regresión

Documenta las topologías y cierra los enlaces cruzados.

**Files:** Create `docs/pruebas/05-topologias.md`; Modify `README.md`, `prototipo/README.md`.

- [ ] **Step 1: Escribir `docs/pruebas/05-topologias.md`** — tabla de las topologías (`red-cliente`, `red-cliente-firewall`, `red-cliente-openwrt`, `smoke-test`): para qué sirve cada una, cuándo usarla, y cómo lanzarla:
  ```
  Sinopsis: sh lab/lab.sh ( up | down | status | test ) [topologia=red-cliente]
  Ejemplo:  sh lab/lab.sh up red-cliente-firewall   # escalada host->firewall real
  ```
  Incluye el mapa de nodos/IPs (de la cabecera de `red-cliente.clab.yml`) y qué escenario del §04 ejercita cada topología.

- [ ] **Step 2: Actualizar enlaces** — en `README.md` y `prototipo/README.md`, apuntar las referencias de "cómo probar" a `docs/pruebas/README.md` (además de/o en vez de `COMO-PROBAR.md`).
  Run: `grep -rn "COMO-PROBAR" README.md prototipo/README.md`
  Expected: revisar cada match y actualizar el texto/enlace.

- [ ] **Step 3: Regresión de no-regresión** (nada de código de motor cambió):
  Run: `for s in prototipo/tests lab/dataset/tests evaluacion/tests; do python3 -m unittest discover -s $s 2>&1 | grep -E "^(OK|FAILED)"; done`
  Expected: `OK` en las tres.

- [ ] **Step 4: Commit**
  ```bash
  git add docs/pruebas/05-topologias.md README.md prototipo/README.md
  git commit -m "docs(pruebas): guia de topologias + actualizar enlaces a docs/pruebas"
  ```

---

## Verificación (de punta a punta)

1. **Estructura:** `docs/pruebas/` tiene los 6 ficheros; `COMO-PROBAR.md` es un índice corto; los enlaces resuelven.
2. **Escenarios A–E:** cada uno corrido a mano da el comportamiento declarado (salida real pegada en el §04).
3. **Topología:** `red-cliente-firewall.clab.yml` es YAML válido y (si el entorno está) arranca con el `borde` aceptando SSH + `iptables FORWARD`.
4. **No-regresión:** las tres baterías `unittest` en verde (no se tocó el motor).

## Self-Review (hecho)

- **Cobertura del spec:** split docs → Task 1; catálogo por comportamiento → Task 2; topología + selector → Task 3; guía de topologías + enlaces → Task 4. La corrección honesta (no hay "degradación" alcanzable; escalada = agente) está en Global Constraints y Task 2.
- **Sin placeholders:** cada escenario trae su JSON/commando real; la topología trae el `exec` concreto del `borde`.
- **Consistencia:** el `name: red-cliente` se mantiene en la topología nueva para no romper los nombres `clab-red-cliente-*` que usan los scripts y el conector; `lab.sh` resuelve el fichero por `[topologia]` pero los contenedores conservan el prefijo.
- **Riesgo anotado:** el Step 3.4 (arranque real) depende de Docker/Containerlab; si no está disponible se marca pendiente sin bloquear la doc.
```
