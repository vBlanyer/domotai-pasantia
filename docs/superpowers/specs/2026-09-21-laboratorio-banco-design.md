# Laboratorio del banco y banco de pruebas de casos de producción — diseño

**Fecha:** 21/09/2026 · **Estado:** diseño aprobado por secciones, pendiente de revisión del texto.

## 1. Objetivo

Probar el prototipo en una red cercana a producción, no solo en la red pequeña de siete nodos:

- servicios que **no se pueden tumbar**;
- **cascadas** cuando cae un servicio del que dependen otros importantes;
- el resto de casos que el sistema encontrará en la realidad.

Todo lo que no quepa en este laboratorio **se dice**, y se indica dónde y cómo se prueba (en otro
laboratorio o como límite declarado). Ningún caso queda fuera sin nombrarlo.

## 2. Decisiones tomadas

| # | Decisión | Alternativa descartada |
|---|---|---|
| L1 | Se modela la **red del banco** de `prototipo/perfiles/bancario.yml`: el perfil ya existe y el laboratorio lo convierte en una red real | Empresa genérica (perfil desde cero) |
| L2 | **Servicios mínimos con dependencias reales**, más un **monitor de salud** que mide la cascada observada y la compara con la predicha | Solo puertos abiertos (la cascada seguiría sin comprobarse) |
| L3 | **Banco de pruebas automático** con veredicto por caso, más **modo paso a paso** y **guías en Markdown**, todo generado desde **una única definición por caso** | Guías manuales sueltas |
| L4 | **El banco como núcleo, más laboratorios satélite** solo para lo incompatible o demasiado pesado | Muchos laboratorios pequeños / uno gigante |

## 3. Hallazgos que condicionan el diseño

**H1. El sistema solo ejecuta bloqueos de IP.**
- La política determinista (`prototipo/politica.py`) asocia la única clase de amenaza que se produce hoy
  (`vp_intento_acceso`) a `BLOQUEAR_IP`.
- El agente (`agente_mitigacion._ACCION_POR_ROL`) solo sabe `bloquear_ip`, en el host o en el
  cortafuegos.
- **Ningún componente propone** `AISLAR_NODO`, `BLOQUEAR_PUERTO` ni `CERRAR_SERVICIO`.

Las protecciones asociadas a esas acciones (la excepción de puerto, el veto a aislar la gestión y la
cascada de nodos) tienen tests unitarios, pero son **salvaguardas latentes**: ningún camino real llega a
ellas.

**H2. Bloquear la IP de un activo interno puede provocar una cascada que no se predice.**
`impacto.determinar` solo calcula `activos_afectados_en_cascada` para acciones sobre puerto o nodo. En
el banco, si `middleware` está comprometido y se bloquea su IP en `fw-core`, cae todo el tráfico
DMZ → core hacia él: `web-banking` y `api-movil` quedan fuera de servicio. El analista ve «bloquea a
middleware (activo interno)» **sin aviso de cascada**. Bloquear la IP del atacante **en la víctima**
(`core-db`) produce el mismo efecto, porque corta la dependencia.

- El laboratorio **debe** destapar este caso (K1): se espera que hoy falle.
- La corrección **no** forma parte de este trabajo; es una tarea aparte, con su propio diseño.

**H3. El conector está atado a la red pequeña.** `prototipo/conector.py:60` fija el contenedor
`clab-red-cliente-auditor` y el usuario `msfadmin`. Para el banco hay que parametrizar desde qué nodo
se ejecuta y con qué credencial. La red pequeña sigue siendo el valor por defecto.

## 4. Catálogo de casos

**Alcance** (cómo llega el caso al sistema):
- **real**: por el camino determinista del daemon;
- **agente**: por `--agente` con un generador guionizado;
- **inyectada**: el banco de pruebas entrega la acción al filtro, porque ningún componente la propone
  hoy (H1); desde el filtro en adelante todo es real;
- **perfil**: solo lógica sobre el perfil, sin red.

**Dónde:**
- **B** = laboratorio del banco;
- **S-x** = laboratorio satélite x;
- **F** = fuera de alcance, declarado y con la forma en que se evaluaría.

El ataque exacto de cada caso lo fija el plan, contrastado con lo que Wazuh detecta de verdad (fase 0).

### 4.1 Decisión sobre la amenaza

