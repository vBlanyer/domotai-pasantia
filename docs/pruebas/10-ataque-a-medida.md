# 10 · Ataque a medida: qué resultado esperar

Referencia para validar el banco en vivo con la opción `a` de `sh lab/banco/banco.sh atacar` (ver
[RUNBOOK §C](../../RUNBOOK.md)). Eliges **equipo objetivo**, **servicio/tipo de ataque** y **origen**;
este cuadro dice qué **debería** decidir el MDR en cada combinación.

Las cifras salen de pasar la alerta de cada variante por el motor real (`triaje.procesar`) con
`prototipo/perfiles/bancario.yml` y los hallazgos del auditor del banco
(`lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json`). **Están verificadas sobre las 340
combinaciones que el menú puede producir** (10 objetivos × tipos aplicables × 10 orígenes), no sobre
una muestra; el script del final las regenera.

Recuerda que el MDR **no detecta la alerta** — eso lo hace el SIEM (Wazuh). El MDR **refina**: decide
si la alerta del SIEM es una amenaza real y qué contención aplica. Todo lo de abajo es «qué hace el
MDR con la alerta que ya levantó Wazuh».

## El resultado depende de tres cosas

1. **El tipo de ataque → la familia → la conducta:**
   | Tipo (menú) | Familia | Conducta base |
   |---|---|---|
   | Fuerza bruta SSH | `acceso_credenciales` | contener (bloquear la IP de origen) |
   | Reconocimiento (escaneo SSH) | `reconocimiento` | contener |
   | Telnet expuesto | `servicio_expuesto` | contener **solo si el servicio está expuesto** |
   | Explotación web: **SQLi, path traversal, Log4Shell, inyección de comandos** | `explotacion_conocida` | **enrutar** (triar y encaminar, sin contener) |

   > **Honesto sobre los cuatro ataques web:** a nivel del **motor** son **indistinguibles** — todos
   > llegan como `explotacion_conocida` sobre `http` y se **enrutan a appsec**; ni la clase ni el
   > veredicto cambian entre un SQLi y un Log4Shell. La diferencia es de **detección** (cada uno lo
   > levanta una regla de Wazuh distinta, con su técnica MITRE) y de **lo que recibe appsec**, no del
   > triaje. El realismo amplía lo que el SIEM caza y encamina, no el dictamen del MDR.

2. **El objetivo → la exposición.** El auditor dice qué puertos están abiertos en cada equipo. Hay
   **tres situaciones** según el objetivo:
   - **servicio expuesto** (p. ej. SSH en cualquier equipo, telnet solo en atm) → amenaza real;
   - **servicio NO expuesto** (p. ej. telnet en web-banking) → `fp_exposicion_inexistente`, no se actúa;
   - **objetivo que el auditor no escanea** → el **plano de gestión** (mdr-siem, auditor): sin postura,
     el motor no puede descartar exposición, así que lo trata como amenaza probable con **confianza
     0.5** y lo **retiene para un humano** (nunca automático).

3. **El origen → el actor.** Para las familias que se contienen:
   - **internet (externo):** bloqueo **automático**… salvo contra el plano de gestión (ver arriba);
   - **equipo interno** (taquilla, un servidor…): **retenida** → la decides tú; si apruebas, bloquea;
   - **gestión** (mdr-siem, auditor; orígenes legítimos del perfil): **actividad legítima** (FP), no se
     hace nada… salvo que llegue en **ráfaga** (≥ 9 en 60 s): entonces el MDR sospecha de suplantación
     o equipo de gestión comprometido, lo marca VP con confianza 0.6 y lo **retiene**, pero **nunca
     corta el plano de gestión** (RF-19).

> **Principio que explica toda la columna «¿Humano?»: el MDR automatiza solo donde no puede dañar al
> cliente.** Lo automático no es «lo que viene de internet», sino «lo que el MDR puede cortar sin
> riesgo para el banco». Bloquear una **IP externa** es de bajo riesgo (es un desconocido de fuera;
> tirarlo no tumba nada propio) → lo hace solo. Bloquear una **IP interna** es de alto riesgo (es una
> máquina del propio banco; un falso positivo corta operación real) → lo decide una persona. En cuanto
> la acción tocaría un activo interno, una joya de la corona o el plano de gestión, o el motor no puede
> confirmar la exposición (confianza 0.5), se **retiene** para un humano. En la práctica, lo automático
> es casi siempre un atacante externo contra un servidor normal del plano de datos.

## Exposición por equipo (del auditor)

