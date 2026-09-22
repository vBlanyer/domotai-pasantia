# 08 · Prueba manual en el laboratorio del banco

Guía paso a paso para ver el prototipo decidir sobre **ataques reales** en la red del banco. Cubre levantar
el laboratorio, cada caso de prueba, cómo limpiar entre casos y cómo apagarlo y empezar de cero.

- Qué es el laboratorio: [`lab/banco/README.md`](../../lab/banco/README.md).
- Resultados medidos: [`lab/banco/verificaciones.md`](../../lab/banco/verificaciones.md).

**Todos los comandos se ejecutan desde la raíz del repositorio**, en una **terminal real**, no en el panel
del editor: el menú de validación lee tu respuesta del teclado (`/dev/tty`).

---

## 0. Requisitos (una sola vez)

| Necesitas | Comprobación |
|---|---|
| Docker y Containerlab | `containerlab version` |
| Python 3 y PyYAML | `python3 -c "import yaml"` |
| La imagen de los nodos | `sh lab/banco/construir-imagen.sh` (solo la primera vez, o si cambian `servicio.py`, `monitor.py` o `reenviador.py`) |

El banco y la red pequeña (`red-cliente`) **no pueden estar levantados a la vez**, porque comparten la red de
gestión. Si la red pequeña está arriba, bájala antes con `sh lab/lab.sh down`.

---

## 1. Levantar el laboratorio

```bash
sh lab/lab.sh up banco                  # despliega los 14 nodos, Wazuh, servicios, monitor (~1-2 min)
sh lab/banco/banco.sh aprovisionar      # usuario y permisos del conector en cada nodo
sh lab/banco/banco.sh test              # prueba de humo
```

`aprovisionar` hace falta **después de cada `up`**, porque Containerlab recrea los contenedores y el usuario
del conector no sobrevive.

**Qué debe salir en `test`:**

```
-- 1. internet -> web-banking (a traves de fw-edge y fw-core)
   HTTP 200
-- 2. mdr-siem llega a los dos cortafuegos
   10.0.0.1 OK
   10.0.0.254 OK
-- 3. Todos los servicios sanos
   OK
```

---

## 2. Comprobar la cascada real (sin el prototipo)

```bash
sh lab/banco/banco.sh cascada core-db
```

Tumba el servicio de `core-db`, muestra la salud y lo restaura.

- **Con `core-db` caído:** `caido` en `api-movil`, `atm`, `core-db`, `middleware` y `web-banking`; `ok` en
  `hsm` y `swift-alliance`.
- **Tras restaurar:** todo `ok`.

`atm` cae porque depende de `middleware`. En el perfil esa dependencia **no está declarada, a propósito**:
es el caso K3, una dependencia que existe en la red pero que el inventario desconoce.

---

## 3. Preparar las tres terminales

**Terminal 1: el panel de salud.** Muestra lo que de verdad está cayendo: una fila por servicio en verde
(`● OK`) o rojo (`✖ CAÍDO`), de quién depende, cuánto lleva así y los últimos cambios. Se refresca cada 2 s.

```bash
sh lab/banco/banco.sh vigilar
```

Si prefieres el dato en bruto (una línea JSON cada ~2 s):
`docker exec clab-banco-mdr-siem tail -f /var/log/banco/salud.jsonl`.

**Terminal 2: el daemon del MDR**, con el perfil bancario y el conector real ejecutando desde `mdr-siem`:

```bash
export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
rm -f /tmp/traza-banco.jsonl            # empezar con una traza limpia
docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
  | python3 -m prototipo.stream - prototipo/perfiles/bancario.yml \
      lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json \
      --ventana-agrupacion 15 --salida /tmp/traza-banco.jsonl
```

Debe aparecer el cartel «Monitor MDR en tiempo real — ACTIVO» con `Perfil: bancario.yml`. Tras cada ataque,
el incidente tarda unos **15-25 s** en aparecer: lo que tarda Wazuh más la ventana de agrupación.

**Terminal 3: los ataques.**

> **Deja más de 60 segundos entre un ataque y el siguiente.** La regla de fuerza bruta de Wazuh (5763)
> se silencia 60 s después de dispararse, **para cualquier origen**; lo medimos en V2. Si lanzas dos ataques
> seguidos, el segundo no genera la alerta correlacionada.

