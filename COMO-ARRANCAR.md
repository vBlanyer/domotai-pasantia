# Cómo arrancar y probar el sistema

Runbook operativo del MDR: cómo levantar todo, qué pantallas hay (terminal, web, lanzador de ataques,
panel de salud, banco de pruebas) y cómo apagarlo. Para el detalle de cada prueba, ver
[`docs/pruebas/`](docs/pruebas/README.md); para el laboratorio del banco, [`docs/pruebas/08`](docs/pruebas/08-laboratorio-banco.md)
y el [README del banco](lab/banco/README.md); para el visor web, [`docs/pruebas/09`](docs/pruebas/09-tablero-web.md).

El sistema **no detecta** ataques: **refina** las alertas que genera un SIEM (aquí Wazuh emula el del
cliente). El escenario insignia es el **laboratorio del banco** (14 nodos en Containerlab); todo lo de abajo
usa ese escenario.

---

## 1. Requisitos

| Para… | Necesitas |
|---|---|
| El motor y sus pruebas | **Python 3** (probado en 3.14) + **PyYAML**. Sin pip/venv/pytest. |
| El laboratorio (demo en vivo) | **Docker** + **Containerlab**. |
| El visor web (React) | **Node.js** + **npm** (solo para `visor/`; el núcleo sigue Python). |
| Justificación con LLM (`--con-llm`) | Entorno conda con `llama.cpp` + el modelo `modelos/llama-3.2-1b-q4.gguf`. **Opcional**: sin él, la justificación es por plantilla, instantánea. |

Todos los comandos se ejecutan **desde la raíz del repositorio**, salvo los de `visor/` (que lo indican).

---

## 2. Arrancar el sistema (laboratorio del banco)

```bash
# 2.1 Construir la imagen de los nodos (una sola vez)
sh lab/banco/construir-imagen.sh

# 2.2 Levantar el banco: 14 nodos + Wazuh + monitor de salud (arranca solo)
sh lab/lab.sh up banco

# 2.3 Aprovisionar el mínimo privilegio del conector — HAY QUE HACERLO TRAS CADA `up`
sh lab/banco/banco.sh aprovisionar

# 2.4 Comprobar que todo está sano (conectividad + servicios)
sh lab/banco/banco.sh test
```

