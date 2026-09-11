# 05 · Topologías del laboratorio

El laboratorio se despliega con **Containerlab**; los ficheros viven en `lab/topologias/`. `lab.sh` acepta
la topología como segundo argumento.

```
Sinopsis:  sh lab/lab.sh ( up | down | status | test ) [topologia=red-cliente]
Ejemplo:   sh lab/lab.sh up red-cliente-firewall     # escalada host->firewall REAL
```

Todas las topologías conservan `name: red-cliente`, así que los contenedores mantienen el prefijo
`clab-red-cliente-*` que usan los scripts, el conector SSH y el perfil (`topologia.gateway.ip = 192.168.1.1`).

## Mapa de nodos (común a las variantes de red-cliente)

```
proveedor ──WAN── borde ──LAN── sw-lan ─┬─ puesto        (.10 atacante)
                 (router)                ├─ iot           (.20 telnet 23 + web 80)
                                         └─ objetivo-vuln (.30 Metasploitable2, sshd)
auditor  (solo plano de gestion, escanea a traves de borde)
```
Direccionamiento: WAN `10.0.1.0/24` (proveedor .1, borde .2) · LAN `192.168.1.0/24` (borde .1, puesto .10,
iot .20, vuln .30) · Gestión `172.20.20.0/24`.

## Las topologías disponibles

| Topología | Para qué sirve | Cuándo usarla | Escenario (04) |
|---|---|---|---|
| **`red-cliente`** (default) | La red del cliente estándar; el `borde` es un router. La escalada a firewall se demuestra **simulada**. | Uso general: demos, daemon, fuerza bruta SSH, telnet al IoT. | A, B, D, E |
| **`red-cliente-firewall`** | Igual, pero el `borde` corre **sshd + msfadmin** → el conector empuja `iptables -A FORWARD` de verdad → **escalada host→firewall REAL**. | Probar la escalada multi-nodo con el ejecutor de firewall real (`--lab`). | C (en vivo) |
| **`red-cliente-openwrt`** | Variante donde el `borde` es OpenWrt (kind `openwrt`). Bloqueada por un cuelgue del bootstrap de vrnetlab (ver `lab/mediciones.md`). | Trabajo futuro, cuando se resuelva el bootstrap. | — |
| **`smoke-test`** | Topología mínima para validar que Containerlab funciona en la máquina. | Diagnóstico de entorno. | — |

## Ejemplos

**Levantar la topología estándar** (la mayoría de las pruebas):
```bash
sh lab/lab.sh up
```

**Levantar la variante con firewall gestionable** (para escalada real):
```bash
sh lab/lab.sh down                       # bajar la topología actual primero
sh lab/lab.sh up red-cliente-firewall
# verificar que el borde acepta SSH + iptables desde el auditor:
docker exec clab-red-cliente-auditor sh -c 'sshpass -p msfadmin ssh -o StrictHostKeyChecking=no \
  -o PreferredAuthentications=password msfadmin@192.168.1.1 "echo msfadmin | sudo -S iptables -L FORWARD -n"'
# luego, el agente con el conector SSH real:
python3 lab/scripts/demo-agente-escalado.py --lab
```

**Bajar / estado / prueba de humo** (aceptan también la topología):
```bash
sh lab/lab.sh status
sh lab/lab.sh down red-cliente-firewall
```

> **Ejercida en vivo el 11/09/2026:** desplegada, ambos nodos gestionados aprovisionados con mínimo
> privilegio (`aprovisionar-minimo-privilegio.sh` para `objetivo-vuln` y para `borde`), y el escenario C
> ejecutado por el lazo por defecto (sin `--agente`): sshd del objetivo parado → paso en el host rc=255 →
> validación humana para el cortafuegos → `iptables -A FORWARD -s 192.168.1.10 -j DROP` real en el borde,
> verificado → reversión desde la traza. Dos rarezas del despliegue limpio que ya cubren los scripts: el
> contenedor de Metasploitable no arranca su syslogd (lo arranca `reenvio-syslog.sh`), y el sshd de Alpine
> rechaza cuentas con `!` en `/etc/shadow` aunque la clave valga (el aprovisionamiento pone `*`).