| Equipo | Plano | SSH (22) | Telnet (23) | Web (80/443/8080/8443) | Otros abiertos |
|---|---|:--:|:--:|:--:|---|
| web-banking | datos | ✅ | ❌ | ✅ 80, 443 | — |
| api-movil | datos | ✅ | ❌ | ✅ 443 | — |
| atm | datos | ✅ | ✅ | ✅ 8080 | — |
| middleware | datos | ✅ | ❌ | ✅ 8443 | — |
| core-db | datos | ✅ | ❌ | ❌ | oracle 1521 |
| hsm | datos | ✅ | ❌ | ❌ | cslistener 9000 |
| swift-alliance | datos | ✅ | ❌ | ❌ | nimhub 48002 |
| taquilla | datos | ✅ | ❌ | ❌ | — |
| **mdr-siem** | **gestión** | **no escaneado** | | | consola SOC/MDR |
| **auditor** | **gestión** | **no escaneado** | | | auditor Nmap |

El menú ofrece las **explotaciones web** (SQLi, path traversal, Log4Shell, inyección de comandos) solo
donde hay puerto web: **web-banking, api-movil, atm, middleware**. El resto solo ofrece SSH /
reconocimiento / telnet.

> **Recomendación dirigida (nueva):** desde la correspondencia servicio↔vulnerabilidad, cada decisión
> lleva además una **recomendación asesora** —`contener_origen` / `endurecer_servicio` / `enrutar`— que
> ve el analista y el agente, **sin cambiar** la acción automática. Para las explotaciones web la
> recomendación es **enrutar → appsec**; para la fuerza bruta/recon, **contener el origen**.

## Cuadro de resultados (verificado con el motor)

### A · Fuerza bruta SSH y Reconocimiento (SSH está abierto en todo el plano de datos)

| Objetivo | Origen | Clase | Conf. | ¿Humano? | Resultado |
|---|---|---|:--:|:--:|---|
| cualquier equipo del **plano de datos** | internet | `vp_intento_acceso` | 1.0 | no | **Bloqueo automático** de la IP (incluso en joyas: corta al atacante, no aísla el equipo) |
| cualquier equipo del **plano de datos** | interno (taquilla, servidor…) | `vp_intento_acceso` | 1.0 | **sí** | Retenida; si apruebas, bloquea la IP interna |
| cualquier equipo del **plano de datos** | gestión (mdr-siem / auditor) | `fp_actividad_legitima` | 1.0 | no | **Nada**: origen legítimo |
| cualquiera | gestión + **ráfaga ≥ 9** | `vp_intento_acceso` | 0.6 | **sí** | Retenida; **nunca** corta la gestión |
| **mdr-siem / auditor** (plano de gestión) | internet o interno | `vp_intento_acceso` | **0.5** | **sí** | **Retenida** (no automático): el auditor no tiene postura del objetivo |

### B · Telnet

| Objetivo | Origen | Clase | Conf. | ¿Humano? | Resultado |
|---|---|---|:--:|:--:|---|
| **atm** (único con telnet expuesto) | internet | `vp_intento_acceso` | 1.0 | no | **Bloqueo automático** |
| **atm** | interno | `vp_intento_acceso` | 1.0 | **sí** | Retenida |
| **atm** | gestión | `fp_actividad_legitima` | 1.0 | no | Nada: origen legítimo |
| cualquier otro del **plano de datos** (telnet cerrado) | internet o interno | `fp_exposicion_inexistente` | 1.0 | no | **Nada**: telnet no está expuesto ahí |
| cualquier otro del plano de datos | gestión | `fp_actividad_legitima` | 1.0 | no | Nada: origen legítimo |
| **mdr-siem / auditor** | internet o interno | `vp_intento_acceso` | **0.5** | **sí** | **Retenida** (sin postura, no se puede descartar) |

### C · Explotación web (SQLi) — solo web-banking, api-movil, atm, middleware

| Objetivo | Origen | Clase | Conf. | ¿Humano? | Resultado |
|---|---|---|:--:|:--:|---|
| cualquiera de los cuatro | **cualquier origen** | `amenaza_enrutada` | 1.0 | no | **Se enruta**, no se contiene (la familia manda; ni la exposición ni el origen cambian esto) |

Notas de lectura:
- **«Bloqueo automático»** = el MDR aplica `BLOQUEAR_IP` (un `DROP` de la IP de origen) en el equipo
  objetivo sin preguntar. En el visor el equipo pasa a **contenido**.
- **«Retenida»** = aparece una tarjeta en Aprobaciones; el equipo objetivo queda en **ámbar** hasta
  que decidas. Si rechazas, no se toca nada. (Las retenidas con confianza 0.5/0.6 traen
  `final=BLOQUEAR_IP` a la espera de tu aprobación, pero **no** se aplican solas.)
