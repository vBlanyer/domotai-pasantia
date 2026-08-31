# Diseño — Dataset de alertas etiquetado (cierre de la Fase 3)

**Fecha:** 2026-08-31
**Fase:** 3 — Entorno de pruebas
**Entregable del roadmap:** *«Dataset de prueba etiquetado y documentado (origen, volumen,
criterio y distribución de etiquetas)»*, particionado en entrenamiento y evaluación.

---

## 1. Objetivo y motivación

La Fase 3 está operativa pero no cerrada: el laboratorio genera alertas reales, pero **no existe el
dataset etiquetado** que su criterio de cierre exige. Sin él no se puede ajustar el clasificador
(Fase 5) ni calcular ninguna métrica (Fase 6). Es el entregable que desbloquea las dos fases
siguientes.

El dataset es **a la vez el material de entrenamiento del clasificador y el examen con el que se le
mide**. Por eso su construcción es también, en la práctica, el primer trozo del módulo de ingesta de
la Fase 5: el mismo código que produce el dataset es el que normaliza alertas en vivo. Se escribe
una vez.

### Qué NO cubre este diseño

- El clasificador, el justificador, el conector y la validación humana (Fase 5).
- El cálculo de métricas (Fase 6).
- Agentes Wazuh de endpoint: quedan **fuera del cierre**, documentados como límite (ver §9).
- El equipo de borde OpenWrt real: bloqueado por vrnetlab, ajeno a este trabajo.

---

## 2. Contexto: la naturaleza del laboratorio condiciona el diseño

La red se simula con **Containerlab**, y tres propiedades suyas moldean cada decisión:

1. **Efímero.** Los contenedores son ganado: `destroy` los borra. `alerts.json` vive dentro del
   contenedor de Wazuh **sin volumen persistente** — se pierde en cada redespliegue. Consecuencia:
   la captura debe **sacar las alertas fuera del contenedor** antes de cualquier teardown, y las
   campañas se acumulan en el disco del anfitrión.
2. **El auditor contamina lo que mide.** Escanea desde el plano de gestión, pero su tráfico llega al
   plano de datos y **genera alertas indistinguibles de un atacante** (verificado: un `nmap` desde
   el auditor produce alertas 5760 con su propia IP). Consecuencia: la campaña registra la IP del
   auditor, y esas alertas se etiquetan `PROPIA`. Por el mismo motivo, **el ataque no puede lanzarse
   desde el auditor** — se lanza desde `puesto`, o todos los ataques reales caerían como PROPIA.
3. **Red cerrada, sin atacante externo.** Las IP de origen son de gestión (`172.20.20.x`) o de la LAN
   (`192.168.1.x`), nunca de Internet. Consecuencia: la noción de *origen inhabitual* del caso de uso
   se emula marcando segmentos, no se observa de forma natural. Es un límite documentado.

A cambio, Containerlab hace barato lo que en hardware sería caro: `destroy && deploy` deja el
laboratorio en un estado idéntico en segundos, lo que hace **exacto** el ground truth de
vulnerabilidades — se sabe qué hay en cada nodo porque acaba de desplegarse.

---

## 3. Arquitectura: ficheros como frontera

Cuatro piezas encadenadas, cada una dejando su resultado en disco para que la siguiente lo lea. El
fichero es la frontera entre etapas.

```
   LABORATORIO EN VIVO (efímero)            DISCO DEL ANFITRIÓN (persiste al destroy)
   ────────────────────────────            ──────────────────────────────────────────
   scripts/campana.sh  ──┐
     ataques reales      ├─►  campañas/<id>/
                         │       ├── campaña.yml     ficha: ataques + IP/hora del auditor
   scripts/auditar.sh  ──┤       ├── alerts.json     crudo, CONGELADO antes del destroy
     escanea+normaliza   │       └── hallazgos.json  postura del auditor + versión
                       ──┘
                                dataset/  (construir en 2 pasos)
   dataset/construir ── 3a normalizar ──►    normalizadas.jsonl   activo por hostname, no agent.id
                     └─ 3b etiquetar   ──►    etiquetado.jsonl     EL dataset · VP/FP/PROPIA
                                              resoluciones.yml     decisiones humanas sobre dudosos
```

