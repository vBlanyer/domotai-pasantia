# Guía de operación del prototipo de triaje asistido

**Para quién:** el operador de Domotai que lo despliega y lo vigila. **Qué es:** un servicio que lee las
alertas de Wazuh, las clasifica y prioriza con reglas deterministas, propone una acción del catálogo
cerrado filtrada por el perfil del cliente, la **justifica** con un modelo de lenguaje local apoyado en
recuperación (RAG), pide validación humana cuando el perfil lo exige, la ejecuta por SSH con mínimo
privilegio, verifica el efecto y deja una traza encadenada por hash. **Qué no es:** el modelo no decide
nada; si el modelo no responde, el sistema sigue decidiendo igual y justifica con plantilla.

Todo lo que sigue se ejecutó el 11/09/2026 sobre el laboratorio; los resultados esperados que se citan son
los que se obtuvieron. Las guías de *prueba* (`docs/pruebas/`) cubren cómo demostrarlo; esta cubre cómo
operarlo.

---

## 1. Requisitos

| Pieza | Qué hace falta | Notas |
|---|---|---|
| Máquina | Linux (WSL2 vale). GPU recomendada: con una RTX 5070 el 8B responde en 0,4 s; solo CPU funciona con el 1B, más lento | `docs/pruebas/06-rendimiento-y-hardware.md` |
| Python | 3.x con `pyyaml`; el resto es biblioteca estándar | sin dependencias de red ni de nube |
| Inferencia | `llama.cpp` (`llama-server`, `llama-embedding`) en el entorno Conda `triaje-ml` | `prototipo/README.md §9` |
| Modelos | `modelos/llama-3.1-8b-instruct-q4.gguf` (generador; cae al 1B si no está) y `modelos/bge-m3-q8.gguf` (embedder) | no se versionan; ~5,6 GB |
| Fuente de alertas | Wazuh: el fichero `alerts.json` del manager, accesible al servicio | otra fuente = otro adaptador (RNF-06) |
| Acceso a los nodos | SSH desde el nodo de gestión (el auditor) a cada nodo gestionado, con el usuario de mínimo privilegio | §3.3 |

## 2. Configuración por cliente (lo que cambia entre clientes, y solo eso)

Los cinco puntos de variabilidad del diseño se tocan en tres ficheros; el código no se toca.

1. **Perfil del cliente** `prototipo/perfiles/<cliente>.yml` — activos y su criticidad, servicios que
   prestan, `origenes_legitimos` (la administración del cliente **y el auditor del propio servicio**: si
   no se declara, sus barridos se clasifican como ataque; medido), `continuidad` (qué impacto se ejecuta
   automáticamente y con qué confianza, qué exige humano, reversibilidad obligatoria, no cortar gestión),
   `topologia` (solo para el agente de escalada).
2. **Postura de los activos** `hallazgos.json` — la produce el auditor (`sh lab/scripts/auditar.sh
   salida.json`). Es lo que distingue «intento contra un servicio expuesto» de «intento contra algo que no
   existe». Se regenera cuando cambia el inventario.
3. **Catálogo de acciones** `prototipo/catalogo.yml` — cerrado. Cada acción lleva comando, reversión,
   verificación e impacto. **Cambiarlo obliga a re-aprovisionar el mínimo privilegio (§3.3)**: el sudoers
   de los nodos se genera desde el catálogo, y un comando nuevo no aprovisionado será denegado (falla
   cerrado, que es lo correcto).

## 3. Puesta en marcha, en este orden

### 3.1 Servidores de inferencia (una vez por arranque de la máquina)
```bash
sh lab/scripts/llm-server.sh             # generador  → http://127.0.0.1:8080
sh lab/scripts/llm-server.sh --embedder  # embedder   → http://127.0.0.1:8082
```
Esperado: `listo en http://127.0.0.1:8080` y `…:8082`. Si ya están, lo dice y no arranca otro. Sin el
generador, el servicio funciona con justificación de plantilla (RNF-09); sin el embedder, usa el subproceso
(mismo resultado, ~2 s más por justificación). Ambos envían siempre las opciones de reproducibilidad
(`cache_prompt: false`; un texto por petición): no las quites.

### 3.2 Índice del RAG (cuando cambie el corpus o el embedder)
```bash
python3 -m prototipo.rag --indexar       # esperado: "indice regenerado: 32 documentos"
```
Si alguien cambia el embedder sin reindexar, la recuperación se detiene con un error explícito de
dimensiones en lugar de devolver similitudes sin sentido.

