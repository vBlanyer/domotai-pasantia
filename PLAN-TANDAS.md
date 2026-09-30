# Plan de pulido del prototipo: tandas pendientes

Origen: auditoría del 29/09/2026 (8 áreas, cada hallazgo verificado contra el código) más lo que
salió al probar en vivo el 30/09. Cada ítem dice **qué pasa**, **dónde** (ruta:línea aproximada;
comprueba antes de tocar, el código ha cambiado) y **qué hacer**. Esfuerzo: S (horas), M (1 día),
L (varios días).

Cómo trabajar cada tanda:
- Una rama por tanda (`fix/tanda2-…`), TDD (test que falla → arreglo → suite en verde) y un commit por ítem.
- Antes de fusionar, pasan todas las suites y el test de valores canónicos
  (`evaluacion/tests/test_canonicos.py`); si ese falla, el cambio movió las cifras del informe.
- Con Claude: «Lee PLAN-TANDAS.md y ejecuta la Tanda N».

```bash
python3 -m unittest discover -s prototipo/tests
python3 -m unittest discover -s evaluacion/tests -t .
python3 -m unittest discover -s lab/banco/tests -t .
python3 -m unittest discover -s lab/dataset/tests -t .
cd visor && npx vitest run && npx tsc -b && npm run lint && npm run build
```

---

## Hecho (no repetir)

- **Tanda 1** (fusionada en `main` el 30/09):
  - escalada web con humano en cada salto;
  - supresión por (IP, activo, familia) con excepción perimetral;
  - verificación `grep DROP | grep -wF --`;
  - veto sin IP de origen IPv4;
  - Ctrl+C con el resumen real;
  - barrera de excepciones y timeouts;
  - contexto y horas reales en la traza;
  - revertir con flock y `--indice`;
  - test canónico en lote y causal (recall 1.000 / 0.908).
- **B4 del modo agente**: lo retenido se decide antes de que actúe el agente, el respaldo pregunta
  siempre y, sin servidor del modelo, se arranca sin LLM.
- **Tarjeta del agente** con la decisión y qué se aprueba; eco del MDR tras una contención del agente.
- **Justificación descartada visible**: si el modelo responde pero no pasa el anclaje, la tarjeta y
  el detalle dicen por qué.
- **Detalle del visor**: parte líneas en lugar de desbordar en horizontal.
- **Banco de pruebas**: `pruebas.evaluar` compara la clase.

---

## Tanda 2: la demo sin LLM y lo que se ve en pantalla (≈2 días)

**A8. La plantilla es la justificación del producto, pero se presenta como avería y omite la razón decisiva.** M
- `analisis.py:67-84`:
  - sufijo «[justificación de plantilla — baseline, no modelo]»;
  - en un FP por origen legítimo dice «el auditor confirma que ssh está expuesto… Clasificada como
    fp_actividad_legitima», que se lee como contradicción.
- Hacer:
  - `clasificar` devuelve un `motivo` (la rama que decidió: origen legítimo declarado; ráfaga N ≥ umbral que prevalece sobre el origen; familia encaminada a `<ruta>`; fuera del perímetro; sin IP de origen);
  - la plantilla cita ese motivo;
  - quitar el sufijo y subir la versión a `plantilla-1` (`triaje.py`, `justificador_llm.py`);
  - visor: píldora «determinista» en lugar de «plantilla» (`Decisiones.tsx:14-29`) y ocultar el bloque RAG si no hay pasajes. El texto del bloque RAG (`Decisiones.tsx:47-55`) dice que solo se activa en accesos a credenciales, y es falso;
  - pasar la suite de evaluación: mide el anclaje de la plantilla.

**A9. Los KPI del visor usan nombres del informe con otro significado.** S
- `tablero.py:259-287`, `Metricas.tsx`, `Dashboard.tsx`:
  - la «tasa de FP» del visor (30–40 %) no es la del informe (0.009);
  - el «MTTR» es en realidad el tiempo del analista;
  - las `no_soportada` cuentan como automatizadas.