---

## 4. Los casos

Cada caso indica el ataque, qué debe verse y cómo **deshacerlo** para dejar el laboratorio limpio.

### Caso D1: atacante externo, el sistema actúa solo

```bash
for i in $(seq 1 10); do docker exec clab-banco-internet sh -c "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 -o PubkeyAuthentication=no -o PreferredAuthentications=password cliente@10.10.0.10 id" 2>/dev/null; done
```

**Qué debe verse:**
- **Terminal 2:** incidente `198.51.100.10 -> web-banking (ssh)`, clase `vp_intento_acceso`, confianza `1.0`,
  `filtro: automática`, `Consecuencia: bloquea a 198.51.100.10 (origen no inventariado) · 0 servicios
  detenidos`. **No aparece menú**, porque un origen externo con confianza ≥ 0,9 se bloquea solo
  según el perfil bancario.
- **Terminal 1:** todo sigue `ok`, porque bloquear al atacante no tumba nada.
- **Comprobación:** `docker exec clab-banco-web-banking iptables -S INPUT` muestra
  `-A INPUT -s 198.51.100.10/32 -j DROP`.

**Deshacer:**
```bash
docker exec clab-banco-web-banking iptables -D INPUT -s 198.51.100.10 -j DROP
```

### Caso A1: equipo interno comprometido, el sistema te pregunta

`taquilla` (un puesto de sucursal) ataca a `web-banking`:

```bash
for i in $(seq 1 10); do docker exec clab-banco-taquilla sh -c "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 -o PubkeyAuthentication=no -o PreferredAuthentications=password cliente@10.10.0.10 id" 2>/dev/null; done
```

**Qué debe verse (terminal 2):** el recuadro «Validación humana requerida» con
`Filtro: retenida — espera tu aprobación` y `Consecuencia: bloquea a taquilla (activo interno: puesto de
taquilla de sucursal)`, y el menú `1) aprobar  2) rechazar  3) reclasificar`.

Repite el caso (esperando 60 s entre intentos) probando cada respuesta:

| Respondes | Qué pasa | Deshacer |
|---|---|---|
| `2` rechazar, o Enter en blanco | No se ejecuta nada; en el resumen, `Rechazadas: 1` | Nada |
| `3` reclasificar | Submenú de clases; eliges una; no se ejecuta nada; en la traza, `clase_reclasificada` | Nada |
| `1` aprobar | Se bloquea `10.200.0.10` en `web-banking`; el monitor sigue `ok` | `docker exec clab-banco-web-banking iptables -D INPUT -s 10.200.0.10 -j DROP` |

### Caso K1: el fallo que encontramos (cascada no avisada)

`middleware` comprometido ataca a `core-db`:

```bash
for i in $(seq 1 10); do docker exec clab-banco-middleware sh -c "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 -o PubkeyAuthentication=no -o PreferredAuthentications=password cliente@10.50.0.10 id" 2>/dev/null; done
```

**Qué debe verse:**
- **Terminal 2:** menú con `Consecuencia: bloquea a middleware (activo interno: middleware del core
  bancario) · 0 servicios detenidos`, **sin ningún aviso de cascada**.
- **Aprueba (`1`)** y mira la **terminal 1**: en pocos segundos pasan a `caido` `middleware`, `web-banking`,
  `api-movil` y `atm`.

Eso es **K1**: el sistema anunció «0 servicios detenidos» y tumbó cuatro. Además se ve **C4**: la regla se
escribe en el propio `core-db`, una joya de la corona, en vez de contener en el cortafuegos.

**Deshacer (y comprobar que todo vuelve a `ok` en la terminal 1):**
```bash
docker exec clab-banco-core-db iptables -D INPUT -s 10.40.0.10 -j DROP
```

### Caso E1: la víctima no responde y se escala al cortafuegos

Se simula que el MDR no puede entrar en `web-banking`, bloqueando solo el SSH que viene de `mdr-siem`. El
atacante externo sigue pudiendo atacar:

```bash
docker exec clab-banco-web-banking iptables -I INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP
for i in $(seq 1 10); do docker exec clab-banco-internet sh -c "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 -o PubkeyAuthentication=no -o PreferredAuthentications=password cliente@10.10.0.10 id" 2>/dev/null; done
```