| ID | Caso | Esperado | Alcance | Dónde |
|---|---|---|---|---|
| D1 | Fuerza bruta externa contra el SSH expuesto de `web-banking` | VP con confianza 1,0; `BLOQUEAR_IP` de la IP externa, automático (≥ 0,9) | real | B |
| D2 | La misma alerta contra un servicio que el auditor no ve expuesto | FP por exposición inexistente; sin acción | real | B |
| D3 | Actividad desde el SOC o el auditor (origen legítimo) | FP por actividad legítima; sin acción | real | B |
| D4 | Ráfaga desde un origen legítimo | VP con confianza 0,6 → humano | real | B |
| D5 | Explotación web conocida contra `web-banking` | `amenaza_enrutada` hacia `cola-appsec-banco`; sin contención | real | B (si Wazuh la detecta: fase 0) |
| D6 | Alerta de una familia no soportada | `no_soportada`; nada | real | B |
| D7 | Reconocimiento externo | Según la familia registrada | real | B |

### 4.2 Continuidad: servicios que no se pueden tumbar

| ID | Caso | Esperado | Alcance | Dónde |
|---|---|---|---|---|
| C1 | `BLOQUEAR_PUERTO` 1521 en `core-db` (excepción `nunca_automatica`) | Se degrada a `BLOQUEAR_IP` del atacante; el monitor mantiene `core-db` arriba | inyectada | B |
| C2 | Igual con el 8443 de `middleware` | Igual que C1 | inyectada | B |
| C3 | Acción que alcanza un servicio (`AISLAR_NODO` de un host de la DMZ) | Humano siempre; nada automático | inyectada | B |
| C4 | Ataque cuya víctima es una joya de la corona (HSM o SWIFT, que no son `host_victima`) | La contención va **directamente** al cortafuegos; el activo nunca se toca y el monitor lo mantiene arriba | real (el salto directo al cortafuegos se verifica en la fase 0) | B |
| C5 | Acción sin reversión definida | Veto duro (RF-18) | perfil | B (catálogo de prueba) |

### 4.3 Cascada de dependencias

| ID | Caso | Esperado | Alcance | Dónde |
|---|---|---|---|---|
| **K1** | `middleware` comprometido ataca a `core-db`; el analista aprueba bloquear su IP | **Hoy se espera FALLO** (H2): el monitor ve caer `web-banking` y `api-movil`, y la predicción no los avisó | real | B |
| K2 | `AISLAR_NODO` de `core-db`, aprobado | Cascada transitiva predicha (`middleware` → `web-banking`, `api-movil`) igual a la observada; la reversión lo recupera todo | inyectada | B |
| K3 | `AISLAR_NODO` de `middleware` con una **dependencia real no declarada** (`atm` → `middleware`, presente en el laboratorio y ausente del perfil a propósito) | El monitor ve caer `atm`, que la predicción no avisó → **discrepancia de inventario** (esperada: el límite documentado) | inyectada | B |
| K4 | `depende_de` circular | La predicción termina sin bucle | perfil | B (sin red) |
| K5 | Compromiso de `taquilla` (nadie depende de ella) | Sin cascada predicha ni observada | real | B |

### 4.4 A quién afecta la acción

| ID | Caso | Esperado | Alcance | Dónde |
|---|---|---|---|---|
| A1 | Ataque desde `taquilla` comprometida | Retenida para el humano: «bloquea a taquilla…» | real | B |
| A2 | El origen aparente es un cortafuegos | Retenida; sube a `alcanza_servicio` | real | B |
| A3 | El origen aparente es `mdr-siem` (gestión) | Veto duro | real | B |
| A4 | IP interna no inventariada | Activo interno por red interna → humano | real | B |
| A5 | `AISLAR_NODO` del nodo de gestión | Veto duro | inyectada | B |

### 4.5 Ejecución, escalada y reversión

| ID | Caso | Esperado | Alcance | Dónde |
|---|---|---|---|---|
| E1 | Víctima caída | Escala a `fw-core`; el bloqueo queda allí | real | B |
| E2 | Víctima y `fw-core` inaccesibles | Escala a `fw-edge` (dos saltos) | real | B |
| E3 | Todos los puntos inaccesibles | Sin contención; queda como no mitigado | real | B |
| E4 | Ejecuta, pero la verificación falla | No se da por mitigado | real | B |
| E5 | Reversión de una acción aprobada (RF-18) | La regla desaparece y el servicio se recupera en el monitor | real | B |
| E6 | Escalada por el agente | Mismo resultado que E1/E2, con aprobación por paso | agente | B |

