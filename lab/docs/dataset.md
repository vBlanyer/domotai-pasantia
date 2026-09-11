# Dataset de alertas etiquetado

**Entregable de la Fase 3.** El conjunto de alertas reales de Wazuh, cruzadas contra el
inventario del auditor y etiquetadas con el ground truth (verdadero positivo / falso positivo /
propia / no soportada) que la Fase 6 usa para medir precisión, recall y F1 del motor de triaje
frente al baseline de Wazuh.

Vive en [`lab/dataset/etiquetado.jsonl`](../dataset/etiquetado.jsonl), una línea JSON por alerta.
El diseño completo —arquitectura, árbol de decisión y límites conocidos— está en la
[especificación](../../docs/superpowers/specs/2026-08-31-dataset-alertas-etiquetado-design.md).

---

## Cómo se genera

Tres piezas encadenadas, todas ejecutables desde la raíz del repo:

1. **`sh lab/scripts/campana.sh <id-campaña>`** — lanza actividad real contra el laboratorio
   (fuerza bruta SSH desde `puesto`, logins fallidos benignos desde `borde` con la IP del admin
   declarada, y un escaneo de puertos desde `auditor`), congela `alerts.json` fuera del
   contenedor y escribe la ficha `campaña.yml` (quién es el auditor, quién es legítimo). Termina
   invocando `auditar.sh`, que escanea los nodos y produce `hallazgos.json` — la postura real de
   cada activo, con la versión de Nmap registrada.

   **`sh lab/scripts/campana-recon.sh <id-campaña>`** (11/09/2026) — la misma estructura para la
   familia `reconocimiento`: barridos de puertos y sondeos de protocolo contra el 22 desde `puesto`,
   comprobaciones benignas desde `borde` y un barrido desde `auditor`. Dos diferencias medidas: los
   sondeos se hacen con `nc` porque **nmap no deja rastro en el sshd de Metasploitable** (un escaneo
   SYN no completa la conexión y sshd no lo ve; `nmap -sT` cierra con RST y ese sshd de 2007 solo
   registra el cierre limpio con FIN) —por eso la campaña original, que escaneaba desde el auditor,
   no produjo ni una alerta de esta familia—; y se congela **solo la ventana temporal** de la campaña,
   no `alerts.json` entero. Cada campaña deja 15 alertas: 9 del atacante (6×5706 «Did not receive
   identification string», 3×5701 «Bad protocol version identification»), 4 del admin (FP) y 2 del
   auditor (PROPIA).

   **`sh lab/scripts/campana-telnet.sh <id-campaña>`** (11/09/2026) — familia `servicio_expuesto`:
   conexiones al telnet en claro del objetivo con `nc` desde `puesto` (ocho en dos minutos: dispara
   además la correlación 5631 de nivel 10), `borde` (FP) y `auditor` (PROPIA). El `in.telnetd` de
   Metasploitable escribe en `daemon.log` (el reenvío lo lleva desde este día) con el formato de tcpd,
   que el decodificador de fábrica de Wazuh no sabe leer: `lab/wazuh/local_decoder_telnetd.xml`. 13
   alertas por campaña: 8 del atacante (7×5602, 1×5631), 3 del admin, 2 del auditor.

   **`sh lab/scripts/campana-reglas-fallan.sh <id-campaña>`** (11/09/2026) — los casos en que las cinco
   reglas fallan, con la **verdad declarada por el experimento**: la ficha lleva un bloque `verdad:` con
   `origen`, `desde`, `hasta`, `etiqueta` y `motivo`, que el etiquetador aplica antes que las reglas
   (`etiqueta_por: campaña`). Sin esto, las etiquetas las generaban las mismas señales que usa el
   clasificador y un modelo entrenado solo podía copiarlas.

2. **`lab/dataset/particion.yml`** — reparto a priori de campañas a `entrenamiento` o
   `evaluacion`, fijado **antes** de construir el dataset y versionado.

3. **`python3 -m lab.dataset.construir lab/campañas lab/dataset/particion.yml
   lab/dataset/resoluciones.yml lab/dataset/etiquetado.jsonl`** — normaliza cada alerta cruda al
   esquema del proyecto, la etiqueta cruzándola contra `hallazgos.json` y la ficha de la campaña,
   le asigna la partición, y escribe `etiquetado.jsonl`. Imprime cuántas alertas quedaron
   `PENDIENTE` (casos grises que la regla no pudo decidir); esas se resuelven a mano en
   `lab/dataset/resoluciones.yml` (`id_alerta: VP|FP|PROPIA|no_soportada`) y se reconstruye hasta
   que no quede ninguna.