**Qué debería verse:**
1. El bloqueo automático en `web-banking` falla, porque el conector no llega.
2. El sistema **escala** a `fw-core` y te pide aprobación, porque bloquear en un cortafuegos alcanza a un
   servicio.
3. Aprueba (`1`): la regla queda en `fw-core` (`docker exec clab-banco-fw-core iptables -S FORWARD`).

> Este caso no está incluido en las verificaciones automáticas de la fase 0, que probaron la escalada
> con el conector de forma aislada (V6). Si no se comporta así, guarda la salida de la terminal 2: es un
> resultado.

**Deshacer:**
```bash
docker exec clab-banco-fw-core iptables -D FORWARD -s 198.51.100.10 -j DROP
docker exec clab-banco-web-banking iptables -D INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP
docker exec clab-banco-web-banking iptables -D INPUT -s 198.51.100.10 -j DROP 2>/dev/null   # por si llegó a aplicarse
```

---

## 5. Limpiar entre casos

**Limpieza rápida:** después de cada caso, ejecuta su bloque «Deshacer» y comprueba:

```bash
sh lab/banco/banco.sh test                      # todo OK
for n in web-banking core-db fw-core fw-edge; do echo "== $n"; docker exec clab-banco-$n iptables -S | grep -v -- '-P \|-i eth0'; done
```

El segundo comando no debe listar ninguna regla. La regla `-A INPUT -i eth0 -p tcp -j DROP` es parte del
estado base: aísla la red de gestión y por eso se filtra de la salida.

**Si algo quedó raro:** baja y vuelve a levantar todo (3-4 minutos) con el apartado 7.

**Traza:** cada sesión del daemon añade registros a `/tmp/traza-banco.jsonl`. Para verificar su integridad:

```bash
python3 -m prototipo.traza --verificar /tmp/traza-banco.jsonl
```

Para empezar una sesión nueva desde cero, bórrala (`rm -f /tmp/traza-banco.jsonl`) antes de arrancar el
daemon. Si reutilizas una traza de una versión anterior del prototipo, puede fallar al leerla.

---

## 6. Apagar

```bash
# Terminal 2: Ctrl+C (el daemon muestra el resumen de la sesión)
# Terminal 1: Ctrl+C
sh lab/lab.sh down banco
unset TRIAJE_NODO_GESTION AUDITOR_PUERTOS
```

`TRIAJE_NODO_GESTION` le dice al conector que ejecute desde `mdr-siem`. Si no la borras y vuelves a la red
pequeña, el conector buscaría un contenedor que ya no existe. Cerrar la terminal tiene el mismo efecto.

---

## 7. Empezar de cero

```bash
sh lab/lab.sh down banco
sh lab/lab.sh up banco
sh lab/banco/banco.sh aprovisionar
sh lab/banco/banco.sh test
rm -f /tmp/traza-banco.jsonl
```

Y vuelve al apartado 3.

---

## 8. Si algo no sale

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El daemon no muestra ningún incidente | Menos de 60 s desde el ataque anterior (regla 5763), o Wazuh aún arrancando | Espera 60 s y repite el ataque |
| No aparece el menú | La terminal no es interactiva | Usa una terminal real, no el panel del editor |
| `test` da un servicio caído sin haber atacado | Quedó una regla de un caso anterior | Apartado 5, o el 7 |
| El conector falla en todos los nodos | Falta `aprovisionar` tras el último `up`, o falta el `export` | `sh lab/banco/banco.sh aprovisionar` y el `export` del apartado 3 |
| `La red pequeña esta levantada` | Las dos redes no conviven | `sh lab/lab.sh down` |

---

## 9. ¿Se ve en `containerlab inspect`?

**No, y es lo correcto.** `containerlab inspect -t lab/topologias/banco.clab.yml` muestra el **estado del
contenedor** (`running`), y el MDR **nunca apaga un equipo**: sus acciones son reglas de cortafuegos
(bloquear una IP). En los casos D1, A1 y K1 todos los nodos siguen `running`. Lo que cambia es que un
**servicio** deja de responder, y eso lo muestra el monitor de salud (terminal 1), no Containerlab.

Que un contenedor pasara de `running` a parado sería apagar un servidor del banco, justo lo que el perfil de
continuidad prohíbe hacer de forma automática. Ningún componente del prototipo propone hoy esa acción.
