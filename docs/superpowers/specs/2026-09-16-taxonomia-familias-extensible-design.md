# Diseño: taxonomía de familias extensible (MITRE) con respuesta en tres niveles

**Fecha:** 2026-09-16 · **Estado:** diseño para revisión · **Deriva de:** revisión de familias (huecos y
deriva) y la decisión de mantener el sistema agnóstico de red y cliente.

## 1. Problema

La taxonomía de familias de ataque tiene tres defectos, verificados:

- **Deriva entre fuentes:** el caso de uso define 5 familias descriptivas, el código un `set` de 4 slugs
  (`FAMILIAS_ATAQUE`), y el dataset ejercita 3. No mapean 1:1.
- **Familia muerta:** `explotacion_conocida` está declarada (la asigna `adaptador_wazuh.familia_de` con los
  grupos `exploit`/`attack`) pero sin lógica de clasificación ni datos ni acción — cobertura falsa.
- **Sólo dos estados de respuesta:** hoy el motor **actúa** (contiene) o marca **`no_soportada`** (se lava las
  manos). Falta el punto medio, que es donde un MDR aporta más valor fuera del plano de gestión: **triar,
  priorizar, enriquecer y encaminar** una amenaza que no debe auto-contenerse (un ataque web no se auto-bloquea
  ni se descarta: se prioriza y se enruta a AppSec).

Cubrir "todas las familias que faltan" con reglas vacías repetiría el error de `explotacion_conocida` ×N. La
decisión tomada: un **framework extensible** en vez de amplitud a lo bruto.

## 2. Objetivo y no-objetivos

**Objetivo:** reemplazar el `set` hardcodeado por un **registro extensible alineado a MITRE ATT&CK**, y añadir
un **tercer nivel de respuesta** (`triar_y_enrutar`) entre `actuar` y `no_soportada`, sin romper el
agnosticismo de red/cliente.

**No-objetivos (de esta iteración):**

- No se implementan clasificadores VP/FP para familias nuevas (no hay datos; sería cobertura falsa).
- No se construye la integración de entrega real de la ruta (email/cola/ticket): la ruta se **registra en la
  traza** y el binding a un destino concreto es trabajo de producción.
- No se toca el catálogo de acciones (RF-15) ni la escalada.

## 3. Agnosticismo: dónde vive cada cosa

| Pieza | Agnóstica | Dónde vive |
|---|---|---|
| Registro de familias (familia→MITRE, nivel, rol de ruta) | **Sí** (vocabulario neutro + MITRE) | `prototipo/familias.yml` |
| Lógica de clasificación y niveles | **Sí** | `prototipo/analisis.py`, `politica.py` |
| Alerta cruda → `familia` | No (específico del SIEM) | `adaptador_wazuh.familia_de` (RNF-06); se cambia por SIEM |
| Rol de ruta lógico → equipo/cola real del cliente | No (específico del cliente) | perfil del cliente (`perfiles/*.yml`) |
| Qué familias llegan de verdad | No (lo fija el SIEM del cliente) | fuera del MDR |

El framework preserva la separación existente (motor agnóstico · adaptador para la fuente · perfil para el
cliente). La cobertura real por cliente = *registro ∩ lo que su SIEM detecta*; `no_soportada` es la frontera
honesta para lo no mapeado.

## 4. Diseño

### 4.1 El registro `prototipo/familias.yml`

Mismo patrón que `catalogo.yml` (YAML cargado una vez). Cada familia declara su mapeo MITRE, su nivel de
respuesta y —si es enrutable— el rol lógico de destino:

```yaml
acceso_credenciales:  { mitre: [T1110, T1078], nivel: actuar }
reconocimiento:       { mitre: [T1595, T1046], nivel: actuar }
servicio_expuesto:    { mitre: [T1190],        nivel: actuar }
aplicacion_web:       { mitre: [T1190, T1059], nivel: triar_y_enrutar, ruta: appsec }
# familia ausente del registro  -> no_soportada (frontera honesta)
# 'plataforma'/'otra' (ruido)   -> no se listan -> no_soportada, como hoy
```

Añadir una familia = añadir una línea. `explotacion_conocida` se **elimina** del adaptador y del registro
hasta que tenga datos/detección (o se mapea a `servicio_expuesto`/`aplicacion_web` según su semántica real —
decisión de migración, ver §4.6).

### 4.2 Los tres niveles de respuesta

| `nivel` | `clasificar` | `politica.proponer` | Traza |
|---|---|---|---|
| `actuar` | VP/FP por postura/origen/ráfaga (lógica actual) | acción del catálogo | igual que hoy |
| `triar_y_enrutar` | clase `amenaza_enrutada`, prioridad por criticidad+familia | **sin acción**, fija `ruta` | `familia`, `mitre`, `ruta`, prioridad |
| (ausente del registro) | `no_soportada` | sin acción | como hoy |

