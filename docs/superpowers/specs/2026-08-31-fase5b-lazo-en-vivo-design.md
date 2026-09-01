# Diseño — Fase 5B: el lazo en vivo del motor de triaje

**Fecha:** 2026-08-31
**Fase:** 5 — Implementación del prototipo (subproyecto B de tres)
**Requisitos que ejercita:** RF-08 (validación humana), RF-09 (traza), RF-15 (acción por catálogo
cerrado), RF-17 (impacto), RF-18/RF-19 (reversibilidad, no cortar gestión), y el criterio de cierre
de la Fase 5 *«el lazo completo funciona en vivo»*.

---

## 1. Objetivo y encuadre

Con 5A el motor **decide** hasta antes de ejecutar. 5B cierra el lazo: ejecuta la acción sobre el
nodo, retiene lo que exige aprobación para validación humana, verifica el efecto, y registra la
traza completa. Es el subproyecto que cumple el criterio de cierre de la Fase 5.

- **5A (hecho)** — ingesta → análisis baseline → política → perfil → decisión (traza).
- **5B (este)** — orden de acción → conector SSH → validación humana → verificación → traza del lazo.
- **5C (pendiente)** — el ML real detrás de la interfaz de análisis; bloqueado por datos y herramientas.

### Prueba de viabilidad (hecha antes de diseñar)

Verificado en vivo sobre `objetivo-vuln`: SSH (con algoritmos del sshd de 2007) → `iptables -A INPUT
-s <ip> -j DROP` → verificación (`iptables -L` muestra la regla) → reversión (`-D`). El lazo en vivo
es viable con lo que el laboratorio da hoy.

### Alcance de este ciclo: lazo mínimo demostrable

- **El conector actúa sobre `objetivo-vuln`.** Es el único nodo con sshd (`puesto`, `iot`, `borde`
  no lo tienen). No es limitación del lazo: el atacante es `puesto` y la acción `BLOQUEAR_IP` se
  ejecuta **en la víctima**, que es donde tiene sentido.
- **La acción demostrable es `BLOQUEAR_IP`** (localizada), que es lo que el baseline+política
  proponen sobre las alertas reales.
- **La validación humana se demuestra con un escenario provocado** (confianza baja o acción de
  impacto), porque con el baseline sobre datos reales `requiere_humano` casi nunca se dispara.

### Qué NO cubre 5B

- El conector completo de las 14 acciones (muchas no son ejercitables: nodos sin sshd, servicios
  inexistentes). Solo las que el lazo mínimo usa.
- El ML (5C).
- Autenticación por clave dedicada: el laboratorio usa `msfadmin` + `sudo` como **sustituto**
  documentado (ver §6).

---

## 2. Arquitectura

Nuevos módulos en `prototipo/`, todos consumiendo la orden de acción como **dato**, no como llamada
acoplada — lo que mantiene barato un futuro conector en Go.

```
alerta → triaje.procesar (5A) → decisión
   │
   ├─ ¿requiere_humano? ── validacion.pedir (TUI) ── aprobar/rechazar/modificar
   │
   └─ orden.construir(decisión, alerta) ── conector.ejecutar_orden(orden, catalogo, ejecutor)
                                                    │
                                        verificacion.confirmar (auditor)
                                                    │
                                        traza_lazo.registrar (RF-09)
```

| Módulo | Responsabilidad |
|--------|-----------------|
| `prototipo/orden.py` | Construye la orden de acción (mensaje) desde la decisión + la alerta |
| `prototipo/conector.py` | Traduce acción→comando, ejecuta por el ejecutor inyectado, captura resultado |
| `prototipo/validacion.py` | La TUI de validación humana (aprobar/rechazar/modificar) |
| `prototipo/verificacion.py` | Confirma el efecto de la acción (verificación del catálogo / reescaneo) |
| `prototipo/lazo.py` | Orquestador del lazo en vivo + CLI |

---

## 3. La orden de acción (la frontera)

El motor emite la orden como **dato plano** (dict/JSON), no como objeto acoplado. Es el contrato de
[flujo §5](../../../documentacion/04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md):

```
orden = {
  decision_id      # trazable hasta la alerta de origen (RF-09)
  accion_id        # del catálogo cerrado (p.ej. BLOQUEAR_IP)
  nodo_objetivo    # dónde se ejecuta (objetivo-vuln)
  nodo_ip          # IP del nodo objetivo en el plano de datos
  params           # {ip: 192.168.1.10}  — el atacante a bloquear
  impacto          # localizado
  justificacion    # el texto que respalda la orden
}
```