- Hacer:
  - renombrar: «alertas descartadas como ruido del SIEM», «escalado a humano», «tiempo hasta el veredicto del analista», «repeticiones suprimidas»;
  - sacar las `no_soportada` del porcentaje automatizado;
  - test de Métricas.

**A10. La vista Equipos da una postura falsa.** S
- `Equipos.tsx:45-50`, `:76-77`: marca como «bloqueado» lo que el analista rechazó, cuenta los FP
  como ataques y rotula las enrutadas como «sin acción».
- Hacer:
  - `_resumen_traza` expone `contencion` (contenida | fallida | retenida | enrutada | sin_accion | revertida) y `dispositivo`, con la misma lógica que `datos.contencionDe`;
  - Equipos y Decisiones usan ese campo.

**A11. Feed de Decisiones.** S
- Hoy: lo más antiguo arriba, la hora en UTC cruda, sin columna de origen y las supresiones anónimas.
- Hacer:
  - orden por índice descendente;
  - hora local con `Intl.DateTimeFormat`, dejando el ISO en el `title`;
  - columna Origen y aviso «últimos 50 de N»;
  - supresión legible: «↩ IP → activo · familia: +N (ya decidido en sN, <desenlace>)», con enlace a sN; el registro ya guarda activo y desenlace;
  - casilla «ocultar actividad propia», activada por defecto.

**B5. La API local admite CSRF y trata una respuesta inválida como «rechazar».** S
- `tablero.py` responde con `Access-Control-Allow-Origin: *`, no valida Content-Type, Origin ni Host,
  y en `stream.py` una respuesta fuera del menú cuenta como «rechazar».
- Hacer:
  - proxy `/api` en `vite.config.ts` y quitar CORS;
  - rechazar cualquier Origin ajeno y exigir `application/json`;
  - `paso` obligatorio;
  - 400 ante una respuesta fuera del menú, sin tocar la cola;
  - actualizar `test_tablero.py` (hoy fija el CORS abierto).

**B6. Arrancar la demo con un solo comando.** S
- `reiniciar.sh`:
  - la traza se nombra por minuto (`%H%M`): dos reinicios en el mismo minuto comparten fichero. Usar `%H%M%S`;
  - `export TRIAJE_ANCLA=${TRIAJE_ANCLA:-127.0.0.1:514}` (no crea bucle: el adaptador descarta el grupo triaje; probar una vez en vivo);
  - construir el visor o avisar si falta `visor/dist` o está más viejo que `src`.
- Banner: perfil y hallazgos cargados; `/` sirve una página de ayuda si falta el build.
- Opcional: `banco.sh demo`, que encadene restaurar → test → reiniciar.

**B6b (nuevo, 30/09). Avisar si el conector va a usar la contraseña de laboratorio.** S
- Si el banco se recrea (p. ej. tras reiniciar WSL), se pierde la clave del conector en `mdr-siem`
  y `conector.ejecutor_por_defecto` cae en silencio al modo contraseña (`msfadmin`).
- Resultado: ninguna contención funciona (rc 5 en todos los nodos) y los logins fallidos del propio
  MDR llegan como «fuerza bruta desde 10.100.0.10».
- Hacer: al arrancar con `TRIAJE_NODO_GESTION` apuntando al banco y sin clave aprovisionada,
  **avisar en grande** («ejecuta `sh lab/banco/banco.sh aprovisionar`») o negarse a arrancar.
- Mientras tanto: tras cada `up` del banco, `sh lab/banco/banco.sh aprovisionar`.

**B6c (nuevo, 30/09). Marcar las decisiones provocadas por los fallos del propio MDR.** S
- Si el origen es `ip_gestion`, la familia es de acceso y hubo SSH fallidos del MDR a ese nodo en
  la ventana (`ActividadMDR`), la tarjeta y el detalle deberían decirlo.
- Mantener el triaje: un nodo de gestión comprometido tiene que seguir detectándose.

