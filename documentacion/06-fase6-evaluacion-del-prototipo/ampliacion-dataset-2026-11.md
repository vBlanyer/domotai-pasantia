# Ampliación del conjunto de datos y prioridad por familia (R1 + R2) — diseño fijado antes de medir

> **Cifra vigente: §10 (n=417, con los ataques lentos).** §8 recoge el paso intermedio (n=356).

> **Estado:** diseño del 11/11/2026, escrito **antes** de lanzar ninguna campaña. Todo lo que fija este
> documento (escenarios, verdad de cada uno, reparto, prioridad esperada y correcciones del adaptador) se
> decide sin haber visto los resultados, y no se cambia al verlos. Recomendaciones R1 y R2 de
> [recomendaciones-y-orden.md](../00-general/recomendaciones-y-orden.md).

## 1. Por qué

- **R1.** De las 300 etiquetas de la partición de evaluación, 236 las produjo una regla de etiquetado y no
  el experimento; las soportadas pertenecen todas a un único equipo (`objetivo-vuln`), con ataques internos.
  Se añaden casos cuya verdad la declara el experimento, sobre **otro equipo**, **otro servicio**, con
  **atacante externo** y con **usuarios legítimos desde orígenes no declarados**.
- **R2.** El reconocimiento tiene clase propia pero la prioridad de un intento de acceso (3). Un sondeo
  aislado es un precursor, no un acceso: se rebaja a **2**.

Se acepta de antemano que las cifras pueden empeorar. Se publican **junto a** las de n=300, como un paso
más de la progresión del informe, nunca sustituyéndolas en silencio.

## 2. Laboratorio

El pequeño (`red-cliente`, el mismo del conjunto actual) con el perfil `empresarial`, para que las cifras
sigan siendo comparables. Dos añadidos de instrumentación, sin cambiar qué está expuesto:

1. **FTP de `objetivo-vuln`:** se reenvía también `/var/log/vsftpd.log` con cabecera syslog (programa
   `vsftpd`). Sin ello solo llega el primer fallo de cada ráfaga (`auth.log` pliega los repetidos) y nunca
   el acceso correcto.
2. **Telnet de `iot`:** el `telnetd` de BusyBox no deja registro. Se sustituye por el señuelo del banco
   (`lab/banco/telnet_expuesto.py`) y su reenviador, que registran cada conexión como `in.telnetd` (regla
   5602). El puerto 23 sigue abierto y expuesto; la diferencia es que el señuelo no entrega una shell.

Sondas del 11/11 (antes de este diseño): las tres vías generan alertas con el equipo y el origen correctos.

## 3. Escenarios y verdad declarada

Cada escenario sale de **su propia IP** (alias en el nodo), de modo que la verdad se asigna por origen sin
depender de ventanas ajustadas. Dos campañas idénticas: `2026-11-11-ampliacion-entrenamiento` y
`2026-11-11-ampliacion-evaluacion`.

| Id | Eje | Desde (IP) | Contra | Qué se hace | Verdad | Qué dirían las reglas |
|---|---|---|---|---|---|---|
| A1 | Atacante externo | `proveedor` (10.0.1.50) | `objetivo-vuln` SSH | Fuerza bruta `root@`, 10 intentos | **VP** | VP |
| A2 | Atacante externo | `proveedor` (10.0.1.51) | `iot` telnet | 3 conexiones | **VP** | VP |
| B1 | Otro equipo víctima | `puesto` (192.168.1.42) | `iot` telnet | 3 conexiones desde un equipo interno | **VP** | VP |
| B2 | Otro equipo víctima | `puesto` (192.168.1.43) | `iot` telnet | Un técnico de mantenimiento, 1 conexión | **FP** | VP (origen no declarado) |
| C1 | Otro servicio | `puesto` (192.168.1.44) | `objetivo-vuln` FTP | Fuerza bruta `msfadmin@`, 8 intentos | **VP** | VP |
| C2 | Otro servicio | `puesto` (192.168.1.45) | `objetivo-vuln` FTP | Usuario legítimo: 1 error y acceso correcto | **FP** | VP (origen no declarado) |
| D1 | Legítimo no declarado | `proveedor` (10.0.1.52) | `objetivo-vuln` SSH | Técnico del proveedor: 2 errores y acceso correcto | **FP** | VP (origen no declarado) |

B2, C2 y D1 son los casos difíciles: legítimos que las reglas actuales tratarán como amenaza. Las alertas
de sesión y de acceso correcto quedan fuera de las familias soportadas (`no_soportada`), como hoy.

## 4. Correcciones del producto decididas antes de medir

