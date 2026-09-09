# 04 · Escenarios de ataque (pruebas manuales por comportamiento)

Catálogo para practicar a mano, **organizado por lo que hace el sistema** ante cada tipo de alerta. Es
**híbrido**: en vivo donde el laboratorio lo permite, e **inyección** de alertas crudas al daemon para los
comportamientos que conviene disparar con precisión.

**Cómo inyectar una alerta** (sin lab ni modelo; el daemon usa el justificador de plantilla y un ejecutor
simulado):

```
Sinopsis:  printf '%s\n' '<alerta cruda Wazuh JSON>' | python3 -m prototipo.stream - <perfil.yml> --sin-lab --ventana-agrupacion 0
```

La alerta cruda lleva solo campos que el adaptador Wazuh mapea: `rule.id`, `rule.groups` (→ servicio y
familia), `rule.mitre.id`, `predecoder.hostname` (→ activo), `data.srcip` (→ origen).

## Matriz

| Comportamiento | Familia / técnica (ejemplo) | Disparo | Qué observar en la traza |
|---|---|---|---|
| **A. Auto-bloqueo** | credenciales · T1110.001 | vivo (fuerza bruta SSH) o inyección | `permite`, `requiere_humano=false`, `Ejecutadas: 1` |
| **B. Confirmación humana** | credenciales, activo sin postura | inyección | conf 0.5, `veta`, abre `[aprobar/rechazar/reclasificar]` |
| **C. Escalada a firewall** | cualquiera, víctima inalcanzable | agente (`demo-agente-escalado.py`) | `BLOQUEAR_IP_FIREWALL`, `escalado: True` |
| **D. Falso positivo** | admin declarado (origen legítimo) | **vivo** (ataque desde .1) o inyección | `fp_actividad_legitima`, sin acción |
| **E. `no_soportada`** | fuera de perímetro | inyección | `no_soportada`, sin acción |

**En vivo vs inyección (qué reproduce este lab):**

- **A, C, D → en vivo.** A = fuerza bruta SSH a la víctima; C = el agente (host caído → firewall);
  D = fuerza bruta **desde el borde** (.1, origen legítimo). Todos verificados contra el laboratorio.
- **B, E → solo por inyección**, y no por capricho sino porque **este lab no los produce a demanda**:
  - **B** (confianza 0.5) exige un activo **sin postura**; pero los 4 nodos del lab (`objetivo-vuln`,
    `puesto`, `iot`, `borde`) están **todos** en los hallazgos del auditor, así que un ataque real siempre
    cae sobre un activo "conocido" → confianza 1.0. No hay dónde disparar B en vivo aquí.
  - **E** exige una alerta de **familia fuera de las 4**; Wazuh no dispara una a demanda en este lab (el
    telnet al IoT no genera alerta; rootcheck/syscheck corren en su propio ciclo).
  - La inyección es la vía **controlada** para verlos — es la fuente equivalente a que el SIEM del cliente
    los entregue.

> **Nota honesta:** la **escalada a firewall (C)** la produce el **agente de mitigación**, no el motor base
> del daemon. Y la "degradación" del perfil (permite→degrada→veta) **no** se alcanza en el flujo base actual
> (la única acción que propone la política hoy es `BLOQUEAR_IP`, localizada); está documentada como capacidad
> de configuración, no como escenario reproducible.

---

## A · Auto-bloqueo (credenciales sobre activo con postura)

Fuerza bruta SSH contra un activo cuyo auditor confirma exposición (`objetivo-vuln`) → confianza 1.0 →
`BLOQUEAR_IP` localizado → el perfil **permite** sin humano.

**En vivo** (requiere el lab; ver [03 · Lab en vivo](03-lab-en-vivo.md) §3.5, terminal B):
```bash
for i in $(seq 1 8); do
  docker exec clab-red-cliente-puesto sh -c "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no \
    -o ConnectTimeout=4 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no \
    -o PreferredAuthentications=password msfadmin@192.168.1.30 id 2>/dev/null"; done
```

**Por inyección** (sin lab):
```bash
printf '%s\n' '{"id":"A1","rule":{"id":"5760","level":10,"groups":["sshd","authentication_failed"],"mitre":{"id":["T1110.001"]}},"predecoder":{"hostname":"objetivo-vuln","program_name":"sshd"},"data":{"srcip":"192.168.1.10"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Failed password for root from 192.168.1.10"}' \
  | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
```

**Esperado** (salida real):
```
Clase: vp_intento_acceso · Prioridad: 3 · Confianza: 1.0 · accion BLOQUEAR_IP -> BLOQUEAR_IP (filtro permite)
Ejecutadas: 1
```

---

## B · Confirmación humana (activo sin postura → baja confianza)

Misma fuerza bruta pero contra un activo que el auditor **no** conoce (sin postura) → confianza 0.5 < umbral
0.7 → el perfil **veta** y **exige humano**: el daemon abre el prompt. (Se pipea `rechazar` para no bloquear.)

```bash
printf '%s\nrechazar\n' '{"id":"B1","rule":{"id":"5760","level":10,"groups":["sshd","authentication_failed"],"mitre":{"id":["T1110.001"]}},"predecoder":{"hostname":"camara-desconocida","program_name":"sshd"},"data":{"srcip":"192.168.1.55"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Failed password for admin from 192.168.1.55"}' \
  | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
```

**Esperado** (salida real):
```
── Validación humana requerida ──
Clase: vp_intento_acceso  ·  Prioridad: 3  ·  Confianza: 0.5
¿aprobar / rechazar / reclasificar?
… accion BLOQUEAR_IP -> BLOQUEAR_IP (filtro veta)
Rechazadas: 1 · Ejecutadas: 0
```