**B7. El lanzador de ataques contamina la secuencia de la demo.** S
- `lab/banco/demo.py`:
  - pregunta «¿deshacer?» antes de que el MDR decida;
  - la preparación de E1 persiste;
  - rota también los orígenes internos, con lo que K1 pierde su cascada y A1 deja de ser «taquilla»;
  - hay una espera de 65 s.
- Hacer:
  - menú con «d) deshacer último» y «R) restaurar»;
  - E1 retira su preparación al lanzar otro caso;
  - rotar solo orígenes externos;
  - quitar la espera;
  - CASCADA al final, marcada «(sin MDR)».

**B8. La salud del laboratorio puede engañar.** S
- `banco.sh status` no comprueba el plano de datos; tras un reinicio de WSL los nodos siguen «Up»
  sin sus IP 10.x.
- Hacer:
  - sondear 10.10.0.10 y, si falla, mostrar «ROTO → down + up»;
  - añadir `edad_seg` a la salud;
  - pintar «—, sin monitor» en lugar de «0 %».

**B9. La API relanza docker y relee la traza en cada sondeo.** S
- Hacer:
  - caché de 2 s para la salud;
  - un único sondeo en App;
  - verificar la cadena bajo demanda o cachearla por (mtime, tamaño);
  - guarda de «petición en vuelo» en `useSondeo`.

**B10 (resto). Tests.** S
- `npm run typecheck` hoy no comprueba nada: usar `tsc -b`.
- Añadir las dependencias que faltan en `useSondeo`.
- Tests de Metricas, Salud y App.
- Silenciar los prints de las suites Python.

**B11. Deuda menor.** S
- Cada contención abre 4 SSH: reutilizar la verificación.
- Añadir `perfil.validar` al arrancar; `rafaga.ventana_s` se ignora hoy.
- Test de validación del catálogo: verificaciones que no discriminan; `MATAR_CONEXION` con el éxito invertido.
- Retirar `orden.IP_DE_NODO` y `conector._AUDITOR` del camino del banco.
- Visor:
  - README y favicon siguen siendo los de la plantilla Vite;
  - mapa de clases repetido;
  - botón «Volver» en el submenú de reclasificar;
  - filas que no se abren con teclado.

**Decisión del LLM (E1).** El daemon usa el modo estructurado `llm-7e`, que nunca se ha medido; la
evaluación usa el libre `llm-6`. Probado el 30/09 con Qwen2.5-3B: 5/5 anclados en los dos modos y el
libre algo más limpio. Recomendado: `stream.py`, `construir_justificar_fn`, `estructurada=False`
(una línea).

**Idea anotada, sin decidir (30/09).**
- Hoy el anclaje descarta algunos textos correctos del Qwen: explican bien la ráfaga, pero no nombran
  literalmente la IP ni el activo.
- Opción: en modo estructurado, campos obligatorios `origen` y `activo` en el esquema JSON,
  restringidos a los valores reales de la alerta, que el código pone al principio del texto.
- Se garantizaría que la justificación nombra la alerta sin que el modelo pueda inventar datos.
- Decidirlo después de medir los modelos en GPU (ver `EVALUAR-LLM-EN-GPU.md`).

---

## Tanda 3: documentación y evidencia (≈1–2 días)

Regla: los registros congelados (`archivo/`, campañas con fecha, `lab/banco/verificaciones.md`, el
plan de trabajo) no se corrigen; como mucho se anotan como históricos. ★ = lo que el tutor ve primero.

- **★ README.md**:
  - cifras vigentes: 300/106, recall 1.000 frente a 0.920, FP 0.009 frente a 0.310, escalado 0.297, 0 automáticas indebidas, más la nota de la ráfaga causal;
  - el LLM «opcional, medido en GPU el 10–11/09» (hoy dice «verificado en vivo» y 487 tests);
  - filas para la consola web, el banco y el lanzador.