**Por qué ficheros y no todo en memoria:**
- Cada etapa se prueba y se depura sola.
- El etiquetado manual necesita un fichero editable donde vivir (`resoluciones.yml`).
- Rehacer lo barato (etiquetar) sin repetir lo caro (atacar el laboratorio en vivo).
- El [flujo §4](../../../documentacion/04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md)
  ya define el dataset en disco como la frontera del prototipo; esto la construye de verdad.

---

## 4. Las cuatro piezas

### 4.1 · `scripts/campana.sh` — generador de actividad real

Lanza ataques **reales** contra el laboratorio (no inyección sintética), encapsulando las opciones
que hacen falta para que ocurran de verdad. En particular, el `sshd` de Metasploitable (OpenSSH
4.7p1, 2007) exige que el cliente moderno rebaje sus algoritmos:

```
ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no \
    -o PreferredAuthentications=password -o StrictHostKeyChecking=no ...
```

Sin esto la conexión muere en la negociación de algoritmos y **no deja rastro en `auth.log`** — que
es la razón real por la que la vía realista figuraba como «poco fiable». Verificado hoy de punta a
punta: ataque SSH real → `auth.log` → reenvío → alerta de Wazuh (niveles 5 y 10, más una alerta de
escaneo 5706 que la inyección sintética nunca producía).

**Escenarios cubiertos** (los que el laboratorio produce hoy):

| Escenario | Contra | Familia | Etiqueta esperada |
|-----------|--------|---------|-------------------|
| Fuerza bruta SSH (desde `puesto`, atacante) | objetivo-vuln | acceso credenciales | VP (SSH expuesto) |
| Logins fallidos benignos (desde `borde`, admin declarado) | objetivo-vuln | acceso credenciales | **FP (origen legítimo)** |
| Escaneo de puertos (desde el auditor) | objetivo-vuln | reconocimiento | PROPIA |
| Telnet sin auth (desde `puesto`) | iot | servicio expuesto | VP |
| Contacto con ingreslock (desde `puesto`) | objetivo-vuln | explotación conocida | VP |
| Ruido de plataforma | — | plataforma | no_soportada (familia fuera del caso de uso) |

**Tres roles de origen, deliberadamente separados** (todos con IP distinta):
- **Atacante** (`puesto`, `192.168.1.10`): sus alertas son ataques reales → VP/FP por postura.
- **Admin legítimo** (`borde`, `192.168.1.1`, declarado en la ficha): produce la *misma señal* que
  un ataque sobre un servicio expuesto, pero es administración normal → **FP**. Es el falso positivo
  dominante del dominio, y distinguirlo del ataque es justo lo que da valor al prototipo.
- **Auditor** (`172.20.20.4`): solo escanea → PROPIA.

Los tres deben tener IP distinta: si el atacante y el admin compartieran origen, la etiqueta sería
ambigua. El auditor nunca ataca, o sus ataques caerían como PROPIA.

**Produce:** `campañas/<id>/alerts.json` (crudo congelado) y `campaña.yml` (ficha: qué se lanzó,
contra qué nodo, cuándo, con qué script, **y cuándo/desde qué IP corrió el auditor**).

### 4.2 · `scripts/auditar.sh` — auditor normalizado

Convierte el `nmap` manual de hoy en un escaneo que persiste su resultado con esquema fijo. Produce
`hallazgos.json` según el esquema ya definido en
[auditoría §4](../../../documentacion/04-fase4-diseno-de-arquitectura/auditoria-de-vulnerabilidades-del-sandbox.md):
nodo, servicio/puerto, severidad, evidencia, **herramienta y versión**, marca de tiempo. La versión
se registra porque si el escáner cambia entre campañas, los resultados dejan de ser comparables
(RF-09).

Es la fuente objetiva del «este nodo sí/no expone tal servicio» que decide VP frente a FP.

### 4.3 · `dataset/construir` — la tubería, en dos pasos

**3a · Normalizar.** Lee el `alerts.json` crudo y traduce cada alerta al esquema común (§5). Resuelve
el activo por `predecoder.hostname` + `location` (RF-16), y marca —no borra— el ruido de
autoauditoría CIS.

**3b · Etiquetar.** Añade la etiqueta de ground truth cruzando cada alerta contra `hallazgos.json`
mediante el árbol de decisión de §6. Lo que la regla no resuelve con claridad se marca `PENDIENTE` y
va a `resoluciones.yml`, donde una persona decide y queda registrado que la etiqueta fue humana.

