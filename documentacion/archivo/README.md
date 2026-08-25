# Archivo — material superado

Documentos que **ya no reflejan el diseño actual** del proyecto pero se conservan por trazabilidad
y como referencia. No deben leerse como diseño vigente.

| Documento | Por qué está aquí | Reemplazado por |
|-----------|-------------------|-----------------|
| [planDeTrabajo.md](planDeTrabajo.md) | Versión antigua del plan: 6 objetivos, uno cortado a media frase | [planDeTrabajoActualizado.md](../00-general/planDeTrabajoActualizado.md) |
| [symons.md](symons.md) | Sysmon es telemetría solo-Windows; el sandbox es OpenWrt/Linux | La telemetría del laboratorio la da [Wazuh](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) |
| [herramientas-auxiliares.md](herramientas-auxiliares.md) | Proponía generar el dataset con Atomic Red Team → Sysmon → Sigma; el ground truth ahora sale de Metasploitable + Wazuh | [vulnerabilidades-esperadas.md](../../lab/vulnerabilidades-esperadas.md), [auditoría](../04-fase4-diseno-de-arquitectura/auditoria-de-vulnerabilidades-del-sandbox.md) |

Parte del contenido de `herramientas-auxiliares.md` (catálogo de SIEM, correlación y threat
intelligence) sigue siendo referencia válida; se conserva íntegro por si se retoma.
