# Estructura del repositorio

Mapa de un vistazo de qué es cada carpeta. El diseño completo está en
[`documentacion/`](documentacion/README.md); cómo operar el sistema, en [`RUNBOOK.md`](RUNBOOK.md).

```
.
├── prototipo/          Producto: motor de triaje MDR (paquete Python, stdlib + yaml)
├── visor/              Producto: consola web (React/TS/Vite) que sirve el daemon
├── deploy/             Producto: kit de despliegue en producción (systemd + /healthz)
├── evaluacion/         Arnés de evaluación contra el baseline + resultados medidos
├── lab/                Laboratorio: banco Containerlab, dataset etiquetado, topologías, scripts, campañas
├── documentacion/      Tesis por fases (00-general … 07-fase7) + material-superado/
├── docs/               Guías de prueba y evidencia (docs/pruebas/)
├── archivo/            Archivo del PROCESO de desarrollo (planes/specs); no es diseño vigente
├── README.md           Qué es el proyecto y qué hay construido
├── CHANGELOG.md        Qué cambió en cada versión (v1.0, v1.1 y posteriores)
├── RUNBOOK.md          Cómo arrancar y operar todo, paso a paso
├── EVALUAR-LLM-EN-GPU.md  Cómo medir un modelo de justificación en una máquina con GPU
└── reiniciar.sh        Reinicia el daemon en vivo sobre el banco levantado
```

## Producto (lo que se entrega como sistema)

- **[`prototipo/`](prototipo/)** — el motor: ingesta → clasificación → política determinista →
  filtro del perfil de cliente → traza encadenada → acción con validación humana. Incluye el daemon
  en vivo (`stream.py`), la API/consola (`tablero.py`), el justificador LLM+RAG y el agente ReAct.
  El registro de familias extensible vive en [`prototipo/familias.yml`](prototipo/familias.yml).
- **[`visor/`](visor/)** — la consola SOC web (React/TypeScript) que consume la API del daemon.
- **[`deploy/`](deploy/)** — unidad systemd, wrapper del *pipe*, `EnvironmentFile` de ejemplo y guía
  de supervisión (`/healthz`, retención de traza, receptor por red).

## Evaluación y laboratorio (la evidencia y cómo se reproduce)

- **[`evaluacion/`](evaluacion/resultados/README.md)** — campañas, métricas frente al baseline de
  reglas y los resultados datados que respaldan el capítulo de resultados del informe.
- **[`lab/`](lab/)** — el laboratorio ejecutable: el **banco** bancario sobre Containerlab
  ([`lab/banco/`](lab/banco/)), el **dataset etiquetado** ([`lab/dataset/`](lab/dataset/)), las
  topologías, los scripts de aprovisionamiento/auditoría/campañas y las campañas datadas que
  generaron el dataset.

## Documentación

- **[`documentacion/`](documentacion/README.md)** — el diseño completo en 7 fases. Dentro,
  **[`documentacion/material-superado/`](documentacion/material-superado/)** conserva documentos que
  ya no reflejan el diseño vigente (se guardan por trazabilidad).
- **[`docs/pruebas/`](docs/pruebas/)** — guías de prueba y evidencia por escenario.

## Archivo de proceso

- **[`archivo/`](archivo/)** — el registro del **proceso de desarrollo** (planes y specs de cada
  fase). Es historia del cómo se construyó, no diseño vigente ni parte del producto.

> Dos archivos distintos, a propósito: `archivo/` es el **proceso de desarrollo**;
> `documentacion/material-superado/` es **material de referencia superado** del propio diseño.
