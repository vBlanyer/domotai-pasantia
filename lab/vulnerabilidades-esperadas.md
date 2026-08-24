# Inventario de vulnerabilidades esperadas

**Este documento es el *ground truth* del proyecto.** Registra qué se ha plantado
deliberadamente en cada nodo de [fttx-lab.clab.yml](fttx-lab.clab.yml), de modo que al evaluar
se sepa de antemano:

- qué **debería** encontrar el auditor — los verdaderos positivos esperados;
- qué **no existe** y por tanto sería un **falso positivo**;
- qué debería decidir el EDR ante una alerta que apunte a cada nodo.

Sin este inventario, el etiquetado del dataset de la Fase 6 sería un juicio subjetivo. Con él,
se deriva de la composición conocida del laboratorio.

> **Regla de mantenimiento:** todo nodo que se añada o modifique en el `.clab.yml` se refleja
> aquí en el mismo commit. Si los dos ficheros se desincronizan, la evaluación deja de ser
> válida y nadie se entera.

Verificado el 24/08/2026 con `nmap -Pn -sV` desde el nodo `auditor`.

---

## `objetivo-vuln` · 192.168.1.30

**Imagen:** `tleemcjr/metasploitable2:latest`

Es el nodo del que depende la evaluación. Metasploitable2 es un objetivo de práctica
reconocido, con servicios cuyas vulnerabilidades están documentadas públicamente.

### Hallazgos esperados

| Puerto | Servicio y versión | Qué debe detectarse | Gravedad |
|--------|--------------------|---------------------|----------|
| 21/tcp | **vsftpd 2.3.4** | Versión con **puerta trasera conocida** (CVE-2011-2523) | Crítica |
| 6667/tcp | **UnrealIRCd** | Versión con **puerta trasera conocida** (CVE-2010-2075) | Crítica |
| 139, 445/tcp | **Samba 3.x** | Ejecución de comandos por *usermap script* (CVE-2007-2447) | Crítica |
| **1524/tcp** | **ingreslock** | **Shell de root sin autenticación.** La huella de nmap devuelve literalmente `root@objetivo-vuln:/#` | Crítica |
| 512, 513, 514/tcp | rexec, rlogin, rsh | **Servicios «r» sin cifrar**, autenticación basada en confianza | Alta |
| 23/tcp | Linux telnetd | Administración **sin cifrar** | Alta |
| 5900/tcp | VNC protocolo 3.3 | Escritorio remoto con protocolo obsoleto y contraseña débil | Alta |
| 3306/tcp | MySQL 5.0.51a | Base de datos expuesta, credenciales por defecto | Alta |
| 5432/tcp | PostgreSQL 8.3 | Base de datos expuesta, credenciales por defecto | Alta |
| 1099/tcp | java-rmi (GNU Classpath) | Registro RMI que permite carga remota de clases | Alta |
| 6000/tcp | X11 | Servidor gráfico accesible por red | Media |
| 22/tcp | OpenSSH 4.7p1 | Versión obsoleta (2007) | Media |
| 80/tcp | Apache 2.2.8 con DAV/2 | Servidor web obsoleto con WebDAV activo | Media |
| 25/tcp | Postfix smtpd | Correo expuesto | Media |
| 111/tcp | rpcbind | Enumeración de servicios RPC | Media |
| 2121/tcp | ProFTPD 1.3.1 | Segundo FTP, versión obsoleta | Media |

**Total: 19 puertos abiertos**, de los que 981 de los 1000 más comunes están cerrados.

Los tres CVE citados son los mejor documentados del conjunto. El resto se clasifica por
**categoría de exposición**, que es lo que el auditor debe reportar aunque no exista un CVE
concreto asociado.

---

## `iot` · 192.168.1.20

**Imagen:** `alpine:latest` con servicios añadidos deliberadamente.

Representa una cámara, un televisor o un enchufe inteligente sin parchear: la clase de equipo
que suele ser la puerta de entrada a una red doméstica.

| Puerto | Servicio | Qué debe detectarse | Gravedad |
|--------|----------|---------------------|----------|
| 23/tcp | telnetd (busybox) | **Telnet sin cifrar y sin autenticación**: entrega una shell directa | Crítica |
| 80/tcp | darkhttpd 1.17 | Interfaz de administración web sin TLS | Media |

Nmap lo identifica como `Coolstream set-top box telnetd` y clasifica el equipo como
**media device**, lo que confirma que la huella es realista.

**Nota:** la página del puerto 80 simula el panel de un «IPCam-2000» con firmware de 2016. Es
decorativa — **no** implementa autenticación real, así que **no** debe esperarse ningún
hallazgo de credenciales débiles sobre ella. Detectarlo sería un falso positivo.

---

## Nodos sin vulnerabilidades plantadas

Igual de importante: aquí **no debe encontrarse nada**. Cualquier hallazgo sobre estos nodos es
un **falso positivo** salvo que se documente antes en este fichero.

| Nodo | Dirección | Estado |
|------|-----------|--------|
| `cpe` | 192.168.1.1 · 10.0.1.2 | **Todos los puertos cerrados.** Es el CPE provisional en Linux: solo encamina |
| `borde` | 10.0.1.1 | Sin servicios |
| `sw-lan` | Sin IP | Capa 2, sin superficie |
| `abonado` | 192.168.1.10 | Sin servicios |
| `auditor` | Solo gestión | Es quien escanea, no un objetivo |

### El hueco más importante del inventario

**El CPE, que es el objetivo principal del proyecto, hoy no tiene ninguna vulnerabilidad.**

Un OpenWrt real expondría dropbear en el 22, LuCI en el 80 y dnsmasq en el 53, además de sus
credenciales de fábrica y su gestión remota — que es justo la superficie que el caso de uso
quiere estudiar. El CPE provisional no ofrece nada de eso.

Mientras siga bloqueado el arranque de OpenWrt en vrnetlab, **la evaluación no puede cubrir el
escenario central**: compromiso del CPE por credenciales débiles o gestión expuesta. Puede
cubrir movimiento lateral y compromiso de dispositivos de la LAN, que no es poco, pero conviene
que conste como limitación en el informe.

---

## Cómo se usa esto para etiquetar

1. Se genera actividad sobre el laboratorio y **Wazuh emite alertas**.
2. Cada alerta se contrasta contra la fila de este documento correspondiente al nodo al que
   apunta.
3. Si la alerta señala una exposición **listada aquí** → **verdadero positivo**.
4. Si señala algo que este documento dice que **no está presente** → **falso positivo**.
5. Se conserva el **nivel de regla de Wazuh** de cada alerta: es el baseline con el que se
   comparará el prototipo en la Fase 6.

> **Aviso metodológico.** Este inventario se construyó a partir de la salida del propio escáner,
> así que no es independiente de él. Para evaluar al **auditor** hay que contrastarlo además
> con la documentación pública de Metasploitable2, no solo con lo que Nmap reporte. Para
> evaluar al **EDR** sí sirve directamente, porque ahí el auditor es una entrada y no el sujeto
> de la medición.
