# Correspondencia servicio↔vulnerabilidad y respuesta dirigida — plan de implementación

> **Para ejecutores:** SUB-SKILL REQUERIDA: superpowers:executing-plans (nativo) o
> superpowers:subagent-driven-development. Los pasos usan checkbox (`- [ ]`) para seguimiento.

**Goal:** Que el servicio atacado pondere la prioridad y genere una recomendación de respuesta
dirigida (contener origen / endurecer servicio / enrutar / observar), visible para analista, agente,
traza y visor, **sin cambiar** la acción automática ni las métricas canónicas.

**Architecture:** Aditivo en 3 piezas. (1) Esquema de servicios enriquecido y retrocompatible,
normalizado en un módulo neutro `prototipo/servicios.py`. (2) Registro de datos
`prototipo/correspondencia.yml` + `prototipo/correspondencia.py`. (3) La decisión gana un campo
`recomendacion` que viaja por `triaje.procesar` → `traza` → API/visor y una línea en la tarjeta humana.

**Tech Stack:** Python 3 (stdlib + yaml) en `prototipo/`; visor Vite/React 19/TS/Zod/Vitest.

**Spec:** [2026-10-06-correspondencia-servicio-vulnerabilidad-design.md](../specs/2026-10-06-correspondencia-servicio-vulnerabilidad-design.md)

## Global Constraints

- Backend solo biblioteca estándar + `yaml`. `prototipo/` **no** importa `lab/`.
- Visor: **sin dependencias nuevas**.
- TDD estricto: RED→GREEN por paso; suite completa en verde antes de cada commit.
- Commits terminados en `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Rama: `feat/correspondencia-servicio` (ya creada; el spec está en ella).
- **Métricas canónicas intactas** (recall 1,000; FP 0,000/0,009; escalado 0,297; matriz
  {174,4,422,0}; partición eval {87,2,211,0}, 89/300). La red de seguridad es
  `evaluacion/tests/test_canonicos.py`: se corre al final de las tareas 2 y 7 sin tocar números.
- **No** `git add -A`: el directorio `lab/campañas/2026-09-24-banco-regresion/` sigue sin rastrear.
- **Ruling (desviación del spec, registrada):** la normalización del esquema vive en un módulo
  neutro `prototipo/servicios.py` (no en `perfil.py`), porque `perfil.py` ya importa `impacto`
  ([perfil.py:4](../../../../prototipo/perfil.py#L4)) e `impacto` debe consumir la normalización →
  un helper en `perfil` crearía el ciclo `perfil↔impacto`. `servicios.py` solo importa `postura`
  (que no importa nada de `prototipo`). Intención del spec («una sola fuente de verdad») preservada.
  Coste si erróneo: un módulo de más; trivial de mover.
- **Ruling:** `correspondencia.recomendar` no recibe `expuesto` (el spec lo listaba): la `clase` ya
  codifica la exposición (`fp_exposicion_inexistente` cuando no está expuesto), que es el gate de
  `None`. Menos superficie, mismo comportamiento.

## Review Focus

Entradas/fallos que el spec implica y que conviene verificar explícitamente:

1. **Perfil con `servicios_prestados` mixto** (enteros + dicts): el cruce con el auditor
   (`impacto`/`inventario`) da el **mismo** conjunto de puertos que con enteros puros — no regresión.
   → cubierto en Tarea 1 (`test_servicios`, `test_impacto`, `test_inventario`).
2. **Alerta sin `servicio` o `desconocido`**: `criticidad_servicio` cae al activo; `recomendar` usa
   solo familia; nada lanza. → Tarea 1 y Tarea 3.
3. **Dict de servicio sin `puerto` o `criticidad` fuera de vocabulario**: `perfil.validar` avisa, no
   lanza, y el puerto ausente no corrompe el conjunto declarado. → Tarea 1.
4. **Alias web nombre↔puerto** (`apache`/`nginx`→`http`/`https`): `criticidad_servicio` empareja por
   nombre y por puerto vía hallazgos. → Tarea 1.
5. **`recomendacion` None** (FP/no_soportada): `validacion.mostrar` y el feed no muestran bloque
   vacío; la cadena de traza sigue válida (`traza.verificar`). → Tareas 4 y 5.

---

## File Structure

- **Crear** `prototipo/servicios.py` — normalización del esquema + `criticidad_servicio` (importa solo `postura`).
- **Crear** `prototipo/correspondencia.yml` — dato: familia/servicio → respuesta recomendada.
- **Crear** `prototipo/correspondencia.py` — `cargar`/`registro`/`recomendar`.
- **Modificar** `prototipo/impacto.py` — `_declarados` → `servicios.puertos_declarados`.
- **Modificar** `prototipo/inventario.py` — conjunto declarado → `servicios.puertos_declarados`.
- **Modificar** `prototipo/analisis.py` — `enriquecer` usa `servicios.criticidad_servicio`.
- **Modificar** `prototipo/perfil.py` — `validar` avisa de dicts de servicio mal formados.
- **Modificar** `prototipo/triaje.py` — calcula `recomendacion`, lo mete en `analisis_out`.
- **Modificar** `prototipo/traza.py` — `construir` guarda `recomendacion`.
- **Modificar** `prototipo/validacion.py` — `mostrar` añade la línea «Recomendado: …».
- **Modificar** `prototipo/agente_mitigacion.py` — la recomendación entra en el contexto del prompt.
- **Modificar** `prototipo/tablero.py` — `_resumen_traza` expone `recomendacion`.
- **Modificar** `visor/src/api.ts` — `DecisionSchema` y `DetalleSchema` + `recomendacion`.
- **Modificar** `visor/src/components/Decisiones.tsx` — `Campo` en el detalle + distintivo en la fila.
- Tests nuevos/ampliados: `prototipo/tests/test_servicios.py`, `test_correspondencia.py`, y ampliar
  `test_impacto.py`, `test_inventario.py`, `test_analisis.py`, `test_perfil.py`, `test_triaje.py`,
  `test_traza.py`, `test_validacion.py`, `test_agente_mitigacion.py`, `test_tablero.py`;
  `visor/src/api.test.ts`.

---

## Task 1: Esquema de servicios enriquecido (`servicios.py`) + migrar `impacto`/`inventario`

**Files:**
- Create: `prototipo/servicios.py`, `prototipo/tests/test_servicios.py`
- Modify: `prototipo/impacto.py` (`_declarados`, 83-84), `prototipo/inventario.py` (23),
  `prototipo/perfil.py` (`validar`, 43-55)
- Test: ampliar `prototipo/tests/test_impacto.py`, `test_inventario.py`, `test_perfil.py`

**Interfaces — Produces:**
- `servicios.normalizar(entradas, criticidad_activo) -> list[dict]` con claves
  `{"puerto": int|None, "servicio": str|None, "criticidad": str, "rol": str|None}`.
- `servicios.de_activo(perfil, activo) -> list[dict]`
- `servicios.puertos_declarados(perfil, activo) -> set[int]`
- `servicios.criticidad_servicio(perfil, activo, servicio, hallazgos=None) -> str`

- [ ] **Step 1: Test de `servicios.normalizar`/`puertos_declarados`/`criticidad_servicio` (RED)**

```python
# prototipo/tests/test_servicios.py
import unittest
from prototipo import servicios

