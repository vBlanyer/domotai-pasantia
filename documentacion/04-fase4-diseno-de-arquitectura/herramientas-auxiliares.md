# Herramientas auxiliares para pruebas de XDR

Este documento recopila las **herramientas auxiliares** que se utilizarán para probar y validar el uso de XDR y del módulo de triaje del proyecto. Incluye herramientas de **pentesting** y simulación de ataques —que generan telemetría real para fuentes como [Sysmon](./symons.md)— y herramientas de **análisis de comportamiento y patrones de ataque**, empleadas para detectar, correlacionar y explicar la actividad maliciosa.

Sirve como base de la Fase 4 (diseño de arquitectura) y de la Fase 3 (entorno de pruebas), donde estas herramientas alimentan el dataset etiquetado y validan que las reglas de detección funcionen frente a comportamiento real.

> **Nota de alcance:** las herramientas ofensivas descritas aquí se emplean **exclusivamente** en el entorno de pruebas aislado del proyecto, sobre sistemas propios y con autorización. Su finalidad es defensiva: generar telemetría conocida para validar la cobertura de detección.

---

## Propósito y encaje en el proyecto

El flujo de validación del XDR y del módulo de triaje se apoya en tres capas de herramientas:

```
Herramientas de ataque/pentesting  →  generan actividad maliciosa controlada
        ↓
Fuentes de telemetría (Sysmon, EDR, logs)  →  registran la actividad
        ↓
Herramientas de análisis de comportamiento y patrones  →  detectan, correlacionan y explican
```

- **Generación de telemetría:** las herramientas de pentesting y simulación producen eventos que Sysmon y el resto de sensores capturan, permitiendo comprobar la cobertura de detección.
- **Validación de reglas:** cada técnica ejecutada debe traducirse en una detección esperada (mapeada a MITRE ATT&CK) para medir verdaderos positivos y falsos negativos.
- **Dataset etiquetado:** la actividad conocida (ground truth) alimenta el dataset de la Fase 3 con verdaderos positivos y falsos positivos documentados.

### Stack recomendado para el proyecto

Combinación práctica y de bajo coste, alineada con el enfoque en PYMEs:

```
Atomic Red Team / Caldera   →   Sysmon + Wazuh/Elastic   →   Reglas Sigma
     (ataque)                     (telemetría)                (detección)
                              todo mapeado a MITRE ATT&CK
```

---

## Índice de herramientas

### 1. Generación de telemetría y fuentes de datos

| Herramienta | Categoría | Estado |
|-------------|-----------|--------|
| [Sysmon](./symons.md) | Telemetría de endpoint (Windows) | Documentado |
| Auditd | Auditoría de kernel (Linux) | Listado |
| Sysmon for Linux | Telemetría de endpoint (Linux) | Listado |
| osquery | Estado del sistema (multi-plataforma) | Listado |
| Wazuh (agente) | Recolección de logs + HIDS | Listado |
| Winlogbeat / Filebeat / Fluentd | Forwarders de logs | Listado |
| Zeek / Suricata | Telemetría y detección de red (NDR) | Listado |

### 2. Herramientas de pentesting y simulación de ataques

| Herramienta | Categoría | Estado |
|-------------|-----------|--------|
| Atomic Red Team | BAS / pruebas atómicas ATT&CK | Listado |
| Caldera (MITRE) | Emulación de adversarios | Listado |
| Red Team Automation (RTA) | Emulación por técnica | Listado |
| Stratus Red Team | Ataques en cloud | Listado |
| PurpleSharp | Simulación en Windows/AD | Listado |
| Metasploit Framework | Explotación / post-explotación | Listado |
| Sliver / Mythic / Havoc / Cobalt Strike | Command & Control (C2) | Listado |
| Impacket | Ataques a protocolos Windows/AD | Listado |
| BloodHound | Enumeración de rutas en AD | Listado |
| Nmap / Masscan | Reconocimiento y escaneo | Listado |
| CrackMapExec (NetExec) / Hydra | Movimiento lateral / fuerza bruta | Listado |

