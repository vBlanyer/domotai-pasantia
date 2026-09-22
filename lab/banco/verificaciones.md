# Fase 0 — verificaciones en vivo (laboratorio del banco)

Registro honesto de siete verificaciones ejecutadas contra el laboratorio del banco ya
levantado (`sh lab/banco/banco.sh status`: 14 contenedores `clab-banco-*` arriba, Wazuh
`clab-red-cliente-wazuh` arriba, salud inicial de los 7 activos con servicio en `ok`).
Formato por verificación: **comando exacto → salida literal (recortada) → conclusión →
casos afectados**. No se modificó `prototipo/` para forzar ningún resultado; los límites y
fallos esperados quedan anotados como tales.

---

## V1 — mínimo privilegio desde `mdr-siem`

```sh
export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
for n in web-banking:10.10.0.10 api-movil:10.20.0.10 atm:10.210.0.10 fw-core:10.0.0.1 \
         fw-edge:10.0.0.254 middleware:10.40.0.10 core-db:10.50.0.10 hsm:10.60.0.10 \
         swift-alliance:10.30.0.10 taquilla:10.200.0.10; do
  sh lab/scripts/aprovisionar-minimo-privilegio.sh clab-banco-${n%%:*} ${n##*:} || echo "FALLO en $n"
done
```

Salida (idéntica en los 10 nodos, aquí la de `web-banking` como muestra):

```
== 1. Clave del conector en el auditor ==
== 2. Usuario 'triaje' en clab-banco-web-banking, solo con clave ==
== 3. Sudoers generado desde el catalogo ==
# AVISO: sin ruta en el nodo, fuera del sudoers: ss, tc, service, restaurar
   17 comandos permitidos
== 4. Comprobaciones ==
   permitido (del catalogo):  iptables -L -n   OK
   denegado (fuera del catalogo): cat /etc/shadow   OK
   denegado (mismo binario, argumentos fuera del catalogo): iptables -F   OK
== listo: el conector usara la clave (conector.ejecutor_por_defecto) ==
```

**Conclusión:** los 10 nodos (`web-banking`, `api-movil`, `atm`, `fw-core`, `fw-edge`,
`middleware`, `core-db`, `hsm`, `swift-alliance`, `taquilla`) pasan las tres comprobaciones
sin ningún `FALLO`: `iptables -L -n` permitido, `cat /etc/shadow` denegado, `iptables -F`
(mismo binario, fuera de catálogo) denegado. El aviso «sin ruta en el nodo... ss, tc,
service, restaurar» es informativo (esos comandos del catálogo no tienen binario instalado
en la imagen del banco) y no afecta las tres comprobaciones.

**Casos afectados:** ninguno reprobado. Base para V6/V7 (usa el mismo `TRIAJE_NODO_GESTION`).

---

## V2 — detección de fuerza bruta SSH (D1, A1, K1)

```sh
for i in $(seq 1 10); do docker exec clab-banco-internet sh -c \
  "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 \
   -o PubkeyAuthentication=no -o PreferredAuthentications=password cliente@10.10.0.10 id" 2>/dev/null; done
for i in $(seq 1 10); do docker exec clab-banco-taquilla sh -c \
  "sshpass -p mal_$i ssh ... cliente@10.50.0.10 id" 2>/dev/null; done
for i in $(seq 1 10); do docker exec clab-banco-middleware sh -c \
  "sshpass -p mal_$i ssh ... cliente@10.50.0.10 id" 2>/dev/null; done
sleep 8
docker exec clab-red-cliente-wazuh sh -c "grep -a '\"srcip\":\"198.51.100.10\"\|\"srcip\":\"10.200.0.10\"\|\"srcip\":\"10.40.0.10\"' /var/ossec/logs/alerts/alerts.json" \
  | python3 -c "...Counter por (srcip, hostname, rule_id, level)..."
```

Salida (las tres ráfagas lanzadas seguidas, ventana de 8 s):