PERFIL = {"activos": {
    "web": {"criticidad": "alta", "servicios_prestados": [443, {"puerto": 80, "criticidad": "media"},
                                                           {"puerto": 22, "servicio": "ssh", "rol": "gestion"}]},
    "db":  {"criticidad": "critica", "servicios_prestados": [1521]},
}}
HALLAZGOS = {"nodos": {"web": [{"puerto": 443, "servicio": "https", "estado": "open"}]}}

class TestServicios(unittest.TestCase):
    def test_entero_hereda_criticidad_del_activo(self):
        n = servicios.normalizar([443], "alta")
        self.assertEqual(n, [{"puerto": 443, "servicio": None, "criticidad": "alta", "rol": None}])

    def test_dict_con_criticidad_propia_y_fallback(self):
        n = servicios.normalizar([{"puerto": 80, "criticidad": "media"}, {"puerto": 22}], "alta")
        self.assertEqual(n[0]["criticidad"], "media")
        self.assertEqual(n[1]["criticidad"], "alta")   # sin criticidad -> hereda

    def test_puertos_declarados_mezcla_entero_y_dict(self):
        self.assertEqual(servicios.puertos_declarados(PERFIL, "web"), {443, 80, 22})

    def test_dict_sin_puerto_se_ignora_en_el_conjunto(self):
        p = {"activos": {"x": {"servicios_prestados": [443, {"criticidad": "alta"}]}}}
        self.assertEqual(servicios.puertos_declarados(p, "x"), {443})

    def test_criticidad_por_nombre(self):
        self.assertEqual(servicios.criticidad_servicio(PERFIL, "web", "ssh"), "media")   # activo alta, servicio ssh hereda alta? -> ssh no declara criticidad: hereda alta

    def test_criticidad_por_puerto_via_hallazgos(self):
        # la alerta trae el nombre "https"; el puerto 443 (entero) hereda la criticidad del activo
        self.assertEqual(servicios.criticidad_servicio(PERFIL, "web", "https", HALLAZGOS), "alta")

    def test_criticidad_fallback_al_activo_si_no_empareja(self):
        self.assertEqual(servicios.criticidad_servicio(PERFIL, "db", "desconocido"), "critica")

    def test_servicio_de_menor_criticidad_que_el_activo(self):
        self.assertEqual(servicios.criticidad_servicio(PERFIL, "web", "http", HALLAZGOS), "media")  # puerto 80 -> media
