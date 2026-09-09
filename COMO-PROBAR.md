# Cómo probar el prototipo

Guía práctica ordenada por **niveles de dependencia**. El contenido detallado vive en
**[`docs/pruebas/`](docs/pruebas/README.md)** — un fichero por categoría, cada prueba con su
**Sinopsis** (sintaxis) y un **Ejemplo** listo para pegar.

## Índice

- [Índice, requisitos y arranque rápido](docs/pruebas/README.md)
- [01 · Motor sin dependencias](docs/pruebas/01-motor.md) — tests, triaje, ingesta (RF-01), agrupación (RF-11)
- [02 · RAG y evaluación](docs/pruebas/02-rag-evaluacion.md) — extractor ATT&CK, índice/consulta, `campana`, banco de simulación
- [03 · Lab en vivo](docs/pruebas/03-lab-en-vivo.md) — levantar lab, demos, daemon, agente, monitoreo vs ataque
- [04 · Escenarios de ataque](docs/pruebas/04-escenarios-de-ataque.md) — por comportamiento (auto-bloqueo, confirmación humana, escalada a firewall, FP, `no_soportada`)
- [05 · Topologías del laboratorio](docs/pruebas/05-topologias.md)
- [06 · Rendimiento y hardware](docs/pruebas/06-rendimiento-y-hardware.md) — latencia por modo/hardware; perfil 9800X3D + RTX 5070

## Arranque rápido (copia-pega)

```bash
# 0) Sanidad (segundos, sin dependencias)
python3 -m unittest discover -s prototipo/tests

# 1) El motor decide sobre 410 alertas reales (sin dependencias)
python3 -m prototipo.triaje lab/dataset/etiquetado.jsonl prototipo/perfiles/empresarial.yml \
    lab/campañas/2026-08-31-evaluacion/hallazgos.json salida.jsonl

# 2) Evaluación contra el baseline (sin modelo, rápido)
python3 -m evaluacion.campana --particion evaluacion --sin-llm

# 3) Lab en vivo (necesita Docker + Containerlab + modelo)
sh lab/lab.sh up && python3 lab/scripts/demo-agente-escalado.py --autonomo
```
