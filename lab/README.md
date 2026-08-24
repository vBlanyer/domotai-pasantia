# Laboratorio

Topologías de Containerlab del proyecto. Ver el diseño en
[sandbox-red-containerlab.md](../documentacion/03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md)
y el plan de ejecución en [camino-paso-a-paso.md](../documentacion/00-general/camino-paso-a-paso.md).

| Fichero | Qué es | Estado |
|---------|--------|--------|
| [fttx-lab.clab.yml](fttx-lab.clab.yml) | **Topología de trabajo.** Cadena FTTx con CPE provisional en Linux | **Operativa** |
| [fttx-base.clab.yml](fttx-base.clab.yml) | Variante con CPE OpenWrt real (VM QEMU) | **Bloqueada** — ver mediciones |
| [smoke-test.clab.yml](smoke-test.clab.yml) | Tres nodos Alpine. Valida la cadena WSL → Docker → Containerlab | Validado 23/08/2026 |
| [mediciones.md](mediciones.md) | Consumo real por escalón — Paso 1 del camino | En curso |

## Uso

```bash
containerlab validate -t lab/fttx-lab.clab.yml
containerlab deploy   -t lab/fttx-lab.clab.yml
containerlab destroy  -t lab/fttx-lab.clab.yml
```

En VS Code, la extensión de Containerlab detecta los ficheros sola y **TopoViewer** dibuja la
topología. Las etiquetas `graph-icon`, `graph-group` y `graph-level` de cada nodo controlan
cómo se agrupa y se dibuja.

---

## La topología

```
  Proveedor            Domicilio                        Gestión
  ─────────            ─────────                        ───────
   borde ──WAN── cpe ──LAN── sw-lan ─┬─ abonado          auditor
  10.0.1.1      .2   192.168.1.1     ├─ iot          (fuera del plano
                                     └─ objetivo-vuln     de datos)
```

| Red | Rango | Quién |
|-----|-------|-------|
| Acceso (WAN) | 10.0.1.0/24 | borde `.1` · cpe `.2` |
| LAN del abonado | 192.168.1.0/24 | cpe `.1` · abonado `.10` · iot `.20` · objetivo-vuln `.30` |
| Gestión | 172.20.20.0/24 | La crea Containerlab sola, todos los nodos |

> **La ruta por defecto pertenece a la red de gestión.** Añadir otra la pisa y se pierde el
> acceso a los nodos, así que el plano de datos usa **rutas específicas**.

---

## Los nodos, uno a uno

### Grupo «Proveedor»

#### `borde`

**Colapsa toda la parte del operador en un solo nodo**: el OLT de la central, los divisores
ópticos y la red de agregación. Emular OMCI o el plano PON no aportaría nada al triaje de
alertas y sí bastante trabajo, así que se abstrae.

Lleva `ip_forward` activado y una ruta de vuelta hacia la LAN del abonado.

*En el flujo del EDR:* es «el exterior» — la dirección por la que llegaría un ataque desde
fuera y por la que sale el tráfico del abonado. Desde aquí se simula la exposición del CPE
hacia el lado WAN.

### Grupo «Domicilio»

#### `cpe` — el nodo que importa

El **router/HGU de casa del abonado**, y el objetivo central del proyecto. Dos patas: `eth1`
mira al proveedor (10.0.1.2) y `eth2` mira a la casa (192.168.1.1), y encamina entre ambas.

Es el objetivo porque concentra lo que hace vulnerable a un CPE real: firmware que nadie
actualiza, credenciales de fábrica sin cambiar y gestión remota accesible.

*En el flujo del EDR cumple tres papeles a la vez:* es el equipo sobre el que el EDR ejecuta
acciones por SSH, la fuente de syslog que alimenta a Wazuh, y el objetivo principal de los
escaneos del auditor.

> **Es provisional.** Hoy es un contenedor Linux que encamina, no OpenWrt. Le falta el firmware
> real, LuCI, UCI y la superficie de ataque concreta de un CPE — un escaneo de puertos le
> devuelve todo cerrado, mientras que un OpenWrt real mostraría dropbear, LuCI y dnsmasq.
> Cuando se resuelva el cuelgue de vrnetlab, basta cambiar `kind` e `image` en este nodo.

#### `sw-lan`

El **switch de la casa** — o la parte de conmutación del HGU, que en un equipo real suele ir
integrada. Un contenedor con un bridge Linux `br0` que esclaviza `eth1` a `eth4`: `eth1` sube
al CPE y los otros tres bajan a los dispositivos. **No tiene IP porque trabaja en capa 2.**