### 4.6 Validación humana

| ID | Caso | Esperado | Alcance | Dónde |
|---|---|---|---|---|
| H1–H3 | Aprobar / rechazar / reclasificar | Ejecuta / no ejecuta / no ejecuta y registra la clase corregida | real | B |
| H4 | Respuesta en blanco | Rechazar | real | B |

### 4.7 Operación del sistema

| ID | Caso | Esperado | Alcance | Dónde |
|---|---|---|---|---|
| O1 | Cientos de alertas de un mismo ataque | Un incidente | real | B |
| O2 | Ataques simultáneos a varios activos | Incidentes separados y bien atribuidos | real | B |
| O3 | Campos críticos ausentes | Se avisa; no se inventa | real | B |
| O4 | Reinicio del daemon a mitad de sesión | La cadena de la traza continúa | real | B |
| O5 | Wazuh cae y vuelve | El daemon espera sin romperse | real | B |
| O6 | Carga sostenida (miles de alertas por minuto) | Latencia y memoria medidas | real | **S-carga** |

### 4.8 Seguridad del propio MDR

| ID | Caso | Esperado | Alcance | Dónde |
|---|---|---|---|---|
| X1 | Campo con caracteres de shell | `validar_comando` lo rechaza; nada se ejecuta | real | B |
| X2 | Rotación de la clave del conector | Sigue funcionando con la clave nueva | real | B |
| X3 | Traza manipulada o truncada | La verificación contra el ancla lo detecta | real | B |

### 4.9 Fuera del banco

| ID | Caso | Dónde y cómo |
|---|---|---|
| S1 | Borde con OpenWrt real (máquina virtual) | **S-openwrt** (`lab/topologias/red-cliente-openwrt.clab.yml`, ya existe) |
| S2 | Segunda fuente (CEF) o segundo SIEM | **S-fuente**; aparcado (ver el análisis de adaptabilidad del 21/09) |
| S3 | Modelo 8B con GPU | **F** en el portátil; se evalúa en la máquina con GPU |
| S4 | Detección primaria nueva (malware, C2, DoS, movimiento lateral este-oeste) | **F por diseño** (estado §7): la detección primaria es del SIEM |
| S5 | Uso real de un servicio en este momento | **F** (Nivel 3); se podría probar con un satélite de tráfico sintético de usuarios |
| S6 | Alta disponibilidad de los cortafuegos | Variante futura del banco |

## 5. El laboratorio del banco

### 5.1 Topología

Se mantienen los segmentos e IPs de `bancario.yml`:

```
internet (atacante) ── fw-edge ── fw-core ─┬─ DMZ-10   web-banking  10.10.0.10
                                           ├─ DMZ-20   api-movil    10.20.0.10
                                           ├─ SWIFT-30 swift        10.30.0.10
                                           ├─ CORE-40  middleware   10.40.0.10
                                           ├─ CORE-50  core-db      10.50.0.10
                                           ├─ CORE-60  hsm          10.60.0.10
                                           ├─ SUC-200  taquilla     10.200.0.10
                                           ├─ SUC-210  atm          10.210.0.10
                                           └─ SOC-100  mdr-siem 10.100.0.10 · auditor 10.100.0.20
```

- Las direcciones de enlace entre `fw-edge` y `fw-core` (`10.0.0.254` y `10.0.0.1` en el perfil) las
  fija el plan.
- Wazuh queda **fuera de banda**, como hoy (`lab/scripts/wazuh-run.sh`, red de gestión de Containerlab).
  Todos los nodos le envían su syslog.

### 5.2 Piezas

- **Imagen `banco-nodo`:** Alpine con Python, sshd, iptables y rsyslog, construida una vez en local.
  Los despliegues son rápidos, no descargan paquetes y todos los nodos se comportan igual.
- **`servicio.py`**, un único servicio genérico configurado por nodo con su puerto y sus dependencias
  (`host:puerto`).
  - Expone `/salud`, que responde bien solo si él **y todas sus dependencias** responden. La cascada es
    real, no declarada.
  - Escribe un registro de accesos en formato Apache hacia el syslog, para que Wazuh pueda detectar
    ataques web.
- **Cortafuegos `fw-edge` y `fw-core`:** encaminan, y corren sshd con el usuario de mínimo privilegio
  (`lab/scripts/aprovisionar-minimo-privilegio.sh`). La contención y la escalada son reales.