1. **Adaptador:** `vsftpd` (y `proftpd`, `pure-ftpd`) → protocolo `ftp` en `prototipo/motor/postura.py`
   (`_PROTOCOLOS`), el mismo mecanismo que ya traduce `apache` → `http`. Sin ello, un ataque real al FTP
   expuesto saldría «no expuesto». No afecta a ninguna alerta del conjunto actual (ninguna es de FTP).
2. **R2:** `_PRIORIDAD_BASE["vp_reconocimiento"] = 2` en `prototipo/motor/analisis.py`.

## 5. Prioridad esperada por familia

`evaluacion/prioridad_esperada.yml` pasa de (equipo, etiqueta) a (equipo, etiqueta) **con excepciones por
familia**. Fuente: la gravedad documentada en `lab/docs/vulnerabilidades-esperadas.md`.

| Equipo | VP | FP | Excepción |
|---|---|---|---|
| `objetivo-vuln` | 4 (vsftpd, telnetd y SSH críticos o altos) | 1 | reconocimiento VP → **2** |
| `iot` | 4 (telnet sin autenticación: crítica) | 1 | reconocimiento VP → **2** |

La excepción del reconocimiento se aplica también a la partición actual, así que la priorización medida
de n=300 cambia: se reporta la anterior y la nueva.

## 6. Reparto

A priori, como el resto: `ampliacion-entrenamiento` → entrenamiento, `ampliacion-evaluacion` →
evaluación. Partición nueva esperada: 300 + las alertas de la campaña de evaluación.

## 7. Qué se mide y cómo se reporta

- La campaña canónica completa con el perfil empresarial sobre la partición nueva: clasificación frente al
  baseline, priorización, escalado y continuidad.
- **Por separado, las alertas de la ampliación**, para ver qué hacen las reglas con cada eje.
- El árbol de decisión, reentrenado sobre la partición de entrenamiento nueva; si propone una regla, se
  refuerza con variedad antes de adoptarla, como con el ataque lento.
- En el informe: la progresión gana una fila; n=300 se conserva como estaba.

## 8. Resultados (11/11/2026, medidos después de fijar todo lo anterior)

**Captura.** Dos campañas idénticas de 56 alertas (`lab/campañas/2026-11-11-ampliacion-*`); 42 soportadas
cada una, todas con la verdad del experimento. Incidencias de la captura, ninguna del producto: el
reenviador de `vsftpd.log` sin `#!/bin/sh` no arrancaba (primera captura de entrenamiento repetida) y
`pkill -f` dentro de un `sh -c` que contiene el nombre del proceso se mataba a sí mismo.
`lab/dataset/construir.py` recibió el filtro de carpetas sin ficha de la rama del experimento del ataque
lento. Las 600 alertas anteriores salen idénticas; el normalizador actual solo añade `destino_ip` y
`usuario`, y la reevaluación de las 300 antiguas da exactamente lo mismo.

**Partición de evaluación: 356 alertas, 148 soportadas** (`evaluacion/resultados/campana-2026-11-11.json`).

| | Prototipo (n=356) | Baseline (n=356) | Prototipo (n=300, antes) |
|---|---|---|---|
| Precisión | 0,931 | 0,602 | 0,978 |
| Exhaustividad | 1,000 | 0,893 | 1,000 |
| F1 | 0,964 | 0,719 | 0,989 |
| Tasa de FP | 0,038 | 0,308 | 0,009 |
| Escalado a humano | 0,292 | — | 0,297 |
| Contenciones automáticas (indebidas) | 27 (**4**) | — | 0 (0) |
| Priorización ±1 / Spearman | 0,939 / 0,808 | — | 0,981 / 0,935 (0,944 con R2) |

**Por escenario.** A1, A2, B1 y C1 (VP) se detectan todos: A1 y A2, de origen externo, se contienen solos; B1
y C1, internos, van a un analista. C1 confirma la corrección `vsftpd` → `ftp`. El baseline pierde las 6
conexiones telnet a `iot` (nivel 3). Los **7 falsos positivos nuevos** son exactamente B2, C2 y D1: los
legítimos desde orígenes no declarados, que ningún campo de la alerta separa de un ataque. **D1 se bloquea
de forma automática** (las 4 indebidas): un técnico legítimo del proveedor, de origen externo y confianza
alta. Ni el umbral (barrido RF-07, plano) ni la política de actores lo retienen.

**El control previsto** es declarar al proveedor en `terceros_confiables`. Comprobado aparte (sin tocar la
cifra canónica): con 10.0.1.0/24 declarado, los indebidos pasan a 0, pero también se retienen los dos
atacantes externos de esa red (automáticas 27 → 0, escalado 0,292 → 0,368). Es una decisión del cliente.

**Priorización.** R2 solo, sobre las 300 anteriores, sube el Spearman de 0,935 a 0,944. Sobre n=356 baja a
0,808 porque los 7 falsos positivos nuevos reciben la prioridad de una amenaza (3) frente a la esperada (1).