Existe en vez de colgar los dispositivos directamente del CPE porque en una casa real están
**en el mismo segmento**, y eso es lo que permite estudiar el **movimiento lateral** entre
ellos. Sin switch, un IoT comprometido no podría alcanzar al PC del abonado y se perdería el
escenario más interesante.

Es además el punto natural donde pinchar el tráfico si algún día se añade un IDS de red.

#### `abonado`

El **PC o el móvil del usuario final**, en 192.168.1.10. Objetivo clásico de un EDR y el único
nodo que en el mundo real llevaría un agente.

*En el flujo:* el segundo equipo sobre el que el EDR puede actuar, y fuente de telemetría de
host — aquí sí encajaría un agente Wazuh de verdad.

*Pregunta abierta:* si debería ser Windows. Ganaría realismo, pero exige licencia y una VM
completa, lo que rompe el modelo ligero de contenedores.

#### `iot`

Un **dispositivo del hogar** —cámara, televisor, enchufe inteligente— en 192.168.1.20.
Representa la clase de equipos con firmware antiguo y servicios expuestos (Telnet, UPnP) que
nadie parchea, y que en la práctica son la puerta de entrada más común a una red doméstica.

> **Hoy es un marcador:** un Alpine pelado, sin servicios expuestos. Cumple el papel en el
> diagrama pero no genera nada que el auditor pueda encontrar. Darle contenido es el Paso 4.

#### `objetivo-vuln`

En 192.168.1.30. **De este nodo depende toda la evaluación.**

Su función es tener **vulnerabilidades conocidas y documentadas**. Como se sabe exactamente qué
falla en él, se sabe qué debería encontrar el auditor, qué debería decidir el EDR y qué
detección sería un falso positivo. De ahí sale el ground truth de la Fase 6 sin etiquetar a ojo.

> **También es un marcador.** Necesita una imagen realmente vulnerable —Metasploitable, algún
> escenario de Vulhub— con su inventario de CVEs documentado al lado. Sin eso, la Fase 6 no
> tiene contra qué medirse.

### Grupo «Gestión»

#### `auditor`

El único nodo que **no está en el plano de datos**: no aparece en ningún enlace de la
topología, solo tiene `eth0` en la red de gestión. Lleva **nmap** instalado y rutas hacia
`192.168.1.0/24` y `10.0.1.0/24` a través del CPE, para poder escanear el plano de datos sin
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
recibiendo syslog del CPE y agentes de los nodos Linux.

**El EDR** no aparece y no debería: no es un nodo de la red, es el software del proyecto. Se
conecta al laboratorio desde fuera, por la red de gestión.

---

## Lanzar un nmap desde consola

El auditor ya trae nmap y las rutas al plano de datos. Tres formas de usarlo:

**Consola interactiva** (la más cómoda):

```bash
docker exec -it clab-fttx-lab-auditor sh
# ya dentro:
nmap -sn 192.168.1.0/24
```

**Un comando suelto, sin entrar:**

```bash
docker exec clab-fttx-lab-auditor nmap -Pn --top-ports 50 192.168.1.1
```

**Desde la extensión de VS Code:** clic derecho sobre el nodo `auditor` en el panel de
Containerlab → *Attach shell*.

### Escaneos útiles

```bash
# Descubrimiento de la LAN del abonado
nmap -sn 192.168.1.0/24

# Puertos y versiones del CPE por su interfaz LAN
nmap -Pn -sV --top-ports 100 192.168.1.1

# El CPE desde el lado del proveedor (superficie expuesta al WAN)
nmap -Pn -sV 10.0.1.2

# Toda la LAN, con deteccion de version y scripts por defecto
nmap -Pn -sC -sV 192.168.1.0/24

# Scripts de vulnerabilidades sobre el objetivo etiquetado
nmap -Pn --script vuln 192.168.1.30
```

> **Ojo con el plano que escaneas.** Cada nodo tiene una IP de gestión (172.20.20.x) además de
> su IP del plano de datos. Escanear la de gestión **no es lo mismo** que escanear la del plano
> de datos: los servicios pueden estar ligados a una interfaz concreta. Para auditar el CPE
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
Reproducido en 23.05.5 y 24.10.0. Detalle en [mediciones.md](mediciones.md).

**Los puertos bajos pueden estar ocupados.** El laboratorio comparte máquina con otros
desarrollos; el 8080 lo tenía un servidor Vite. Los puertos de LuCI se movieron a 8180 y 8543.

**Los `exec` no configuran el reenvío.** Para que un nodo encamine hay que activar
`net.ipv4.ip_forward` con la clave `sysctls`, y añadir la ruta de vuelta en el otro extremo.
