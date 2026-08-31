# Laboratorio

Topologías de Containerlab del proyecto. Ver el diseño en
[sandbox-red-containerlab.md](../documentacion/03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md)
y el plan de ejecución en [camino-paso-a-paso.md](../documentacion/00-general/camino-paso-a-paso.md).

```
lab/
├── lab.sh              control maestro: up · down · status · test
├── topologias/         las topologías de Containerlab
├── scripts/            Wazuh, reenvío de syslog, campañas, auditoría y visor de alertas
├── campañas/           actividad real congelada, una subcarpeta por campaña
├── dataset/            la tubería de etiquetado y el dataset resultante
└── docs/               instalación, verificación, ground truth y dataset
```

## Documentos

| Documento | Qué es | Estado |
|-----------|--------|--------|
| [instalacion.md](docs/instalacion.md) | **Guía de instalación**: de una máquina limpia a `lab.sh up` | Empieza aquí |
| [prueba-manual.md](docs/prueba-manual.md) | **Verificación de extremo a extremo** | Después de instalar |
| [generar-alertas.md](docs/generar-alertas.md) | Cómo producir alertas, manualmente y por reenvío | — |
| [vulnerabilidades-esperadas.md](docs/vulnerabilidades-esperadas.md) | **Ground truth**: qué se ha plantado en cada nodo | Verificado 24/08/2026 |
| [mediciones.md](docs/mediciones.md) | Consumo real por escalón — Paso 1 del camino | En curso |
| [dataset.md](docs/dataset.md) | **Dataset de alertas etiquetado**: cómo se genera, esquema de 16 campos, distribución de etiquetas | **Entregado 31/08/2026** |

## Topologías

| Fichero | Qué es | Estado |
|---------|--------|--------|
| [red-cliente.clab.yml](topologias/red-cliente.clab.yml) | **La topología de trabajo.** Red del cliente con el equipo de borde provisional en Linux | **Operativa** |
| [red-cliente-openwrt.clab.yml](topologias/red-cliente-openwrt.clab.yml) | Variante con el equipo de borde OpenWrt real (VM QEMU) | **Bloqueada** — ver [mediciones](docs/mediciones.md) |
| [smoke-test.clab.yml](topologias/smoke-test.clab.yml) | Tres nodos Alpine. Valida la cadena WSL → Docker → Containerlab | Validado 23/08/2026 |

## Scripts

| Fichero | Qué hace |
|---------|----------|
| [lab.sh](lab.sh) | Control maestro. Es el único que necesitas invocar a diario |
| [scripts/wazuh-run.sh](scripts/wazuh-run.sh) | Arranca el manager de Wazuh y activa la recepción de syslog |
| [scripts/reenvio-syslog.sh](scripts/reenvio-syslog.sh) | Reenvía el `auth.log` del objetivo hacia Wazuh |
| [scripts/ver-alertas.sh](scripts/ver-alertas.sh) | Visor de alertas en tiempo real (flujo de dos terminales) |
| [scripts/campana.sh](scripts/campana.sh) | Genera una campaña de actividad real (ataques + tráfico legítimo) y la congela en `campañas/` |
| [scripts/auditar.sh](scripts/auditar.sh) | Escanea el plano de datos con Nmap y emite `hallazgos.json` normalizado |

> **Nomenclatura.** Los identificadores siguen la terminología vigente del proyecto: la topología
> es `red-cliente`, y sus nodos son `proveedor` (antes del punto de entrega), `borde` (el equipo de
> borde del cliente, objetivo prioritario), `sw-lan`, `puesto`, `iot`, `objetivo-vuln` y `auditor`.
> Los contenedores se llaman `clab-red-cliente-<nodo>`. Ver la
> [Fase 1](../documentacion/01-fase1-analisis-del-modulo/) para el modelo del que salen.

## Uso

Todo el laboratorio (red + Wazuh + reenvío) con un comando:

```bash
sh lab/lab.sh up       # levanta todo
sh lab/lab.sh test     # prueba de humo de extremo a extremo
sh lab/lab.sh status   # que esta vivo
sh lab/lab.sh down     # apaga todo
```

Ver la guía completa en [instrucciones-prueba-manual.md](docs/prueba-manual.md). Solo la red:

```bash
containerlab deploy  -t lab/topologias/red-cliente.clab.yml
containerlab destroy -t lab/topologias/red-cliente.clab.yml
```

En VS Code, la extensión de Containerlab detecta los ficheros sola y **TopoViewer** dibuja la
topología. Las etiquetas `graph-icon`, `graph-group` y `graph-level` de cada nodo controlan
cómo se agrupa y se dibuja.

---

## La topología

```
  Proveedor              Red del cliente                     Gestión
  ─────────              ───────────────                     ───────
   proveedor ──WAN── borde ──LAN── sw-lan ─┬─ puesto          auditor
   10.0.1.1          .2   192.168.1.1      ├─ iot         (fuera del plano
                                           └─ objetivo-vuln    de datos)
```