```

(Corrige el comentario de `test_criticidad_por_nombre`: `ssh` no declara criticidad propia, hereda
`alta` del activo; el test afirma `"media"` solo si se decide que `rol: gestion` no afecta la
criticidad — **afirmar `"alta"`**. Ajusta el `assertEqual` a `"alta"` antes de implementar.)

- [ ] **Step 2: Ejecuta el test (RED)** — `python3 -m unittest prototipo.tests.test_servicios -v` → ModuleNotFoundError / AttributeError.

- [ ] **Step 3: Implementa `servicios.py` (GREEN)**

```python
# prototipo/servicios.py
"""Esquema de `servicios_prestados` enriquecido y retrocompatible, y criticidad por servicio.

Un activo declara servicios como enteros (puerto) o dicts {puerto, servicio?, criticidad?, rol?}.
Fuente única: `impacto`/`inventario` toman aquí el conjunto de puertos; `analisis` la criticidad del
servicio atacado. Importa solo `postura` (traducción nombre↔protocolo); nunca `perfil` ni `impacto`,
para no crear ciclos."""
from prototipo import postura

def _a_entero(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

def normalizar(entradas, criticidad_activo):
    salida = []
    for e in entradas or []:
        if isinstance(e, dict):
            salida.append({"puerto": _a_entero(e.get("puerto")), "servicio": e.get("servicio"),
                           "criticidad": e.get("criticidad") or criticidad_activo, "rol": e.get("rol")})
        else:
            salida.append({"puerto": _a_entero(e), "servicio": None,
                           "criticidad": criticidad_activo, "rol": None})
    return salida

def _activo(perfil, activo):
    return ((perfil or {}).get("activos") or {}).get(activo) or {}

def de_activo(perfil, activo):
    a = _activo(perfil, activo)
    return normalizar(a.get("servicios_prestados"), a.get("criticidad", "media"))

def puertos_declarados(perfil, activo):
    return {e["puerto"] for e in de_activo(perfil, activo) if e["puerto"] is not None}

def criticidad_servicio(perfil, activo, servicio, hallazgos=None):
    """Criticidad del servicio atacado: por nombre (con alias web), luego por puerto vía hallazgos,
    y si nada empareja, la del activo (fallback). Nunca infiere; nunca lanza."""
    criticidad_base = _activo(perfil, activo).get("criticidad", "media")
    if not servicio or servicio == "desconocido":
        return criticidad_base
    entradas = de_activo(perfil, activo)
    prot = postura._protocolos(servicio)
    # 1) por nombre declarado (alias web en ambos sentidos)
    for e in entradas:
        if e["servicio"] and (postura._protocolos(e["servicio"]) & prot):
            return e["criticidad"]
    # 2) por puerto: el nombre atacado -> puertos abiertos del auditor -> entrada declarada
    nodos = (hallazgos or {}).get("nodos") or {}
    puertos = {s.get("puerto") for s in (nodos.get(activo) or [])
               if s.get("estado") == "open" and (postura._protocolos(s.get("servicio")) & prot)}
    for e in entradas:
        if e["puerto"] is not None and e["puerto"] in puertos:
            return e["criticidad"]
    return criticidad_base
```

- [ ] **Step 4: Ejecuta el test (GREEN)** — `python3 -m unittest prototipo.tests.test_servicios -v` → OK.

- [ ] **Step 5: Migra `impacto._declarados` e `inventario` a `servicios.puertos_declarados` (RED→GREEN)**

Test de no-regresión primero (en `test_impacto.py`):

```python
def test_declarados_igual_para_enteros_y_dicts(self):
    from prototipo import impacto
    p_int  = {"activos": {"web": {"criticidad": "alta", "servicios_prestados": [443, 80]}}}
    p_dict = {"activos": {"web": {"criticidad": "alta", "servicios_prestados": [{"puerto": 443}, {"puerto": 80, "criticidad": "media"}]}}}
    self.assertEqual(impacto._declarados(p_int, "web"), impacto._declarados(p_dict, "web"))
    self.assertEqual(impacto._declarados(p_dict, "web"), {443, 80})
```

Impl en `impacto.py` (añade import y reescribe `_declarados`):

```python
from prototipo import actores, servicios   # (añadir servicios)
...
def _declarados(perfil, activo):
    return servicios.puertos_declarados(perfil, activo)
```

En `inventario.py` (import `servicios`; línea 23):

```python
declarados = servicios.puertos_declarados(perfil, nombre)
```

Añade un test en `test_inventario.py`: `reconciliar` con `servicios_prestados` de dicts da el mismo
`declarados_no_abiertos`/`abiertos_no_declarados` que con enteros.

- [ ] **Step 6: `perfil.validar` avisa de dicts de servicio mal formados (RED→GREEN)**

Test en `test_perfil.py`:

```python
def test_validar_avisa_servicio_sin_puerto_y_criticidad_invalida(self):
    from prototipo import perfil as perfilm
    p = {"activos": {"web": {"criticidad": "alta",
         "servicios_prestados": [{"criticidad": "media"}, {"puerto": 80, "criticidad": "altisima"}]}}}
    avisos = perfilm.validar(p)
    self.assertTrue(any("sin puerto" in a for a in avisos))
    self.assertTrue(any("criticidad" in a and "altisima" in a for a in avisos))
```

Impl: dentro del bucle `for nombre, a in activos.items()` de `validar`, tras el chequeo de `ip`:

```python
_CRITICIDADES = ("baja", "media", "alta", "critica")
...
for sp in a.get("servicios_prestados") or []:
    if isinstance(sp, dict):
        if sp.get("puerto") is None:
            avisos.append(f"activo {nombre}: servicio sin puerto ({sp!r})")
        c = sp.get("criticidad")
        if c is not None and c not in _CRITICIDADES:
            avisos.append(f"activo {nombre}: criticidad de servicio no reconocida ({c!r})")
```

- [ ] **Step 7: Suite prototipo en verde** — `python3 -m unittest discover -s prototipo/tests` → OK.

- [ ] **Step 8: Commit**

```bash
git add prototipo/servicios.py prototipo/tests/test_servicios.py prototipo/impacto.py \
        prototipo/inventario.py prototipo/perfil.py prototipo/tests/test_impacto.py \
        prototipo/tests/test_inventario.py prototipo/tests/test_perfil.py
git commit -m "feat(servicios): esquema servicios_prestados enriquecido y criticidad por servicio

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Prioridad ponderada por el servicio atacado (`analisis.enriquecer`)

**Files:** Modify `prototipo/analisis.py` (23-24, import); Test `prototipo/tests/test_analisis.py`.
**Interfaces — Consumes:** `servicios.criticidad_servicio` (Tarea 1).

- [ ] **Step 1: Test (RED)** en `test_analisis.py`:

```python
def test_prioridad_pondera_por_servicio_atacado(self):
    from prototipo import analisis
    perfil = {"activos": {"web": {"criticidad": "baja",
        "servicios_prestados": [{"puerto": 443, "servicio": "https", "criticidad": "critica"},
                                {"puerto": 80,  "servicio": "http",  "criticidad": "baja"}]}}}
    hall = {"nodos": {"web": [{"puerto": 443, "servicio": "https", "estado": "open"},
                              {"puerto": 80,  "servicio": "http",  "estado": "open"}]}}
    base = {"familia": "acceso_credenciales", "activo": "web", "origen_ip": "203.0.113.9"}
    alta = analisis.clasificar({**base, "servicio": "https"}, analisis.enriquecer({**base, "servicio": "https"}, hall, perfil))
    baja = analisis.clasificar({**base, "servicio": "http"},  analisis.enriquecer({**base, "servicio": "http"},  hall, perfil))
    self.assertGreater(alta["prioridad"], baja["prioridad"])

def test_sin_criticidad_por_servicio_prioridad_identica(self):
    # perfil con servicios como enteros: criticidad = la del activo, como hoy
    from prototipo import analisis
    perfil = {"activos": {"web": {"criticidad": "media", "servicios_prestados": [443]}}}
    hall = {"nodos": {}}
    a = {"familia": "acceso_credenciales", "activo": "web", "servicio": "https", "origen_ip": "203.0.113.9"}
    self.assertEqual(analisis.enriquecer(a, hall, perfil)["criticidad"], "media")
```

- [ ] **Step 2: Ejecuta (RED)** — AttributeError o prioridad igual.

- [ ] **Step 3: Impl (GREEN)** en `analisis.py`:

```python
from prototipo import actores, familias, servicios   # (añadir servicios)
...
def enriquecer(alerta, hallazgos, perfil):
    activo = alerta.get("activo")
    postura = postura_de(hallazgos, activo, alerta.get("servicio"))
    criticidad = servicios.criticidad_servicio(perfil, activo, alerta.get("servicio"), hallazgos)
    ...
```

- [ ] **Step 4: Ejecuta (GREEN)** — OK.

- [ ] **Step 5: Red de seguridad canónica** —
  `python3 -m unittest discover -s evaluacion/tests` → OK **sin tocar números**. (Los perfiles de
  evaluación usan enteros → criticidad heredada → prioridad idéntica.) Si algo se mueve, PARA y revisa.

- [ ] **Step 6: Suite prototipo** — `python3 -m unittest discover -s prototipo/tests` → OK.

- [ ] **Step 7: Commit** `feat(analisis): la prioridad pondera por la criticidad del servicio atacado`.

---

## Task 3: Registro de correspondencia (`correspondencia.yml` + `correspondencia.py`)

**Files:** Create `prototipo/correspondencia.yml`, `prototipo/correspondencia.py`,
`prototipo/tests/test_correspondencia.py`.
**Interfaces — Produces:** `correspondencia.cargar(ruta=...)`, `correspondencia.registro()`,
`correspondencia.recomendar(familia, servicio, clase, registro) -> dict|None`.

- [ ] **Step 1: Test (RED)** `test_correspondencia.py`:

```python
import unittest
from prototipo import correspondencia

REG = correspondencia.cargar()

class TestCorrespondencia(unittest.TestCase):
    def test_familia_contener_origen(self):
        r = correspondencia.recomendar("acceso_credenciales", "ssh", "vp_intento_acceso", REG)
        self.assertEqual(r["respuesta"], "contener_origen")
        self.assertEqual(r["accion_sugerida"], "BLOQUEAR_IP")

    def test_servicio_afina_la_familia(self):
        r = correspondencia.recomendar("acceso_credenciales", "rdp", "vp_intento_acceso", REG)
        self.assertEqual(r["respuesta"], "endurecer_servicio")
        self.assertEqual(r["accion_sugerida"], "CERRAR_SERVICIO")

    def test_enrutar_lleva_ruta(self):
        r = correspondencia.recomendar("explotacion_conocida", "http", "amenaza_enrutada", REG)
        self.assertEqual(r["respuesta"], "enrutar")
        self.assertEqual(r["ruta"], "appsec")

    def test_sin_recomendacion_en_fp_y_no_soportada(self):
        self.assertIsNone(correspondencia.recomendar("acceso_credenciales", "ssh", "fp_actividad_legitima", REG))
        self.assertIsNone(correspondencia.recomendar("desconocida", "ssh", "no_soportada", REG))

    def test_sin_servicio_usa_solo_familia(self):
        r = correspondencia.recomendar("servicio_expuesto", None, "vp_intento_acceso", REG)
        self.assertEqual(r["respuesta"], "endurecer_servicio")
```

- [ ] **Step 2: Ejecuta (RED)** — ModuleNotFoundError.

- [ ] **Step 3: Crea `correspondencia.yml` (GREEN)**

```yaml
# Correspondencia amenaza->respuesta recomendada (asesora; NO cambia la accion automatica).
# respuesta en {contener_origen, endurecer_servicio, enrutar, observar}. Agnostico del SIEM (por
# familia/servicio). `por_servicio` afina y prevalece sobre `por_familia`.
por_familia:
  acceso_credenciales:  { respuesta: contener_origen }
  reconocimiento:       { respuesta: contener_origen, nota: "escaneo: bloquear o vigilar el origen" }
  servicio_expuesto:    { respuesta: endurecer_servicio, nota: "exposicion del servicio: cerrar/endurecer o quitar la exposicion" }
  explotacion_conocida: { respuesta: enrutar, ruta: appsec }
por_servicio:
  rdp:    { respuesta: endurecer_servicio, nota: "RDP expuesto: alto riesgo, cerrar o publicar tras VPN" }
  smb:    { respuesta: endurecer_servicio, nota: "SMB no deberia estar expuesto en el borde" }
  telnet: { respuesta: endurecer_servicio, nota: "telnet en claro: desactivar, migrar a SSH" }
  sql:    { respuesta: endurecer_servicio, nota: "base de datos: no deberia aceptar conexiones externas" }
  http:   { respuesta: enrutar, ruta: appsec, nota: "capa web: enrutar a appsec para revision/parcheo" }
```

- [ ] **Step 4: Crea `correspondencia.py` (GREEN)**

```python
"""Registro de correspondencia amenaza->respuesta recomendada (dato, RNF-03). Asesor: no cambia la
accion automatica ni el filtro del perfil; produce la recomendacion que ve el analista/agente."""
import os, yaml
from prototipo.analisis import CLASES_SIN_AMENAZA

RUTA = os.path.join(os.path.dirname(__file__), "correspondencia.yml")
_REGISTRO = None
_ACCION_POR_RESPUESTA = {"contener_origen": "BLOQUEAR_IP", "endurecer_servicio": "CERRAR_SERVICIO",
                         "enrutar": None, "observar": None}

def cargar(ruta=RUTA):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def registro():
    global _REGISTRO
    if _REGISTRO is None:
        _REGISTRO = cargar()
    return _REGISTRO

def recomendar(familia, servicio, clase, registro):
    if clase in CLASES_SIN_AMENAZA:
        return None
    base = dict((registro.get("por_familia") or {}).get(familia) or {})
    refin = (registro.get("por_servicio") or {}).get(servicio) if servicio else None
    if refin:
        base.update(refin)
    respuesta = base.get("respuesta")
    if not respuesta:
        return None
    return {"respuesta": respuesta,
            "accion_sugerida": base.get("accion_sugerida", _ACCION_POR_RESPUESTA.get(respuesta)),
            "ruta": base.get("ruta"), "servicio": servicio, "nota": base.get("nota", "")}
```

(Comprueba que `analisis` no importa `correspondencia` — no debe, para no ciclar.)

- [ ] **Step 5: Ejecuta (GREEN)** — OK.
- [ ] **Step 6: Suite prototipo** — OK.
- [ ] **Step 7: Commit** `feat(correspondencia): registro familia/servicio -> respuesta recomendada`.

---

## Task 4: Cablear `recomendacion` en la decisión (`triaje` + `traza`)

**Files:** Modify `prototipo/triaje.py` (procesar, 5-29), `prototipo/traza.py` (construir, 257-288);
Test `prototipo/tests/test_triaje.py`, `test_traza.py`.
**Interfaces — Consumes:** `correspondencia.recomendar`/`registro`.

- [ ] **Step 1: Test (RED)** en `test_triaje.py`: una alerta `acceso_credenciales` sobre `rdp`
  produce un registro con `recomendacion.respuesta == "endurecer_servicio"` y `accion_final`
  intacta (`BLOQUEAR_IP` o veto por perfil, según el perfil del test). En `test_traza.py`: añade
  `"recomendacion"` a la lista de claves esperadas del registro y comprueba que es `None` cuando
  `analisis_out` no lo trae (retrocompat de la cadena).

- [ ] **Step 2: Ejecuta (RED)**.

- [ ] **Step 3: Impl (GREEN)** en `triaje.py`:

```python
from prototipo import analisis, politica, perfil as perfilm, traza, catalogo as catm, correspondencia

def procesar(alerta, hallazgos, perfil_dict, perfil_nombre, catalogo, id_decision, timestamp,
             justificar_fn=analisis.justificar, registro_correspondencia=None):
    ctx = analisis.enriquecer(alerta, hallazgos, perfil_dict)
    clas = analisis.clasificar(alerta, ctx)
    ...
    reg_corr = registro_correspondencia if registro_correspondencia is not None else correspondencia.registro()
    recomendacion = correspondencia.recomendar(alerta.get("familia"), alerta.get("servicio"),
                                               clas["clase"], reg_corr)
    analisis_out = {**clas, "justificacion": just, ..., "justificacion_descartada": descartada,
                    "recomendacion": recomendacion}
    ...
```

En `traza.construir`, añade (junto a `"ruta"`):

```python
"recomendacion": analisis_out.get("recomendacion"),
```

- [ ] **Step 4: Ejecuta (GREEN)** — OK. El camino en vivo (`lazo.py:8 → triaje.procesar`) usa el
  `default` → `correspondencia.registro()` cachea (como `familias.registro()`); no toca `stream.py`.

- [ ] **Step 5: Suite prototipo** — OK.
- [ ] **Step 6: Commit** `feat(triaje): la decision lleva la recomendacion de respuesta (traza incluida)`.

---

## Task 5: Exponer la recomendación — tarjeta humana + agente + API

**Files:** Modify `prototipo/validacion.py` (mostrar, 26-47), `prototipo/agente_mitigacion.py`
(prompt de contexto), `prototipo/tablero.py` (`_resumen_traza`, 220-229); Test `test_validacion.py`,
`test_agente_mitigacion.py`, `test_tablero.py`.

- [ ] **Step 1: Test (RED)** `test_validacion.py`: `mostrar` de una decisión con
  `recomendacion={"respuesta":"endurecer_servicio","servicio":"telnet","nota":"telnet en claro…"}`
  incluye una línea que empieza por `"Recomendado:"` y menciona `telnet`; sin `recomendacion`, **no**
  aparece esa línea. `test_tablero.py`: `_resumen_traza` de un registro con `recomendacion` la expone.

- [ ] **Step 2: Ejecuta (RED)**.

- [ ] **Step 3: Impl `validacion.mostrar` (GREEN)** — añade antes del `return` y mete `recomendado`
  en la cadena (tras la línea de «Acción sugerida/Impacto/Filtro»):

```python
_RESPUESTA_LEGIBLE = {"contener_origen": "contener el origen (bloquear la IP atacante)",
                      "endurecer_servicio": "endurecer el servicio", "enrutar": "enrutar para revision/parcheo",
                      "observar": "observar/vigilar"}

def _recomendado(decision):
    rec = decision.get("recomendacion")
    if not rec:
        return ""
    txt = _RESPUESTA_LEGIBLE.get(rec.get("respuesta"), rec.get("respuesta"))
    if rec.get("respuesta") == "endurecer_servicio" and rec.get("servicio"):
        txt = f"endurecer el servicio {rec['servicio']}"
    if rec.get("ruta"):
        txt += f" → {rec['ruta']}"
    nota = f" — {rec['nota']}" if rec.get("nota") else ""
    return f"Recomendado: {txt}{nota}\n"
```

Inserta `f"{_recomendado(decision)}"` en el `return` de `mostrar`, justo tras la línea de «Acción
sugerida … Filtro». Así aparece en terminal y en la tarjeta web (el daemon captura las líneas de
`mostrar`).

- [ ] **Step 4: Impl contexto del agente (GREEN)** en `agente_mitigacion.py`: donde se arma el
  contexto del prompt del sistema (nodo: función/criticidad/servicios), añade, si la decisión trae
  `recomendacion`, una línea `f"Recomendacion del triaje: {respuesta} ({nota})"`. Test: el prompt
  contiene «Recomendacion del triaje» cuando se pasa una decisión con recomendación.

- [ ] **Step 5: Impl `tablero._resumen_traza` (GREEN)** — añade al dict devuelto:
  `"recomendacion": reg.get("recomendacion")`. (El detalle `/api/traza/<id>` ya devuelve el registro
  crudo, así que `recomendacion` viaja también ahí.)

- [ ] **Step 6: Suite prototipo** — OK.
- [ ] **Step 7: Commit** `feat(recomendacion): visible en la tarjeta humana, el agente y la API`.

---

## Task 6: Visor — recomendación en el detalle y distintivo en la fila

**Files:** Modify `visor/src/api.ts` (DecisionSchema 16-40, DetalleSchema 59-95),
`visor/src/components/Decisiones.tsx` (Detalles, FilaDecision); Test `visor/src/api.test.ts`.
**Interfaces — Consumes:** campo `recomendacion` de la API (Tarea 5).

- [ ] **Step 1: Test (RED)** en `api.test.ts`: `DecisionSchema`/`DetalleSchema` parsean un objeto con
  `recomendacion: {respuesta, accion_sugerida, ruta, servicio, nota}` y con `recomendacion: null`.

- [ ] **Step 2: Ejecuta (RED)** — `cd visor && npx vitest run src/api.test.ts`.

- [ ] **Step 3: Impl `api.ts` (GREEN)** — define el esquema una vez y añádelo a ambos:

```ts
export const RecomendacionSchema = z.object({
  respuesta: z.string().nullable().optional(), accion_sugerida: z.string().nullable().optional(),
  ruta: z.string().nullable().optional(), servicio: z.string().nullable().optional(),
  nota: z.string().nullable().optional(),
}).passthrough()
```
Añade `recomendacion: RecomendacionSchema.nullable().optional(),` a `DecisionSchema` y a `DetalleSchema`.

- [ ] **Step 4: Impl `Decisiones.tsx` (GREEN)** — (a) en `Detalles`, un `Campo` nuevo tras «Política
  del perfil» cuando `det.recomendacion`:

```tsx
{det.recomendacion?.respuesta && (
  <Campo etiqueta="Recomendación">
    <div className="text-sm">
      {det.recomendacion.respuesta === "endurecer_servicio" && det.recomendacion.servicio
        ? `Endurecer el servicio ${det.recomendacion.servicio}`
        : det.recomendacion.respuesta}
      {det.recomendacion.ruta ? ` → ${det.recomendacion.ruta}` : ""}
    </div>
    {det.recomendacion.nota && <div className="mt-0.5 text-xs text-muted-foreground">{det.recomendacion.nota}</div>}
  </Campo>
)}
```

(b) en `FilaDecision`, un distintivo compacto en la celda «Acción» cuando la recomendación diverge de
`contener_origen` (respuesta `endurecer_servicio`/`enrutar`), reutilizando `Pildora`:

```tsx
{d.recomendacion?.respuesta && d.recomendacion.respuesta !== "contener_origen" && (
  <> <Pildora tono="bg-sky-500/15 text-sky-700 dark:text-sky-300" title={d.recomendacion.nota ?? undefined}>
    rec: {d.recomendacion.respuesta === "endurecer_servicio" ? "endurecer servicio" : "enrutar"}
  </Pildora></>
)}
```

- [ ] **Step 5: Verde del visor** — `cd visor && npx vitest run && npx tsc -b && npm run lint && npm run build`.
- [ ] **Step 6: Commit** `feat(visor): recomendacion de respuesta en el detalle y distintivo en la fila`.

---

## Task 7: Cierre

- [ ] **Step 1: Las 5 suites + visor en verde**
  - `python3 -m unittest discover -s prototipo/tests`
  - `python3 -m unittest discover -s evaluacion/tests` (**canónicos intactos**)
  - `python3 -m unittest discover -s lab/banco/tests -t .`
  - `python3 -m unittest discover -s lab/dataset/tests -t .`
  - `cd visor && npx vitest run && npx tsc -b && npm run lint && npm run build`
- [ ] **Step 2: Revisión de toda la rama** con un revisor fresco (modelo más capaz). Arregla crítico/
  importante con TDD (RED→GREEN + suite verde por arreglo). Foco: los 5 puntos de Review Focus.
- [ ] **Step 3:** si todo verde, `superpowers:finishing-a-development-branch` (menú al usuario).

## Verificación de punta a punta (la hace el usuario con el banco levantado)

1. Añadir una criticidad por servicio a un activo del banco (p.ej. `core-db: servicios_prestados:
   [{puerto: 1521, servicio: sql, criticidad: critica}]`) y lanzar un ataque a ese servicio → la
   prioridad sube; la tarjeta/feed muestran «Recomendado: endurecer el servicio sql».
2. Un ataque de fuerza bruta externo normal → `recomendacion = contener_origen`, coincide con
   `BLOQUEAR_IP`, sin distintivo divergente en la fila.
3. Las cifras canónicas no se mueven.

## Self-review (hecha)

- **Cobertura del spec:** G1 (Tarea 1-2), G3 (Tarea 3), G2-suave (Tareas 4-6). ✔
- **Placeholders:** ninguno; todo paso lleva código real. El contenido de `correspondencia.yml` es
  definitivo (con sql/http añadidos por decisión del usuario). ✔
- **Consistencia de tipos:** `recomendacion` = mismo objeto en Python (triaje/traza), API
  (`_resumen_traza`) y Zod (`RecomendacionSchema`); claves idénticas. `servicios.puertos_declarados`
  consumido igual por `impacto` e `inventario`. ✔
- **Review Focus:** los 5 puntos tienen test en la tarea que posee el código. ✔
- **Invariancia de métricas:** protegida por *fallback* + campo aditivo; `test_canonicos` se corre en
  Tarea 2 y Tarea 7. ✔
