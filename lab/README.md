# Laboratorio

Topologías de Containerlab del proyecto. Ver el diseño en
[sandbox-red-containerlab.md](../documentacion/03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md)
y el plan de ejecución en [camino-paso-a-paso.md](../documentacion/00-general/camino-paso-a-paso.md).

| Fichero | Qué es | Estado |
|---------|--------|--------|
| [smoke-test.clab.yml](smoke-test.clab.yml) | Tres nodos Alpine en línea: `borde` → `cpe` → `abonado`. Valida la cadena WSL → Docker → Containerlab | **Validado** 23/08/2026 |
| [fttx-base.clab.yml](fttx-base.clab.yml) | Primer tramo FTTx con CPE OpenWrt real (VM QEMU) | **Bloqueado** — ver mediciones |
| [mediciones.md](mediciones.md) | Consumo real por escalón — Paso 1 del camino | En curso |

## Uso

```bash
containerlab validate -t lab/smoke-test.clab.yml
containerlab deploy   -t lab/smoke-test.clab.yml
containerlab destroy  -t lab/smoke-test.clab.yml
```

## Trampas encontradas

**`host` es un nombre reservado.** Designa el namespace de red raíz de la máquina.
Un nodo llamado `host` provoca que la interfaz se cree en el sistema anfitrión en
lugar de dentro del contenedor, y Containerlab **lo reporta como éxito sin error**.
El síntoma aparece después, como `ip: can't find device 'eth1'` en los comandos `exec`.

**El bootstrap de OpenWrt en vrnetlab se cuelga.** La VM arranca bien y consume poco, pero
`launch.py` no llega a configurar la interfaz de gestión ni a reasignar la LAN a `eth2`.
Detalle y opciones en [mediciones.md](mediciones.md).

**Los `exec` no configuran el reenvío.** Para que un nodo encamine hay que activar
`net.ipv4.ip_forward` con la clave `sysctls`, y añadir la ruta de vuelta en el otro extremo.
