# Catálogo cerrado de acciones

El motor de triaje no ejecuta comandos: **selecciona una acción de este catálogo**, y el conector la traduce
al comando concreto sobre el nodo. Un conjunto cerrado y enumerado es auditable, comprobable y
acotado en su radio de impacto; un canal de comandos libres no lo es. Esta es la condición que
impide que el canal SSH degenere en ejecución remota arbitraria (ver [protocolos](./protocolos-comunicacion-sandbox.md)).

Cada acción se define por: **precondición**, **efecto esperado**, **reversibilidad**, **cómo se
verifica** y si **requiere validación humana**. El comando mostrado es el del sandbox actual
(nodos Linux); sobre un equipo de borde OpenWrt real cambiaría el conector, no la acción abstracta que el
Motor de triaje emite.

---

## Estructura de una orden de acción

Lo que el motor de triaje emite hacia el conector (ver el contrato en [flujo §5](./flujo-triaje-playbook-sandbox.md)):

```
accion_id        identificador del catalogo (p. ej. AISLAR_NODO)
decision_id      trazable hasta la alerta que la origino
nodo_objetivo    activo sobre el que se actua
parametros       especificos de la accion (IP a bloquear, servicio, etc.)
impacto          ninguno | localizado | alcanza_servicio  (RF-17: lo que el perfil filtra y las metricas de continuidad miden)
requiere_humano  si la orden queda retenida hasta aprobacion (lo deriva el perfil del impacto)
justificacion    razonamiento explicable que la sustenta
```

Dos propiedades no negociables, ya fijadas en el diseño del flujo: **idempotencia** (reejecutar
no cambia el efecto) y **trazabilidad** (toda orden reconstruible hasta su alerta de origen).

---

## Las acciones

### Categoría A — Observación (sin efecto sobre el objetivo)

Acciones de solo lectura. Impacto `ninguno`: nunca requieren validación humana porque no cambian nada.

| ID | Impacto | Efecto | Comando (sandbox Linux) | Verificación |
|----|---------|--------|--------------------------|--------------|
| `OBS_CONEXIONES` | ninguno | Volcar conexiones activas del nodo | `ss -tunap` / `netstat -tunap` | Salida capturada |
| `OBS_PROCESOS` | ninguno | Listar procesos en ejecución | `ps aux` | Salida capturada |
| `OBS_ESCUCHA` | ninguno | Puertos a la escucha | `ss -lntu` | Salida capturada |
| `OBS_CONFIG` | ninguno | Recoger configuración de red | `ip addr; ip route` | Salida capturada |
| `OBS_CAPTURA` | ninguno | Captura breve de tráfico (N paquetes) | `timeout 10 tcpdump -c 100 -w -` | Fichero pcap devuelto |

**Precondición común:** acceso SSH al nodo. **Reversibilidad:** no aplica (no hay efecto).

### Categoría B — Contención de red (reversible)