```
10 ('10.200.0.10', 'core-db', '5760', 5)
10 ('10.40.0.10', 'core-db', '5760', 5)
9 ('198.51.100.10', 'web-banking', '5760', 5)
1 ('198.51.100.10', 'web-banking', '5763', 10)
```

`5760` (fallo de autenticación individual) se dispara siempre y con el `hostname`
correcto — confirma que `reenviador.desde_sshd` parsea bien lo que escribe `sshd -E`; no
hizo falta tocar la expresión regular. `5763` (fuerza bruta correlacionada, nivel 10) solo
se disparó para el atacante externo (`internet` → `web-banking`); ni `taquilla` ni
`middleware` (atacantes internos, mismos 10 intentos cada uno) lo dispararon en esta
corrida.

Se investigó la causa antes de concluir «no detectado»: la regla nativa de Wazuh
(`/var/ossec/ruleset/rules/0095-sshd_rules.xml`) es
`id="5763" level="10" frequency="8" timeframe="120" ignore="60"` con `<same_source_ip/>`
sobre `if_matched_sid=5760`. Repitiendo el ataque de `taquilla` en solitario (sin las otras
dos ráfagas superpuestas en la misma ventana):

```sh
for i in $(seq 11 20); do docker exec clab-banco-taquilla sh -c \
  "sshpass -p mal_$i ssh ... cliente@10.50.0.10 id" 2>/dev/null; done
```

```
2026-09-22T15:09:37.998+0000 10.200.0.10 core-db 5763 10
```

`5763` sí se dispara con normalidad cuando la ráfaga corre aislada.

**Conclusión:** la detección de fuerza bruta SSH funciona (D1/A1/K1 confirmados) para el
caso simple de un único atacante. Lo observado en la corrida combinada es un límite del
motor de correlación nativo de Wazuh: el conteo `frequency`/`same_source_ip` de la regla
5763 comparte una ventana/búfer por regla, y cuando varios orígenes atacan casi al mismo
tiempo (segundos de diferencia), el conteo de un origen puede diluirse entre eventos de
otro y no llegar al umbral de 8. No es un fallo de `reenviador.py` (el parseo y el
`hostname` son correctos en el 100 % de los eventos) ni algo que corresponda arreglar en
`prototipo/`: es un límite del ruleset estándar de Wazuh ante ataques concurrentes
multiorigen, documentado aquí como tal.

**Casos afectados:** D1, A1, K1 — **confirmados** para ataque de un solo origen;
**límite de detección** documentado para ráfagas concurrentes multiorigen dentro de la
misma ventana de correlación (no aplicable a K1 tal como está planteado, que usa un solo
origen).

---

## V3 — ataque web (D5) y reconocimiento (D7)

```sh
docker exec clab-banco-internet sh -c "for p in \"/?id=1'%20OR%20'1'='1\" '/../../etc/passwd' '/?q=<script>alert(1)</script>'; do curl -s -m3 -o /dev/null \"http://10.10.0.10:443\$p\"; done"
docker exec clab-banco-internet nmap -Pn -sT -p 1-2000 10.10.0.10 >/dev/null
sleep 8
docker exec clab-red-cliente-wazuh sh -c "grep -a '198.51.100.10' /var/ossec/logs/alerts/alerts.json" \
  | python3 -c "... print(rule.id, level, groups, description) ..."
```

Salida (alertas para `198.51.100.10`, todas las reglas, conteo):

```
1 ('31106', 6, ('web', 'accesslog', 'attack'), 'A web attack returned code 200 (success).')
9 ('5760', 5, ('syslog', 'sshd', 'authentication_failed'), 'sshd: authentication failed.')
1 ('5763', 10, ('syslog', 'sshd', 'authentication_failures'), 'sshd: brute force trying to get access to the system. Authen')
```

(Las `5760`/`5763` son residuo de V2 sobre el mismo origen externo; para V3 lo relevante es
la única `31106`.) Log crudo de acceso de `web-banking` con las tres peticiones:

