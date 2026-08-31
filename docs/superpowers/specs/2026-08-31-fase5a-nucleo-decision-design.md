# Diseño — Fase 5A: el núcleo de decisión del motor de triaje

**Fecha:** 2026-08-31
**Fase:** 5 — Implementación del prototipo (subproyecto A de tres)
**Requisitos que ejercita:** RF-03 (clasificar), RF-04 (prioridad), RF-05/RNF-02 (justificación),
RF-06 (confianza), RF-07 (escalado), RF-09 (traza), RF-10 (no soportada), RF-15/RF-17 (acción por
catálogo con impacto), RNF-03 (reproducibilidad), RNF-14 (perfiles configurables).

---

## 1. Objetivo y encuadre

La Fase 5 se descompone en tres subproyectos:

- **5A (este)** — el núcleo de decisión, offline, sin dependencias pesadas ni SSH.
- **5B** — el lazo en vivo: conector SSH, validación humana TUI, verificación por el auditor.
- **5C** — el ML real (encoder con fine-tuning + justificador de 3B) detrás de la interfaz.

5A construye el lazo de decisión completo **hasta antes de ejecutar**: ingesta → análisis →
política → perfil → traza. No ejecuta acciones (eso es 5B) ni usa modelos (eso es 5C).

**Por qué 5A primero.** El dataset actual es pequeño y de una sola familia de ataque (10 VP / 8 FP /
187 no_soportada en entrenamiento; familias `acceso_credenciales` y `plataforma`), y la máquina no
tiene `torch`/`transformers` ni runtime de LLM, ni `pip`/`venv`. El clasificador real (5C) está
bloqueado por esas dos compuertas. Pero la [interfaz de análisis](../../../documentacion/04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md#5-interfaz-común-lo-que-hace-real-la-escalabilidad)
del diseño permite construir el lazo con un **baseline determinista** detrás y enchufar el ML
después sin tocar el motor.

### Qué NO cubre 5A

- Ejecución de acciones sobre nodos (conector SSH) — es 5B.
- La TUI de validación humana — es 5B; 5A solo marca `requiere_humano` y retiene.
- El encoder con fine-tuning y el justificador de 3B — es 5C.
- Verificación por reescaneo del auditor — es 5B.

---

## 2. Arquitectura

Paquete nuevo `prototipo/`. Reutiliza la ingesta ya construida (`esquema.normalizar_alerta` de
`lab/dataset/` — es el Paso 11, compartido entre el dataset y el motor en vivo).

```
alerta normalizada ──► enriquecer con postura (hallazgos.json)
                         ▼
              clasificar()  [interfaz — baseline]  ──► clase · prioridad · confianza
                         ▼
              justificar()  [interfaz — plantilla] ──► texto que cita campos (RNF-02)
                         ▼
              política de decisión  ──► acción candidata
                         ▼
              perfil de cliente / filtro  ──► permite · degrada · veta
                         ▼
              decisión de triaje ──► traza (RF-09)     [SIN ejecutar: eso es 5B]
```

| Módulo | Responsabilidad |
|--------|-----------------|
| `prototipo/analisis.py` | Interfaz `clasificar`/`justificar` + implementación baseline |
| `prototipo/catalogo.py` | El catálogo de acciones como dato (impacto, reversión, precondición, comando) |
| `prototipo/politica.py` | La regla clase × postura × criticidad → acción candidata |
| `prototipo/perfil.py` | Carga el perfil YAML y aplica el filtro permite/degrada/veta |
| `prototipo/traza.py` | Registra la decisión completa (RF-09) |
| `prototipo/triaje.py` | Orquesta el lazo y expone el CLI |

Datos versionados: `prototipo/catalogo.yml`, `prototipo/perfiles/residencial.yml`,
`prototipo/perfiles/empresarial.yml`.

**Dependencia cruzada deliberada:** `prototipo/` importa `lab.dataset.esquema`. La ingesta es
genuinamente compartida; mover `esquema.py` a un sitio común sería más limpio pero innecesario para
un prototipo.

**Sin dependencias externas:** solo stdlib de Python 3.14 + `pyyaml` (ya instalado). Tests con
`unittest`.

---

## 3. El clasificador baseline

`clasificar(alerta, contexto) -> (clase, prioridad, confianza)`. Mapea la alerta enriquecida a una
clase del [caso de uso §6](../../../documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md#6-categorías-de-clasificación),
usando solo lo que un clasificador **podría inferir** —familia, postura, nivel de Wazuh— y **no**
información privilegiada (la lista de orígenes legítimos es ground truth).

| Condición | Clase | Confianza |
|-----------|-------|-----------|
| familia `plataforma` / `otra` | **no_soportada** | 1.0 |
| familia de ataque + servicio **expuesto** (postura) | **vp_intento_acceso** | 1.0 |
| familia de ataque + servicio **no expuesto** | **fp_exposicion_inexistente** | 1.0 |
| familia de ataque + postura **desconocida** (gris) | **vp_intento_acceso** (baja) | 0.5 |

- **Prioridad**: se deriva de clase × criticidad del activo (del perfil V4) a un ordinal 1–4.
- **Confianza**: determinista; baja (0.5) cuando la postura es gris, y esa confianza baja activa el
  escalado a humano (RF-07). El baseline «sabe que no sabe».

**Límite documentado, no defecto.** El baseline **no puede** producir tres de las seis clases —
`vp_acceso_consumado`, `vp_exposicion_gestion`, `fp_actividad_legitima`— porque exigen contexto que
una regla no tiene. Eso es exactamente lo que motiva el ML de 5C, y la Fase 6 lo medirá. El valor de
5A está en demostrar que el lazo funciona, no en la calidad de la clasificación.

`justificar(alerta, contexto, clase) -> texto`. Plantilla que cita campos concretos (RNF-02):

> «Alerta {regla_id} ({descripción}, técnica {mitre}) desde {origen_ip} contra {activo}
> ({servicio}). El auditor {confirma/no confirma} que {servicio} está expuesto en {activo}.
> Clasificada como {clase} con confianza {confianza}.»

Cada afirmación apunta a un campo que existe; se marca como plantilla, no prosa de modelo.

---

## 4. Catálogo como dato

`catalogo.yml` — cada acción con lo que política y perfil leen, y la plantilla de comando para 5B:

```yaml
BLOQUEAR_IP:
  categoria: contencion
  impacto: localizado
  reversion: definida
  comando: "iptables -A INPUT -s {ip} -j DROP"
  reversion_cmd: "iptables -D INPUT -s {ip} -j DROP"
  verificacion: "iptables -L -n | grep {ip}"
  no_cortar_gestion: false
```

Las catorce acciones del [catálogo](../../../documentacion/04-fase4-diseno-de-arquitectura/catalogo-de-acciones.md),
con su impacto (RF-17) tal como quedó en la revisión de la Fase 4. El documento markdown sigue siendo
la narrativa; `catalogo.yml` es la fuente para máquinas.

---

## 5. La política de decisión

`proponer(clase, postura, criticidad) -> (accion_id, parametros) | None`. Implementa la tabla de
[política §3](../../../documentacion/04-fase4-diseno-de-arquitectura/politica-decision-continuidad.md#3-la-política-de-decisión):

| Clase | Acción candidata |
|-------|------------------|
| vp_acceso_consumado | MATAR_CONEXION + BLOQUEAR_IP (5A propone la primera; el encadenado es 5B) |
| vp_intento_acceso | BLOQUEAR_IP del origen |
| vp_exposicion_gestion | CERRAR_SERVICIO o BLOQUEAR_PUERTO |
| fp_actividad_legitima | OBS_* o ninguna |
| fp_exposicion_inexistente | ninguna |
| no_soportada | ninguna (cola manual) |

Principio de mínimo impacto: nunca propone REINICIAR_NODO ni RESTAURAR_CONFIG (solo por escalado).

---

## 6. El perfil de cliente y el filtro

`perfil.cargar(ruta) -> Perfil` y `perfil.filtrar(accion, impacto, activo, criticidad, confianza)
-> Resultado`. Estructura del perfil ([política §4](../../../documentacion/04-fase4-diseno-de-arquitectura/politica-decision-continuidad.md#4-el-perfil-de-cliente)):

```yaml
activos:
  servidor-web: { criticidad: alta, servicios_prestados: [443, 80] }
continuidad:
  impacto_ninguno:          automatica
  impacto_localizado:       automatica_si_confianza
  impacto_alcanza_servicio: humano_siempre
  reversibilidad_obligatoria: true
  no_cortar_gestion: true
excepciones:
  - { servicio: 443, activo: servidor-web, regla: nunca_automatica }
```

El filtro devuelve una de tres salidas (RNF-09, nunca descarta en silencio):

- **permite** — la acción sigue tal cual.
- **degrada** — la sustituye por una de menor impacto (BLOQUEAR_PUERTO → BLOQUEAR_IP).
- **veta** — la retiene, `requiere_humano = true`.

Precondiciones duras antes de evaluar impacto: `reversibilidad_obligatoria` (RF-18) descarta acciones
sin reversión definida; `no_cortar_gestion` (RF-19) rechaza las que dejarían el activo sin gestión.

### Demostración de RNF-14

La divergencia de perfiles se demuestra **a nivel de filtro**, no por CLI: `test_rnf14.py` llama
`perfil.filtrar(...)` directamente con `BLOQUEAR_PUERTO` (impacto `alcanza_servicio`) sobre
`servidor-web:443` y muestra que `residencial` permite mientras `empresarial` degrada a
`BLOQUEAR_IP` por su excepción `nunca_automatica`. Por CLI, sobre el dataset real, `residencial.yml`
y `empresarial.yml` producen las **mismas** decisiones: el baseline solo emite
`vp_intento_acceso`/`fp_exposicion_inexistente`/`no_soportada`, y `vp_intento_acceso` propone
`BLOQUEAR_IP` (impacto `localizado`), un impacto que ningún perfil degrada. El baseline no puede
producir `vp_exposicion_gestion` —la clase que propondría una acción `alcanza_servicio`— porque
exige contexto que una regla no tiene; por eso no hay hoy un escenario e2e por CLI que ejerza la
divergencia. Esa divergencia e2e llega con **5C**, cuando el clasificador real sí produzca las
clases ricas. No es un defecto del filtro (que es correcto): es el límite documentado del baseline.

---

## 7. El registro de decisión (traza)

Una línea JSONL por alerta, `prototipo/trazas/<perfil>.jsonl`:

```
id_decision, timestamp, id_alerta,
activo, clase, prioridad, confianza, justificacion,
accion_propuesta, impacto,
perfil_aplicado, resultado_filtro (permite|degrada|veta), accion_final,
requiere_humano,
version_baseline, version_perfil
```

Registra qué propuso la política, qué hizo el perfil y con qué se quedó — la auditabilidad del
diseño. Lo consumen 5B (la validación humana muestra la justificación) y la Fase 6 (las métricas de
continuidad leen `impacto` y `resultado_filtro`). Los timestamps se pasan como parámetro (Python 3.14
en este entorno no permite `Date.now()` en algunos contextos; el CLI los inyecta).

---

## 8. Artefactos que produce 5A

- `prototipo/` con los seis módulos y `catalogo.yml`, `perfiles/residencial.yml`, `perfiles/empresarial.yml`.
- Tests `unittest` por módulo.
- El CLI `python3 -m prototipo.triaje <dataset.jsonl> <perfil.yml> <salida.jsonl>` que corre el lazo
  de decisión sobre un dataset y escribe las trazas.
- `test_rnf14.py`, que ejercita la divergencia de perfiles a nivel de filtro (ver §6).

---

## 9. Criterio de cierre de 5A

- El CLI procesa el `etiquetado.jsonl` con un perfil y produce trazas de decisión completas.
- La divergencia de perfiles (RNF-14) queda demostrada **a nivel de filtro**, en `test_rnf14.py`
  (`perfil.filtrar` con `BLOQUEAR_PUERTO`), no por CLI: el baseline no produce ninguna clase que
  proponga una acción `alcanza_servicio`, así que correr el CLI con `residencial.yml` y con
  `empresarial.yml` sobre el dataset real da las mismas decisiones. La divergencia e2e por CLI queda
  para 5C, cuando el clasificador real produzca las clases ricas.
- Cada traza registra clase, confianza, justificación anclada, acción propuesta, resultado del filtro
  y acción final.
- Batería `unittest` verde.

---

## Documentos relacionados

- [Política de decisión y perfil de cliente](../../../documentacion/04-fase4-diseno-de-arquitectura/politica-decision-continuidad.md) — la lógica de política y perfil que 5A implementa.
- [Catálogo de acciones](../../../documentacion/04-fase4-diseno-de-arquitectura/catalogo-de-acciones.md) · [Selección del modelo §5](../../../documentacion/04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) — la interfaz de análisis.
- [Caso de uso §6](../../../documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md) — las clases.
- [README de la Fase 5](../../../documentacion/05-fase5-implementacion-del-prototipo/README.md).