**Despliegue limpio por campaña.** `alerts.json` es acumulativo dentro del contenedor: arrastra
actividad de ejecuciones previas. Por eso cada campaña se genera tras `sh lab/lab.sh down && sh
lab/lab.sh up` (con el plano de datos verificado por `sh lab/lab.sh status`) — nunca reutilizando
un laboratorio que ya tenía tráfico encima. `sh lab/lab.sh test` no se usa nunca en este flujo:
inyecta tráfico sintético (origen `10.20.30.x`) que no pertenece a ninguna campaña real.

## Esquema (16 campos)

Cada línea de `etiquetado.jsonl` sigue el contrato de la especificación —
[§5 Esquema normalizado](../../docs/superpowers/specs/2026-08-31-dataset-alertas-etiquetado-design.md#5-esquema-normalizado-el-contrato).
Resumen:

| Grupo | Campos |
|-------|--------|
| Identidad y trazabilidad | `id_alerta`, `timestamp`, `campaña`, `fuente` |
| Activo y evento | `activo`, `servicio`, `familia`, `origen_ip`, `mitre`, `evento_crudo` |
| Baseline | `nivel_wazuh`, `regla_id` |
| Ground truth | `etiqueta`, `etiqueta_por`, `postura_activo`, `particion` |

`evento_crudo` es el texto original de Wazuh: se guarda porque el justificador de la Fase 5 lo
necesita, pero el contrato lo declara **dato inerte, nunca instrucción** (RNF-08).

## Origen y volumen

Dos campañas reales, cada una tras un despliegue limpio del laboratorio:

| Campaña | Partición | Alertas |
|---------|-----------|---------|
| `2026-08-31-entrenamiento` | entrenamiento | 205 |
| `2026-08-31-evaluacion` | evaluacion | 205 |
| **Total** | | **410** |

## Distribución de etiquetas

Salida real del guard de cierre (`et`/`pa` sobre `etiquetado.jsonl`, ver spec §10):

```
total: 410
etiquetas: {'no_soportada': 374, 'VP': 20, 'FP': 16}
partición: {'entrenamiento': 205, 'evaluacion': 205}
CIERRE OK
```

Por partición, la distribución es simétrica (ambas campañas ejecutan el mismo guion de
`campana.sh`):

| Partición | VP | FP | no_soportada |
|-----------|----|----|---------------|
| entrenamiento | 10 | 8 | 187 |
| evaluacion | 10 | 8 | 187 |

`no_soportada` domina porque la mayoría del tráfico de fondo del laboratorio (ruido de
plataforma, servicios sin familia mapeada) cae fuera del [caso de uso
acotado](../../documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md); queda en el
dataset con su severidad intacta, a cola manual, en vez de descartarse (RF-10). No hubo alertas
`PROPIA`: el escaneo del auditor no dispara ninguna regla de Wazuh en este laboratorio, así que
no hay tráfico propio que filtrar en esta iteración.

Ambos lados de la partición contienen VP y FP — condición necesaria para que la evaluación pueda
calcular precisión (VP/(VP+FP)).

## Política de partición

Fijada **a priori** en [`lab/dataset/particion.yml`](../dataset/particion.yml), por identificador
de campaña completo (nunca por alerta individual, para no filtrar información entre ráfagas de la
misma sesión), antes de construir el dataset y sin tocarse después al ver los números:

```yaml
entrenamiento:
  - 2026-08-31-entrenamiento
evaluacion:
  - 2026-08-31-evaluacion
```

Con solo dos campañas el reparto es 50/50 en vez del ~80/20 recomendado en la especificación; se
acepta en esta iteración porque cada lado ya cumple la condición estratificada obligatoria
—ambas etiquetas VP y FP presentes en los dos lados—, que es lo que hace calculable la
evaluación. Añadir más campañas de entrenamiento sin tocar `2026-08-31-evaluacion` es la vía para
acercarse al 80/20 sin volver a tocar el lado de evaluación ni contaminarlo.

## Reproducir

```bash
sh lab/lab.sh down && sh lab/lab.sh up
sh lab/lab.sh status   # confirma "OK: el puesto tiene su IP de LAN"
sh lab/scripts/campana.sh <id-campaña>
# ... repetir down/up/campana.sh por cada campaña nueva ...
python3 -m lab.dataset.construir lab/campañas lab/dataset/particion.yml \
  lab/dataset/resoluciones.yml lab/dataset/etiquetado.jsonl
```

Las campañas `prueba-*` bajo `lab/campañas/` (generadas al probar el pipeline) están en
`.gitignore` y no se versionan ni se cuentan en el dataset — `construir.py` recorre todas las
subcarpetas de `lab/campañas/`, así que cualquier campaña de prueba debe borrarse antes de
reconstruir para no contaminar el resultado.