```
198.51.100.10 - - [22/Sep/2026:15:10:00 +0000] "GET /?id=1'%20OR%20'1'='1 HTTP/1.1" 200 27 "-" "curl/8.14.1"
198.51.100.10 - - [22/Sep/2026:15:10:00 +0000] "GET /etc/passwd HTTP/1.1" 200 27 "-" "curl/8.14.1"
198.51.100.10 - - [22/Sep/2026:15:10:00 +0000] "GET /?q=<script>alert(1)</script> HTTP/1.1" 200 27 "-" "curl/8.14.1"
```

De las tres peticiones craftadas, solo **una** produjo alerta (`31106`, disparada por la
regla hija `31103`/`31104` que reconoce el patrón SQLi `OR '1'='1` y luego `31106` que
exige código `200`). Las otras dos no dispararon nada:

- la ruta `/../../etc/passwd` llegó al servidor ya normalizada por `curl` como
  `/etc/passwd` (sin el patrón `../` en el log), así que ninguna regla de recorrido de
  directorios (que busca `../` literal en la URL) tenía nada que emparejar — no es que
  Wazuh la dejara pasar, es que la señal nunca llegó al log en esa forma;
- el XSS se envió sin codificar (`<script>alert(1)</script>` literal), y la regla nativa
  `31105` busca los patrones URL-codificados (`%3Cscript`, `script%3E`, etc.), así que
  tampoco emparejó.

Para el escaneo de reconocimiento:

```sh
docker exec clab-banco-internet nmap -Pn -sT -p 1-2000 10.10.0.10 >/dev/null
```

No aparece **ninguna** alerta asociada al escaneo (ni grupo `recon`, `ids`, ni nada
distinto de las tres anteriores) en los logs de Wazuh para `198.51.100.10` tras el nmap.

**Conclusión:**
- **D5 (ataque web):** parcialmente confirmado y parcialmente límite. El SQLi clásico sí
  se detecta con el ruleset estándar de Wazuh. El XSS y el recorrido de directorios, tal
  como se los craftó en este ensayo (sin codificación URL / normalizados por el cliente
  antes de salir), **no se detectan** — límite de detección del ruleset estándar frente a
  variantes de payload, no un fallo del reenviador (el log de acceso se parsea y llega
  correctamente).
- **D7 (reconocimiento con nmap):** **límite de detección** (R3). Ninguna regla del
  grupo `web`/`attack`/`recon` salta para el escaneo de puertos porque el laboratorio no
  ingiere logs de firewall/IDS de red (solo syslog de aplicación vía el reenviador); Wazuh,
  tal como está desplegado aquí, no ve tráfico de red crudo.

**Casos afectados:** D5 — confirmado (SQLi) / límite de detección (XSS, path traversal sin
codificar). D7 — límite de detección.

---

## V4 — el auditor y la reconciliación del inventario

```sh
AUDITOR_NODOS="$(python3 -m lab.banco.red nodos)" AUDITOR_PUERTOS="$(python3 -m lab.banco.red puertos)" \
TRIAJE_AUDITOR=clab-banco-auditor sh lab/scripts/auditar.sh lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json
python3 -m prototipo.inventario prototipo/perfiles/bancario.yml lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json
```

`red.nodos_auditor()` / `red.puertos_auditor()`:

```
nodos:   api-movil:10.20.0.10 atm:10.210.0.10 core-db:10.50.0.10 hsm:10.60.0.10 middleware:10.40.0.10 swift-alliance:10.30.0.10 taquilla:10.200.0.10 web-banking:10.10.0.10
puertos: 22,80,443,1521,8080,8443,9000,48002
```

Salida del auditor:

```
hallazgos -> lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json (64 servicios, 8 nodos)
```

Salida de la reconciliación:

