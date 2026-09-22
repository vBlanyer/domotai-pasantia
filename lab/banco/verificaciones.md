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
(`/var/ossec/ruleset/rules/0095-sshd_rules.xml` ~479-481) es

```
<rule id="5763" level="10" frequency="8" timeframe="120" ignore="60">
  <if_matched_sid>5760</if_matched_sid>
  <same_source_ip/>
```

`same_source_ip` gobierna el *conteo* (hace falta 8 `5760` del mismo origen en 120 s), pero
`ignore="60"` es una supresión aparte: una vez que la regla 5763 dispara, Wazuh la silencia
durante 60 s para **cualquier** origen, no solo para el que la disparó. Los timestamps
literales (recorte de `grep -a` sobre `alerts.json`, mismo comando de conteo de la sección
anterior pero imprimiendo el timestamp) lo confirman:

```
2026-09-22T15:08:20.474+0000 198.51.100.10 web-banking 5763 10   <- dispara, abre la ventana de silencio hasta 15:09:20.474
2026-09-22T15:08:21.287+0000 10.200.0.10   core-db     5760 5    <- taquilla, dentro de la ventana
...
2026-09-22T15:08:24.294+0000 10.200.0.10   core-db     5760 5    <- taquilla, 10/10 intentos, sin 5763 (dentro de la ventana)
2026-09-22T15:08:24.695+0000 10.40.0.10    core-db     5760 5    <- middleware, dentro de la ventana
...
2026-09-22T15:08:27.502+0000 10.40.0.10    core-db     5760 5    <- middleware, 10/10 intentos, sin 5763 (dentro de la ventana)
```

taquilla y middleware acumularon 10 `5760` cada uno — por encima del umbral `frequency=8` —
y aun así ninguno disparó `5763`, porque los dos cayeron dentro de los 60 s posteriores al
disparo de `198.51.100.10`. Repitiendo el ataque de `taquilla` en solitario, ya fuera de esa
ventana:

```sh
for i in $(seq 11 20); do docker exec clab-banco-taquilla sh -c \
  "sshpass -p mal_$i ssh ... cliente@10.50.0.10 id" 2>/dev/null; done
```

```
2026-09-22T15:09:36.194+0000 10.200.0.10 core-db 5760 5   <- 15:09:20.474 (fin de la ventana) ya pasó
...
2026-09-22T15:09:37.998+0000 10.200.0.10 core-db 5763 10  <- dispara con normalidad
```

**Conclusión:** la detección de fuerza bruta SSH funciona (D1/A1/K1 confirmados): el
`5760` de cada intento y el `hostname` son correctos en el 100 % de los eventos
(`reenviador.desde_sshd` no tiene ningún defecto de parseo), y `5763` dispara con
normalidad cuando se prueba en solitario. Lo observado en la corrida combinada no es una
«dilución de conteo por búfer compartido»: es el comportamiento documentado de
`ignore="60"` en la regla nativa 5763 — tras el primer disparo (de cualquier origen), la
regla queda silenciada 60 s para *todos* los orígenes, así tengan de sobra los 8 eventos
del umbral. No es un fallo de `reenviador.py` ni algo que corresponda arreglar en
`prototipo/`: es un límite operativo real del ruleset estándar de Wazuh — un ataque de
fuerza bruta correlacionado silencia la alerta de fuerza bruta para cualquier otro origen
durante el minuto siguiente. Esto importa en particular para el caso O2 (ataques
simultáneos desde varios orígenes): con la regla nativa tal cual está, solo el primero en
llegar produce la alerta correlacionada; los demás, aunque superen el umbral, quedan sin
`5763` mientras dure la ventana de silencio.

**Casos afectados:** D1, A1, K1 — **confirmados** (5760 y 5763 funcionan correctamente
para un ataque probado de forma aislada). **Límite operativo documentado** para O2
(orígenes simultáneos): la ventana `ignore="60"` de la regla 5763 silencia la alerta
correlacionada para cualquier origen adicional durante 60 s tras el primer disparo.

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