### 4.3 `analisis.clasificar` consulta el registro

Sustituye `if alerta.get("familia") not in FAMILIAS_ATAQUE: no_soportada` por una consulta al registro:

```python
entrada = familias.registro().get(alerta.get("familia"))
if entrada is None:
    return no_soportada
if entrada["nivel"] == "triar_y_enrutar":
    return {"clase": "amenaza_enrutada", "prioridad": _priorizar(...), "confianza": 1.0,
            "ruta": entrada.get("ruta")}
# nivel "actuar": la lógica VP/FP actual, intacta
```

El registro se carga en un módulo `prototipo/familias.py` (con `registro()` cacheado e inyectable para
tests), igual que `catalogo`/`perfil`.

### 4.4 La clase `amenaza_enrutada`

Una única clase genérica para lo enrutado (no un `vp_*` por familia): lleva `familia` + `mitre` + `prioridad`
+ `ruta`. Se añade a `_PRIORIDAD_BASE` (p. ej. 3, alta) y **no** a `CLASES_SIN_AMENAZA` (es una amenaza, no un
descarte). El justificador/RAG la enriquece con su ficha MITRE. La distinción VP/FP *dentro* del nivel
enrutado queda como trabajo futuro (la decide el equipo receptor).

### 4.5 `politica.proponer` respeta el nivel

Para `amenaza_enrutada` devuelve `(None, {})` (sin contención) — la respuesta es la **ruta**, no una acción
sobre la red. `triaje.procesar` propaga `ruta` a la traza; el daemon imprime `enrutado a <rol>`.

### 4.6 Binding de la ruta en el perfil (lo específico del cliente)

El registro usa el rol lógico (`appsec`). El perfil lo enlaza al destino real del cliente:

```yaml
# en perfiles/bancario.yml
rutas:
  appsec: "cola-appsec-banco"
  neteng: "noc-red"
  ir-edr: "csirt"
```

Sin binding, la traza registra el rol lógico (útil igual). El envío real es trabajo de producción (§2).

### 4.7 Migración y deriva

- `FAMILIAS_ATAQUE` (set) → `familias.yml` (registro). Las 3 familias reales pasan a `nivel: actuar`.
- `explotacion_conocida`: se retira de `familia_de` y no entra al registro (sin datos). Alternativa a decidir:
  mapear los grupos `exploit`/`attack` de Wazuh a `aplicacion_web`/`servicio_expuesto` según su grupo real.
- **Caso de uso (§3):** se actualiza para incluir `reconocimiento` y para describir los tres niveles y el
  registro. Se marca explícitamente qué categorías quedan **fuera de alcance conocido** (malware/C2, lateral,
  red, DoS, pagos) para que `no_soportada` sea decisión, no olvido.

## 5. Alcance de esta iteración

Framework + migrar las 3 familias actuales a `actuar` + **una** familia ejemplar `triar_y_enrutar`
(**`aplicacion_web`** → AppSec) probada de extremo a extremo (clasifica → sin acción → ruta en la traza →
el daemon la imprime). Las demás familias del registro se añaden **cuando haya datos/detección**.

## 6. Testing (TDD, `unittest`)

- `familias`: el registro carga; `registro().get(x)` devuelve nivel/mitre/ruta; familia ausente → None.
- `analisis.clasificar`: familia `actuar` → lógica VP/FP intacta (no-regresión); familia `triar_y_enrutar` →
  `amenaza_enrutada` con `ruta`; familia ausente → `no_soportada`.
- `politica.proponer`: `amenaza_enrutada` → sin acción; las clases `actuar` → acción como hoy.
- `traza`/`triaje`: la traza de una `amenaza_enrutada` lleva `ruta`/`mitre` y no lleva orden/ejecución.
- `perfil`: el binding `rutas` resuelve el rol lógico; sin binding, cae al rol.
- Regresión: las suites de `prototipo`, `dataset` y `evaluacion` verdes; el dataset (3 familias `actuar`)
  clasifica igual que hoy.

## 7. Riesgos y decisiones abiertas

- **`amenaza_enrutada` sin VP/FP:** al no filtrar FP en el nivel enrutado, un WAF ruidoso genera enrutados de
  más. Aceptable en esta iteración (el receptor filtra); el FP-en-enrutado es trabajo futuro.
- **`explotacion_conocida`:** ¿retirar o remapear? Recomendado retirar hasta tener datos.
- **Prioridad de `amenaza_enrutada`:** valor base a fijar (propuesto 3/alta), ajustable por criticidad.

## 8. Fuera de alcance

Clasificadores VP/FP de familias nuevas, integración de entrega de la ruta, acciones de capa-app/red/endpoint,
contención este-oeste, y cualquier familia sin datos ni detección.