```
api-movil: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
atm: 2 abierto(s) no declarado(s) (exposición no reconocida): ssh/22, http-proxy/8080
core-db: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
hsm: 2 abierto(s) no declarado(s) (exposición no reconocida): ssh/22, cslistener/9000
middleware: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
swift-alliance: 2 abierto(s) no declarado(s) (exposición no reconocida): ssh/22, nimhub/48002
taquilla: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
web-banking: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
inventariados y no escaneados: mdr-siem
```

**Conclusión:** el auditor escanea los 8 nodos con servicios (`fw-core`/`fw-edge` no
tienen servicios propios que auditar, solo reglas de firewall — quedaron fuera a propósito,
igual que `mdr-siem`, plano de gestión, marcado «inventariado y no escaneado»). Como se
esperaba: el `22` (sshd del conector, `usuario cliente`) aparece como no declarado en los 8
nodos — exposición conocida del laboratorio, no un hallazgo real. `hsm` (`9000`) y
`swift-alliance` (`48002`) también salen como no declarados: sus puertos nominales no
figuran todavía en `servicios_prestados` del perfil (`prototipo/perfiles/bancario.yml` los
deja en `[]`), pendiente de la Task 9. Además apareció `atm` con `8080` no declarado, por
el mismo motivo (puerto nominal de `atm` aún no está en el perfil) — se anota aquí junto a
los otros dos porque es el mismo caso, no una sorpresa nueva.

**Casos afectados:** ninguno reprobado; hallazgos esperados según lo indicado en el brief,
más `atm:8080` con la misma causa raíz que `hsm`/`swift-alliance`. Pendiente de Task 9
(declarar los puertos nominales en el perfil).

---

## V5 — qué hace el lazo con una víctima que es una joya de la corona (C4)

```sh
PYTHONPATH=. python3 - <<'EOF'
from prototipo import lazo, catalogo as catm, perfil as perfilm
p = perfilm.cargar("prototipo/perfiles/bancario.yml"); c = catm.cargar_catalogo("prototipo/catalogo.yml")
toc = []
def ej(ip, cmd): toc.append(ip); return (0, "DROP") if "grep" in cmd and len(toc) > 1 else (1, "")
a = {"id_alerta": "v5", "regla_id": "5763", "origen_ip": "198.51.100.10", "activo": "hsm", "servicio": "ssh",
     "familia": "acceso_credenciales", "mitre": ["T1110"], "timestamp": "2026-09-22T00:00:00Z"}
h = {"nodos": {"hsm": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
r = lazo.procesar_lazo(a, h, p, "bancario", c, ej, "v5", a["timestamp"], leer=lambda _: "1")
print("accion_final:", r["accion_final"], "| filtro:", r["resultado_filtro"])
print("orden sobre:", (r.get("orden") or {}).get("nodo_ip"), "| IPs contactadas:", toc)
EOF
```

Salida:

```
── Validación humana ── BLOQUEAR_IP_FIREWALL en fw-core (10.0.0.1) contra 198.51.100.10
Consecuencia: bloquea a 198.51.100.10 (origen no inventariado) · 0 servicios detenidos
accion_final: BLOQUEAR_IP | filtro: permite
orden sobre: 10.60.0.10 | IPs contactadas: ['10.60.0.10', '10.60.0.10', '10.60.0.10', '10.60.0.10']
```

**Conclusión:** la primera (y única, en este ensayo) IP contactada por el ejecutor es
`10.60.0.10` — el propio HSM, la víctima, no el firewall. El mensaje de validación humana
que se imprime sí habla de `BLOQUEAR_IP_FIREWALL en fw-core`, pero la orden ejecutada
(`orden sobre: 10.60.0.10`) y las llamadas reales al ejecutor van contra el activo. Esto
confirma **C4 como fallo esperado**: `prototipo/perfiles/bancario.yml` documenta
explícitamente («las joyas de la corona NO se listan como host: una contención sobre ellas
escala directa al firewall, contener aguas arriba, nunca tocar el activo crítico») una
garantía que el código de `lazo.py` no cumple — el lazo intenta primero contactar/consultar
la víctima y solo, si eso fallara, escalaría. Lo documentado en el perfil no está
garantizado por el código. Queda como tarea aparte (fuera del alcance de esta fase), igual
que H2 (ver V7).

