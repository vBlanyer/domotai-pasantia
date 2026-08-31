# Fase 3 — Configuración del entorno de pruebas

**Objetivo (plan de trabajo, objetivo 3):** poner en funcionamiento un entorno de pruebas con casos
reales, garantizando que los datos no salen a servicios externos, y preparar un conjunto de alertas
**etiquetado** (verdaderos y falsos positivos) que sirva de referencia de evaluación.

---

## Resumen

El entorno es una **red de cliente emulada con Containerlab**: siete nodos que reproducen la
cadena desde el punto de entrega del proveedor hacia dentro —borde, conmutación, puesto, IoT y un
servidor vulnerable— más un auditor en el plano de gestión. Containerlab se eligió por ser gratuito,
auditable y muy ligero; Packet Tracer se descartó por simular en vez de virtualizar, y CML por su
tope duro de nodos.

El entorno funciona y es reproducible de extremo a extremo con `lab/lab.sh`. **Wazuh genera alertas
reales** dentro del laboratorio: un login fallido da nivel 5 y una fuerza bruta correlacionada da
nivel 10, con IP y usuario parseados. Se despliega sin indexer ni dashboard, porque el prototipo
consume `alerts.json` y no una interfaz. Esa decisión resuelve tres cosas a la vez: da entrada al
motor de triaje, da superficie que etiquetar, y **su nivel de regla es el baseline** contra el que
la Fase 6 compara.

El consumo medido desmintió el presupuesto estimado: laboratorio y Wazuh juntos ocupan **menos de
0,8 GB** frente a los ~6 GB previstos. El límite real resultó ser otro — WSL2 exponía la mitad de
la RAM del anfitrión hasta corregirlo.

La fase distingue explícitamente **dos ground truths que no son el mismo**: el de vulnerabilidades,
que sale de la composición documentada de la topología y sirve para evaluar al auditor; y el de
alertas —verdadero o falso positivo—, que sale de contrastar cada alerta contra el inventario del
nodo al que apunta y es lo que evalúa al triaje. El primero está hecho; el segundo es lo que falta.

**Dos límites conocidos.** El equipo de borde es un contenedor Linux provisional y no OpenWrt real,
porque el arranque de vrnetlab se cuelga; deja de ser bloqueante desde que el caso de uso se acota
por familia de alerta, pero sigue siendo el escenario más representativo. Y Greenbone no cabe junto
al resto, así que el auditor opera hoy con Nmap.

---

## Documentos

- [Diseño del sandbox: la red del cliente emulada con Containerlab](sandbox-red-containerlab.md) — qué se emula y qué no, elección de plataforma, topología, Wazuh como fuente y baseline, y los dos ground truths.

En [`lab/`](../../lab/), fuera de esta carpeta, vive el laboratorio ejecutable:

- [lab/README.md](../../lab/README.md) — índice del laboratorio y nodo a nodo.
- [lab/docs/instalacion.md](../../lab/docs/instalacion.md) — **guía de instalación**: de una máquina limpia a `lab.sh up`. El punto de partida.
- [lab/docs/prueba-manual.md](../../lab/docs/prueba-manual.md) — verificación de extremo a extremo, una vez instalado.
- [lab/docs/vulnerabilidades-esperadas.md](../../lab/docs/vulnerabilidades-esperadas.md) — **ground truth de vulnerabilidades**: qué se ha plantado en cada nodo.
- [lab/docs/generar-alertas.md](../../lab/docs/generar-alertas.md) — cómo producir alertas y qué nivel asigna Wazuh a cada una.
- [lab/docs/mediciones.md](../../lab/docs/mediciones.md) — consumo real por escalón, frente a lo estimado.

---

## Entradas y salidas

**Consume:** de la [Fase 1](../01-fase1-analisis-del-modulo/), el arquetipo de red que el
laboratorio instancia y el perímetro que decide qué actividad merece generarse.

**Entrega a:**

| Fase | Qué se lleva |
|------|--------------|
| [4](../04-fase4-diseno-de-arquitectura/) | Las restricciones reales —memoria medida, Greenbone fuera del camino en vivo— que condicionan el diseño |
| [5](../05-fase5-implementacion-del-prototipo/) | `alerts.json` como entrada real del módulo de ingesta |
| [6](../06-fase6-evaluacion-del-prototipo/) | El dataset etiquetado y el baseline de Wazuh |

---

## Estado

**Entorno operativo y verificado; el entregable de datos, pendiente.**

Hecho: topología versionada y reproducible, superficie de ataque real con ground truth de
vulnerabilidades documentado, Wazuh emitiendo alertas, auditor con Nmap, y el consumo medido.

Falta para cerrar la fase, según su criterio del roadmap —*el dataset cuenta con ground truth
suficiente para calcular precisión, recall y F1*—:

- **Dataset de alertas etiquetado** (verdadero / falso positivo) y documentado: origen, volumen,
  criterio y distribución.
- **Partición en entrenamiento y evaluación** con campañas disjuntas, exigida si el perfil de
  modelo requiere ajuste fino. Entrenar y medir sobre las mismas alertas invalidaría la Fase 6.
- **Salida normalizada del auditor**, con la versión de su base de datos fijada y registrada.
