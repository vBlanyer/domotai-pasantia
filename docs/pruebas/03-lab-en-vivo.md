# Nivel 3 · En vivo, de punta a punta (lab + modelo)

## 3.0 · Levantar el laboratorio (imprescindible para el resto del Nivel 3)

**Sinopsis**
```
sh lab/lab.sh ( up | down | status | test )
```

**Ejemplo**
```bash
sh lab/lab.sh up          # despliega la red + Wazuh + aprovisiona el auditor (~2 min)
sh lab/lab.sh status      # comprobar: 8 nodos arriba, plano de datos OK
```

Asegúrate de tener el índice RAG (`python3 -m prototipo.rag --indexar`, Nivel 2.3).

## 3.1 · Demo del lazo completo (víctima / atacante / triaje)

Ataque real → Wazuh alerta → triaje justifica con RAG → validación → bloqueo por SSH → verificación.

**Sinopsis**
```
python3 lab/scripts/demo-lazo-vivo.py
```

**Ejemplo**
```bash
python3 lab/scripts/demo-lazo-vivo.py
```

**Esperado:** narra las 3 vistas; el bloqueo `iptables` aparece en la víctima y el atacante deja de
alcanzar el puerto 22.

## 3.2 · Demo de validación humana real

**Sinopsis**
```
python3 lab/scripts/demo-validacion-humana.py
```

**Ejemplo**
```bash
python3 lab/scripts/demo-validacion-humana.py
```

**Esperado:** una acción que alcanza el servicio se **degrada** y **exige aprobación**; se corre el mismo
punto de decisión **rechazar** (no ejecuta) y **aprobar** (ejecuta por SSH).

> Deja el lab neutro tras las demos:
> `docker exec clab-red-cliente-objetivo-vuln iptables -D INPUT -s 192.168.1.10 -j DROP`

## 3.3 · Modo tiempo real continuo (daemon / listener MDR)

Se **queda escuchando** `alerts.json` sin cerrarse (como en producción): colapsa la ráfaga (RF-11),
clasifica, justifica (con RAG si `--con-llm`), abre el prompt **[Aprobar/Rechazar/Reclasificar]** cuando hace
falta humano, ejecuta, escribe la traza línea a línea y vuelve a escuchar. `Ctrl+C` cierra con resumen.

**Sinopsis**
```
python3 -m prototipo.stream <alerts.json | -> [perfil.yml] [hallazgos.json] \
        [--con-llm | --sin-llm] [--agente] [--ventana-agrupacion N] [--sin-lab] [--salida trazas.jsonl]
```
(`--ventana-agrupacion N`: acumula la ráfaga N s antes de emitir el incidente; `N=0` = al instante. Default 5.)

**`--agente`** — en vez del bloqueo determinista de **un** nodo, delega la mitigación al **agente ReAct**:
decide la estrategia y **escala de dispositivo** (host → firewall) si el objetivo no responde, consultando
ATT&CK/D3FEND. La aprobación es **por paso** (cada acción de dispositivo pide humano; se pierde
"reclasificar"). Usa el 1B para el razonamiento (implica coste LLM, ver [06 · Rendimiento](06-rendimiento-y-hardware.md));
sin modelo, degrada al motor determinista. Requiere `topologia` en el perfil (la tiene `empresarial.yml`).
La escalada **real** se ejerce con la topología `red-cliente-firewall` (ver [05 · Topologías](05-topologias.md)).

**Ejemplo** (en el lab: el `alerts.json` vive dentro del contenedor de Wazuh → canaliza su `tail -F`)
```bash
docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --con-llm --ventana-agrupacion 10
    # con los servidores residentes arrancados (sh lab/scripts/llm-server.sh y --embedder) la justificación
    # tarda ~3 s por incidente; sin ellos, el daemon sigue funcionando pero más despacio
```
(en otra terminal, lanza el ataque; p. ej. corre `demo-lazo-vivo.py` o la fuerza bruta a mano)

**Ejemplo** (en producción: Wazuh escribe a un fichero del host montado)
```bash
python3 -m prototipo.stream /var/ossec/logs/alerts/alerts.json prototipo/perfiles/empresarial.yml --con-llm
```