- **Monitor de salud** en el segmento SOC: consulta `/salud` de todos cada pocos segundos y escribe una
  línea de tiempo JSON. Es el juez de continuidad y de cascada.
- **Atacantes:**
  - `internet`, externo, con `sshpass`, `nmap` y `curl`, **sin salida real**;
  - `taquilla`, equipo interno comprometido;
  - `middleware`, comprometido en K1.
- **Auditor** en el SOC: escanea el banco y produce los hallazgos que usa el motor.

### 5.3 Dependencias reales del laboratorio

| Servicio | Depende de | ¿Declarado en el perfil? |
|---|---|---|
| web-banking | middleware | sí |
| api-movil | middleware | sí |
| middleware | core-db, hsm | sí |
| swift | hsm | sí |
| **atm** | **middleware** | **no, a propósito** (K3) |

### 5.4 Perfil bancario alineado

- El HSM y el SWIFT reciben un puerto en `servicios_prestados`, para que el monitor y la reconciliación
  los vean.
- Las IPs se verifican contra el laboratorio.
- La omisión de `atm → middleware` se documenta **en el propio perfil** como omisión deliberada de
  prueba.

### 5.5 Convivencia y recursos

- Unos 13 contenedores Alpine (menos de 1 GB) más Wazuh (unos 0,6 GB).
- El banco y la red pequeña comparten la red de gestión y **no corren a la vez**. `lab.sh` elige cuál
  levantar y el banco de pruebas comprueba el entorno antes de empezar.

## 6. El banco de pruebas

### 6.1 Definición de un caso

Un YAML por caso en `lab/escenarios/banco/`. Es la única fuente de la que salen los tres usos. Campos:

- `id`, `titulo`, `grupo` y `alcance` (real / agente / inyectada / perfil);
- `preparar`: pasos (ejecutar en un nodo, detener un servicio, inaccesibilizar un nodo);
- `ataque`: pasos (en qué nodo y qué ejecutar), o `accion_inyectada` para los casos inyectados;
- `validacion`: `aprobar` | `rechazar` | `reclasificar:<clase>` | `vacio` | `ninguna`;
- `esperado`:
  - `decision`: los campos de la traza a comparar;
  - `cascada_predicha`;
  - `salud.caen` y `salud.siguen`;
  - `escalada`;
  - `discrepancia_esperada`;
  - `fallo_esperado`, con el motivo (K1);
- `restaurar`: `revertir` o pasos explícitos;
- `requiere`: por ejemplo `modelo` para E6.

### 6.2 Ciclo del ejecutor (`python3 -m lab.banco_pruebas`)

1. **Estado base:** todos los servicios sanos y los cortafuegos sin reglas añadidas. Si no se cumple,
   el caso queda **BLOQUEADO**.
2. **Preparar y atacar** con `docker exec`.
3. **El prototipo real decide:** el mismo `stream.ejecutar` del daemon, leyendo las alertas de Wazuh,
   con un lector guionizado para la validación y la traza en un fichero propio del caso. En los casos
   inyectados, la acción entra por `perfil.filtrar` y sigue por `orden`, el conector y la verificación.
4. **Espera por condición con plazo**, nunca por tiempo fijo. Se registra cuánto tardó cada caso.
5. **Verificar:** la decisión contra la traza, la salud contra la línea de tiempo del monitor, la cascada
   predicha contra la observada y la integridad de la cadena de la traza.
6. **Restaurar** y comprobar de nuevo el estado base.

### 6.3 Resultados

| Resultado | Significado |
|---|---|
| APROBADO | Lo observado coincide con lo esperado (una discrepancia o un fallo marcados como esperados cuentan como aprobado y se listan aparte) |
| FALLO | Diferencia no esperada, con lo que se esperaba y lo que se obtuvo |
| BLOQUEADO | El laboratorio no estaba en su estado base: el problema es del laboratorio, no del prototipo |
| OMITIDO | Falta un requisito del caso (por ejemplo, el modelo), siempre con el motivo |

Si el monitor ve caer algo que la predicción no avisó, es una **discrepancia de inventario**. Solo es
aceptable donde el caso la declara (K3). K1 declara `fallo_esperado` mientras H2 no se corrija; cuando
se corrija, se quita la marca y el caso pasa a exigir la predicción correcta.

### 6.4 Modos