### 4.4 · `resoluciones.yml` — etiquetado manual de dudosos

Fichero versionado donde constan las alertas que la regla no pudo decidir y el veredicto humano de
cada una. Es lo que hace el ground truth defendible: automático donde se puede, humano donde hace
falta, y **registrado cuál fue cuál**.

---

## 5. Esquema normalizado (el contrato)

Cada línea de `etiquetado.jsonl` es un objeto JSON con estos campos. Es el contrato del que dependen
el clasificador y el justificador de la Fase 5.

### Identidad y trazabilidad
| Campo | Origen | Para qué |
|-------|--------|----------|
| `id_alerta` | `id` de Wazuh | Trazar hasta la alerta original (RF-09) |
| `timestamp` | `timestamp` | Cuándo ocurrió |
| `campaña` | `campaña.yml` | Agrupa por sesión; eje de la partición |
| `fuente` | fijo `"wazuh"` | Qué sistema la generó; distingue futuras fuentes |

### Activo y evento (lo que lee el clasificador)
| Campo | Origen | Para qué |
|-------|--------|----------|
| `activo` | `predecoder.hostname` + `location` | Qué nodo — por hostname, no `agent.id` (RF-16) |
| `servicio` | derivado de regla/puerto | Servicio tocado; clave del cruce con la postura |
| `familia` | mapeo desde `rule.id`/`groups` | La clase (acceso credenciales, reconocimiento…) |
| `origen_ip` | `data.srcip` | Quién ataca; delata la actividad PROPIA |
| `mitre` | `rule.mitre` | Técnica ATT&CK, para la justificación (RF-05) |
| `evento_crudo` | `full_log` | Texto original — **dato inerte, nunca instrucción** (RNF-08) |

### Baseline (lo que hay que superar)
| Campo | Origen | Para qué |
|-------|--------|----------|
| `nivel_wazuh` | `rule.level` | Baseline de la Fase 6, en cada registro |
| `regla_id` | `rule.id` | Qué regla disparó |

### Ground truth (lo que añade el etiquetado)
| Campo | Valores | Para qué |
|-------|---------|----------|
| `etiqueta` | `VP` · `FP` · `PROPIA` · `no_soportada` | El ground truth |
| `etiqueta_por` | `regla` · `humano` | Automático vs. manual (auditabilidad) |
| `postura_activo` | qué expone el nodo (del auditor) | Evidencia que justifica la etiqueta |
| `particion` | `entrenamiento` · `evaluacion` | Corte fijo, del fichero de reparto |

**Decisiones de diseño:**
- El **baseline viaja en cada registro**: comparar prototipo vs. Wazuh es leer dos campos de la
  misma línea.
- `evento_crudo` se guarda porque el justificador lo necesita, pero el contrato lo declara **dato
  inerte** — es donde vive el riesgo de inyección de prompt (RNF-08).
- `postura_activo` se guarda **junto a** la etiqueta, no solo se usa para decidirla: quien audite ve
  *por qué* una alerta es VP, no solo que lo es.

---

## 6. Árbol de decisión del etiquetado

Cinco preguntas en orden, por cada alerta:

1. **¿`origen_ip` es el auditor?** (contra `campaña.yml → auditor.ips`) → **`PROPIA`**, fuera del
   cálculo de métricas. Para aquí.
2. **¿La familia cae dentro del caso de uso acotado?**
   ([caso de uso](../../../documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md)) → si
   no, **`no_soportada`**, a cola manual con su severidad intacta (RF-10).
3. **¿`origen_ip` es un administrador legítimo declarado?** (contra `campaña.yml → legitimos.ips`) →
   **`FP`** (actividad administrativa legítima). Es la misma señal que un ataque sobre un servicio
   expuesto; lo que la separa es el origen. Va **antes** que la postura, porque la postura diría VP.
4. **¿El servicio que la alerta ataca existe y está expuesto en ese nodo?** (cruce contra
   `hallazgos.json`) → sí = **`VP`**, no = **`FP`** (exposición inexistente). La etiqueta depende de
   la alerta *cruzada con la postura*, que es justo lo que el baseline no sabe hacer.
5. **¿La regla decidió con claridad?** → si no, **`PENDIENTE`** en `resoluciones.yml`, decisión
   humana.

