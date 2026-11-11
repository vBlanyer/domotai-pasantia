# Validación en el banco de los recortes ante fallos de contención (11/11/2026)

Recomendación R8 de [recomendaciones-y-orden.md](../../../documentacion/00-general/recomendaciones-y-orden.md);
recortes de las fases 4–6 del
[plan de fallos](../../../documentacion/05-fase5-implementacion-del-prototipo/plan-manejo-fallos-contencion.md).

**Método.** Banco recreado (`down` → `up` → `aprovisionar` → `test` en verde). Un daemon propio en `:8791`, con su
traza aparte, lee las alertas de Wazuh. En cada caso se provoca el fallo en el equipo
(`python3 -m lab.banco.fallos provocar …`), se lanza un ataque real desde una IP de origen nueva y se mide
desde el lanzamiento hasta que la decisión queda escrita en la traza (incluye la latencia de Wazuh). Se
repite con los cinco interruptores a `0` y a `1`. Arnés: [`lab/banco/validar_recortes.py`](../../../lab/banco/validar_recortes.py).

## Parte A — recortes sin contexto de la consola (`FALLO_RAPIDO`, `MEMORIA_FALLOS`)

Ataque: fuerza bruta SSH (caso D1) contra web-banking; «sshd parado», telnet contra atm (con el sshd del
equipo parado una fuerza bruta SSH no deja rastro). Segundos hasta la decisión en la traza.

| Caso | Apagados | Encendidos | Desenlace (los dos modos) |
|---|---|---|---|
| Sin fallo | 11,0 | 10,9 | Contenido y verificado en el equipo |
| F5 — el equipo descarta el SSH del MDR (E1) | 32,0–34,0 | 17,9–20,0 | Contenido en fw-core |
| F5 — sshd parado (atm) | 13,4 | 13,3 | Contenido en fw-core |
| F4 — clave del conector borrada | 14,9 | 12,9 | Contenido en fw-core |
| F3 — clave del host regenerada | 15,0 | 14,9 | Contenido en fw-core; causa F3 en los dos |
| F8 — contramedida que borra la regla | 15,0 | 15,1 | Contenido en fw-core; causa F8 en los dos |
| F5 cuatro veces seguidas | 34,1 · 31,0 · 30,0 · 30,9 | 17,9 · 13,2 · 13,4 · **7,3** | Contenido en fw-core; el 4.º, con la memoria abierta, no se intenta en el equipo (`omitido: sin_acceso`) |

- **Ninguna contención se pierde** con los recortes encendidos.
- **Memoria de fallos:** se abre al tercer fallo («el MDR no tiene acceso a 10.10.0.10 … 3 fallos seguidos, F5»)
  y se cierra sola tras deshacer el fallo («el MDR recupera el acceso»), dentro de los 75 s observados. Por
  diseño (sondeo cada 15 s de equipos con 60 s sin probar) tarda entre 60 y 75 s, algo más que los
  «menos de 60 s» del criterio del plan.
- **F3 y F8** (pueden ser un ataque) dan la misma causa, el mismo desenlace y el mismo tiempo en los dos modos.

**Decisión (11/11):** los cinco recortes pasan a **encendidos por defecto** (`fallos.VALIDADOS`; se apagan
con `=0`). Ver también la parte B.

**Incidencias del laboratorio corregidas por el camino** (no del MDR):
- `lab/banco/fallos.py`: `pkill -x sshd` no encontraba el sshd del banco (se renombra a
  `sshd: /usr/sbin/sshd … [listener]`), así que «sshd» no paraba nada y «clave-host» no recargaba.
- Tras regenerar la clave del host, el atacante conservaba la huella vieja y OpenSSH desactivaba la
  contraseña: la fuerza bruta no dejaba rastro. El arnés borra esa huella en el atacante antes de cada ataque.
- La contramedida de `fallos.py` borra reglas de `192.0.2.0/24`; el atacante del banco usa `198.51.100.0/24`.
  El arnés usa una variante con el rango del atacante.

## Parte B — recortes que dependen de la consola

Antes de cada modo, «Probar» de Conectividad sobre web-banking (opt-in de laboratorio
`TRIAJE_CONECTIVIDAD_ABIERTA=1`): verificada, y su sudoers no tiene `ss -K dst *` (el nodo no trae `ss`). «Sin
huella fijada» = la huella del equipo quitada del `known_hosts` del conector (con copia, repuesta al terminar).
La primera tanda se interrumpió por un cierre de WSL (11:26) y se repitió con el banco recreado
(`parte-b.log`); F6 se repitió aparte (`f6/`) porque la regla 5763 de Wazuh calla 60 s tras dispararse y,
sin ella, la correlación de intrusión (40112 → 100600) no salta: ahora el arnés espera 70 s antes de ese ataque.

| Recorte | Caso | Apagado | Encendido |
|---|---|---|---|
| `PRECHECK_APROVISIONADO` | F2 — web-banking sin huella fijada (D1) | 5,3 s · se intenta, falla (F2) · contenido en fw-core | 6,3 s · **no se intenta** (`omitido: sin_aprovisionar`, F2) · contenido en fw-core |
| `ESCALADA_SOLO_APROVISIONADOS` | E1 en web-banking + fw-core sin huella fijada | 30,4 s · fw-core falla (rc 255) · contenido en fw-edge | **15,4 s** · «salto omitido: fw-core sin aprovisionar» · contenido en fw-edge |
| `ACCION_NO_EJECUTABLE` | F6 — acceso consumado → `MATAR_CONEXION` sin `ss` | 16,6 s · se intenta, sudo lo rechaza (rc 1, F6) · contenido en fw-core | **9,6 s** · no se intenta (`omitido: no_ejecutable`, F6) · contenido en fw-core |

- **Ninguna contención se pierde** y la causa es la misma en los dos modos.
- `PRECHECK` no ahorra tiempo (F2 falla al instante): evita lanzar contra el equipo un SSH que se sabe
  inútil y que el SIEM del cliente vería como ruido.
- En el modo encendido van los cinco interruptores a la vez: el ahorro de la fila de `ESCALADA_SOLO` suma el
  de `FALLO_RAPIDO` en el equipo; lo propio de este recorte es el salto omitido de fw-core.
- Memoria disponible durante toda la parte B: ≥ 7,4 GB (`memoria.log`).