`orden.construir(decision, alerta) -> orden | None`. Devuelve `None` cuando la decisión no lleva
acción (`accion_final` es None, o fue rechazada). Los `params` salen de la alerta (`origen_ip`), que
el orquestador tiene en mano.

**Por qué dato y no llamada:** un conector en Go leería el mismo JSON. `conector.py` añade un
`__main__` que lee una orden de fichero/stdin, así la frontera es de proceso y el swap a Go es
reescribir solo ese programa, sin tocar el motor.

---

## 4. El conector

`ejecutar_orden(orden, catalogo, ejecutor) -> resultado`.

**Traducción acción→comando.** Rellena la plantilla `comando` del `catalogo.yml` con los `params`.
El motor nunca emite comandos: selecciona del catálogo cerrado, el conector materializa. Es lo que
impide que el canal SSH degenere en ejecución arbitraria (RF-15).

**Idempotencia por «verificar-antes-de-actuar»** (RF de flujo §5, propiedad no negociable):
1. Ejecuta el comando de **verificación** del catálogo. Si el estado deseado ya está →
   `ya_aplicada`, no reejecuta.
2. Si no → ejecuta el **comando**, y vuelve a verificar para confirmar el efecto.

Reejecutar la misma orden no duplica nada, y la verificación del efecto sale del mismo mecanismo.

**Resultado** (registro de ejecución, RF-09):
```
resultado = { decision_id, accion_id, nodo, comando_ejecutado,
              codigo_salida, salida, exito (bool), idempotente (bool), timestamp }
```

**El ejecutor, inyectable** (la frontera de transporte):
- Laboratorio: `ejecutor_ssh_lab(nodo_ip, comando)` → `docker exec clab-red-cliente-auditor ssh
  <opts-algoritmos-viejos> msfadmin@<ip> "echo <pass> | sudo -S <comando>"`. Va por el plano de
  gestión (como el auditor), porque el anfitrión no alcanza el plano de datos directamente.
- Tests: un **ejecutor falso** que devuelve salidas prefijadas → el conector se prueba entero sin
  laboratorio.
- Despliegue real: un ejecutor con SSH directo y clave de servicio. El conector no cambia.

Toda la lógica del conector (render, idempotencia, resultado) es pura y recibe el ejecutor como
parámetro. Solo `ejecutor_ssh_lab` toca el laboratorio, y se valida en vivo, no con unittest.

---

## 5. La validación humana (TUI)

Cuando la decisión trae `requiere_humano`, la orden queda retenida y el analista decide **por
terminal** (decisión D11 — sin UI gráfica).

`validacion.pedir(decision, alerta, leer=input) -> veredicto`. **Muestra** (todo lo que 5A ya
produjo): resumen de la alerta, clase, prioridad, confianza, la **justificación** que cita campos,
la postura del auditor, la acción propuesta (y si el perfil la degradó) con su impacto. **Captura**
(RF-08):
- `aprobar` → la orden sigue al conector.
- `rechazar` → sin acción, registrado.
- `modificar` → el analista elige otra acción del catálogo, registrado como decisión humana.

La lectura de la respuesta (`leer`) se **inyecta**: un `input` falso en los tests, el prompt real en
vivo. Así la presentación se prueba sin teclear.

Cada veredicto (aprobada/rechazada/modificada) va a la traza — semilla del aprendizaje continuo
(trabajo futuro).

---

## 6. Verificación y traza del lazo

**Verificación en dos niveles:**
- **De conector** (§4): la verificación del catálogo confirma el efecto directo (la regla `iptables`
  existe). Suficiente para la acción localizada del lazo mínimo.
- **De auditor** ([auditoría §5.2](../../../documentacion/04-fase4-diseno-de-arquitectura/auditoria-de-vulnerabilidades-del-sandbox.md)):
  un reescaneo confirma que la exposición se cerró — para acciones de endurecimiento; demostrable si
  se provoca una.

`verificacion.confirmar(orden, catalogo, ejecutor) -> {verificado: bool, evidencia}`.