De las tres peticiones craftadas, solo **una** produjo alerta (`31106`). Para saber cuál
de las tres la disparó (la atribución inicial a "SQLi" era una suposición, no verificada)
se alimentó cada línea del `access.log`, ya envuelta con `reenviador.desde_web` (mismo
formato que sale por el reenviador real: `<30>{fecha} web-banking apache: {línea}`, sin el
prefijo `<30>` que `wazuh-logtest` no necesita), a `wazuh-logtest` (herramienta de solo
lectura, no genera alertas reales ni toca el laboratorio):

```sh
docker exec -i clab-red-cliente-wazuh /var/ossec/bin/wazuh-logtest <<'EOF'
Sep 22 15:29:40 web-banking apache: 198.51.100.10 - - [22/Sep/2026:15:10:00 +0000] "GET /?id=1'%20OR%20'1'='1 HTTP/1.1" 200 27 "-" "curl/8.14.1"
EOF
```

```
**Phase 3: Completed filtering (rules).
	id: '31100'
	level: '0'
	description: 'Access log messages grouped.'
```

El SQLi (`?id=1' OR '1'='1`) **no llega a ninguna regla de ataque**: se queda en `31100`
(el rule padre, nivel 0). Revisando `0245-web_rules.xml` (~37-41), la regla `31103`
(SQLi) exige alguna de estas palabras clave en la URL: `select%20|select+|insert%20|
%20from%20|%20where%20|union%20|union+|where+|null,null|xp_cmdshell` — el payload usado
(`' OR '1'='1`) no contiene ninguna. No es un límite del reenviador ni de la ingesta: el
patrón elegido para el ensayo simplemente no coincide con la firma que Wazuh usa para
SQLi.

```sh
docker exec -i clab-red-cliente-wazuh /var/ossec/bin/wazuh-logtest <<'EOF'
Sep 22 15:29:40 web-banking apache: 198.51.100.10 - - [22/Sep/2026:15:10:00 +0000] "GET /etc/passwd HTTP/1.1" 200 27 "-" "curl/8.14.1"
EOF
```

```
**Phase 3: Completed filtering (rules).
	id: '31108'
	level: '0'
	description: 'Ignored URLs (simple queries).'
```

La ruta `/../../etc/passwd` llegó al servidor ya normalizada por `curl` como `/etc/passwd`
(sin el patrón `../` en el log): la regla `31108` («ignored URLs, simple queries») la
clasifica como una consulta simple porque no queda rastro del patrón sospechoso en la
URL registrada — la señal nunca llegó al log en la forma que cualquier regla de recorrido
de directorios necesita.

```sh
docker exec -i clab-red-cliente-wazuh /var/ossec/bin/wazuh-logtest <<'EOF'
Sep 22 15:29:40 web-banking apache: 198.51.100.10 - - [22/Sep/2026:15:10:00 +0000] "GET /?q=<script>alert(1)</script> HTTP/1.1" 200 27 "-" "curl/8.14.1"
EOF
```

```
**Phase 3: Completed filtering (rules).
	id: '31106'
	level: '6'
	description: 'A web attack returned code 200 (success).'
	groups: '['web', 'accesslog', 'attack']'
**Alert to be generated.
```

El XSS (`<script>alert(1)</script>`, enviado **sin** codificar) es el que dispara `31106`.
La regla `31105` (`0245-web_rules.xml` ~66-68) incluye en su lista de patrones el literal
**sin codificar** `script>` (`<url>%3Cscript|%3C%2Fscript|script>|script%3E|SRC=javascript|
IMG%20|</url>`) — no solo variantes URL-codificadas como se había anotado antes; ese
literal empareja directamente con `<script>alert(1)</script>`, dispara `31105` y encadena
a `31106` (código `200`). La única alerta `31106` observada en la corrida real es, por
tanto, del **XSS**, no del SQLi.

Para el escaneo de reconocimiento:

```sh
docker exec clab-banco-internet nmap -Pn -sT -p 1-2000 10.10.0.10 >/dev/null
```

No aparece **ninguna** alerta asociada al escaneo (ni grupo `recon`, `ids`, ni nada
distinto de las tres anteriores) en los logs de Wazuh para `198.51.100.10` tras el nmap.

