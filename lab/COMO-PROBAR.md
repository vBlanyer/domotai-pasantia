# Cómo probar todo el laboratorio

Guía de verificación de extremo a extremo. Si sigues esto y todo pasa, el Bloque 1 del
[camino](../documentacion/00-general/camino-paso-a-paso.md) está operativo: la red FTTx genera
alertas reales que el EDR podrá consumir.

Requisitos: WSL con Docker y Containerlab; el entorno de desarrollo pesado (VS Code, otros
proyectos) **cerrado** si vas a medir memoria, porque es el único consumidor grande de la máquina.

---

## 1. Levantar todo de una vez

```sh
sh lab/lab.sh up
```

Hace tres cosas en orden: despliega la red (`containerlab deploy`), arranca el Wazuh manager
(`wazuh-run.sh`) y activa el reenvío de syslog (`reenvio-syslog.sh`). Tarda 1–2 min, casi todo
esperando a que Wazuh levante sus demonios.

Comprobar que está todo vivo:

```sh
sh lab/lab.sh status
```

Debe listar 7 nodos `clab-fttx-lab-*` más `clab-fttx-lab-wazuh`, todos *Up*.

---

## 2. Prueba de humo automática

```sh
sh lab/lab.sh test
```

Verifica los tres eslabones de la cadena y debe imprimir:

```
-- 1. Conectividad LAN (abonado -> objetivo)      OK
-- 2. El auditor ve los servicios del objetivo    10 puertos abiertos detectados
-- 3. Un ataque genera alerta en Wazuh            10 alertas ... nivel 10: OK
```

Si el paso 3 da 0 alertas, el reenvío no está activo: `sh lab/reenvio-syslog.sh`.

---

## 3. Pruebas manuales, una por capa

### 3.1 La red encamina

```sh
# dentro de la LAN
docker exec clab-fttx-lab-abonado ping -c2 192.168.1.30
# extremo a extremo, atravesando el CPE (2 saltos)
docker exec clab-fttx-lab-abonado traceroute -n 10.0.1.1
```

### 3.2 El auditor descubre y escanea

```sh
docker exec -it clab-fttx-lab-auditor sh      # entrar al auditor
nmap -sn 192.168.1.0/24                        # los 4 hosts de la LAN
nmap -Pn -sV 192.168.1.30                      # 19 servicios de Metasploitable
nmap -Pn -sV --top-ports 100 192.168.1.20      # telnet + http del IoT
nmap -Pn --top-ports 100 192.168.1.1           # el CPE: TODO cerrado (esperado)
```

> Escanea siempre las IP del plano de datos (192.168.1.x, 10.0.1.x), **nunca** las de gestión
> (172.20.20.x). Contrasta lo que encuentres con [vulnerabilidades-esperadas.md](vulnerabilidades-esperadas.md):
> lo que salga ahí es verdadero positivo; lo que no, falso positivo.

### 3.3 Tomar una shell de un equipo comprometido

```sh
# puerta trasera ingreslock: shell de root directa
docker exec -it clab-fttx-lab-auditor sh
nc 192.168.1.30 1524
id                    # uid=0(root)
hostname              # objetivo-vuln  (estas DENTRO de esa maquina)

# telnet sin auth del IoT
nc 192.168.1.20 23    # ignora los bytes raros del inicio; escribe: id, hostname
```

### 3.4 Generar alertas en Wazuh

Ver [generar-alertas.md](generar-alertas.md) para el detalle. Lo esencial:

```sh
# un login fallido (via reenvio real desde auth.log) -> nivel 5
docker exec clab-fttx-lab-objetivo-vuln sh -c \
 'logger -p auth.info -t "sshd[8001]" "Failed password for admin from 88.88.88.88 port 41001 ssh2"'

# ver la alerta que consumira el EDR
docker exec clab-fttx-lab-wazuh sh -c 'tail -3 /var/ossec/logs/alerts/alerts.json'
```

Debe aparecer `rule.level: 5`, `rule.id: 5760`, `data.srcip: 88.88.88.88`.

---

## 4. Qué estás mirando: la alerta que consume el EDR

Cada línea de `alerts.json` es un objeto con los campos que el módulo de ingesta normalizará:

| Campo | Ejemplo | Papel en el EDR |
|-------|---------|-----------------|
| `rule.level` | `5` / `10` | **Baseline** de la Fase 6 |
| `rule.id` | `5760` / `5763` | Qué regla disparó |
| `rule.description` | `sshd: brute force...` | Texto de la alerta |
| `data.srcip` | `88.88.88.88` | IP del atacante (ya parseada) |
| `data.dstuser` | `root` | Usuario objetivo |
| `agent.id` | `000` | Nodo sin agente → se identifica por los campos, no por el id |
| `full_log` | texto crudo | Se conserva para la traza (RF-09) |

Nivel 5 = un intento suelto. Nivel 10 = fuerza bruta **correlacionada**. Esa distinción es
justo lo que el EDR debe priorizar.

---

## 5. Reiniciar limpio y apagar

```sh
sh lab/lab.sh down          # baja red + Wazuh
sh lab/lab.sh up            # vuelve a levantar todo
```

> **Nunca** uses `docker restart` sobre un nodo: borra el cableado del plano de datos que crea
> Containerlab. Para reiniciar uno, redespliega con `containerlab deploy -t lab/fttx-lab.clab.yml --reconfigure`.

---

## 6. Límites conocidos de esta prueba

- **El CPE no expone nada.** Es el sustituto en Linux; el escaneo devuelve todo cerrado. Con
  OpenWrt real mostraría dropbear, LuCI y dnsmasq. El escenario central del caso de uso
  —compromiso del CPE— no es evaluable hasta resolver el arranque de OpenWrt en vrnetlab.
- **La fuerza bruta de nivel 10 se prueba por inyección directa al manager.** El reenvío desde
  `auth.log` entrega bien los eventos sueltos, pero su latencia por datagrama dispersa las
  ráfagas fuera de la ventana de correlación de Wazuh. Es una limitación del reenviador
  artesanal, no del pipeline.
- **Las primeras ~180 alertas tras arrancar Wazuh** son su autoauditoría CIS del propio
  contenedor, no del laboratorio. Se filtran por regla (190xx).
- **El reenvío no sobrevive a un redespliegue:** tras cada `containerlab deploy`, reejecuta
  `sh lab/reenvio-syslog.sh` (o usa `sh lab/lab.sh up`, que ya lo hace).
- **Reproducibilidad verificada:** el ciclo `sh lab/lab.sh down && sh lab/lab.sh up && sh lab/lab.sh test`
  pasa los tres eslabones desde cero, sin ningún estado montado a mano. Wazuh activa su recepción
  de syslog al arrancar y el CPE tiene IP de gestión fija para que las rutas del auditor aguanten.