### 3. Herramientas de análisis de comportamiento y patrones de ataque

| Herramienta | Categoría | Estado |
|-------------|-----------|--------|
| Sigma | Reglas de detección genéricas | Listado |
| YARA | Patrones sobre archivos/memoria | Listado |
| Wazuh | HIDS + correlación + SIEM | Listado |
| Elastic Security (ELK) | SIEM/XDR con reglas y ML | Listado |
| Microsoft Sentinel | SIEM/SOAR cloud (KQL, UEBA) | Listado |
| Splunk (+ ES / UBA) | SIEM con UEBA | Listado |
| Security Onion | Distribución NSM todo-en-uno | Listado |
| TheHive + Cortex | Gestión de casos y enriquecimiento | Listado |
| MISP | Threat intelligence / IoCs | Listado |
| Velociraptor | Caza de amenazas y forense | Listado |
| RITA / HELK | Análisis de beaconing y comportamiento | Listado |

---

## 1. Generación de telemetría y fuentes de datos

Sensores que registran la actividad del sistema y la envían al XDR/SIEM. Sin buena telemetría no hay detección: esta capa determina el techo de lo que las herramientas de análisis pueden ver.

| Herramienta | Plataforma | Qué aporta | Integración |
|-------------|-----------|------------|-------------|
| **[Sysmon](./symons.md)** | Windows | Telemetría de alta fidelidad: procesos con línea de comandos y hashes, conexiones de red, cambios de registro, creación de archivos, carga de DLLs. | Event Log → forwarder → SIEM. Ver documento dedicado. |
| **Auditd** | Linux | Auditoría de syscalls, ejecución de procesos, accesos a ficheros y cambios de configuración. Estándar en distribuciones Linux. | Reglas en `auditd`; recolección vía agente/forwarder. |
| **Sysmon for Linux** | Linux | Port oficial de Sysmon basado en eBPF; esquema de eventos equivalente al de Windows. | Mismo canal de eventos que Sysmon; salida a syslog. |
| **osquery** | Windows/Linux/macOS | Expone el estado del sistema como tablas SQL consultables (procesos, puertos, usuarios, paquetes). Útil para hunting y snapshots. | Consultas programadas → logs → SIEM (Fleet/Kolide para gestión). |
| **Wazuh (agente)** | Multi-plataforma | Recolección de logs, monitoreo de integridad de archivos (FIM) y detección local (HIDS). | Agente → manager Wazuh (también actúa como SIEM, ver sección 3). |
| **Winlogbeat / Filebeat / Fluentd / Fluent Bit** | Multi-plataforma | Forwarders ligeros que envían logs y eventos (incluido Sysmon) al SIEM. | Salida a Elastic, Splunk, Kafka, etc. |
| **Zeek / Suricata** | Red | Telemetría de red (Zeek: metadatos de conexiones y protocolos) y detección por firmas (Suricata: IDS/IPS). Base de la visibilidad NDR. | Sensores en TAP/SPAN; salida a Elastic/SIEM. |
| **Elastic Agent / Azure Monitor Agent** | Multi-plataforma | Agentes nativos del stack XDR que recolectan endpoint + logs con integraciones preconstruidas. | Nativo de Elastic Security / Microsoft Sentinel. |

---

## 2. Herramientas de pentesting y simulación de ataques

Ejecutan técnicas ofensivas de forma controlada para generar telemetría real y validar la cobertura de detección. Se dividen en **simulación de adversarios (BAS)** —lo más útil para probar detecciones de forma reproducible— y **frameworks ofensivos / C2** de uso dual, que requieren autorización y aíslan.

### 2.1 Simulación de adversarios / Breach & Attack Simulation (BAS)

Reproducen técnicas conocidas mapeadas a MITRE ATT&CK; ideales para validar reglas de detección de manera repetible y segura.

