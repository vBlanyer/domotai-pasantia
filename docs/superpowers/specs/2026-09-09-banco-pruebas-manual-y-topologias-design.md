# Banco de pruebas manual (docs + escenarios de ataque) y topología de firewall — Diseño

**Fecha:** 2026-09-09 · **Estado:** aprobado en chat, listo para plan de trabajo.

## Contexto y objetivo

La guía `COMO-PROBAR.md` creció a un solo fichero y no cubre pruebas **manuales por familia de ataque** ni
las distintas **respuestas del sistema** (auto-bloqueo, confirmación humana, escalada a firewall,
`no_soportada`, FP de admin legítimo). Además el laboratorio tiene una sola topología efectiva y la
escalada host→firewall solo se demuestra **simulada**. Objetivo: dividir la guía por tipo de prueba,
añadir un **catálogo categorizado de escenarios de ataque** para practicar a mano, y añadir **una topología
nueva** que permita ejercer la escalada a firewall **real**.

## Decisiones (fijadas con el usuario)

1. **Docs:** carpeta `docs/pruebas/` con un MD por categoría; `COMO-PROBAR.md` queda como índice corto.
2. **Escenarios:** **híbrido** — en vivo donde el lab lo permite (fuerza bruta SSH a la víctima; telnet al
   IoT), e **inyección de alertas crudas** al daemon para los comportamientos que requieren control exacto
   (escalada, confirmación humana, `no_soportada`, FP legítimo).
3. **Topología:** **una** nueva (`red-cliente-firewall`) con el `borde` gestionable por SSH, para escalada
   host→firewall real. `lab.sh` gana selector de topología.

## 1. Estructura de documentos

`COMO-PROBAR.md` → índice corto que enlaza a:

- `docs/pruebas/README.md` — índice, convención de sintaxis (`<oblig>`/`[opc]`/`a|b`/`-`=stdin), requisitos por nivel, arranque rápido.
- `docs/pruebas/01-motor.md` — Nivel 0 (unittest) + Nivel 1 (triaje, ingesta RF-01, agrupación RF-11). Sin dependencias.
- `docs/pruebas/02-rag-evaluacion.md` — extractor ATT&CK, `rag --indexar/--consulta`, `evaluacion.campana`, banco de simulación.
- `docs/pruebas/03-lab-en-vivo.md` — levantar lab, demos (lazo-vivo, validación-humana, agente-escalado), daemon, y multi-terminal monitoreo vs ataque.
- `docs/pruebas/04-escenarios-de-ataque.md` — **nuevo**, el catálogo (§2).
- `docs/pruebas/05-topologias.md` — **nuevo**, las topologías y cuándo usar cada una (§3).

Cada fichero conserva el patrón **Sinopsis + Ejemplo + Esperado**. Se actualizan los enlaces a
`COMO-PROBAR.md` en `README.md` y `prototipo/README.md`.

## 2. Catálogo de escenarios de ataque (`04-escenarios-de-ataque.md`)

Matriz (familia · técnica · comportamiento · disparo · qué observar) + un bloque por escenario. Los siete:

| # | Familia / técnica | Comportamiento esperado | Disparo |
|---|---|---|---|
| 1 | acceso_credenciales · T1110.001 | **auto-bloqueo** (`permite`, `requiere_humano=false`) | vivo: fuerza bruta SSH puesto(.10)→víctima(.30) |
| 2 | acceso_credenciales · activo sin postura | **confirmación humana** (confianza 0.5 → veta) | inyección de alerta cruda |
| 3 | servicio_expuesto · telnet · T1133 | **degrada + confirmación humana** (alcanza servicio) | vivo: telnet al IoT(.20) |
| 4 | explotacion_conocida · T1190 | **confirmación humana** | inyección |
| 5 | cualquiera, víctima inalcanzable | **escalada a firewall** (`BLOQUEAR_IP_FIREWALL`) | topología `red-cliente-firewall` / `demo-agente-escalado.py` |
| 6 | admin declarado (origen 192.168.1.1) | **FP, no ejecuta** (`fp_actividad_legitima`) | inyección |
| 7 | fuera de perímetro (familia no atacante) | **`no_soportada`**, conserva severidad | inyección |

Cada escenario de inyección trae su **JSON de alerta cruda de Wazuh** listo para
`printf '%s\n' '<json>' | python3 -m prototipo.stream - <perfil> --sin-lab --ventana-agrupacion 0`.
**Validación:** en la implementación se corre cada escenario y se confirma que la traza da la
`clase`/`accion_final`/`resultado_filtro`/`requiere_humano` declarados (red de seguridad; sin esto el
catálogo no se da por bueno).

## 3. Topología nueva y selector en `lab.sh`

- **`lab/topologias/red-cliente-firewall.clab.yml`** — clon de `red-cliente.clab.yml`; el nodo `borde`
  añade en su `exec`: `apk add openssh sshpass`, crea `msfadmin/msfadmin`, arranca `sshd`. Así el conector
  (`ejecutor_ssh_lab`, que usa `msfadmin@<ip>`) puede empujar `iptables -A FORWARD -s <ip> -j DROP` al
  firewall → **escalada real**. El resto de nodos y enlaces, idénticos.
- **`lab.sh`**: `up`/`down`/`status`/`test` aceptan `[topologia]` (default `red-cliente`); resuelve
  `lab/topologias/<topologia>.clab.yml`. La provisión de `borde` (si aplica) va en el propio `exec` de la
  topología, así que `lab.sh up` no necesita lógica condicional nueva más allá de elegir el fichero.
- El perfil `empresarial.yml` ya declara `topologia.gateway.ip: 192.168.1.1` (= `borde`), así que el agente
  no cambia.

## Validación (cómo se prueba)

1. **Suite en verde** (sin tocar el modelo): `python3 -m unittest discover -s prototipo/tests` (+ dataset + evaluacion) — el cambio es docs + datos + topología; cero código de motor.
2. **Escenarios de inyección:** cada uno corrido a mano confirma su comportamiento declarado (clase/acción/filtro/humano) — se documenta el "Esperado" con la salida real.
3. **Escenarios en vivo:** fuerza bruta SSH → alerta 5760 (ya validado hoy); telnet al IoT → alerta/observación.
4. **Topología nueva:** `sh lab/lab.sh up red-cliente-firewall` arranca; el `borde` acepta SSH y `iptables -A FORWARD`. (End-to-end con víctima "caída" se declara incremental.)

## Fuera de alcance (YAGNI)

- No se modifica el motor (`prototipo/*`), solo docs, un `.clab.yml` y `lab.sh`.
- Una sola topología nueva (no residencial ni multi-segmento por ahora).
- No se automatiza el disparo de escenarios (son comandos manuales, ese es el punto).