Si `aprovisionar` o `test` fallan, ve a [§7 Problemas](#7-solución-de-problemas).

**El daemon (el motor MDR)** lee las alertas de Wazuh por stdin y decide. Antes, exporta el nodo de
gestión para que el conector ejecute desde `mdr-siem`:

```bash
export TRIAJE_NODO_GESTION=clab-banco-mdr-siem

docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
  | python3 -m prototipo.stream - prototipo/perfiles/bancario.yml \
      lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --web
```

- `-` = la fuente es **stdin** (la cola de alertas de Wazuh).
- `--web` levanta además el **visor web** en `http://127.0.0.1:8787` (ver §3B). Quítalo si solo quieres terminal.
- El daemon queda escuchando; cada alerta que Wazuh levante se decide y, si hace falta humano, pide aprobación.

---

## 3. Las pantallas / interfaces

### A. Terminal — el daemon (siempre)

La salida de `python3 -m prototipo.stream …` es la vista principal:
- **Feed de decisiones:** una línea por incidente (clase, confianza, acción propuesta/final, filtro del
  perfil, impacto y cascada).
- **Menú de aprobación:** cuando una decisión requiere humano, aparece `[1] Aprobar · [2] Rechazar ·
  [3] Reclasificar` (o `¿aprobar la ejecución? [s/N]` en la escalada del agente). Se responde por el
  **teclado de la terminal** (`/dev/tty`), aunque las alertas entren por el *pipe*.
- **Supresión:** si el mismo ataque `(IP, familia)` ya se decidió, las repeticiones salen como
  `↩ … ya decidido · +N suprimida(s)` en vez de volver a preguntar (desactivable con `--sin-supresion`).
- Al salir (`Ctrl+C`), imprime un resumen (alertas, incidentes, aprobadas/rechazadas, ejecutadas, suprimidas).

### B. Web — el visor React (con `--web`)

Consola visual que consume la misma API del daemon. **Cuatro paneles:** Salud (servicios verde/rojo +
dependencias), Decisiones (el feed), Aprobaciones (aprobar/rechazar desde el navegador) y Trazas (registro
completo + verificar la cadena de hashes).

- **En vivo (lo normal):** con el daemon lanzado con `--web`, abre **`http://127.0.0.1:8787`**. El visor ya
  está construido y lo sirve el propio daemon. `--web 9000` usa otro puerto.
- **Desarrollo del visor** (recarga en caliente): en otra terminal,
  ```bash
  cd visor && npm install      # una sola vez
  npm run dev                  # Vite en http://127.0.0.1:5173 (habla con el daemon en :8787 por CORS)
  ```
- **Reconstruir el visor** tras cambiar su código: `cd visor && npm run build` (genera `visor/dist`, que
  sirve el daemon).

La aprobación por web **y** por terminal conviven: apruebas donde prefieras; los logs siguen en la terminal.
Un clic en Aprobar ejecuta la contención real (`iptables`) por el conector; queda en la traza. Es local
(`127.0.0.1`) y **sin autenticación** (etapa inicial).

### C. Lanzador de ataques por número (para demos)

En **otra terminal**, un menú para disparar ataques y verlos decidir en el daemon/visor:

```bash
sh lab/banco/banco.sh atacar
```

Lista los casos vivos (CASCADA, D1, A1, K1, E1); eliges por número, lo lanza (respeta los 60 s de silencio
de la regla 5763 de Wazuh entre ataques) y ofrece deshacer/restaurar.

**IP de origen rotativa (tecla `r`):** por defecto cada caso ataca desde su IP fija (p. ej. D1 desde
`198.51.100.10`), así que al repetirlo choca con el bloqueo automático y con la supresión del MDR y "no pasa
nada". Con `r` enciendes la **rotación**: cada ataque sale desde una IP nueva de la misma subred del atacante
(`198.51.100.11`, `.12`, …) atando el cliente SSH a esa IP; Wazuh la ve como origen distinto, así que puedes
**re-lanzar el mismo ataque cuantas veces quieras** (cada uno genera su propio bloqueo, como un atacante real
que rota IPs) y **sin esperar los 60 s**. El deshacer retira el bloqueo de la IP rotada correspondiente.

### D. Panel de salud en la terminal

Vista de los servicios en verde/rojo con dependencias y últimos cambios (lo mismo que el panel Salud del
visor, pero en texto):

```bash
sh lab/banco/banco.sh vigilar
```

### E. Banco de pruebas automático (regresión, sin operar a mano)

Corre el catálogo de casos y da un veredicto por caso (OK/FALLO/BLOQUEADO/OMITIDO):

```bash
python3 -m lab.banco.pruebas              # niveles decision/inyectada/perfil, sin lab, segundos
python3 -m lab.banco.pruebas --con-vivo   # además los casos de extremo a extremo (banco levantado)
python3 -m lab.banco.pruebas --guias      # regenera una guía por caso en docs/pruebas/banco/
```

---

## 4. Flags del daemon (`prototipo.stream`)

```
python3 -m prototipo.stream <fuente> <perfil> <hallazgos> [flags]
```

- `<fuente>`: `-` (stdin, lo normal con el pipe de Wazuh) o la ruta de un fichero de alertas.
- `<perfil>`: `prototipo/perfiles/bancario.yml` (banco) · `<hallazgos>`: los del auditor del banco.

| Flag | Efecto |
|---|---|
| `--web [puerto]` | Levanta el visor web (por defecto `8787`). |
| `--con-llm` / `--sin-llm` | Justificación con el LLM 1B real / por plantilla (rápida). Por defecto sin LLM. |
| `--agente` | Mitigación con el agente ReAct (escala host→cortafuegos, aprobación por paso). |
| `--ventana-agrupacion N` | Segundos para agrupar alertas en incidentes (por defecto 5). |
| `--salida F` | Fichero de traza (por defecto `trazas-stream.jsonl`). Usa uno nuevo para una cadena limpia. |
| `--sin-supresion` | Desactiva la supresión de repetidos (audita cada alerta). |
| `--sin-lab` | No usa el laboratorio (ejecutor simulado); para probar el motor sin Docker. |

---

## 5. Una demo completa (tres terminales)

```
Terminal 1 — daemon + web:
  export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
  docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
    | python3 -m prototipo.stream - prototipo/perfiles/bancario.yml \
        lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --web
  → abre http://127.0.0.1:8787

Terminal 2 — salud (opcional):
  sh lab/banco/banco.sh vigilar

Terminal 3 — lanzar ataques:
  sh lab/banco/banco.sh atacar
  → elige, p. ej., A1 (interno, se retiene): aparece en Aprobaciones (web) y en el menú de la Terminal 1.
    Apruébalo/recházalo; la decisión pasa a Decisiones y a Trazas.
```

---

## 6. Apagar y limpiar

```bash
# Bajar el banco (y Wazuh)
sh lab/lab.sh down banco

# Quitar las variables de sesión (importante antes de volver a la red pequeña)
unset TRIAJE_NODO_GESTION AUDITOR_PUERTOS
```

---

## 7. Solución de problemas

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `aprovisionar` falla con «no se pudo leer la clave del host» | Contenedores rancios de un deploy anterior → el `up` no reasignó las IPs 10.x del plano de datos | `sh lab/banco/banco.sh down && sh lab/lab.sh up banco && sh lab/banco/banco.sh aprovisionar` (redeploy limpio) |
| El daemon no muestra nada tras un ataque | La regla 5763 de Wazuh se silencia 60 s tras dispararse | Espera ~60 s y repite (el lanzador `atacar` ya lo respeta) |
| El conector falla en todos los nodos | Falta `aprovisionar` tras el último `up`, o falta el `export TRIAJE_NODO_GESTION` | Ejecuta ambos (§2.3 y el `export`) |
| El visor muestra «sin conexión con el daemon» | El daemon no corre con `--web`, o el puerto no coincide | Lanza el daemon con `--web`; en `npm run dev`, el daemon debe estar en `:8787` |
| `Address already in use` al lanzar `--web` | Ya hay un daemon en ese puerto | Cierra el anterior, o usa `--web <otro-puerto>` |
| «La red pequeña está levantada» al hacer `up banco` | Las dos redes no conviven | `sh lab/lab.sh down` y reintenta |
| `Trazas` en el visor dice «cadena rota» | El fichero de traza por defecto arrastra registros viejos (previos al encadenado) | Arranca el daemon con `--salida trazas-banco-$(date +%F).jsonl` (cadena limpia) |

---

## 8. Alternativa: la red pequeña (sin banco)

El motor también corre sobre la red pequeña del cliente (Metasploitable + Wazuh):

```bash
sh lab/lab.sh up                                    # topología red-cliente
python3 lab/scripts/demo-agente-escalado.py --autonomo   # demo del agente de mitigación
sh lab/lab.sh down
```

No conviven las dos redes a la vez (comparten la red de gestión); `lab.sh` lo protege.

---

## 9. Probar las suites (antes de fusionar)

```bash
# Núcleo Python (motor, evaluación, dataset, banco)
for d in prototipo/tests evaluacion/tests lab/dataset/tests lab/banco/tests; do \
  PYTHONPATH=. python3 -m unittest discover -s "$d" -t . 2>&1 | tail -1; done

# Visor React
cd visor && npm run typecheck && npm run test && npm run build
```

Todo debe dar `OK` / verde.