| Herramienta | Enfoque | Por qué encaja |
|-------------|---------|----------------|
| **Atomic Red Team** | Biblioteca de "pruebas atómicas" mapeadas 1:1 a técnicas ATT&CK, ejecutables con un runner (Invoke-Atomic). | La opción más directa para validar una regla por técnica; bajo coste y reproducible. |
| **Caldera (MITRE)** | Framework de emulación automatizada que encadena técnicas en operaciones de adversario completas (con agentes). | Simula cadenas de ataque realistas para probar correlación multi-evento. |
| **Red Team Automation (RTA)** | ~50 scripts en Python que emulan tácticas por técnica ATT&CK. | Complemento ligero a Atomic Red Team. |
| **Stratus Red Team** | Técnicas de ataque específicas de cloud (AWS, Azure, GCP). | Para validar detección en entornos cloud si aplica. |
| **PurpleSharp** | Simulación de técnicas en Windows y Active Directory. | Genera telemetría rica de endpoint/AD para tuning de reglas. |
| **Infection Monkey / Prelude Operator** | Plataformas BAS con validación de propagación y postura. | Evaluación continua de la postura de detección. |

### 2.2 Frameworks ofensivos y C2 (uso dual — requieren autorización)

Emulan el comportamiento de atacantes reales (explotación, post-explotación, command & control). Generan la telemetría más representativa de un incidente real, pero deben usarse solo en el laboratorio aislado.

| Herramienta | Uso | Telemetría que genera |
|-------------|-----|-----------------------|
| **Metasploit Framework** | Explotación y post-explotación. | Procesos anómalos, inyección, conexiones a listeners. |
| **Sliver / Mythic / Havoc / Cobalt Strike** | Command & Control (emulación de APT). | Beaconing de red, procesos de C2, movimiento lateral. |
| **Empire / Covenant** | Post-explotación en PowerShell / .NET. | Eventos de PowerShell (Script Block Logging), procesos hijos. |
| **Impacket** | Ataques a protocolos Windows/AD (SMB, Kerberos, WMI). | Autenticaciones anómalas, ejecución remota (psexec/wmiexec). |
| **BloodHound (+ SharpHound)** | Enumeración de rutas de ataque en Active Directory. | Consultas LDAP masivas, recolección de sesiones. |
| **Mimikatz** | Extracción de credenciales (LSASS, tickets Kerberos). | Acceso a LSASS — evento de detección de alto valor. |
| **Nmap / Masscan** | Reconocimiento y escaneo de puertos/servicios. | Escaneos detectables en red (Zeek/Suricata). |
| **CrackMapExec (NetExec) / Hydra** | Movimiento lateral y fuerza bruta de credenciales. | Múltiples autenticaciones fallidas, spray de contraseñas. |

> **Precaución:** Mimikatz, Cobalt Strike y los C2 son marcadamente sensibles. En el proyecto se prefieren para generar detecciones específicas (p. ej. acceso a LSASS, beaconing), siempre en red aislada y sobre hosts de prueba.

---

## 3. Herramientas de análisis de comportamiento y patrones de ataque

Consumen la telemetría para detectar comportamiento anómalo, correlacionar eventos y reconocer patrones de ataque conocidos. Es la capa donde se materializa la detección y donde el módulo de triaje del proyecto aporta clasificación, priorización y explicabilidad.

### 3.1 Motores de reglas y firmas

| Herramienta | Mecanismo | Integración |
|-------------|-----------|-------------|
| **Sigma** | Formato genérico de reglas de detección, convertible a SPL (Splunk), KQL (Sentinel), EQL/Lucene (Elastic) y otros mediante `sigma-cli`/pySigma. | Reglas portables; base recomendada para el proyecto. |
| **YARA** | Reglas de patrones (strings/bytes) sobre archivos y memoria; estándar para clasificación de malware. | Integrable con Velociraptor, TheHive/Cortex, EDRs. |
| **Suricata** | Firmas de red (IDS/IPS) para tráfico malicioso conocido. | Sensores de red → SIEM. |

### 3.2 SIEM / XDR y correlación

