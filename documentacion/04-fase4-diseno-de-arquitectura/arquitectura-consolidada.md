# Arquitectura consolidada

Vista única de todo el sistema: componentes, planos, flujo de datos y los puntos donde el diseño
se aísla de sus dependencias externas. Reúne lo repartido en los documentos de la Fase 4 y cierra
su diseño.

---

## Diagrama de componentes

```mermaid
flowchart TB
    subgraph datos["PLANO DE DATOS — red del cliente (Containerlab)"]
        direction LR
        PROV["proveedor<br/>(punto de entrega)"] --- BORDE["borde<br/>equipo de borde · objetivo prioritario"]
        BORDE --- SW["sw-lan<br/>switch interno"]
        SW --- PC["puesto"]
        SW --- IOT["iot"]
        SW --- VULN["objetivo-vuln<br/>(ground truth)"]
    end

    subgraph gestion["PLANO DE GESTIÓN — red clab (out-of-band)"]
        direction LR
        WZ["Wazuh<br/>fuente de alertas + baseline"]
        AUD["Auditor<br/>Nmap + Greenbone"]
    end

    subgraph edr["Motor de triaje — el prototipo (software)"]
        direction TB
        ING["1· Ingesta y normalización<br/><i>aísla la fuente de alertas</i>"]
        ANA["2· Análisis · clasificar() / justificar()<br/><i>aísla el modelo (Perfil A/B)</i>"]
        DEC["3· Decisión + validación humana"]
        CON["4· Conector<br/><i>aísla el protocolo (SSH → ACS)</i>"]
        TRZ[("Traza auditable")]
        ING --> ANA --> DEC --> CON
        DEC -.-> TRZ
    end

    datos -->|syslog / agente| WZ
    AUD -.escaneo.-> datos
    WZ -->|alerts.json| ING
    AUD -->|postura del nodo| ANA
    CON -->|catálogo de acciones, por SSH| datos
    AUD -->|reescaneo: verificación| CON

    EMP["Sistema de logs<br/>de la empresa"] -.futuro, misma ingesta.-> ING
```

---

## Los tres puntos de aislamiento

El diseño depende de tres cosas externas que hoy no están definidas o son provisionales. En vez
de acoplarse a ellas, el motor de triaje las esconde tras un adaptador. Es el patrón que se repite y lo que
hace el sistema portable:

| Dependencia externa | Hoy | Mañana | Adaptador que lo aísla |
|---------------------|-----|--------|------------------------|
| Fuente de alertas | Wazuh en el sandbox | + sistema de la empresa | **Módulo de ingesta** |
| Modelo de análisis | Perfil A (híbrido, CPU) | Perfil B (Foundation-Sec-8B, GPU) | **Interfaz `clasificar`/`justificar`** |
| Canal hacia el objetivo | SSH | TR-069 / ACS | **Conector** |

Cambiar cualquiera de los tres es escribir un adaptador nuevo, **sin tocar la lógica de decisión
del motor de triaje**. Es lo que permite empezar con lo disponible sin hipotecar el diseño.

---

## El flujo en una frase por etapa

1. **Actividad** en el sandbox (un ataque, un escaneo) →
2. **Wazuh** la convierte en alerta con nivel, IP y crudo →
3. **Ingesta** la normaliza al esquema del motor de triaje (y la enriquece con la postura del auditor) →
4. **Análisis** la clasifica, prioriza y —si hace falta— justifica →
5. **Decisión**: acción directa, o retención para **validación humana** →
6. **Conector** ejecuta una acción del **catálogo cerrado** por SSH →
7. **Auditor** reescanea para **verificar** que la exposición se cerró →
8. Todo queda en la **traza**.

El ciclo es cerrado: la acción genera telemetría nueva que Wazuh vuelve a evaluar.

---

## Modos de ejecución (Perfil A)

Por el presupuesto de memoria medido, el flujo se parte en dos y **el dataset en disco es la
frontera**:

- **En vivo:** sandbox + Wazuh + encoder + modelo 1B. El lazo interactivo, demostrable.
- **En lote:** Greenbone + modelo 8B, con el sandbox apagado. Postura, justificación extensa y métricas.

> **Diseño vs implementación** (actualizado 21/09/2026). El diagrama y los modos de arriba son el
> **diseño**; lo implementado difiere en cuatro puntos, todos por mediciones:
>
> - **Modelo generador.** El diseño previó un 3B interactivo + 8B en lote. Implementado: el 8B
>   (`llama-3.1-8b-instruct-q4`) **no en lote sino como servidor residente**, en la máquina objetivo con GPU,
>   donde justifica en ~0,4 s y midió **18/18 ancladas y 0 contradicciones** con RAG. En la máquina de
>   desarrollo sin GPU se usa el **1B** (`llama-3.2-1b-q4`) o la plantilla determinista. El servidor
>   residente eliminó la separación temporal que el 8B en lote exigía.
> - **Clasificador.** El «encoder» del modo en vivo **se descartó** a favor de un **árbol de decisión** que
>   descubre y valida reglas para el clasificador determinista (escala honesta para unos cientos de filas).
> - **Auditor.** **Greenbone no se desplegó**: no cabe en memoria junto al resto (ver
>   [Fase 3](../03-fase3-entorno-de-pruebas/README.md)). El auditor opera **solo con Nmap**, que inventaría
>   servicios expuestos — suficiente para la postura que usa el triaje (expuesto sí/no), pero **sin dictamen
>   de CVE ni severidad**. La salida normalizada del auditor permite incorporar Greenbone después sin tocar el
>   motor.
> - **Embedder del RAG.** Se añadió `bge-m3` (1024 dim.) como embedder dedicado, también residente.
>
> Ver [`seleccion-del-modelo.md`](./seleccion-del-modelo.md) y los
> [resultados de evaluación](../../evaluacion/resultados/README.md).

---

## Trazabilidad a los documentos de diseño

| Componente | Documento |
|------------|-----------|
| Red del cliente y nodos | [sandbox](../03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) · [nodos](../../lab/README.md) |
| Flujo, contratos, validación humana | [flujo](./flujo-triaje-playbook-sandbox.md) |
| Canal y protocolo | [protocolos](./protocolos-comunicacion-sandbox.md) |
| Auditor | [auditoría](./auditoria-de-vulnerabilidades-del-sandbox.md) |
| Modelo y perfiles | [selección del modelo](./seleccion-del-modelo.md) |
| Acciones | [catálogo](./catalogo-de-acciones.md) |
| Métricas y baseline | [métricas](./metricas-y-evaluacion.md) |
| Requisitos | [registro único](../02-fase2-estado-del-arte/requisitos.md) · [revisión de contexto](../02-fase2-estado-del-arte/revision-requisitos-contexto.md) |

---

## Estado de la Fase 4

Con este documento, el diseño de la arquitectura queda **cerrado**. Todo lo pendiente es
implementación (Fase 5) o depende de datos de la empresa (Fase 1). El único hueco de diseño
conocido es que el equipo de borde es provisional hasta desbloquear OpenWrt en
vrnetlab; las decisiones están tomadas para OpenWrt, solo falta poder probarlas sobre él.
