# Mediciones de consumo — Paso 1 del camino

Consumo real medido por incrementos, para contrastarlo con las estimaciones de
[selección del modelo §2](../documentacion/04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md).

## Entorno

| | |
|---|---|
| Equipo | Portátil, AMD Ryzen 7 5700U (Zen 2, 8c/16t), 16 GB de RAM |
| Sistema | WSL2, kernel 6.18.33.2 |
| **RAM visible en WSL** | **7,4 GiB** — la mitad del anfitrión |
| Docker | 29.7.2, overlayfs, cgroup v2 |
| Containerlab | 0.79.0 |

> **Hallazgo (23/08/2026).** WSL2 asigna por defecto la mitad de la RAM del anfitrión.
> El presupuesto de memoria del diseño se calculó sobre 16 GB, pero solo hay **7,4 GiB**
> disponibles. Se corrige desde Windows con `%UserProfile%\.wslconfig`:
>
> ```ini
> [wsl2]
> memory=12GB
> swap=4GB
> ```
>
> **Aplicado el 23/08/2026.** WSL pasa a exponer **11,7 GiB**. Las mediciones del escalón 1a
> se tomaron con 7,4 GiB; las del 1b en adelante, con 11,7 GiB.

## Resultados

| Escalón | Qué se añade | Estimado | **Medido** | ¿Cabe? |
|---------|--------------|----------|------------|--------|
| 0 | Base: WSL en reposo | — | 1.965 MiB usados, 5.638 MiB libres | — |
| 1a | Containerlab, 3 nodos Alpine (prueba de humo) | — | **+~90 MiB** (6,3 MiB en contenedores) | Sí, holgado |
| 1b | Containerlab con OpenWrt (QEMU) | 1,5–2 GB | **~130 MiB** el nodo CPE | Sí, muy holgado |
| 2 | + Wazuh manager sin indexer ni dashboard | +1–2 GB | *pendiente* | ? |
| 3 | + modelo de 3B cuantizado | +2–2,3 GB | *pendiente* | ? |
| 4 | + Greenbone | +4–8 GB | *pendiente* | **Improbable** |
| 5 | + modelo de 8B cuantizado | +5 GB | *pendiente* | **Improbable** |

## Otras observaciones

- **Ciclo `destroy` + `deploy`: 3 segundos**, sin errores y con la conectividad
  restablecida de inmediato. El criterio de reproducibilidad del Paso 2 se cumple
  para la topología mínima.
- La red de gestión `clab` (172.20.20.0/24) se crea sola, como describe la
  documentación de Containerlab. El plano de gestión out-of-band del diseño sale gratis.
- Los contenedores Alpine consumen ~2 MiB cada uno: el coste del plano de datos
  es despreciable frente a Wazuh, Greenbone y los modelos.

## Escalón 1b — CPE OpenWrt real (23/08/2026)

**La imagen se construye y la VM arranca, pero el bootstrap de vrnetlab se cuelga.**

Lo que **sí** funciona:

- Imagen `vrnetlab/openwrt_openwrt:23.05.5` construida sin `make`, replicando a mano los
  pasos del Makefile. MD5 de la imagen de OpenWrt verificado contra el que declara vrnetlab.
- **KVM disponible en WSL2**: el CPU expone `svm`, `/dev/kvm` existe y QEMU arranca con
  `-enable-kvm` dentro del contenedor privilegiado. No hay emulación por software.
- La VM de OpenWrt **arranca correctamente**: el log muestra el prompt `root@OpenWrt:/#`.
- **Consumo: ~130 MiB**, muy por debajo de la estimación de 0,5–1 GB. La VM no es el problema
  de memoria que temíamos.

Lo que **no** funciona:

El bootstrap de `launch.py` se detiene siempre en el mismo punto: cambia la contraseña de root,
ajusta `/etc/group`, crea `/home/root`, corrige permisos de `/etc/config`, vuelca
`/etc/config/network` y se queda ahí. **Nunca ejecuta los `uci set network.mgmt`** que
configuran la interfaz de gestión, ni reasigna la LAN de `eth0` a `eth2`.

Consecuencias: el nodo queda `unhealthy`, el SSH de la VM no responde (TCP conecta porque lo
sirve QEMU, pero falla el intercambio de banner), y el abonado no obtiene DHCP porque `eth2`
no pertenece a ningún bridge.

**Reproducido tres veces** de forma idéntica, incluida una sin declarar `USERNAME`/`PASSWORD`
—una causa documentada de cuelgues similares— que se descartó así.

**Sospecha principal:** en `launch.py`, el bloque que reasigna la LAN lee la consola con
`read_very_eager()`, que es **no bloqueante**. Si la salida de `cat /etc/config/network` no ha
llegado entera al buffer, el `re.search` del bloque `br-lan` no encuentra nada y la
reconfiguración **se salta en silencio**, sin log ni error. Un entorno lento —QEMU sobre WSL2
en un CPU de 15 W— favorece esa carrera. No está confirmado que sea la causa del cuelgue previo.

**Opciones pendientes de decidir:**

1. Probar OpenWrt **24.10.0**, también en la lista de versiones probadas por vrnetlab.
2. Configurar el CPE a mano por la consola serie, si se consigue tomarla de `launch.py`.
3. Usar un contenedor Linux como CPE provisional y aplazar el OpenWrt real.
4. Abrir incidencia en el proyecto vrnetlab.