**Conclusión:**
- **D5 (ataque web):** parcialmente confirmado y parcialmente límite, pero al revés de lo
  anotado en el primer borrador. El XSS sin codificar (`<script>alert(1)</script>`) sí se
  detecta (`31105`→`31106`), porque la regla nativa incluye el literal `script>` sin
  codificar en su lista de patrones. El SQLi clásico usado en el ensayo (`' OR '1'='1`),
  en cambio, **no se detecta**: no contiene ninguna de las palabras clave que exige la
  regla `31103` (`select`, `union`, `where`, `insert`, `from`...) — es un límite del
  *payload elegido* frente a la firma de la regla, no del reenviador ni de la ingesta (el
  log de acceso se parsea y llega correctamente; verificado con `wazuh-logtest`). El
  recorrido de directorios tampoco se detecta, pero por una causa distinta y ya
  correcta desde el primer borrador: `curl` normalizó `/../../etc/passwd` a `/etc/passwd`
  antes de enviarlo, así que el patrón `../` nunca llegó al log.
- **D7 (reconocimiento con nmap):** **límite de detección** (R3). Ninguna regla del
  grupo `web`/`attack`/`recon` salta para el escaneo de puertos porque el laboratorio no
  ingiere logs de firewall/IDS de red (solo syslog de aplicación vía el reenviador); Wazuh,
  tal como está desplegado aquí, no ve tráfico de red crudo.

**Casos afectados:** D5 — confirmado (XSS sin codificar) / límite de detección (SQLi con
el payload usado, sin las palabras clave de la regla 31103; path traversal normalizado por
el cliente antes de salir). D7 — límite de detección.

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

**Task 9 — reconciliación con puertos del perfil declarados:**

```
api-movil: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
atm: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
core-db: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
hsm: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
middleware: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
swift-alliance: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
taquilla: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
web-banking: 1 abierto(s) no declarado(s) (exposición no reconocida): ssh/22
inventariados y no escaneados: mdr-siem
```

Ahora solo el `22` (sshd del laboratorio) queda como no declarado, confirmando que los
puertos nominales de `hsm` (9000), `swift-alliance` (48002) y `atm` (8080) están correctamente
incluidos en el perfil.

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
(`orden sobre: 10.60.0.10`) y las llamadas reales al ejecutor van contra el activo.

Precisión sobre ese mensaje: el paso de `fw-core` **sí se alcanzó y se preguntó**
(`_aprobar` en `prototipo/agente_mitigacion.py:177` imprime exactamente esa línea antes de
leer la respuesta). Pero `_aprobar` exige que la respuesta empiece por «s»
(`leer(...).strip().lower().startswith("s")`), y el ensayo usó `leer=lambda _: "1"` para
**todas** las lecturas del lazo — válido para otro prompt del mismo flujo (elegir `[1-N]`
de una lista, en `prototipo/validacion.py:56`), pero no para el `[s/N]` de la aprobación de
`fw-core`, donde `"1"` no empieza por «s» y se interpreta como rechazo. El código no se
saltó el firewall por diseño; el guion de prueba respondió «no» sin querer a esa pregunta
concreta. Lo que sí queda como hallazgo (y es lo que muestra V5) es que el primer contacto
real del ejecutor es la víctima (el HSM), no el firewall — con independencia de esa
respuesta de prueba.

Esto confirma **C4 como fallo esperado**: `prototipo/perfiles/bancario.yml` documenta
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

**Conclusión (K1) — causa verificada en el código, no en la dirección de `depende_de`:**
la hipótesis inicial (que `afectados_en_cascada` no camina la dependencia en sentido
inverso) es incorrecta. `prototipo/impacto.py:54-72` construye explícitamente un mapa
`dependientes` invertido (`dependientes.setdefault(dep, set()).add(nombre)` por cada
`nombre: {depende_de: [dep, ...]}` del perfil) y hace el cierre transitivo sobre ese mapa
invertido — si se la invoca con `activo="middleware"`, sí encuentra a `web-banking`,
`api-movil` y `atm` como dependientes. El problema real está un nivel más arriba, en
`determinar()` (`prototipo/impacto.py:189-190`):