> Sustituye `rechazar` por `aprobar` para ejecutar la acción, o `reclasificar` para corregir la clase (RF-08/RF-12).
> **En el agente de mitigación**, cada acción mutante pide aprobación por paso salvo con `--autonomo`.
>
> **Por qué solo por inyección:** la confianza 0.5 exige un activo **sin postura**, pero los 4 nodos del lab
> ya están en los hallazgos del auditor (todos "conocidos") → un ataque real siempre da confianza 1.0. En un
> despliegue real, B aparece cuando llega un ataque contra un activo que el auditor aún no perfiló.

---

## C · Escalada a firewall (víctima inalcanzable → el XDR sube al perímetro)

El **agente de mitigación** intenta el bloqueo local; si el host no responde, **razona y escala** al firewall
perimetral (`BLOQUEAR_IP_FIREWALL`). Reproducible sin lab (ejecutores simulados):

```bash
python3 lab/scripts/demo-agente-escalado.py --autonomo
```
(en vivo con firewall real: `sh lab/lab.sh up red-cliente-firewall` y `--lab` — ver [05 · Topologías](05-topologias.md))

**Esperado** (salida real):
```
Observation: Error: fallo en objetivo-vuln (rc=255)
Observation: OK: BLOQUEAR_IP_FIREWALL aplicada en gateway (rc=0)
Resultado: mitigado · dispositivo ejecutor: gateway · escalado: True · degradado: False
```

---

## D · Falso positivo (admin declarado como origen legítimo)

Un ataque idéntico pero desde una IP declarada en `origenes_legitimos` del perfil (192.168.1.1 = el `borde`,
el plano de administración) → el motor la clasifica **FP** y **no ejecuta** (RF-03).

**En vivo** (fuerza bruta **desde el borde**, .1). El `borde` necesita cliente SSH; se aprovisiona igual que
el atacante:
```bash
docker exec clab-red-cliente-borde apk add --no-cache openssh-client sshpass >/dev/null 2>&1
for i in $(seq 1 5); do
  docker exec clab-red-cliente-borde sh -c "sshpass -p x_$i ssh -o StrictHostKeyChecking=no \
    -o ConnectTimeout=4 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no \
    -o PreferredAuthentications=password msfadmin@192.168.1.30 id 2>/dev/null"; done
```
Wazuh genera la alerta con `srcip 192.168.1.1`; pásala por el daemon (o déjalo escuchando, §3.3):
```bash
docker exec clab-red-cliente-wazuh sh -c "tail -40 /var/ossec/logs/alerts/alerts.json" \
  | grep -a '"srcip":"192.168.1.1"' | tail -1 \
  | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
```

**Por inyección** (sin lab):
```bash
printf '%s\n' '{"id":"D1","rule":{"id":"5760","level":10,"groups":["sshd","authentication_failed"],"mitre":{"id":["T1110.001"]}},"predecoder":{"hostname":"objetivo-vuln","program_name":"sshd"},"data":{"srcip":"192.168.1.1"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Failed password for root from 192.168.1.1"}' \
  | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
```

**Esperado** (salida real, verificado en vivo y por inyección):
```
Clase: fp_actividad_legitima · Prioridad: 1 · Confianza: 1.0 · accion None -> None (filtro sin_accion)
Ejecutadas: 0
```

---

## E · `no_soportada` (fuera del perímetro acotado)

Una alerta de una familia fuera de las cuatro soportadas (aquí `rootcheck` → familia `plataforma`) → el motor
la marca **`no_soportada`** y conserva su severidad, sin inventar una clasificación (RF-10).

```bash
printf '%s\n' '{"id":"E1","rule":{"id":"510","level":7,"groups":["rootcheck"]},"predecoder":{"hostname":"objetivo-vuln","program_name":"rootcheck"},"data":{"srcip":"192.168.1.60"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Rootcheck: integrity change"}' \
  | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
```

**Esperado** (salida real):
```
Clase: no_soportada · Prioridad: 1 · Confianza: 1.0 · accion None -> None (filtro sin_accion)
Ejecutadas: 0
```

> **Por qué solo por inyección:** requiere una alerta de una familia fuera de las 4 soportadas, y este lab no
> la produce a demanda (el telnet al IoT no genera alerta en Wazuh; rootcheck/syscheck corren en su ciclo). En
> producción, E aparece con cualquier alerta que el SIEM entregue fuera del caso de uso acotado.

---

## Cobertura por familia del perímetro

Las 4 familias soportadas se ejercitan cambiando `rule.groups` / `mitre` de la alerta inyectada:

| Familia | `rule.groups` | Ejemplo de técnica |
|---|---|---|
| acceso_credenciales | `["sshd","authentication_failed"]` | T1110.001 (escenarios A/B/D) |
| servicio_expuesto | `["telnetd"]` (servicio telnet) | T1133 — en vivo: `docker exec clab-red-cliente-puesto sh -c "nc -w3 192.168.1.20 23"` al IoT |
| reconocimiento | `["recon"]` o regla 5706 | T1046 |
| explotacion_conocida | `["exploit"]` o `["attack"]` | T1190 |

El **comportamiento** (A–E) de cada familia depende de la **postura del activo** (auto-bloqueo si el auditor
lo confirma expuesto, confirmación humana si es desconocido) y del **origen** (FP si es legítimo), no de la
familia en sí. Para métricas cuantitativas de las 4 familias, ver el banco de simulación en
[02 · RAG y evaluación](02-rag-evaluacion.md) §2.4.