Limitan el alcance del nodo sin apagarlo. Todas reversibles. El **impacto** de cada una es el campo
que el [perfil del cliente](./politica-decision-continuidad.md#4-el-perfil-de-cliente) lee para
decidir si requiere validación humana: `localizado` actúa sobre el atacante y no toca el servicio;
`alcanza_servicio` puede interrumpir lo que el equipo presta.

| ID | Impacto | Efecto | Comando | Reversión |
|----|---------|--------|---------|-----------|
| `BLOQUEAR_IP` | localizado | Descartar tráfico hacia/desde una IP | `iptables -A INPUT -s <ip> -j DROP` | `iptables -D INPUT -s <ip> -j DROP` |
| `BLOQUEAR_PUERTO` | alcanza_servicio | Cerrar un puerto expuesto por firewall | `iptables -A INPUT -p tcp --dport <p> -j DROP` | regla `-D` simétrica |
| `AISLAR_NODO` | alcanza_servicio | Cortar toda la LAN del nodo salvo gestión | `iptables -A FORWARD -s <ip_nodo> -j DROP` | `-D` simétrica |
| `LIMITAR_BANDA` | alcanza_servicio | Estrangular el ancho de banda del nodo (umbral: parámetro del perfil) | `tc qdisc add dev <if> root tbf ...` | `tc qdisc del dev <if> root` |

**Verificación:** reconsultar la tabla (`iptables -L -n` / `tc qdisc show`) y confirmar la regla.

> **Corrección respecto a la versión anterior** (revisión de la Fase 4, RF-17/RF-18). `BLOQUEAR_PUERTO`
> figuraba como «Requiere humano: No», pero cerrar un puerto puede tumbar un servicio de producción:
> su impacto es `alcanza_servicio`, así que **lo decide el perfil**, no un «No» a secas. `LIMITAR_BANDA`
> figuraba «según umbral» sin umbral: el umbral es ahora un parámetro del perfil, no un valor mágico.

### Categoría C — Endurecimiento (parcialmente reversible)

Reducen la superficie de ataque cambiando el estado del equipo. Cambios de credenciales o de
servicios pueden afectar al servicio legítimo, de ahí su impacto `alcanza_servicio`.

| ID | Impacto | Efecto | Comando | Reversión |
|----|---------|--------|---------|-----------|
| `CERRAR_SERVICIO` | alcanza_servicio | Detener un servicio expuesto (telnet, etc.) | `pkill <servicio>` / `service <s> stop` | Rearrancar el servicio |
| `FORZAR_CAMBIO_PASS` | alcanza_servicio | Invalidar credenciales por defecto | `passwd -l <usuario>` (bloquea) | `passwd -u <usuario>` |
| `MATAR_CONEXION` | localizado | Cerrar una sesión concreta sospechosa | `ss -K dst <ip>` | Transitoria: el usuario legítimo reconecta |

> **Precondición RF-19 sobre `CERRAR_SERVICIO`:** si el servicio a detener es el propio canal de
> gestión (SSH), la acción se **rechaza** — dejaría el activo inalcanzable. La precondición
> `no_cortar_gestion` del [perfil](./politica-decision-continuidad.md#44-rf-18-y-rf-19-son-precondiciones-duras-no-criterios-de-escalado) lo garantiza.

### Categoría D — Remediación (alto impacto)

Restauran o reinician. Impacto `alcanza_servicio` y alto: la política **nunca las propone por su
cuenta** ([principio de mínimo impacto](./politica-decision-continuidad.md#3-la-política-de-decisión)); solo llegan por escalado humano.

| ID | Impacto | Efecto | Comando | Reversión |
|----|---------|--------|---------|-----------|
| `REINICIAR_NODO` | alcanza_servicio | Reiniciar el equipo | `reboot` | Auto-reversible: el nodo vuelve solo |
| `RESTAURAR_CONFIG` | alcanza_servicio | Volver a una configuración conocida | copiar respaldo + recargar | Restaurar el respaldo previo |

---

## Regla de validación humana

La validación humana ya **no está hardcodeada por acción**: la deriva el
[perfil del cliente](./politica-decision-continuidad.md#42-política-de-continuidad-v3) a partir del
**impacto** de la acción (columna de arriba) y de la **criticidad** del activo. Sobre esa base
configurable, tres criterios adicionales fuerzan la retención (los umbrales concretos se calibran en
el [Paso 8](./metricas-y-evaluacion.md)):

1. El impacto de la acción y el perfil del cliente lo exigen (p. ej. `alcanza_servicio` sobre un
   servicio prestado) → humano.
2. La **confianza del clasificador** está por debajo del umbral → humano.
3. La clasificación del motor de triaje y la **severidad de Wazuh discrepan** → humano (uno de los dos se equivoca).

Y dos **precondiciones duras**, que no son criterios de escalado sino de descarte: una acción sin
reversión verificable (RF-18) no se propone, y una que dejaría el activo sin plano de gestión (RF-19)
se rechaza. Ver el [perfil §4.4](./politica-decision-continuidad.md#44-rf-18-y-rf-19-son-precondiciones-duras-no-criterios-de-escalado).

---

## Qué queda fuera del catálogo, a propósito

- **Contraataque o acción sobre el origen externo** de la alerta: fuera de alcance y de la red controlada.
- **Borrado de datos o de logs**: destruye la traza de auditoría que el proyecto exige.
- **Cualquier comando no listado**: si el motor de triaje necesitara algo que no está aquí, se añade al
  catálogo con su ficha, no se abre un canal genérico.

---

## Estado en el laboratorio actual

Las acciones de **observación (A)** y **contención de red (B)** son ejecutables hoy sobre los
nodos Linux del sandbox por SSH. Las de **endurecimiento (C)** dependen del servicio concreto.
Las de **remediación (D)** funcionan pero, como todo en el equipo de borde, serán plenamente
representativas solo con OpenWrt real: un `RESTAURAR_CONFIG` sobre un enrutador de verdad usaría
UCI, no copia de ficheros.

> **Límite heredado:** el equipo de borde es uno de los objetivos prioritarios del catálogo, y hoy es provisional.
> Las acciones están diseñadas para ser correctas sobre OpenWrt, pero solo se han podido probar
> sobre el sustituto Linux. Queda como validación pendiente al desbloquear vrnetlab.

---

## Documentos relacionados

- [Flujo de operación](./flujo-triaje-playbook-sandbox.md) · [Protocolos](./protocolos-comunicacion-sandbox.md) · [Métricas y evaluación](./metricas-y-evaluacion.md)