- **★ RUNBOOK.md**:
  - `sh reiniciar.sh` como arranque canónico, que hoy no aparece en ningún `.md`;
  - con `--web` se aprueba en el navegador: quitar el «doble canal»;
  - paso de build del visor;
  - `--con-llm` y `--agente` como experimentales;
  - `aprovisionar` después de cada `up`;
  - fila «no llegan alertas → allowed-ips 172.20.20.0/24»;
  - `hallazgos.json` es entrada viva;
  - `revertir` (con el daemon vivo ya funciona, con `--indice`).
- **★ estado-y-riesgos.md**:
  - cifras y número de tests;
  - D11: el contador en vivo ya existe;
  - D13: «instantánea en los tres modos» es falso con LLM;
  - I-6: indicar la máquina objetivo;
  - §7: IPv6 como límite y la memoria de supresión.
- **★ docs/pruebas/08-laboratorio-banco.md, lab/banco/README.md, pruebas.py y casos.py**:
  - K1 ya no es un fallo: avisa la cascada de los dependientes declarados; atm cae sin predecirse (K3);
  - documentar los casos 6–8;
  - la regla telnet 100210 no existe (es la 5602);
  - regenerar las guías del banco con `--guias`.
- **guia-de-operacion.md**:
  - sin LLM por defecto;
  - flujo `--web` y el banco;
  - revertir;
  - la traza ya guarda contexto y horas;
  - §9 marcado como histórico.
- **prototipo/README.md**:
  - tabla de tipos de registro: decision, actividad_suprimida, actividad_propia, error, reversion;
  - campos nuevos: `contexto`, `ejecutado_en`, `decidido_en`, `incidente`, `impacto_efectivo`, `veredictos_escalada`, `justificacion_descartada`;
  - versiones `plantilla`, `llm-6` y `llm-7e`;
  - sección «API del tablero».
- **docs/pruebas/09-tablero-web.md**: reescribir con los flujos actuales (escalada por salto, cascada, 409, banner, `?limite`, tarjeta del agente).
- **docs/pruebas/01, 03, 06 y 07**: afirmaciones sobre el hardware y `--con-llm` siempre activo.
- **requisitos.md y matriz-trazabilidad.md**:
  - columnas «Cumplimiento» y «Evidencia»;
  - RNF-09 promete una «cola manual» que no existe;
  - RF-11 con cifras de la partición antigua;
  - RNF-12 cita §8 cuando es §9;
  - medir RNF-05 en el banco con `docker stats`.
- **evaluacion/resultados/README.md**:
  - el anexo de 600 alertas es anterior a D16: regenerarlo o marcarlo;
  - declarar que la ráfaga se mide en lote (±60 s) y dar también la cifra causal (0.908).
- **Informe LaTeX** (`documentacion/report/`), más a fondo en la Tanda 4:
  - grep de control `0,282|0,296|233 alertas|cuarenta y dos`;
  - declarar la ráfaga en lote frente a causal (`ip5`, `ip6:793`, que dice «Se verificó en vivo»);
  - la «contención instantánea» (`ip5:255-259`);
  - 353 pruebas (`ip5:279-283`).
- **Limpieza**:
  - no versionar `lab/campañas/2026-09-24-banco-regresion/`;
  - borrar `modelos/*.part` y los `*:Zone.Identifier`.
- **Evidencia**:
  - corrida completa `python3 -m lab.banco.pruebas --con-vivo` versionada como registro vigente;
  - ensayar el guion de la demo (abajo).

## Tanda 4: producto e informe