**La traza del lazo completo** (`lazo.py`), el artefacto que prueba «el lazo funciona en vivo».
Reúne por alerta: la decisión de 5A, el veredicto humano (si lo hubo), la orden, el resultado de
ejecución y la verificación. Reconstruible hasta la alerta de origen (RF-09).

```
traza_lazo = {
  ...campos de la decisión de 5A (clase, accion_final, impacto, resultado_filtro, requiere_humano)...
  veredicto_humano        # aprobar|rechazar|modificar|None
  orden                   # la orden emitida (o None si rechazada/sin acción)
  ejecucion               # el resultado del conector (o None)
  verificacion            # {verificado, evidencia} (o None)
}
```

### El encuadre de alcance (I-7)

El conector ejecuta acciones reales sobre el sandbox. Es **validación en entorno controlado**, no
respuesta automatizada en producción (que el plan declara trabajo futuro). La finalidad es medir la
calidad de la decisión, no remediar incidentes reales. Ver el aviso del
[roadmap Fase 5](../../../documentacion/00-general/roadmap.md).

### Autenticación: sustituto de laboratorio

El diseño manda **clave dedicada y privilegio mínimo**. En el laboratorio, `objetivo-vuln` es
Metasploitable y el conector usa `msfadmin` + `sudo` con contraseña conocida como **sustituto**
documentado de la clave de servicio de un despliegue real. Es honesto, no bloquea el lazo, y queda
como limitación conocida para el informe de la Fase 7.

---

## 7. El orquestador del lazo en vivo

`lazo.py`:
```
para cada alerta de la fuente:
    decision = triaje.procesar(alerta, hallazgos, perfil, ...)      # 5A
    veredicto = None
    if decision["requiere_humano"]:
        veredicto = validacion.pedir(decision, alerta)
        if veredicto in ("rechazar", "modificar"):  registrar(sin ejecución);  continuar
    orden = orden.construir(decision, alerta)
    if orden is None:  registrar(sin acción);  continuar
    resultado = conector.ejecutar_orden(orden, catalogo, ejecutor, timestamp)
    verif = verificacion.confirmar(orden, catalogo, ejecutor)
    traza_lazo.registrar(decision, veredicto, orden, resultado, verif)
```

CLI: `python3 -m prototipo.lazo <alertas.jsonl> <perfil.yml> <hallazgos.json> <salida.jsonl>`, con un
modo `--auto` (ejecutor falso, sin laboratorio, para pruebas) y un modo en vivo (ejecutor SSH).

---

## 8. Artefactos que produce 5B

- `prototipo/orden.py`, `conector.py`, `validacion.py`, `verificacion.py`, `lazo.py` con sus tests.
- El CLI del lazo en vivo.
- Una ejecución en vivo demostrada: alerta real → decisión → `BLOQUEAR_IP` sobre `objetivo-vuln` →
  verificación → traza; y la reversión.
- Un escenario provocado que dispara la validación humana TUI.
- `prototipo/README.md` y el README de la Fase 5 actualizados.

---

## 9. Criterio de cierre de 5B (y de la Fase 5 demostrable)

- El CLI del lazo procesa alertas y, para una `vp_intento_acceso` sobre `objetivo-vuln`, **ejecuta
  `BLOQUEAR_IP` en vivo** y la verificación confirma la regla.
- Un escenario provocado **retiene la orden** y la TUI captura el veredicto humano.
- La traza del lazo reúne decisión + veredicto + orden + ejecución + verificación, reconstruible
  hasta la alerta.
- Batería `unittest` verde (conector, orden, validación, verificación probados con ejecutor/input
  falsos, sin laboratorio).

---

## Documentos relacionados

- [Fase 5A: núcleo de decisión](./2026-08-31-fase5a-nucleo-decision-design.md) — lo que 5B consume.
- [Protocolos de comunicación](../../../documentacion/04-fase4-diseno-de-arquitectura/protocolos-comunicacion-sandbox.md) — SSH y el conector como punto de aislamiento.
- [Flujo §5](../../../documentacion/04-fase4-diseno-de-arquitectura/flujo-triaje-playbook-sandbox.md) — el contrato de la orden (idempotencia, trazabilidad).
- [Catálogo de acciones](../../../documentacion/04-fase4-diseno-de-arquitectura/catalogo-de-acciones.md) · [Auditoría §5.2](../../../documentacion/04-fase4-diseno-de-arquitectura/auditoria-de-vulnerabilidades-del-sandbox.md).
