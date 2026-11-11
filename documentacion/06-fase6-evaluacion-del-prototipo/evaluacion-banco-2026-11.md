# Evaluación aparte en el laboratorio del banco — diseño fijado antes de medir

> **Estado:** diseño del 11/11/2026, escrito antes de lanzar la campaña. Es una evaluación **separada**:
> no se mezcla con la canónica (perfil empresarial, laboratorio pequeño, n=417) y se reporta en su propia
> tabla. Complementa la ampliación R1 ([ampliacion-dataset-2026-11.md](ampliacion-dataset-2026-11.md)).

## 1. Por qué

La evaluación canónica se hace en una red pequeña con un perfil empresarial. El banco tiene otra
topología (14 nodos, dos cortafuegos, dependencias reales entre servicios) y otro perfil (`bancario`,
continuidad extrema, activos críticos que no se tocan en automático). Medir ahí comprueba si lo que dice
la evaluación canónica se sostiene en otra red y con otra política, sin cambiar el motor.

## 2. Qué se puede medir y qué no

El conjunto de datos etiqueta las cuatro familias del caso de uso: acceso por credenciales,
reconocimiento, servicio expuesto y explotación conocida. Las otras seis familias del banco (cuentas,
integridad, denegación de servicio, acceso consumado, exfiltración y malware) se validaron en vivo, pero
aquí quedarían como `no_soportada`; no entran en esta medida. La priorización tampoco se mide: la tabla de
prioridad esperada describe el laboratorio pequeño, y no se inventa otra para el banco.

## 3. Escenarios y verdad declarada

Una sola campaña, `2026-11-11-banco-evaluacion`, con cada escenario desde su propia IP. Los ataques
reutilizan los casos del banco (`lab/banco/casos.py`) con la IP de origen rotada.

| Id | Desde (IP) | Contra | Qué se hace | Verdad |
|---|---|---|---|---|
| BD1 | `internet` (198.51.100.60) | web-banking SSH | Fuerza bruta externa (caso D1) | **VP** |
| BRC | `internet` (198.51.100.61) | web-banking SSH | Reconocimiento externo (caso RECON) | **VP** |
| BTN | `internet` (198.51.100.62) | atm telnet | Conexiones al telnet expuesto (caso TELNET) | **VP** |
| BEX | `internet` (198.51.100.63) | web-banking web | Inyección SQL (caso EXPLOIT; se enruta, no se contiene) | **VP** |
| BA1 | `taquilla` (10.200.0.10) | web-banking SSH | Fuerza bruta desde un puesto interno (caso A1) | **VP** |
| BK1 | `middleware` (10.40.0.10) | core-db SSH | Fuerza bruta desde un servidor comprometido (caso K1) | **VP** |
| BL1 | `internet` (198.51.100.70) | api-movil SSH | Técnico externo legítimo: 1 error y acceso correcto | **FP** |
| BL2 | `taquilla` (10.200.0.11) | web-banking SSH | Empleado de taquilla: 1 error y acceso correcto | **FP** |

La postura se toma de un escaneo del auditor del banco hecho al cerrar la campaña. El perfil es
`prototipo/perfiles/bancario.yml` tal cual: no se declara a nadie como tercero de confianza.

## 4. Qué se espera, dicho antes de medir

Las amenazas (BD1, BRC, BTN, BEX, BA1, BK1) deberían detectarse todas; las internas (BA1, BK1) y todo lo que
toca un activo crítico deberían ir a un analista. BL1 y BL2 deberían salir como falsos positivos por la
misma razón que en la ampliación: nada en la alerta los separa de un ataque. BL1, de origen externo y
contra un activo de criticidad alta, podría bloquearse solo como el técnico del proveedor de la canónica.

## 5. Cómo se reporta

Tabla propia: clasificación del prototipo frente al baseline, contenciones automáticas e indebidas y
escalado, con el desglose por escenario. Sin mezclar con n=417.

## 6. Resultados (11/11/2026)

Campaña `lab/campañas-banco/2026-11-11-banco-evaluacion` (45 alertas, 42 soportadas; banco recreado y con
`banco.sh test` en verde; sin el daemon en marcha). Conjunto aparte: `lab/dataset/etiquetado-banco.jsonl`
(`particion-banco.yml`). Resultado: `evaluacion/resultados/banco/`.

```
python3 -m evaluacion.campana --particion evaluacion --sin-llm --perfil bancario \
    --dataset lab/dataset/etiquetado-banco.jsonl \
    --hallazgos lab/campañas-banco/2026-11-11-banco-evaluacion/hallazgos.json --salida-dir evaluacion/resultados/banco
```

| Escenario | Verdad | Decisión del motor (perfil bancario) |
|---|---|---|
| BD1 fuerza bruta externa → web-banking | VP (10) | Amenaza; bloqueo automático |
| BRC reconocimiento externo → web-banking | VP (4) | Reconocimiento; bloqueo automático |
| BTN telnet expuesto → atm | VP (3) | Amenaza; bloqueo automático |
| BEX inyección SQL → web-banking | VP (3) | Enrutada a appsec, sin contener |
| BA1 fuerza bruta desde la taquilla → web-banking | VP (10) | Amenaza; a un analista (activo interno) |
| BK1 middleware comprometido → core-db | VP (10) | Amenaza; a un analista (activo interno y crítico) |
| BL2 empleado legítimo de taquilla → web-banking | FP (1) | Amenaza (FP); a un analista |
| BL1 técnico externo legítimo → api-movil | FP (1) | Amenaza (FP); **bloqueo automático** |

- **Las 40 amenazas se detectan todas** (exhaustividad 1,000) y cada una recibe la respuesta que el
  perfil bancario prevé: lo externo se contiene solo, lo interno y lo crítico va a un analista, y la
  explotación web se enruta. Prototipo: 40/2/3/0.
- **Los dos legítimos son falsos positivos**, como en la canónica; **BL1 se bloquea solo** (1 contención
  automática indebida de 18), el mismo hallazgo que el técnico del proveedor de la ampliación.
- **Las tasas no son comparables con la canónica**: la campaña tiene solo 5 negativos (2 legítimos y 3 no
  soportados), así que una tasa de FP de 0,400 son 2 alertas, y el óptimo del baseline es «todo es amenaza»
  (nivel ≥ 3: 40/5/0/0, F1 0,941). Lo que esta evaluación aporta es el desglose por escenario, no las tasas.
- Escalado a un analista: 0,467 (21 de 45), por la continuidad extrema del perfil bancario.