| Red | Rango | Quién |
|-----|-------|-------|
| Acceso (WAN) | 10.0.1.0/24 | proveedor `.1` · borde `.2` |
| Red interna del cliente | 192.168.1.0/24 | borde `.1` · puesto `.10` · iot `.20` · objetivo-vuln `.30` |
| Gestión | 172.20.20.0/24 | La crea Containerlab sola, todos los nodos |

> **La ruta por defecto pertenece a la red de gestión.** Añadir otra la pisa y se pierde el
> acceso a los nodos, así que el plano de datos usa **rutas específicas**.

---

## Los nodos, uno a uno

### Grupo «Proveedor»

#### `proveedor`

**Colapsa todo el tramo del proveedor en un solo nodo**: la central, la planta externa y la red
de agregación. Emular el plano de transporte no aportaría nada al triaje de alertas y sí bastante
trabajo, así que se abstrae hasta el punto de entrega (ODF).

Lleva `ip_forward` activado y una ruta de vuelta hacia la red interna del cliente.

*En el flujo:* es «el exterior» — la dirección por la que llegaría un ataque desde fuera y por la
que sale el tráfico del cliente. Desde aquí se simula la exposición del equipo de borde hacia el
lado WAN.

### Grupo «Red del cliente»

#### `borde` — el equipo de borde

El **enrutador de borde del cliente**, uno de los dos objetivos prioritarios junto con los
servidores. Dos patas: `eth1` mira al proveedor (10.0.1.2) y `eth2` mira a la red interna
(192.168.1.1), y encamina entre ambas.

Es prioritario porque concentra la superficie del caso de uso: gestión remota accesible,
credenciales sin rotar y firmware que rara vez se actualiza.

*En el flujo cumple tres papeles a la vez:* es el equipo sobre el que el motor de triaje ejecuta
acciones por SSH, la fuente de syslog que alimenta a Wazuh, y uno de los objetivos principales de
los escaneos del auditor.

> **Es provisional.** Hoy es un contenedor Linux que encamina, no OpenWrt. Le falta el firmware
> real, LuCI, UCI y la superficie de ataque concreta de un enrutador — un escaneo de puertos le
> devuelve todo cerrado, mientras que un OpenWrt real mostraría dropbear, LuCI y dnsmasq.
> Cuando se resuelva el cuelgue de vrnetlab, basta cambiar `kind` e `image` en este nodo.

#### `sw-lan`

El **switch de la red interna** — o la parte de conmutación del propio equipo de borde, que en
muchos equipos va integrada. Un contenedor con un bridge Linux `br0` que esclaviza `eth1` a
`eth4`: `eth1` sube al borde y los otros tres bajan a los equipos. **No tiene IP porque trabaja
en capa 2.**

Existe en vez de colgar los equipos directamente del borde porque en una red real están **en el
mismo segmento**, y eso es lo que permite estudiar el **movimiento lateral** entre ellos. Sin
switch, un IoT comprometido no podría alcanzar al puesto ni al servidor y se perdería el
escenario más interesante.

Es además el punto natural donde pinchar el tráfico si algún día se añade un IDS de red.

#### `puesto`

El **puesto de trabajo del usuario**, en 192.168.1.10. Objetivo clásico de endpoint y nodo que en
el mundo real llevaría un agente.

*En el flujo:* otro equipo sobre el que el motor de triaje puede actuar, y fuente de telemetría de
host — aquí sí encajaría un agente Wazuh de verdad.

*Pregunta abierta:* si debería ser Windows. Ganaría realismo, pero exige licencia y una VM
completa, lo que rompe el modelo ligero de contenedores.

#### `iot`

Un **dispositivo del hogar** —cámara, televisor, enchufe inteligente— en 192.168.1.20.
Representa la clase de equipos con firmware antiguo y servicios expuestos (Telnet, UPnP) que
nadie parchea, y que en la práctica son la puerta de entrada más común a una red doméstica.

Expone **telnet sin autenticación** en el 23 —una shell directa, que es la vulnerabilidad
canónica de estos equipos— y una **interfaz web** en el 80. Nmap lo identifica como
`Coolstream set-top box telnetd` y lo clasifica como *media device*.

#### `objetivo-vuln`

En 192.168.1.30. **De este nodo depende toda la evaluación.**

Su función es tener **vulnerabilidades conocidas y documentadas**. Como se sabe exactamente qué
falla en él, se sabe qué debería encontrar el auditor, qué debería decidir el EDR y qué
detección sería un falso positivo. De ahí sale el ground truth de la Fase 6 sin etiquetar a ojo.

Ejecuta **Metasploitable2**, con 19 puertos abiertos y vulnerabilidades documentadas: la puerta
trasera de vsftpd 2.3.4, la de UnrealIRCd, el *usermap script* de Samba, servicios «r» sin
cifrar, y un **shell de root sin autenticación en el 1524**. Inventario completo en
[vulnerabilidades-esperadas.md](docs/vulnerabilidades-esperadas.md).