```python
cascada = (afectados_en_cascada(activo, perfil)
           if accion_id in ACCIONES_SOBRE_PUERTO or accion_id in ACCIONES_SOBRE_NODO else [])
```

y en la clasificación de acciones (`prototipo/impacto.py:15-17`):

```python
ACCIONES_SOBRE_IP     = frozenset({"BLOQUEAR_IP", "BLOQUEAR_IP_FIREWALL", "MATAR_CONEXION"})
ACCIONES_SOBRE_PUERTO = frozenset({"BLOQUEAR_PUERTO", "CERRAR_SERVICIO"})
ACCIONES_SOBRE_NODO   = frozenset({"AISLAR_NODO", "REINICIAR_NODO"})
```

`BLOQUEAR_IP_FIREWALL` (la acción usada en V7) es una `ACCION_SOBRE_IP`, no una
`ACCION_SOBRE_PUERTO` ni `ACCION_SOBRE_NODO`. `determinar()` solo llama a
`afectados_en_cascada` para esas dos últimas categorías, así que para **cualquier**
bloqueo de IP —a un activo crítico o no, con o sin dependientes reales— la cascada
calculada es siempre `[]`, sin que la función que sí sabe caminar el grafo invertido
llegue a ejecutarse. El resultado real es que 4 servicios caen y el módulo de impacto no
lo anticipa: fallo esperado, documentado. La corrección futura (fuera de esta fase) no es
tocar la dirección de `depende_de` — ya es correcta — sino extender el cálculo de cascada
en `determinar()` para cubrir también `ACCIONES_SOBRE_IP` cuando el activo bloqueado es un
activo interno (H2 en el plan).

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
| D1, A1, K1 (fuerza bruta SSH) | confirmado, probado de forma aislada (V2); límite operativo documentado para O2 (`ignore="60"` de la regla 5763 silencia la alerta correlacionada para cualquier otro origen durante 60 s tras el primer disparo) |
| D5 (ataque web) | confirmado (XSS sin codificar, vía regla 31105) / límite de detección (SQLi con el payload usado, sin las palabras clave de la regla 31103; path traversal normalizado por el cliente, según V3) |
| D7 (reconocimiento nmap) | límite de detección (según V3): no hay ingesta de tráfico de red/firewall, solo syslog de aplicación |
| C4 (víctima joya de la corona) | fallo esperado (según V5): el primer contacto real del ejecutor es el activo crítico (HSM), no el firewall, pese a lo documentado en el perfil |
| E1, E2 (escalada real entre cortafuegos) | confirmado (según V6): `BLOQUEAR_IP_FIREWALL` funciona y revierte limpio en `fw-core` y `fw-edge` |
| K1 (cascada real vs. predicha, H2) | fallo esperado (según V7): caen 4 servicios reales, la predicción de impacto da `[]` porque `determinar()` solo calcula cascada para `ACCIONES_SOBRE_PUERTO`/`ACCIONES_SOBRE_NODO`, nunca para bloqueos de IP |

## Hallazgos adicionales fuera de la lista original

- **V4:** `atm:8080` (además de `hsm:9000` y `swift-alliance:48002`) sale como puerto
  nominal no declarado — misma causa raíz (puertos nominales pendientes de la Task 9),
  anotado aquí para que la Task 9 los cubra los tres.
- **V2:** `ignore="60"` en la regla nativa 5763 silencia la alerta correlacionada para
  *cualquier* origen (no solo el que disparó) durante 60 s tras el primer disparo — no es
  una «dilución de conteo por búfer compartido» como se anotó en un primer borrador (los
  timestamps de `alerts.json` lo descartan: taquilla y middleware acumularon 10/10
  eventos por encima del umbral `frequency=8` y aun así no dispararon, porque cayeron
  dentro de la ventana de 60 s). No se tocó el reenviador porque el parseo (`5760`,
  `hostname`) ya funcionaba al 100 %. **Decisión pendiente:** si conviene, en una fase
  posterior, espaciar deliberadamente los ataques simulados en las campañas para no
  toparse con esta ventana de silencio, o documentarlo como comportamiento esperado del
  SIEM del cliente (relevante para el caso O2, orígenes simultáneos).