- `--todos`: la suite completa.
- `--caso ID`: un caso.
- `--paso-a-paso`: se detiene en cada paso, explica qué observar, y la validación se contesta en el menú
  real por `/dev/tty`.
- `--guias`: regenera `docs/pruebas/banco/<ID>.md` desde los YAML.

### 6.5 Informe y evidencia

En `lab/campañas/<fecha>-banco/`:
- `informe.md`, con la tabla por caso y los resúmenes por grupo y por alcance;
- `resultados.json`;
- por cada caso, su traza y su línea de tiempo de salud.

### 6.6 Determinismo

- Por defecto, justificación de plantilla (`--sin-llm`).
- Los casos del agente usan un generador guionizado: prueban la ejecución, no el criterio del modelo.
- Los casos que necesitan el modelo lo declaran en `requiere`.

## 7. Cambios en el prototipo

1. **Conector parametrizable (H3):** el nodo de ejecución y la credencial se configuran por entorno o
   por perfil. Por defecto, el comportamiento actual. Con tests.
2. **Nada más.** La corrección de H2 y cualquier fallo que destape el banco de pruebas se tratan como
   tareas aparte, con su propio diseño, para no mezclar el instrumento de medida con lo que mide.

## 8. Fases y planes

**Plan 1, infraestructura:**

| Fase | Contenido | Hecho cuando |
|---|---|---|
| 0 | Verificaciones previas: qué detecta Wazuh de cada ataque previsto (incluido D5), que `fw-core` encamina con nueve interfaces y que el conector parametrizado llega a los nodos | Cada supuesto confirmado o el caso afectado marcado con su límite |
| 1 | Imagen `banco-nodo`, `servicio.py` y el monitor | Tests fuera del laboratorio en verde |
| 2 | `lab/topologias/banco.clab.yml`, selector en `lab.sh`, syslog hacia Wazuh y auditor | Prueba de humo: todo sano, y al tumbar `core-db` a mano el monitor ve caer `middleware`, `web-banking`, `api-movil` y `atm` |
| 3 | Perfil bancario alineado y reconciliación del inventario contra los hallazgos del banco | La reconciliación solo muestra diferencias explicadas |

**Plan 2, banco de pruebas:**

| Fase | Contenido | Hecho cuando |
|---|---|---|
| 4 | Formato, ejecutor, verificación, informe y modos (TDD contra un laboratorio simulado) | Tests en verde; un caso de ejemplo corre de punta a punta |
| 5 | Escenarios por grupos: D, C, K, A, E, H, O y X | Todos definidos; la suite corre y produce su informe |
| 6 | Guías generadas, catálogo con alcance y laboratorio de cada caso, y documentación de satélites y exclusiones | Documentación coherente con el informe |

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Wazuh no detecta algún ataque previsto | Fase 0; el caso lleva su límite de detección y no se fuerza con alertas inventadas |
| El banco de pruebas destapa fallos del prototipo | Es el objetivo: cada fallo va a una tarea aparte |
| Pruebas que fallan a veces por los tiempos de Wazuh | Espera por condición con plazo y tiempos registrados |
| Conflicto con la red pequeña | Una red cada vez; comprobación del entorno al empezar |
| Encaminamiento asimétrico en `fw-core` | Prueba de humo de conectividad en la fase 2 |
| Un ataque sale del laboratorio | `internet` sin salida real; todo dentro de Containerlab |
| Parametrizar el conector rompe la red pequeña | Valor por defecto intacto; su suite y sus demos, sin cambios |
| Los casos inyectados se leen como capacidades del sistema | Etiqueta «acción inyectada: ningún componente la propone hoy» en el informe y en las guías |

## 10. Criterios de éxito

- Cada caso del catálogo tiene **un laboratorio asignado o una exclusión declarada**, y un alcance.
- `--todos` corre la suite del banco de punta a punta y produce el informe. Todo FALLO no esperado queda
  explicado o abierto como tarea.
- K1 muestra H2 con evidencia (predicción frente a monitor).
- La red pequeña y su suite siguen funcionando igual.

## 11. Restricciones globales

- Python 3 con la biblioteca estándar y PyYAML; tests con `unittest`.
- Commits que terminan en `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`;
  fusión local con `--no-ff`; nunca push.
- Ataques solo dentro del laboratorio aislado de Containerlab; todo local (RNF-01).
- No se modifican el plan de trabajo, el roadmap, el informe `.tex`, los documentos de las Fases 1–4 ni
  `informe-evaluacion.md`.
