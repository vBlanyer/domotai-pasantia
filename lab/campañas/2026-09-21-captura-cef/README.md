# Captura CEF y JSON de Wazuh (21/09/2026)

Evidencia para el [análisis de adaptabilidad a CEF](../../../docs/superpowers/specs/2026-09-21-adaptabilidad-fuente-cef-analisis.md).

- `wazuh-cef.log`: la salida `syslog_output` de Wazuh 4.14.7 con `<format>cef</format>` (demonio `wazuh-csyslogd`).
- `wazuh-json-syslog.log`: los **mismos 11 eventos** con `<format>json</format>`.

**Cómo se obtuvo.** Wazuh reenviaba por UDP al auditor (172.20.20.4, puertos 5514 y 5515) y `nc -u -l`
recibía allí. Los eventos son el arranque del manager más 10 fallos de login SSH. Se escribieron en el
syslog de `objetivo-vuln` con `logger`, con el mismo texto que genera `sshd`, porque el `puesto` no tiene
`sshpass`. Wazuh los decodifica igual que un `sshd` real (regla 5760).

Un datagrama es un mensaje. `nc` los guardó sin salto de línea y aquí se separaron por la cabecera `<PRI>`.

La configuración se aplicó en caliente. `lab/scripts/wazuh-run.sh` **no** la reproduce todavía.