**Ejemplo** (prueba de humo sin lab ni modelo: alerta cruda por *stdin*, ejecutor simulado)
```bash
printf '%s\n' '{"id":"z1","rule":{"id":"5760","level":10,"groups":["sshd","authentication_failed"],"mitre":{"id":["T1110.001"]}},"predecoder":{"hostname":"objetivo-vuln","program_name":"sshd"},"data":{"srcip":"192.168.1.10"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Failed password for root from 192.168.1.10"}' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
```

## 3.4 · Agente de mitigación (escalado multi-nodo host → firewall)

El LLM actúa como **agente ReAct**: decide la estrategia y **escala de dispositivo** (host → firewall)
reaccionando a los errores, pero **elige acciones de un catálogo cerrado** (el código renderiza el
`iptables`, RF-15), valida (RF-19), pide aprobación (RF-08) y ejecuta reversible (RF-18). Consulta el
conocimiento **ATT&CK/D3FEND** del RAG. Si falla, **degrada** al motor determinista (RNF-09).

**Sinopsis**
```
python3 lab/scripts/demo-agente-escalado.py [--lab] [--autonomo] [--con-llm]
```
(`--lab`: conector SSH real · `--autonomo`: sin pausas de aprobación · `--con-llm`: el 1B real como agente)

**Ejemplo** (simulado, sin interacción — el más rápido para ver el escalado)
```bash
python3 lab/scripts/demo-agente-escalado.py --autonomo
```

**Esperado:** consulta el conocimiento → intenta el bloqueo local (falla: *Connection refused*) → **escala
al firewall** (`BLOQUEAR_IP_FIREWALL`) → verifica el corte → registra ambas reversiones; `escalado: True`,
`dispositivo ejecutor: gateway`.

## 3.5 · Demo manual en vivo: monitoreo vs ataque (multi-terminal)

Para la defensa práctica: un lado **monitorea/responde** y otro **ataca**, en terminales separadas. Tras
`sh lab/lab.sh up` el atacante ya queda aprovisionado con cliente SSH (además del auditor).

**Mapa del lab:** atacante `puesto` = **192.168.1.10** · víctima `objetivo-vuln` = **192.168.1.30** ·
firewall `borde` = **192.168.1.1** · manager `wazuh`.

### Terminal A — LADO DE MONITOREO (defensor)

Elige **una** vista (o abre varias terminales):

**A1 · Daemon MDR en tiempo real** (escucha Wazuh, triaja, responde):
```bash
docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --con-llm --ventana-agrupacion 10
```

**A2 · Alertas crudas de Wazuh** (ver lo que detecta el SIEM):
```bash
docker exec clab-red-cliente-wazuh tail -f /var/ossec/logs/alerts/alerts.json
```

**A3 · El bloqueo en la víctima** (ver aparecer la regla `iptables` cuando el motor responde):
```bash
watch -n2 "docker exec clab-red-cliente-objetivo-vuln iptables -L INPUT -n"
```

### Terminal B — LADO DE ATAQUE (atacante, .10)

**B1 · Fuerza bruta SSH real** (dispara las alertas 5760/5712/5763 desde 192.168.1.10):
```bash
for i in $(seq 1 8); do
  docker exec clab-red-cliente-puesto sh -c "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no \
    -o ConnectTimeout=4 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no \
    -o PreferredAuthentications=password msfadmin@192.168.1.30 id 2>/dev/null"
done
```

**B2 · Comprobar alcance del puerto 22** (antes = ALCANZABLE, después del bloqueo = BLOQUEADO):
```bash
docker exec clab-red-cliente-puesto sh -c "nc -z -w3 192.168.1.30 22 && echo ALCANZABLE || echo BLOQUEADO"
```

### Limpieza (dejar el lab neutro tras la práctica)
```bash
docker exec clab-red-cliente-objetivo-vuln iptables -D INPUT -s 192.168.1.10 -j DROP 2>/dev/null
```

> El flujo típico: en **A1** arranca el daemon → en **B1** lanza la fuerza bruta → el daemon emite el
> incidente, justifica con RAG y pide **[Aprobar/Rechazar/Reclasificar]** → al aprobar, en **A3** ves la
> regla `iptables` y en **B2** el puerto pasa a BLOQUEADO.