| Herramienta | Categoría | Notas |
|-------------|-----------|-------|
| **Wazuh** | HIDS + correlación + SIEM open source | Reglas propias + integración con Sigma/MITRE; buen encaje low-cost. |
| **Elastic Security (ELK)** | SIEM/XDR open | Detección basada en reglas y ML; motor de reglas EQL; amplio soporte de Sigma. |
| **Microsoft Sentinel** | SIEM/SOAR cloud | Consultas KQL, UEBA integrada, playbooks de respuesta. |
| **Splunk (+ Enterprise Security / UBA)** | SIEM enterprise | Búsqueda potente y UEBA (User Behavior Analytics). |
| **Security Onion** | Distribución NSM todo-en-uno | Empaqueta Zeek + Suricata + Elastic + herramientas de hunting. |

### 3.3 Análisis de comportamiento (UEBA) y caza de amenazas

| Herramienta | Enfoque |
|-------------|---------|
| **RITA** | Detección de beaconing y actividad C2 sobre metadatos de red (Zeek). |
| **HELK** | Plataforma de hunting sobre ELK con analítica avanzada (Jupyter, Spark). |
| **Velociraptor** | Caza de amenazas y forense en endpoints a escala (consultas VQL). |
| **UEBA (Exabeam, Securonix)** | Análisis de comportamiento de usuarios/entidades para anomalías; enterprise. |

### 3.4 Threat intelligence y gestión de casos

| Herramienta | Función |
|-------------|---------|
| **MISP** | Plataforma de threat intelligence; comparte y correlaciona IoCs. |
| **TheHive + Cortex** | Gestión de casos/incidentes (TheHive) + enriquecimiento automatizado con analizadores (Cortex). |
| **OpenCTI** | Gestión de conocimiento de amenazas (actores, técnicas, IoCs). |

---

## Mapeo a MITRE ATT&CK

Marco común de referencia para relacionar las técnicas ejecutadas por las herramientas de pentesting con las detecciones esperadas en las herramientas de análisis. Cada fila representa un caso de prueba end-to-end del entorno.

| Táctica ATT&CK | Técnica (ejemplo) | Herramienta que la ejercita | Telemetría (fuente) | Detección esperada |
|----------------|-------------------|-----------------------------|---------------------|--------------------|
| Reconnaissance | T1046 Network Service Discovery | Nmap / Masscan | Zeek / Suricata | Regla de escaneo de puertos |
| Execution | T1059 Command and Scripting Interpreter | Atomic Red Team | Sysmon EID 1 | Regla Sigma de proceso sospechoso |
| Credential Access | T1003 OS Credential Dumping | Mimikatz | Sysmon EID 10 (acceso a LSASS) | Regla Sigma de acceso a LSASS |
| Lateral Movement | T1021 Remote Services (SMB/WMI) | Impacket / CrackMapExec | Sysmon EID 1/3 + Windows logs | Regla de ejecución remota |
| Command & Control | T1071 Application Layer Protocol | Sliver / Caldera | Zeek + Sysmon EID 3 | Detección de beaconing (RITA) |
| Discovery (AD) | T1087 Account Discovery | BloodHound / SharpHound | Logs LDAP / Sysmon | Regla de enumeración masiva LDAP |

> Esta tabla se ampliará conforme se definan los casos de prueba de la Fase 3 y el baseline de la Fase 4.

---

## Referencias

- MITRE ATT&CK — https://attack.mitre.org/
- MITRE ATT&CK Evaluations (Enterprise).
- Atomic Red Team — https://github.com/redcanaryco/atomic-red-team
- MITRE Caldera — https://caldera.mitre.org/
- Sigma (reglas de detección) — https://github.com/SigmaHQ/sigma
- SwiftOnSecurity/sysmon-config y olafhartong/sysmon-modular (configuraciones de Sysmon).
- Wazuh — https://wazuh.com/
- Elastic Security / Security Onion / Velociraptor — documentación oficial de cada proyecto.