- **`amenaza_enrutada`** = el MDR la reconoce como amenaza pero su política es encaminarla; en el visor
  **no** pinta «contenido».
- El **plano de gestión** nunca se corta: contra mdr-siem/auditor la contención queda siempre en manos
  de un humano, y un ataque *desde* ellos es actividad legítima.
- En la **vista Red**, un ataque desde internet marca el nodo `internet` como **«origen de ataques»**
  (↗, azul) y suma a su contador «originados»: la IP del atacante externo no es de ningún equipo
  inventariado, así que su origen se atribuye al nodo externo. Un equipo interno que ataca a otro
  queda igual («origen de ataques») en vez de «sin actividad».

## Ataques realistas INYECTADOS (fuera del alcance vivo del lab)

El laboratorio hospeda señuelos **HTTP/SSH/telnet**, no RDP/SMB/Oracle reales, así que estos ataques
no se pueden *lanzar* en vivo. Se incluyen como **casos inyectados** (`lab/banco/casos.py`, nivel
`decision`): cada uno trae su **postura propia** exponiendo el servicio atacado, para demostrar cómo
el MDR triaja la amenaza y **qué recomienda por servicio**. Son el equivalente a que el SIEM del
cliente entregue esa alerta. No tocan las 600 alertas de la evaluación (métricas canónicas intactas).

| Caso | Ataque | Familia / servicio | Clase | Recomendación | ¿Humano? |
|---|---|---|---|---|---|
| `RDP` | Fuerza bruta RDP (3389) en web-banking | `acceso_credenciales` / rdp | `vp_intento_acceso` | **endurecer el servicio** (RDP: cerrar o tras VPN) | automático el bloqueo de IP; la recomendación es asesora |
| `SMB` | SMB expuesto (445) en atm | `servicio_expuesto` / smb | `vp_intento_acceso` | **endurecer el servicio** (SMB no debería estar en el borde) | — |
| `DBDIR` | Acceso directo a la BD (1521) en core-db | `acceso_credenciales` / sql | `vp_intento_acceso` | **endurecer el servicio** (BD no debería aceptar conexiones externas) | — |
| `FPNEX` | RDP contra core-db (sin RDP abierto) | `servicio_expuesto` / rdp | `fp_exposicion_inexistente` | **ninguna** (no es amenaza) | no |

La recomendación **no cambia** la acción que ejecuta el MDR (sigue siendo bloquear la IP de origen, o
retención a humano según el perfil): es la respuesta dirigida que el analista debería valorar. El
último caso muestra la **frontera honesta**: un ataque a un servicio que el auditor no ve expuesto se
descarta como falso positivo, sin recomendación.

Reproducirlos (sin lab, segundos):

```bash
python3 -m lab.banco.pruebas --caso RDP      # o SMB, DBDIR, FPNEX
```

## Cómo reproducir todo el cuadro

```bash
python3 - <<'PY'
import json
from prototipo import triaje, perfil as pf, catalogo as catm
from lab.banco import red, casos
perfil = pf.cargar('prototipo/perfiles/bancario.yml')
cat = catm.cargar_catalogo('prototipo/catalogo.yml')
hall = json.load(open('lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json'))
TIPOS = {
 "fuerza_bruta": dict(familia="acceso_credenciales", servicio="ssh",    regla_id="5763", nivel_wazuh=10),
 "recon":        dict(familia="reconocimiento",      servicio="ssh",    regla_id="5706", nivel_wazuh=5),
 "telnet":       dict(familia="servicio_expuesto",   servicio="telnet", regla_id="5706", nivel_wazuh=6),
 "exploit_web":  dict(familia="explotacion_conocida",servicio="http",   regla_id="5710", nivel_wazuh=7),
}
def run(tipo, activo, oip, raf=1):
    a = {**TIPOS[tipo], "activo":activo, "origen_ip":oip, "timestamp":"t", "rafaga_60s":raf}
    t = triaje.procesar(a, hall, perfil, "bancario", cat, "x", "t")
    return t["clase"], t["confianza"], t["resultado_filtro"], t["accion_final"], t["requiere_humano"]
objetivos = sorted(red.NODOS)
origenes = [("internet","198.51.100.10")] + [(n, red.NODOS[n]["ip"]) for n in objetivos]
for obj in objetivos:
    tipos = [t["clave"] for t in casos.tipos_para(red.SERVICIOS.get(obj, {}).get("puertos", []))]
    for tipo in tipos:
        for onodo, oip in origenes:
            if onodo == obj: continue
            print(f"{tipo:13}{obj:15}{onodo:16}{run(tipo, obj, oip)}")
PY
```

El umbral de ráfaga del perfil es **9** alertas en 60 s (`bancario.yml`, clave `rafaga.umbral`).
