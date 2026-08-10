# Sysmon

## ¿Qué es Sysmon?

Sysmon (System Monitor) es una herramienta de Microsoft, originalmente parte del conjunto Sysinternals, que funciona como un servicio de Windows y driver de kernel residente. Monitorea la actividad del sistema y escribe eventos detallados en el Registro de eventos de Windows, en el canal `Applications and Services Logs/Microsoft/Windows/Sysmon/Operational`.

No es un antivirus ni un EDR completo por sí solo. Es una fuente de telemetría de alta fidelidad orientada a detección, caza de amenazas y forense digital. Entre la información que registra se incluye:

- Creación y terminación de procesos (línea de comandos, proceso padre, hashes)
- Conexiones de red
- Cambios en el registro
- Creación, modificación y eliminación de archivos
- Carga de drivers, DLLs y otros componentes del sistema

Se configura mediante un archivo XML que define qué eventos registrar, incluir o excluir. Configuraciones populares de la comunidad incluyen [SwiftOnSecurity/sysmon-config](https://github.com/SwiftOnSecurity/sysmon-config) y [olafhartong/sysmon-modular](https://github.com/olafhartong/sysmon-modular).

Sysmon registra actividad; no bloquea malware de forma general (salvo eventos específicos de bloqueo en versiones recientes). Su valor principal está en alimentar un SIEM, un XDR o un SOC con datos que los logs nativos de Windows no suelen ofrecer con el mismo nivel de detalle.

## Diferencias en las últimas versiones

### Dos formas de desplegarlo

Desde 2026, Microsoft ofrece Sysmon integrado en Windows como característica opcional nativa en Windows 11 y Windows Server 2025, además de la versión standalone de Sysinternals.

| Aspecto | Sysmon standalone (Sysinternals) | Sysmon integrado (Windows) |
| --- | --- | --- |
| Instalación | Descargar binario de Sysinternals | Activar feature opcional + `sysmon -i` |
| Actualizaciones | Manual o gestión propia | Windows Update |
| Esquema de eventos / XML | Igual | Igual |
| Coexistencia | No pueden convivir en el mismo equipo | — |

El motor, el esquema de eventos y el formato XML son los mismos; cambia principalmente cómo se instala y actualiza.

### Evolución por versión (standalone)

**Sysmon v13 (2021) — Schema 4.50**

- Event ID 25 (Process Tampering): detecta técnicas como process hollowing y process herpaderping, cuando la imagen en memoria no coincide con el archivo en disco.
- v13.01 corrige una regresión donde varios tipos de eventos dejaron de registrarse.

**Sysmon v14 (2022) — Schema 4.82–4.83**

- Event ID 27 (FileBlockExecutable): primer evento con capacidad de bloqueo; impide la creación de ejecutables (PE) según reglas.
- Event ID 28 (FileBlockShredding): detecta y bloquea borrado seguro o shredding de archivos (por ejemplo, con herramientas como SDelete).

**Sysmon v15 (2023–2024) — Schema 4.90**

- El servicio corre como Protected Process Light (PPL), lo que lo hace más resistente a manipulación.
- Event ID 29 (FileExecutableDetected): registra la creación de nuevos PE sin bloquearlos (solo telemetría).
- v15.15 (julio 2024): correcciones de rendimiento, cuelgues con memoria limitada y crashes relacionados con FileBlockShredding y PipeEvent.

### Resumen de eventos nuevos relevantes

| Versión | Event ID | Nombre | Qué hace |
| --- | --- | --- | --- |
| v13 | 25 | ProcessTampering | Detecta manipulación de procesos |
| v14.0 | 27 | FileBlockExecutable | Bloquea creación de ejecutables |
| v14.1 | 28 | FileBlockShredding | Bloquea shredding de archivos |
| v15 | 29 | FileExecutableDetected | Registra creación de ejecutables |

## ¿Con qué sistemas se integra?

Sysmon solo se ejecuta en Windows (cliente y servidor). La integración con otras plataformas se realiza casi siempre a través del canal de Event Log `Microsoft-Windows-Sysmon/Operational`.

### SIEM y plataformas de análisis

| Plataforma | Mecanismo típico |
| --- | --- |
| Splunk | Universal Forwarder + Splunk Add-on for Sysmon |
| Elastic (ELK) | Winlogbeat con módulo Sysmon |
| Microsoft Sentinel | Azure Monitor Agent / Log Analytics, conector de Security Events |
| Wazuh | Agente Wazuh leyendo el canal de Event Log |
| IBM QRadar | Colector de Windows Event Log |
| Otros SIEM | Forwarders de Event Log o agentes compatibles |

### Detección y caza de amenazas

- Sigma: reglas convertibles a SPL, KQL, Elastic y otros formatos mediante pySigma.
- MITRE ATT&CK: los eventos de Sysmon se mapean a técnicas de ataque (por ejemplo, ejecución, evasión, persistencia).
- Simulaciones (Atomic Red Team u otras): permiten validar que las reglas detecten comportamiento real.

### Gestión y despliegue

- Group Policy (GPO)
- Microsoft Intune
- SCCM / Configuration Manager
- Scripts PowerShell (`sysmon -i config.xml`)

### Relación con EDR, XDR y MDR

Sysmon complementa soluciones EDR/XDR; no las reemplaza. Se utiliza frecuentemente cuando no hay presupuesto para un EDR comercial, cuando se busca telemetría adicional junto a un EDR existente, o al construir un SOC propio.

Un EDR comercial suele incluir agente propio con capacidades de respuesta en el endpoint; Sysmon aporta visibilidad profunda que se centraliza en un SIEM o en un servicio MDR.

### Flujo típico de integración

```
Endpoint Windows → Sysmon Service → Event Log (Sysmon/Operational)
    → Agente forwarder (Splunk / Winlogbeat / Wazuh)
    → SIEM / Sentinel / Elastic
    → Reglas Sigma / Detecciones / SOC
```

### Limitaciones

- Solo Windows (no Linux ni macOS).
- Requiere configuración cuidadosa; mal tunado genera mucho ruido.
- No incluye respuesta automática (containment, aislamiento) como un EDR completo.
- Las versiones standalone e integrada no deben instalarse simultáneamente en el mismo host.
