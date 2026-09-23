# 09 · Tablero web

Consola web local de observabilidad y aprobación para el daemon (`prototipo/stream.py`). No sustituye a la
terminal — es una vista adicional: el mismo menú `[Aprobar/Rechazar/Reclasificar]` que hoy se responde por
`/dev/tty` también se puede resolver desde el navegador. El **backend** vive en `prototipo/tablero.py` (API
JSON de la biblioteca estándar, con CORS) y el daemon lo embebe con `stream.py --web`; **no importa nada de
`lab/`** (la salud se lee como JSONL genérico y las dependencias entre activos llegan del perfil). El
**frontend** es un SPA **React** (Vite + TypeScript + shadcn-ui + Tailwind + Zod) en `visor/`, una pieza
aparte con la stack de la empresa que consume esa API. El daemon sirve el build de React (`visor/dist`); en
desarrollo se usa `npm run dev`.

**Correr el visor:**

```bash
cd visor && npm install          # una vez
npm run build                    # genera visor/dist (lo sirve el daemon --web)
# o, en desarrollo, con recarga en caliente contra el daemon --web:
npm run dev                      # Vite en http://127.0.0.1:5173 (CORS habilitado)
```

## Cómo se arranca

Con el banco levantado y el monitor de salud corriendo (ver [08](08-laboratorio-banco.md)):

```bash
sh lab/lab.sh up banco && sh lab/banco/banco.sh aprovisionar
```

Y el daemon con `--web` en vez de (o junto a) la terminal:

```bash
python3 -m prototipo.stream <fuente-wazuh> prototipo/perfiles/bancario.yml \
    lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --web
```

`<fuente-wazuh>` es la misma fuente que en el Nivel 3 (ver [08 §3](08-laboratorio-banco.md), terminal 2):
normalmente `-` (stdin) canalizando `docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F
/var/ossec/logs/alerts/alerts.json'`. `--web` acepta un puerto opcional (`--web 9000`); por defecto es
`8787`. El resto de flags del daemon (`--con-llm`, `--ventana-agrupacion`, `--salida`, `--agente`, …)
conviven con `--web` sin cambios.

El servidor arranca en un hilo en segundo plano — el bucle de triaje sigue igual, solo que el prompt del
menú, cuando hace falta humano, ahora también lo espera el tablero. La consola queda en:

```
http://127.0.0.1:8787
```

## Los cuatro paneles

- **Salud** — una fila por servicio (`● OK` / `✖ CAÍDO`), de qué depende, y cuántos de los servicios están
  caídos ahora mismo. Se lee del JSONL que escribe `lab/banco/monitor.py`; sin monitor, el panel degrada a
  "sin datos del monitor" en vez de romperse.
- **Decisiones** — el feed de las últimas decisiones ya resueltas (cuándo, activo, clase, acción final, si
  fue automática o exigió humano), leído directamente de la traza.
- **Aprobaciones** — la cola de decisiones **pendientes ahora mismo**: cada tarjeta muestra el contexto del
  incidente (las mismas líneas que verías en terminal) y el prompt exacto, con botones para responder.
- **Trazas** — el histórico completo más un botón "verificar" que corre la verificación de la cadena de
  hashes (`traza.verificar_cadena`) y dice si está íntegra o dónde se rompió.

Los cuatro se refrescan solos cada 2 s (sondeo simple, sin WebSockets).

## Nota de seguridad (honesta)

El servidor liga **solo a `127.0.0.1`** — no es alcanzable desde otra máquina de la red. Pero **no tiene
autenticación**: cualquier proceso o pestaña del navegador en la misma máquina puede leer el estado y, más
importante, **puede aprobar**. Pulsar "Aprobar" en el panel de Aprobaciones ejecuta la acción real (por
ejemplo, un `iptables` por SSH contra un activo real del laboratorio o del cliente) exactamente igual que
responder `1` en la terminal. Es un tablero para el analista en su propio puesto, no una consola
multiusuario ni algo para exponer más allá de `localhost`. Login y TLS quedan como trabajo futuro (ver
`documentacion/00-general/estado-y-riesgos.md`, nota D11).

## Nota de limitación (v1): botones del submenú de reclasificar

Los botones "Aprobar (1)" / "Rechazar (2)" del panel de Aprobaciones son fiables **solo para el menú
principal de veredicto** (`1) aprobar · 2) rechazar · 3) reclasificar`), porque ese menú tiene siempre las
mismas tres opciones en el mismo orden. Cuando reclasificas, aparece un **submenú de clases** cuyas
opciones son dinámicas (las clases del catálogo menos la actual del incidente): ahí "Aprobar (1)" **no
aprueba nada** — selecciona lo que sea que esté listado como opción 1 en ese submenú concreto, que casi
nunca es "aprobar". Para el submenú de clase, ignora las etiquetas de los botones y usa el **texto real**
que aparece en el bloque `<pre>` de la tarjeta (la lista numerada de clases) junto con el **campo de texto
libre** para escribir el número correcto. Mejora prevista para v2: etiquetar los botones a partir de las
opciones ya parseadas del prompt, en vez de con números fijos.

## Verificación de extremo a extremo (manual)

Lo único que las pruebas unitarias no cubren es aprobar de verdad desde el navegador. Pasos:

```
1. sh lab/lab.sh up banco && sh lab/banco/banco.sh aprovisionar
2. (arranca el monitor si no corre; ver 08)
3. python3 -m prototipo.stream <fuente-wazuh> prototipo/perfiles/bancario.yml \
       lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --web
4. Abre http://127.0.0.1:8787 → pestaña Salud muestra los nodos; lanza un ataque que exija
   humano (p. ej. A1 del banco de pruebas) → aparece en Aprobaciones → pulsa Aprobar/Rechazar →
   la decisión pasa a Decisiones y a la traza; verifica la cadena en Trazas.
```

**Esperado:** la pestaña Salud muestra los servicios del banco con su estado; al lanzar el caso A1 (equipo
interno comprometido, ver [08 §4](08-laboratorio-banco.md)) aparece una tarjeta nueva en Aprobaciones con
el contexto del incidente y el prompt `1) aprobar 2) rechazar 3) reclasificar`; al pulsar "Aprobar (1)" se
ejecuta el bloqueo real (verificable con `docker exec ... iptables -S INPUT`), la tarjeta desaparece de
Aprobaciones, la decisión aparece en Decisiones, y la pestaña Trazas la lista con la cadena marcada como
íntegra.

Si el tablero se abre **sin** daemon corriendo (modo solo lectura), Salud y Trazas siguen sirviendo lo que
haya en disco o degradan a vacío/"sin datos", y Aprobaciones queda vacía — no hay pendientes que resolver
sin un daemon vivo detrás.