### Grupo «Gestión»

#### `auditor`

El único nodo que **no está en el plano de datos**: no aparece en ningún enlace de la
topología, solo tiene `eth0` en la red de gestión. Lleva **nmap** instalado y rutas hacia
`192.168.1.0/24` y `10.0.1.0/24` a través del equipo de borde, para poder escanear el plano de datos sin
pertenecer a él.

Está fuera del plano de datos por dos razones deliberadas:

- **Independencia.** Debe poder escanear aunque el plano de datos esté degradado o
  comprometido, que es justo el escenario en el que hace falta.
- **No contaminar la telemetría.** Un escaneo genera tráfico que parece hostil. Si circulara
  por el mismo segmento que se observa, el auditor fabricaría las alertas que el sistema debe
  analizar y sesgaría la evaluación.

*En el flujo cumple dos papeles distintos:* antes de decidir aporta la postura del nodo como
contexto de prioridad; después de actuar, verifica que la exposición se cerró de verdad.

---

## Lo que falta en la topología

**Wazuh.** Decidido pero no desplegado. Iría en el plano de gestión, junto al auditor,
recibiendo syslog del equipo de borde y agentes de los nodos Linux.

**El EDR** no aparece y no debería: no es un nodo de la red, es el software del proyecto. Se
conecta al laboratorio desde fuera, por la red de gestión.

---

## Lanzar un nmap desde consola

El auditor ya trae nmap y las rutas al plano de datos. Tres formas de usarlo:

**Consola interactiva** (la más cómoda):

```bash
docker exec -it clab-red-cliente-auditor sh
# ya dentro:
nmap -sn 192.168.1.0/24
```

**Un comando suelto, sin entrar:**

```bash
docker exec clab-red-cliente-auditor nmap -Pn --top-ports 50 192.168.1.1
```

**Desde la extensión de VS Code:** clic derecho sobre el nodo `auditor` en el panel de
Containerlab → *Attach shell*.

### Escaneos útiles

```bash
# Descubrimiento de la red interna
nmap -sn 192.168.1.0/24

# Puertos y versiones del equipo de borde por su interfaz interna
nmap -Pn -sV --top-ports 100 192.168.1.1

# El equipo de borde desde el lado del proveedor (superficie expuesta al WAN)
nmap -Pn -sV 10.0.1.2

# Toda la LAN, con deteccion de version y scripts por defecto
nmap -Pn -sC -sV 192.168.1.0/24

# Scripts de vulnerabilidades sobre el objetivo etiquetado
nmap -Pn --script vuln 192.168.1.30
```

> **Ojo con el plano que escaneas.** Cada nodo tiene una IP de gestión (172.20.20.x) además de
> su IP del plano de datos. Escanear la de gestión **no es lo mismo** que escanear la del plano
> de datos: los servicios pueden estar ligados a una interfaz concreta. Para auditar el borde
> como lo vería un atacante, usa `192.168.1.1` (desde la LAN) o `10.0.1.2` (desde el WAN),
> nunca su IP de gestión.

---

## Trampas encontradas

**`host` es un nombre reservado.** Designa el namespace de red raíz de la máquina. Un nodo
llamado `host` provoca que la interfaz se cree en el sistema anfitrión en lugar de dentro del
contenedor, y Containerlab **lo reporta como éxito sin error**. El síntoma aparece después,
como `ip: can't find device 'eth1'` en los comandos `exec`.

**La ruta por defecto ya existe.** La instala la red de gestión en `eth0`. Un
`ip route add default` en el `exec` falla con `RTNETLINK answers: File exists`, y sobrescribirla
deja el nodo inaccesible. Usa rutas específicas.

**El bootstrap de OpenWrt en vrnetlab se cuelga.** La VM arranca bien y consume poco, pero
`launch.py` no llega a configurar la interfaz de gestión ni a reasignar la LAN a `eth2`.
Reproducido en 23.05.5 y 24.10.0. Detalle en [mediciones.md](docs/mediciones.md).

**Los puertos bajos pueden estar ocupados.** El laboratorio comparte máquina con otros
desarrollos; el 8080 lo tenía un servidor Vite. Los puertos de LuCI se movieron a 8180 y 8543.

**Las IP de gestión se reasignan en cada `deploy`.** Containerlab reparte las 172.20.20.x por
orden de arranque, así que no son estables entre despliegues. Cualquier ruta que dependa de una
—como la del auditor hacia el plano de datos vía el equipo de borde— debe apuntar a una IP
**fijada** con `mgmt-ipv4` en el nodo destino, no a la que tuviera la última vez. El borde usa
`172.20.20.100`.

**Los `exec` no configuran el reenvío.** Para que un nodo encamine hay que activar
`net.ipv4.ip_forward` con la clave `sysctls`, y añadir la ruta de vuelta en el otro extremo.
