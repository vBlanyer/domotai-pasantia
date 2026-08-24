# Catálogo cerrado de acciones

El EDR no ejecuta comandos: **selecciona una acción de este catálogo**, y el conector la traduce
al comando concreto sobre el nodo. Un conjunto cerrado y enumerado es auditable, comprobable y
acotado en su radio de impacto; un canal de comandos libres no lo es. Esta es la condición que
impide que el canal SSH degenere en ejecución remota arbitraria (ver [protocolos](./protocolos-comunicacion-sandbox.md)).

Cada acción se define por: **precondición**, **efecto esperado**, **reversibilidad**, **cómo se
verifica** y si **requiere validación humana**. El comando mostrado es el del sandbox actual
(nodos Linux); sobre un CPE OpenWrt real cambiaría el conector, no la acción abstracta que el
EDR emite.

---

## Estructura de una orden de acción

Lo que el EDR emite hacia el conector (ver el contrato en [flujo §5](./flujo-edr-playbook-sandbox.md)):

```
accion_id        identificador del catalogo (p. ej. AISLAR_NODO)
decision_id      trazable hasta la alerta que la origino
nodo_objetivo    activo sobre el que se actua
parametros       especificos de la accion (IP a bloquear, servicio, etc.)
requiere_humano  si la orden queda retenida hasta aprobacion
justificacion    razonamiento explicable que la sustenta
```

Dos propiedades no negociables, ya fijadas en el diseño del flujo: **idempotencia** (reejecutar
no cambia el efecto) y **trazabilidad** (toda orden reconstruible hasta su alerta de origen).

---

## Las acciones

### Categoría A — Observación (sin efecto sobre el objetivo)

Acciones de solo lectura. Nunca requieren validación humana: no cambian nada.

| ID | Efecto | Comando (sandbox Linux) | Verificación |
|----|--------|--------------------------|--------------|
| `OBS_CONEXIONES` | Volcar conexiones activas del nodo | `ss -tunap` / `netstat -tunap` | Salida capturada |
| `OBS_PROCESOS` | Listar procesos en ejecución | `ps aux` | Salida capturada |
| `OBS_ESCUCHA` | Puertos a la escucha | `ss -lntu` | Salida capturada |
| `OBS_CONFIG` | Recoger configuración de red | `ip addr; ip route` | Salida capturada |
| `OBS_CAPTURA` | Captura breve de tráfico (N paquetes) | `timeout 10 tcpdump -c 100 -w -` | Fichero pcap devuelto |

**Precondición común:** acceso SSH al nodo. **Reversibilidad:** no aplica (no hay efecto).

### Categoría B — Contención de red (reversible)

Limitan el alcance del nodo sin apagarlo. Reversibles. Validación humana **según impacto**: aislar
al abonado interrumpe su servicio; bloquear una IP maliciosa concreta, no.

| ID | Efecto | Comando | Reversión | Requiere humano |
|----|--------|---------|-----------|-----------------|
| `BLOQUEAR_IP` | Descartar tráfico hacia/desde una IP | `iptables -A INPUT -s <ip> -j DROP` | `iptables -D INPUT -s <ip> -j DROP` | No |
| `BLOQUEAR_PUERTO` | Cerrar un puerto expuesto por firewall | `iptables -A INPUT -p tcp --dport <p> -j DROP` | regla `-D` simétrica | No |
| `AISLAR_NODO` | Cortar toda la LAN del nodo salvo gestión | `iptables -A FORWARD -s <ip_nodo> -j DROP` | `-D` simétrica | **Sí** |
| `LIMITAR_BANDA` | Estrangular el ancho de banda del nodo | `tc qdisc add dev <if> root tbf ...` | `tc qdisc del dev <if> root` | Según umbral |

**Verificación:** reconsultar la tabla (`iptables -L -n` / `tc qdisc show`) y confirmar la regla.

### Categoría C — Endurecimiento (parcialmente reversible)

Reducen la superficie de ataque cambiando el estado del equipo. Cambios de credenciales o de
servicios pueden afectar al servicio legítimo → validación humana por defecto.

| ID | Efecto | Comando | Reversión | Requiere humano |
|----|--------|---------|-----------|-----------------|
| `CERRAR_SERVICIO` | Detener un servicio expuesto (telnet, etc.) | `pkill <servicio>` / `service <s> stop` | Rearrancar el servicio | **Sí** |
| `FORZAR_CAMBIO_PASS` | Invalidar credenciales por defecto | `passwd -l <usuario>` (bloquea) | `passwd -u <usuario>` | **Sí** |
| `MATAR_CONEXION` | Cerrar una sesión concreta sospechosa | `ss -K dst <ip>` | No aplica (una sesión) | No |

### Categoría D — Remediación (alto impacto)

Restauran o reinician. Alto impacto, siempre validación humana.

| ID | Efecto | Comando | Reversión | Requiere humano |
|----|--------|---------|-----------|-----------------|
| `REINICIAR_NODO` | Reiniciar el equipo | `reboot` | No aplica (vuelve solo) | **Sí** |
| `RESTAURAR_CONFIG` | Volver a una configuración conocida | copiar respaldo + recargar | Restaurar el respaldo previo | **Sí** |

---

## Regla de validación humana

Se deriva de tres criterios (los umbrales concretos se fijan en el [Paso 8](./metricas-y-evaluacion.md)):

1. La acción **no es reversible** o **interrumpe el servicio del abonado** → siempre humano.
2. La **confianza del clasificador** está por debajo del umbral → humano.
3. La clasificación del EDR y la **severidad de Wazuh discrepan** → humano (uno de los dos se equivoca).

Categorías A y las acciones marcadas «No» pasan directas; el resto queda retenido hasta aprobación.

---

## Qué queda fuera del catálogo, a propósito

- **Contraataque o acción sobre el origen externo** de la alerta: fuera de alcance y de la red controlada.
- **Borrado de datos o de logs**: destruye la traza de auditoría que el proyecto exige.
- **Cualquier comando no listado**: si el EDR necesitara algo que no está aquí, se añade al
  catálogo con su ficha, no se abre un canal genérico.

---

## Estado en el laboratorio actual

Las acciones de **observación (A)** y **contención de red (B)** son ejecutables hoy sobre los
nodos Linux del sandbox por SSH. Las de **endurecimiento (C)** dependen del servicio concreto.
Las de **remediación (D)** funcionan pero, como todo en el CPE, serán plenamente representativas
solo con OpenWrt real: un `RESTAURAR_CONFIG` sobre un CPE de verdad usaría UCI, no copia de ficheros.

> **Límite heredado:** el objetivo principal del catálogo es el CPE, y el CPE es provisional.
> Las acciones están diseñadas para ser correctas sobre OpenWrt, pero solo se han podido probar
> sobre el sustituto Linux. Queda como validación pendiente al desbloquear vrnetlab.

---

## Documentos relacionados

- [Flujo de operación](./flujo-edr-playbook-sandbox.md) · [Protocolos](./protocolos-comunicacion-sandbox.md) · [Métricas y evaluación](./metricas-y-evaluacion.md)