### 3.3 Mínimo privilegio en cada nodo gestionado (una vez por nodo, y tras cada cambio del catálogo)
```bash
sh lab/scripts/aprovisionar-minimo-privilegio.sh <contenedor-o-host> <ip>
```
Deja en el nodo el usuario `triaje` (solo clave), el sudoers generado desde el catálogo y, en el auditor,
la clave y el `known_hosts` del nodo. Esperado al final:
```
permitido (del catalogo):  iptables -L -n   OK
denegado (fuera del catalogo): cat /etc/shadow   OK
denegado (mismo binario, argumentos fuera del catalogo): iptables -F   OK
```
Si cualquiera de los dos «denegado» no aparece, el aprovisionamiento **falla a propósito**: no operes.

### 3.4 El servicio
```bash
# fuente real: el alerts.json de Wazuh
python3 -m prototipo.stream /var/ossec/logs/alerts/alerts.json prototipo/perfiles/<cliente>.yml \
        --con-llm --ventana-agrupacion 10 --salida /var/lib/triaje/trazas.jsonl
# en el laboratorio (el fichero vive dentro del contenedor):
docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
    | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --con-llm --ventana-agrupacion 10
```
Lee el banner antes de nada. Debe decir **con qué credencial entra**:
```
Perfil: empresarial.yml · Justificador: LLM+RAG · Ejecutor: conector SSH con clave (usuario dedicado, sudo acotado)
```
Si dice `conector SSH del laboratorio (contraseña por defecto)`, el mínimo privilegio no está aprovisionado
en el auditor: vuelve a §3.3. (`TRIAJE_SSH_MODO=password` lo fuerza a propósito, solo para el laboratorio.)

## 4. Operación diaria

**Un incidente se ve así** (4 alertas de una ráfaga, agrupadas; ejecutado sin humano porque el perfil
`empresarial` automatiza el impacto localizado con confianza alta):
```
⚠ Incidente: 4 alerta(s) · 192.168.1.10 -> objetivo-vuln (ssh) · reglas [5503x2, 5760x2]
  Clase: vp_intento_acceso · Prioridad: 3 · Confianza: 1.0 · accion BLOQUEAR_IP -> BLOQUEAR_IP (filtro permite) · justificador llm-5:llama-3.1-8b-instruct-q4.gguf
```

**Validación humana.** Cuando el perfil la exige (impacto que alcanza un servicio, confianza baja, acción
degradada), el servicio muestra alerta, clase, prioridad, justificación y acción, y espera en la terminal
de control (`/dev/tty`, no la entrada de alertas):
- `aprobar` → ejecuta, verifica, anota.
- `rechazar` → no ejecuta; queda anotado con veredicto.
- `reclasificar` → no ejecuta y anota la clase que el analista considera correcta (feedback, RF-12).

**Parar:** `Ctrl+C`. Imprime el resumen (alertas, incidentes, aprobadas, rechazadas, reclasificadas,
ejecutadas) y cierra la traza limpiamente. Al volver a arrancar con el mismo `--salida`, la cadena de la
traza continúa donde quedó.

**Revertir una acción** (falso positivo confirmado, cliente que pide levantar un bloqueo):
```bash
python3 -m prototipo.revertir /var/lib/triaje/trazas.jsonl s7 --motivo "falso positivo confirmado por el cliente"
# esperado: s7: BLOQUEAR_IP en objetivo-vuln -> revertida · comando: iptables -D INPUT -s 192.168.1.10 -j DROP
```
La reversión sale de la orden guardada en la traza y del catálogo, la ejecuta el mismo conector, se verifica
que el estado desapareció y **se anota en la misma cadena**. Repetirla dice «ya fue revertida». Solo se
revierten acciones con `reversion: definida`; las transitorias y las de observación no tienen nada que revertir.

## 5. Verificación periódica (qué mirar y con qué frecuencia)

| Qué | Cómo | Cuándo |
|---|---|---|
| Integridad de la traza | `python3 -m prototipo.traza --verificar trazas.jsonl` → `cadena valida: N registros · ultimo hash …` | diario, y antes de cualquier revisión |
| Anclaje del último hash | copia el `ultimo hash` que imprime el verificador a un sitio fuera del fichero (otro sistema, un registro firmado, un correo al cliente) | con cada verificación. **Sin esto, un truncado por el final no se detecta** |
| Servidores vivos | `curl -s 127.0.0.1:8080/health`, `…:8082/health` → `{"status":"ok"}` | al arrancar y si las justificaciones salen «de plantilla» |
| Mínimo privilegio vigente | re-ejecuta `aprovisionar-minimo-privilegio.sh` (es idempotente) | tras cambiar el catálogo o rotar la clave |
| Postura de los activos | regenera `hallazgos.json` con el auditor | tras cambios en el inventario |
| Versiones en la traza | `version_justificador`, `version_perfil`, `version_baseline` en cada registro | al comparar decisiones de fechas distintas |