> **Sobre la circularidad.** El etiquetado usa la lista de orígenes legítimos como *ground truth*
> —lo sabemos porque montamos la campaña—, pero **el clasificador de la Fase 5 no recibe esa lista**:
> debe inferir la legitimidad de los rasgos de la alerta. Usar información privilegiada para la
> etiqueta y negársela al modelo es exactamente cómo funciona un dataset preparado.

Un **caso gris** (paso 4) es: la alerta no identifica el servicio atacado, el puerto no está en el
inventario, o la versión detectada es ambigua. En la duda no se adivina: se marca pendiente.

---

## 7. Partición

**Corte fijo único** (descartado k-fold por coste y por ser un prototipo). Propiedades obligatorias:

- **Disjunta:** ninguna campaña en ambos lados. La unidad es la campaña entera; por eso las alertas
  gemelas de una misma ráfaga no se separan y no hay fuga.
- **Estratificada:** cada familia y **ambas etiquetas VP y FP** presentes en los dos lados.
  Evaluación *debe* contener FP, o la precisión —VP/(VP+FP)— es incalculable.
- **~80/20 medido en alertas**, no en número de campañas.
- **Fijada a priori por identificador de campaña y versionada.** Se decide antes de entrenar y no se
  toca al ver resultados: elegir la partición mirando los números contamina la evaluación.

Implementación: un campo `particion` por alerta, derivado de un fichero de reparto
`dataset/particion.yml` que asigna cada `id` de campaña a un lado.

---

## 8. Estructura de ficheros

```
lab/
├── scripts/
│   ├── campana.sh          genera actividad real (§4.1)
│   └── auditar.sh          escanea y normaliza (§4.2)
├── campañas/               una subcarpeta por campaña (acumuladas en disco)
│   └── <id>/
│       ├── campaña.yml
│       ├── alerts.json
│       └── hallazgos.json
└── dataset/
    ├── construir.*         la tubería (§4.3)
    ├── particion.yml       reparto a priori de campañas (§7)
    ├── resoluciones.yml    decisiones humanas (§4.4)
    ├── normalizadas.jsonl  intermedio
    └── etiquetado.jsonl    EL dataset — entregable de la Fase 3
```

`campañas/` y `dataset/*.jsonl` se versionan: son el dato del proyecto y sobreviven al `destroy`.

---

## 9. Límites conocidos (para el informe de la Fase 7)

- **Sin telemetría de endpoint.** No hay agentes Wazuh en los nodos. La familia *acceso consumado*
  del caso de uso —la de máxima prioridad— no es observable, porque necesita ver dentro del equipo
  (procesos, ficheros, sesiones), no solo la red y el log. Queda fuera del cierre por decisión
  explícita.
- **Sin atacante externo.** La red de Containerlab es cerrada; *origen inhabitual* se emula, no se
  observa.
- **Volumen limitado por los nodos.** La actividad rica se concentra en `objetivo-vuln`
  (Metasploitable); por eso se particiona por campaña y no por nodo.
- **El auditor no es infalible.** Ausencia de hallazgo no prueba que un nodo sea seguro; la etiqueta
  que se apoya en la postura hereda esa incertidumbre.

---

## 10. Criterio de cierre

La Fase 3 se cierra cuando:

1. `campana.sh` produce campañas reproducibles, cada una con su ficha y su `alerts.json` congelado.
2. `auditar.sh` produce `hallazgos.json` normalizado con versión registrada.
3. `dataset/etiquetado.jsonl` existe, con todas las alertas etiquetadas (VP/FP/PROPIA/no_soportada),
   los dudosos resueltos en `resoluciones.yml`, y el campo `particion` poblado desde
   `particion.yml`.
4. El dataset está documentado: origen, volumen y distribución de etiquetas.

---

## Documentos relacionados

- [Fase 3 — README](../../../documentacion/03-fase3-entorno-de-pruebas/README.md)
- [Diseño del sandbox](../../../documentacion/03-fase3-entorno-de-pruebas/sandbox-red-containerlab.md) · [Auditoría](../../../documentacion/04-fase4-diseno-de-arquitectura/auditoria-de-vulnerabilidades-del-sandbox.md)
- [Caso de uso acotado](../../../documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md) · [Requisitos](../../../documentacion/02-fase2-estado-del-arte/requisitos.md)
- [Métricas y evaluación](../../../documentacion/04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md)