**Casos afectados:** C4 — fallo esperado, con evidencia arriba.

---

## V6 — escalada real entre cortafuegos (E1, E2)

```sh
export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
PYTHONPATH=. python3 - <<'EOF'
from prototipo import conector, catalogo as catm
c = catm.cargar_catalogo("prototipo/catalogo.yml"); ej = conector.ejecutor_por_defecto()
for nodo, ip in (("fw-core", "10.0.0.1"), ("fw-edge", "10.0.0.254")):
    o = {"decision_id": "v6", "accion_id": "BLOQUEAR_IP_FIREWALL", "nodo_objetivo": nodo, "nodo_ip": ip,
         "params": {"ip": "192.0.2.99"}}
    print(nodo, conector.ejecutar_orden(o, c, ej, "v6")["exito"])
    print("  revertir:", ej(ip, "iptables -D FORWARD -s 192.0.2.99 -j DROP")[0])
EOF
```

Salida:

```
fw-core True
  revertir: 0
fw-edge True
  revertir: 0
```

Confirmación adicional (reglas ya no presentes tras la reversión):

```sh
docker exec clab-banco-fw-core iptables -L FORWARD -n | grep -c 192.0.2.99   # -> 0
docker exec clab-banco-fw-edge iptables -L FORWARD -n | grep -c 192.0.2.99   # -> 0
```

**Conclusión:** el conector real ejecuta `BLOQUEAR_IP_FIREWALL` con éxito (`exito: True`)
sobre los dos cortafuegos usando el usuario de mínimo privilegio provisto en V1, y la
reversión manual (`iptables -D ...`) confirma que la regla insertada era exactamente la
esperada (código de salida 0, sin rastro de la IP de prueba después).

**Casos afectados:** E1, E2 — confirmados.

---

## V7 — K1 en crudo (H2)

```sh
export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
PYTHONPATH=. python3 -c "
from prototipo import conector
ej = conector.ejecutor_por_defecto(); print(ej('10.0.0.1', 'iptables -A FORWARD -s 10.40.0.10 -j DROP')[0])"
sleep 8; docker exec clab-banco-mdr-siem tail -n1 /var/log/banco/salud.jsonl
PYTHONPATH=. python3 -c "
from prototipo import conector
ej = conector.ejecutor_por_defecto(); print(ej('10.0.0.1', 'iptables -D FORWARD -s 10.40.0.10 -j DROP')[0])"
PYTHONPATH=. python3 -c "
from prototipo import impacto, perfil, catalogo
p = perfil.cargar('prototipo/perfiles/bancario.yml'); c = catalogo.cargar_catalogo('prototipo/catalogo.yml')
d = impacto.determinar('BLOQUEAR_IP_FIREWALL', {'ip': '10.40.0.10'}, 'core-db', p, c)
print('prediccion:', d['activos_afectados_en_cascada'], '|', d['motivo'])"
```

Salida (bloqueo directo de la IP de `middleware` en `fw-core`):

```
0
{"estados": {"api-movil": "caido", "atm": "caido", "core-db": "ok", "hsm": "ok", "middleware": "caido", "swift-alliance": "ok", "web-banking": "caido"}, "t": "2026-09-22T15:13:25Z"}
0
prediccion: [] | bloquea a middleware (activo interno: middleware del core bancario) · 0 servicios detenidos
```