**Margen para un modelo de lenguaje** (ablación de postura): con la postura real, 20 grises y 0 de margen;
retirándola, 131 grises y 9 de margen (antes 2): los legítimos nuevos más los dos de siempre.

**Árbol de decisión.** Reentrenado sobre la partición de entrenamiento ampliada, propone «un acceso por
credenciales sin ráfaga (≤ 8 alertas en un minuto) es FP», que aquí acertaría casi todo (122/1/25/0). **No se
adopta**: el experimento del ataque lento ya mostró que una fuerza bruta lenta da los mismos recuentos que
un usuario que se equivoca, así que la regla cambiaría falsos positivos por amenazas perdidas.

## 9. Segunda parte: los ataques lentos (fijado antes de incorporarlos, 11/11/2026)

R1 pide también «ataques lentos que no formen ráfaga». El experimento del 13–14/10 los capturó en este
mismo laboratorio, con la verdad declarada, pero quedaron en su rama (etiqueta `experimento-ataque-lento`)
y no en el conjunto de datos. Se incorporan **tal cual**, sin volver a capturarlos, con el reparto que se
fijó entonces:

| Campaña | Intentos | Alertas | Partición |
|---|---|---|---|
| `2026-10-13-ataque-lento-entrenamiento` | 12 | 24 | entrenamiento |
| `2026-10-14-lento-8-entrenamiento` | 8 | 16 | entrenamiento |
| `2026-10-13-ataque-lento-evaluacion` | 12 | 24 | evaluación |
| `2026-10-14-lento-18-evaluacion` | 18 | 37 | evaluación |

Escenario (todas): fuerza bruta **lenta** `root@` desde la IP declarada del administrador (192.168.1.1),
un intento cada ~40 s. Verdad: **VP** (suplantación o equipo comprometido). Qué se espera, dicho antes de
medir: la mayoría saldrán como **falsos negativos**, porque no forman ráfaga (≤ 8 alertas en un minuto) y
el origen está declarado; el aviso de vigilancia de ventana larga las marca para el analista, pero no
cambia la clase. Es la medida honesta del punto ciego que el informe ya declara: la exhaustividad dejará
de ser 1,000. No se cambia ninguna regla por ello.

## 10. Resultados con los ataques lentos — cifra vigente (n=417)

Partición de evaluación: **417 alertas, 209 soportadas** (`evaluacion/resultados/campana-2026-11-11.json`).
Decisión del 11/11, tras ver el resultado y conforme a lo fijado en §9: n=417 es la cifra principal, con
desglose.

| | Prototipo (n=417) | Baseline (n=417) | Prototipo sin ataques lentos (n=356) | Prototipo (n=300) |
|---|---|---|---|---|
| Precisión | 0,931 | 0,702 | 0,931 | 0,978 |
| Exhaustividad | **0,667** | 0,929 | 1,000 | 1,000 |
| F1 | **0,777** | **0,800** | 0,964 | 0,989 |
| Tasa de FP | 0,038 | 0,308 | 0,038 | 0,009 |
| Escalado a humano | 0,249 | — | 0,292 | 0,297 |
| Automáticas (indebidas) | 27 (4) | — | 27 (4) | 0 (0) |
| Priorización ±1 / Spearman | 0,665 / 0,227 | — | 0,939 / 0,808 | 0,981 / 0,944 |

- **Las 61 alertas de ataque lento son falsos negativos**, como se esperaba: sin ráfaga y desde un origen
  declarado, el motor las clasifica como actividad legítima. El baseline las detecta porque no mira el
  origen. Con ellas, **el F1 del prototipo queda por debajo del de Wazuh** (0,777 frente a 0,800), aunque
  su tasa de FP siga siendo ocho veces menor. Un solo escenario aporta 61 de las 183 amenazas.
- **Aviso de vigilancia** (ventana de 10 min contada como en vivo, umbral 15): marca 33 de las 61 alertas y
  **los dos ataques de la evaluación**, ambos desde su alerta 15 (hacia el 7.º intento, a 4–5 min de
  empezar); da 2 avisos sobre las 17 alertas legítimas del administrador. No cambia la clase ni contiene:
  la métrica las cuenta, con razón, como amenazas perdidas.
- **Árbol de decisión:** con los ataques lentos separa por `regla_id` (5710) y nivel de Wazuh, es decir,
  memoriza qué regla dispara cada tipo de usuario —el confundido que la campaña de octubre intentaba romper—,
  como ya vio el experimento del ataque lento. No hay regla estable que adoptar.
- Ráfaga contada como en vivo: 114/9/225/69, exhaustividad 0,623. Conjunto completo (813): 244/18/450/101.