| # | Mejora | Esf. |
|---|---|---|
| D1 | KPI de contención en el Panel (contenidas, fallidas, escaladas, retenidas, pendientes), tendencia | S |
| D2 | Repeticiones plegadas bajo su decisión (+N), con clic a la de referencia | S |
| D3 | `GET /api/estado` y cabecera con el modo (perfil, justificador, ejecutor, ancla, ventana) | S |
| D4 | Tiempo hasta contener (alerta → contención verificada; los campos ya existen) | S |
| D5 | Clic en un equipo → Decisiones filtradas | S |
| D6 | **Revertir desde la consola** (`POST /api/revertir`, botón con confirmación, «contenciones activas»); la memoria de supresión se entera | M |
| D7 | «Por qué» completo del filtro (umbral, `humano_siempre`, veto de gestión) en la traza y la tarjeta | M |
| D8 | Nota del analista en el veredicto | S |
| D9 | Prioridad de las `no_soportada` desde el nivel del SIEM | S |
| D10 | `tecnica_familia` cuando el SIEM no trae técnica (telnet sale «s/téc.») | S |
| D11 | Antigüedad de cada tarjeta en Aprobaciones | S |
| D12 | Marcar como mal clasificada una decisión automática (feedback RF-12) | M |
| D13 | Caducidad opcional de los bloqueos (TTL por perfil) | M |

Después: el **informe LaTeX** (secciones nuevas de operación en vivo, familias y el banco como
validación cualitativa, además de lo de la Tanda 3) y la revisión con los tutores.

---

## Menores aplazados de la revisión de la Tanda 1

1. La CLI de revertir lee el hash y el tamaño sin lock antes de su primera escritura (ventana de
   microsegundos). Arreglo: `_tamano=None` cuando hay `ruta`.
2. La clave comodín perimetral no mira qué activos cubre ese cortafuegos (`alcance_en`). Inocua en
   las topologías actuales.
3. `ejecutadas` puede contarse dos veces si el host aplicó la regla sin verificarla y luego se
   resuelve la escalada.
4. `revertir --indice abc` lanza un ValueError; las reversiones antiguas sin `indice_revertido`
   bloquean por id.
5. Una contención fallida se reintenta en cada repetición sin enfriamiento (~20 s de SSH contra un
   host caído).
6. La tarjeta dice «X no respondió» aunque X sea un cortafuegos que aplicó la regla pero no la verificó.
7. La verificación también casa la IP como destino de una regla DROP (el catálogo solo escribe `-s`).
8. En modo terminal, la pregunta de escalada sale por `print`.
9. Comprobar en vivo que `grep -wF` se comporta igual en los nodos del banco (BusyBox o grep antiguo).

## Decisiones que siguen abiertas

- **#8**: clase propia para el reconocimiento. Cambia las métricas y el informe. Si se aplaza, al
  menos comprobar la familia en `pruebas.evaluar`; la traza ya la guarda en `contexto`.
- **Hallazgos del banco**: mover `lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json`, que es
  entrada viva y se editó a mano, a `lab/banco/hallazgos.json` y actualizar los documentos que lo citan.
- **Modelo para la demo**: se decide con `EVALUAR-LLM-EN-GPU.md` (8B, Qwen2.5-3B, Foundation-Sec-1.1).
- **Subir `main`**: el `main` local va por delante de `origin/main`; las ramas de trabajo ya están en el remoto.

## Guion de la demo (~15 min, sin LLM)

```bash
sh lab/lab.sh up banco            # si el banco no está levantado
sh lab/banco/banco.sh aprovisionar
sh lab/banco/banco.sh restaurar
sh reiniciar.sh
```

1. **D1**: atacante externo, contención automática en web-banking.
2. **A1**: la taquilla (activo interno) queda retenida. Rechazar; al repetirse, «ya decidido» y Equipos correcto.
3. **K1**: cascada. Aviso y diálogo; aprobar; atm cae (K3, dependencia no declarada).
4. **E1**: web-banking no responde, así que sale una tarjeta de escalada a fw-core con su alcance.
5. **EXPLOIT**: amenaza enrutada al equipo de AppSec, sin contención.
6. **Trazas**: «Verificar la cadena».
7. **Panel y Métricas**.
8. **Ctrl+C**: el resumen de la sesión con cifras reales.

Entre bloques, `sh lab/banco/banco.sh restaurar`. Revertir en vivo solo si D6 está hecho.