## 6. Qué hacer cuando…

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Las justificaciones dicen `[justificación de plantilla — baseline, no modelo]` | el generador no responde, o la justificación no ancló (menciona una IP o una técnica que no es de la alerta) | `llm-server.sh`; si persiste, es el modelo anclando mal: la decisión sigue siendo correcta, la explicación es la de plantilla |
| Cada justificación tarda ~5 s más | el embedder residente no responde y se usa el subproceso | `llm-server.sh --embedder` |
| `Permission denied (publickey)` o `sudo: … password` en la traza | el nodo no está aprovisionado, o el catálogo cambió | §3.3 |
| `Host key verification failed` | la clave del host cambió (reinstalación… o suplantación) | comprueba con el cliente **antes** de re-aprovisionar; el script reescribe el `known_hosts` |
| El mismo origen genera un incidente tras otro | es un origen legítimo no declarado (administración, escáner, auditor) | decláralo en `origenes_legitimos` del perfil y reinicia el servicio |
| Alertas con clase `no_soportada` | están fuera del perímetro del caso de uso (dos familias hoy) | quedan en la traza con su severidad de origen; no se descartan, no se actúan |
| Wazuh deja de producir alertas | el reenvío syslog del nodo se cayó | en el lab: `sh lab/scripts/reenvio-syslog.sh` |
| Un bloqueo quedó puesto tras una demo o prueba | acción ejecutada y no revertida | `prototipo.revertir` con su `id_decision` (nunca a mano, para que conste) |

## 7. Reproducibilidad: cómo repetir una decisión

Cada registro guarda todo lo que hace falta: la alerta normalizada, el perfil y su versión, la clase, el
enunciado implícito (versión del justificador + pasajes recuperados + consulta usada), la acción y su
ejecución. Con los mismos servidores y las mismas opciones (`cache_prompt: false`, un texto por petición),
el mismo enunciado produce el mismo texto: se midió que sin esas dos opciones no era así, y quedaron fijas
en el código. Para repetir una campaña completa: `python3 -m evaluacion.campana --particion evaluacion
--con-rag --generador servidor`.

## 8. Límites que el operador debe conocer

- **La señal de origen es suplantable.** La distinción administrador/atacante se apoya en la IP declarada.
  Es la señal que hay; no es una prueba de identidad.
- **Dos familias de alerta soportadas** (acceso a credenciales, reconocimiento), un activo y un servicio en
  la evaluación. Lo demás es `no_soportada`, a juicio humano.
- **El corpus del RAG es pequeño** (32 fichas) y curado a mano. Crece cuando el perímetro crece; con el
  embedder actual crecerlo no degrada la recuperación de forma apreciable.
- **La explicación hereda las etiquetas de la fuente.** Si Wazuh etiqueta una regla de reconocimiento como
  T1190, la justificación lo dirá. La clase y la acción no dependen de eso.
- **El agente de escalada (`--agente`) es opcional** y exige GPU: sin ella degrada al motor determinista, que
  ya escala host → cortafuegos por sí mismo.
- **La traza no detecta su propio truncado final** sin el anclaje de §5.
- **El equipo de borde con firmware real no está validado**; el laboratorio usa un sustituto Linux.

## 9. Lista de comprobación de puesta en marcha (lo que se ejecutó el 11/09/2026)

```
[x] sh lab/scripts/llm-server.sh                 → listo en :8080
[x] sh lab/scripts/llm-server.sh --embedder      → listo en :8082
[x] python3 -m prototipo.rag --indexar           → 32 documentos
[x] sh lab/scripts/aprovisionar-minimo-privilegio.sh → permitido OK · denegado OK · denegado OK
[x] daemon con --con-llm, banner "conector SSH con clave"
[x] ataque real (5 intentos SSH) → 1 incidente de 4 alertas, BLOQUEAR_IP ejecutado como triaje
    (auth.log del nodo: sudo: triaje : … COMMAND=/sbin/iptables -A INPUT -s 192.168.1.10 -j DROP)
[x] python3 -m prototipo.traza --verificar       → cadena valida: 1 registros
[x] python3 -m prototipo.revertir … s1 --motivo … → revertida; cadena valida: 2 registros
[x] segunda reversión                            → "ya fue revertida"
```
Tiempo total del lazo, del ataque al bloqueo verificado: unos 45 s, de los que ~40 son el reenvío syslog
del nodo (un datagrama por línea) y ~3 la decisión con justificación.