**Conclusión:** las dos salidas de arriba son la evidencia completa de K1: el monitor de
salud (`/var/log/banco/salud.jsonl`) muestra caídos exactamente `web-banking`, `api-movil`,
`atm` y `middleware` (`core-db` y `hsm`, que no dependen de `middleware`, siguen `ok`)
como consecuencia real de bloquear a `middleware` en `fw-core`. En cambio,
`impacto.determinar` (el módulo de conciencia de impacto usado por el lazo antes de decidir)
predice `activos_afectados_en_cascada: []` y un motivo (`bloquea a middleware...`) que no
menciona ninguna cascada. El bloqueo revertió correctamente (segundo `0`) y, tras la
reversión, `sh lab/banco/banco.sh test` confirmó todos los servicios sanos otra vez.

**Conclusión (K1):** confirma el hallazgo previo (D16/N2): la cadena `depende_de` en el
perfil describe `web-banking → middleware`, `api-movil → middleware`, `middleware →
core-db, hsm`, pero **no** en sentido inverso (qué depende de `middleware`); la fusión N2 de
`depende_de` en cascada cubre la propagación cuando el activo *caído* es el ancestro
consultado hacia adelante, no cuando la acción de contención recae sobre un nodo intermedio
como `middleware` y hay que mirar quién depende de él. El resultado real es que 4 servicios
caen y el módulo de impacto no lo anticipa: fallo esperado, documentado.

**Casos afectados:** K1 — fallo esperado (H2), evidencia completa arriba.

---

## Reversión y estado final del laboratorio

Todas las reglas de iptables añadidas en V6 y V7 se revirtieron con el mismo comando real
(`ej(ip, 'iptables -D ...')`, código de salida `0` en cada caso) y se confirmó ausencia de
la IP de prueba con `iptables -L FORWARD -n`. Verificación final:

```sh
sh lab/banco/banco.sh test
```

```
-- 1. internet -> web-banking (a traves de fw-edge y fw-core)
   HTTP 200
-- 2. mdr-siem llega a los dos cortafuegos
   10.0.0.1 OK
   10.0.0.254 OK
-- 3. Todos los servicios sanos
   OK
```

El laboratorio queda arriba (`UP`), en el mismo estado base que al comenzar la Fase 0.

---

## Tabla final: caso → estado tras la Fase 0

| Caso | Estado tras la fase 0 |
|---|---|
| D1, A1, K1 (fuerza bruta SSH) | confirmado para ataque de un solo origen (V2); límite de correlación de Wazuh ante ráfagas concurrentes multiorigen dentro de la misma ventana |
| D5 (ataque web) | confirmado (SQLi clásico) / límite de detección (XSS y path traversal sin codificar, según V3) |
| D7 (reconocimiento nmap) | límite de detección (según V3): no hay ingesta de tráfico de red/firewall, solo syslog de aplicación |
| C4 (víctima joya de la corona) | fallo esperado (según V5): el lazo contacta primero al activo crítico, no garantiza «nunca tocar» pese a lo documentado en el perfil |
| E1, E2 (escalada real entre cortafuegos) | confirmado (según V6): `BLOQUEAR_IP_FIREWALL` funciona y revierte limpio en `fw-core` y `fw-edge` |
| K1 (cascada real vs. predicha, H2) | fallo esperado (según V7): caen 4 servicios reales, la predicción de impacto da `[]` sin mención de cascada |

## Hallazgos adicionales fuera de la lista original

- **V4:** `atm:8080` (además de `hsm:9000` y `swift-alliance:48002`) sale como puerto
  nominal no declarado — misma causa raíz (puertos nominales pendientes de la Task 9),
  anotado aquí para que la Task 9 los cubra los tres.
- **V2:** la dilución del conteo `frequency`/`same_source_ip` de la regla nativa 5763 ante
  ráfagas concurrentes multiorigen es un límite del ruleset estándar de Wazuh, no de
  `reenviador.py`; no se tocó el reenviador porque el parseo (`5760`, `hostname`) ya
  funcionaba al 100 %. **Decisión pendiente:** si conviene, en una fase posterior, espaciar
  deliberadamente los ataques simulados en las campañas para no toparse con este límite del
  motor de correlación, o documentarlo como comportamiento esperado del SIEM del cliente.
