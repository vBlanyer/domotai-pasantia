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
> **Pendiente de aplicar.** Hasta entonces, todas las mediciones de abajo parten de 7,4 GiB.

## Resultados

| Escalón | Qué se añade | Estimado | **Medido** | ¿Cabe? |
|---------|--------------|----------|------------|--------|
| 0 | Base: WSL en reposo | — | 1.965 MiB usados, 5.638 MiB libres | — |
| 1a | Containerlab, 3 nodos Alpine (prueba de humo) | — | **+~90 MiB** (6,3 MiB en contenedores) | Sí, holgado |
| 1b | Containerlab con OpenWrt (QEMU) y FRR | 1,5–2 GB | *pendiente* | ? |
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
