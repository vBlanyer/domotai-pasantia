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

**Reproducido cuatro veces** de forma idéntica:

| Intento | Versión | Variante | Resultado |
|---------|---------|----------|-----------|
| 1 | 23.05.5 | con `USERNAME`/`PASSWORD` | Cuelgue |
| 2 | 23.05.5 | redespliegue limpio | Cuelgue, mismo punto |
| 3 | 23.05.5 | **sin** bloque `env` | Cuelgue, mismo punto |
| 4 | **24.10.0** | sin bloque `env` | Cuelgue, mismo punto |

Con eso quedan descartadas dos hipótesis: **no es un choque de credenciales** (intento 3) y
**no depende de la versión de OpenWrt** (intento 4, con la otra versión que vrnetlab declara
probada). El punto de parada es exactamente el mismo en los cuatro: tras volcar
`/etc/config/network`, un `^C` y `echo READY`, sin llegar nunca a `uci set network.mgmt`.

**Sospecha principal:** en `launch.py`, el bloque que reasigna la LAN lee la consola con
`read_very_eager()`, que es **no bloqueante**. Si la salida de `cat /etc/config/network` no ha
llegado entera al buffer, el `re.search` del bloque `br-lan` no encuentra nada y la
reconfiguración **se salta en silencio**, sin log ni error. Un entorno lento —QEMU sobre WSL2
en un CPU de 15 W— favorece esa carrera. No está confirmado que sea la causa del cuelgue previo.

**Opciones pendientes de decidir:**

1. ~~Probar OpenWrt 24.10.0~~ — **descartado**, falla igual (intento 4).
2. Configurar el CPE a mano por la consola serie, si se consigue tomarla de `launch.py`.
3. **Usar un contenedor Linux como CPE provisional** y aplazar el OpenWrt real. Es la única
   opción que desbloquea el resto del bloque 1 sin depender de terceros.
4. Abrir incidencia en el proyecto vrnetlab con el diagnóstico ya hecho.

## Otra incidencia: colisión de puertos (24/08/2026)

El despliegue falló con `failed to bind host port 0.0.0.0:8080/tcp: address already in use`.
El puerto lo ocupaba un servidor Vite de otro proyecto del equipo (`crm-v2-domotai-frontend`),
no un resto del laboratorio. **Los puertos de LuCI se movieron a 8180 y 8543.** Conviene
recordarlo: el laboratorio comparte máquina con otros desarrollos y los puertos bajos
habituales pueden estar tomados.

## Escalón 1c — Red FTTx completa con CPE provisional (24/08/2026)

Topología [fttx-lab.clab.yml](fttx-lab.clab.yml): 7 nodos —borde, CPE, switch LAN, abonado,
IoT, objetivo vulnerable y auditor— desplegada **sin errores** y validada de extremo a extremo.

| Comprobación | Resultado |
|--------------|-----------|
| Bridge del switch con sus 4 puertos | Correcto |
| Conectividad dentro de la LAN | 0 % de pérdida |
| Extremo a extremo atravesando el CPE | 0 % de pérdida, 2 saltos |
| Nmap en el auditor | Descubre los 8 hosts del plano de gestión |
| Exportación a draw.io | Genera el diagrama correctamente |

### El sandbox no es el problema de memoria

| Componente | Estimado | **Medido** |
|------------|----------|------------|
| 7 nodos de la topología completa | 1,5–2 GB | **~12 MiB** |
| CPE con OpenWrt (VM QEMU) | 0,5–1 GB | **~130 MiB** |

Las estimaciones del diseño estaban **dos órdenes de magnitud por encima**. El plano de datos
es prácticamente gratis.

### El problema real: la máquina está compartida

Con el laboratorio desplegado, el sistema marcaba 6.154 MiB usados y solo 5.805 MiB
disponibles de 11,9 GiB. **El laboratorio aporta 12 MiB de esos 6 GB.** El resto es el
entorno de trabajo:

| Consumidor | Memoria |
|------------|---------|
| VS Code server, extensiones y procesos node | ~5.176 MiB |
| CLI de cloud-code | ~1.204 MiB |
| Proyecto `crm-v2-domotai` (8 procesos) | ~978 MiB |
| **El laboratorio FTTx** | **~12 MiB** |

**Consecuencia para el presupuesto del Perfil A.** El camino interactivo necesita sandbox
(~0,01 GB) + Wazuh (~4 GB) + encoder (~0,5 GB) + modelo de 3B (~2 GB) ≈ **6,5 GB**, frente a
los ~5,8 GB libres mientras el entorno de desarrollo está abierto. **No cabe trabajando a la
vez.** Cabe si se cierran el otro proyecto y las herramientas que no hagan falta.

No es un bloqueo, pero sí una condición de operación que debe constar: **las campañas de
medición y evaluación se ejecutan con el entorno de desarrollo cerrado**, o los resultados no
serán comparables entre sí.

Wazuh sigue siendo la única cifra grande sin medir, y por tanto el mayor riesgo del
presupuesto.
