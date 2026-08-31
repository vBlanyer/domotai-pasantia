# Generar alertas para Wazuh

Cómo producir las alertas que el EDR consumirá. Hay dos vías: **manual** (fiable, para probar
el pipeline) y **por reenvío** (un ataque real produce la alerta, más realista pero con matices).

Requisito común: el Wazuh manager corriendo (`sh lab/wazuh-run.sh up`) con la recepción de
syslog activada en el 514/udp.

---

## Vía manual — enviar un evento syslog a mano

La más fiable. Se envía un paquete syslog bien formado directamente al manager. Útil para
comprobar reglas concretas sin montar el ataque real.

**Formato del paquete:** `<PRIORIDAD>MES DIA HH:MM:SS host servicio[pid]: mensaje`
La prioridad `38` = facility `auth` (4) × 8 + severidad `info` (6).

### Un login SSH fallido → nivel 5

```sh
docker exec clab-fttx-lab-objetivo-vuln sh -c \
 'echo "<38>Aug 24 15:40:00 objetivo-vuln sshd[9001]: Failed password for root from 45.83.12.7 port 55001 ssh2" | nc -u -w1 172.20.20.9 514'
```

Produce: `nivel 5, regla 5760, sshd: authentication failed, data.srcip=45.83.12.7`.

### Una fuerza bruta → nivel 10 (correlacionada)

Ocho fallos seguidos desde la **misma IP**. Wazuh los correlaciona y eleva el nivel:

```sh
docker exec clab-fttx-lab-objetivo-vuln sh -c '
for i in $(seq 1 8); do
  echo "<38>Aug 24 15:41:0$i objetivo-vuln sshd[81$i]: Failed password for root from 91.240.118.9 port 6000$i ssh2" | nc -u -w1 172.20.20.9 514
done'
```

Produce 7 alertas de nivel 5 **y una de nivel 10, regla 5763, «brute force»**. Es la diferencia
clave para el triaje: siete eventos rutinarios frente a un ataque correlacionado.

### Ver el resultado

```sh
docker exec clab-fttx-lab-wazuh sh -c 'tail -5 /var/ossec/logs/alerts/alerts.json'
# o filtrado por IP:
docker exec clab-fttx-lab-wazuh sh -c 'grep 91.240.118.9 /var/ossec/logs/alerts/alerts.json'
```

---

## Vía por reenvío — desde el propio nodo atacado

Más realista: el nodo reenvía sus logs y un ataque real produce la alerta. Configurado en
`objetivo-vuln` (Metasploitable), que usa el `syslogd` clásico.

```sh
# en el objetivo, una vez:
echo 'auth,authpriv.*   @172.20.20.9' >> /etc/syslog.conf
pkill syslogd; /sbin/syslogd -u syslog        # reinicio COMPLETO, el HUP no basta
```

Luego, cualquier escritura en el log de auth se reenvía:

```sh
docker exec clab-fttx-lab-objetivo-vuln sh -c \
 'logger -p auth.info -t "sshd[2001]" "Failed password for root from 45.83.12.7 port 40001 ssh2"'
```

> **Matiz encontrado (24/08/2026):** el `syslogd` antiguo de Metasploitable reenvía con una
> cabecera que la regla de decodificación de Wazuh **no engancha igual** que un paquete bien
> formado, así que estos eventos no siempre generan alerta. El envío manual con `nc` (vía de
> arriba) sí es fiable. Para el pipeline de pruebas, usar la vía manual; el reenvío queda
> pendiente de afinar el formato o de usar un reenviador más moderno (rsyslog) en los nodos.

---

## Ataques reales que generan logs

Los que ya se pueden lanzar contra el laboratorio. Producen entradas en el `auth.log` del nodo
atacado; para que lleguen a Wazuh hay que combinarlos con el reenvío de arriba.

```sh
# Puerta trasera ingreslock (1524) — deja rastro de conexion
docker exec clab-fttx-lab-auditor sh -c 'echo id | nc -w2 192.168.1.30 1524'

# Telnet sin auth al IoT
docker exec clab-fttx-lab-auditor sh -c 'echo id | nc -w2 192.168.1.20 23'

# Escaneo de puertos — nmap genera conexiones que el objetivo registra
docker exec clab-fttx-lab-auditor nmap -sV 192.168.1.30
```

---

## Mapa de niveles de Wazuh (los que importan para el triaje)

| Nivel | Significado | Ejemplo | Acción típica del EDR |
|-------|-------------|---------|------------------------|
| 3 | Informativo | Servicio arrancado, benchmark CIS | Ignorar / registrar |
| 5 | Aviso | Un login fallido suelto | Vigilar, baja prioridad |
| 10 | Ataque | Fuerza bruta correlacionada | Priorizar, candidato a contención |
| 12+ | Crítico | Compromiso confirmado | Contención inmediata |

El **nivel es el baseline de la Fase 6**: el prototipo se compara contra la clasificación que
Wazuh hace por reglas.

> **Ruido de arranque:** las primeras ~180 alertas tras levantar Wazuh son su autoauditoría CIS
> del propio contenedor (regla 190xx), no del laboratorio. Se filtran por regla o por
> `agent.id`.
