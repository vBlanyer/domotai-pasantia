# Plan de prueba: aprovisionar el banco desde el panel de Conectividad, sin el script

> **Objetivo.** Arrancar el MDR con el laboratorio del banco **sin** ejecutar
> `sh lab/banco/banco.sh aprovisionar`, y dejar cada equipo listo para que el conector contenga en él
> usando solo la vista **Conectividad** del visor, incluido un equipo **nuevo** que llega a la red.
> Al final, comprobar que las contenciones reales y la rotación de la clave funcionan.
>
> **Estado.** Validado de punta a punta contra el laboratorio el 9 nov 2026: 12 equipos verificados
> (los 10 del banco, el auditor y el equipo nuevo `pagos-qr`), contenciones reales en atm, web-banking
> y fw-core, y rotación completa de la clave. Seguridad de la vista y puntos abiertos:
> [CONECTIVIDAD-PENDIENTE-REVISION.md](CONECTIVIDAD-PENDIENTE-REVISION.md).

Duración estimada: unas **2 h** la primera vez (15 min de arranque, 5 min por equipo, 30 min de
contención y 10 min de rotación).

---

## Qué sustituye el panel

El script hace tres cosas, y el panel las tres:

| Paso del script | En el panel |
|---|---|
| 1. Generar la clave del conector en el nodo de gestión | **Generar la clave del conector** (aparece cuando no hay ninguna) |
| 2. Crear el usuario `triaje`, su clave y el sudoers en cada equipo | **Paquete** de alta o de corrección, que ejecuta el «administrador» (en el laboratorio, `docker exec`) |
| 3. Fijar la clave del host de cada equipo | **Fijar la clave del host**, comparando la huella que imprime el paquete |

Y añade lo que el script no tenía: el **papel** de cada equipo (su sudoers es solo lo que necesita y el
motor no le propone lo que no admite), la **prueba con deriva**, el **alta de equipos nuevos** y la
**rotación** de la clave.

---

## Fase 0 · Dejar el laboratorio sin aprovisionar (10 min)

Un `up` limpio recrea todos los contenedores: los equipos pierden el usuario `triaje` y su sudoers, y
el nodo de gestión pierde la clave del conector y su `known_hosts`. Es el punto de partida de un cliente
nuevo. El banco trae además **`pagos-qr`** (`10.70.0.10`): un equipo con sshd que **no** está en el
perfil ni lo toca el script; es el equipo nuevo que se da de alta en la fase 4.

```bash
# desde la raíz del repositorio
sh lab/banco/banco.sh down
sh lab/lab.sh up banco          # despliega el banco y arranca Wazuh (NO aprovisiona)
sh lab/banco/banco.sh test      # conectividad y servicios sanos (no necesita el conector)
```

**No** ejecutes `sh lab/banco/banco.sh aprovisionar`.

Para empezar de cero, aparta el estado de Conectividad del daemon, que vive en `run/` y sobrevive a un
`up` (papeles, altas, pruebas). No es obligatorio: las pruebas hechas con otra clave del conector ya no
se muestran como vigentes, pero los papeles y las altas sí se conservarían.

```bash
mkdir -p run/archivo-$(date +%F)
mv run/conectividad-*.json run/conectividad-*.jsonl run/conectividad-*.yml run/inventario-operativo.yml \
   run/archivo-$(date +%F)/ 2>/dev/null; ls run/archivo-$(date +%F)/
```

**Comprobación de partida** (todo debe salir «no», y pagos-qr con su IP):

```bash
docker exec clab-banco-mdr-siem sh -c 'ls /root/.ssh/triaje 2>/dev/null && echo "clave: si" || echo "clave: no"'
docker exec clab-banco-web-banking sh -c 'id triaje >/dev/null 2>&1 && echo "triaje: si" || echo "triaje: no"'
docker exec clab-banco-pagos-qr sh -c 'ip -4 addr show eth1 | grep inet'
```

---

## Fase 1 · Arrancar el MDR y generar la clave del conector (10 min)

### 1.1 Arrancar el daemon

Elige cómo firmas:

**A. Laboratorio, consola abierta (rápido).** Firmas con un nombre que escribes, sin verificar.

```bash
TRIAJE_CONECTIVIDAD_ABIERTA=1 sh reiniciar.sh
```

**B. Con token de operador (firma verificada).** Recomendado si vas a enseñar el resultado.

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"     # genera tu token y guárdalo
TRIAJE_CONSOLA_OPERADORES='{"PEGA-AQUI-EL-TOKEN": "Blanyer.Vielma"}' sh reiniciar.sh
```

El daemon arranca sin clave y lo dice: «conector sin clave… no se ejecutará ninguna contención hasta que
exista». Es lo esperado. Queda en primer plano en esa terminal (Ctrl+C para pararlo); abre otra para
el resto.

### 1.2 Entrar en la consola

1. Abre `http://127.0.0.1:8787` y recarga con **Ctrl+Shift+R**.
2. Variante A: escribe tu nombre y «Continuar». Variante B: pega el token y «Entrar».
3. Menú **Configurar → Conectividad**.

**Lo que debes ver:** la franja «**Falta la clave del conector.** Genérala aquí abajo para empezar» y,
en la tarjeta «Clave del conector», «No hay clave del conector» con el botón para generarla. Los demás
botones esperan a que exista la clave.

### 1.3 Generar la clave del conector

1. Elige el tipo: **ed25519 (recomendada)**. Todos los equipos del banco tienen OpenSSH actual. (RSA
   3072 es para equipos con OpenSSH antiguo, tipo Metasploitable.)
2. **Generar la clave del conector.**

**Esperado:** la huella `SHA256:…` aparece en la tarjeta, la franja pasa a «Firmas como…» o «Consola
abierta, opción de laboratorio activa», y aparecen **+ Añadir equipo**, **Rotar la clave del
conector…** y **Probar todos**. No hace falta reiniciar el daemon: el conector empieza a usar la clave
en cuanto existe. La privada se crea y se queda en el nodo de gestión; el panel solo ve la pública.

Todos los equipos salen **sin aprovisionar**: aún no tienen usuario ni clave del host fijada.

---

## Fase 2 · Ensayo con el auditor (10 min)

El auditor (`10.100.0.20`) no es objetivo de ninguna contención: es el sitio seguro para aprender el
flujo. Sigue la fase 3 con estos datos: papel **Puesto**, las acciones que trae, sin servicios ni
cuentas. Si queda en **verificada**, sigue con los equipos del banco.

---

## Fase 3 · Aprovisionar cada equipo del banco (5 min por equipo)

### 3.1 Procedimiento (igual para cada equipo)

1. **Elegir el equipo.** Púlsalo en la tabla; el inspector se abre a la derecha.
2. **Declarar su papel.** Sección «Papel y reglas» → **Editar**.
   - Elige el **papel** de la tabla 3.2 y deja las acciones que trae.
   - Si la tabla dice «cualquier cuenta», marca **Cualquier cuenta salvo las del sistema**.
   - **Guardar y generar el paquete de corrección.**
3. **Ver el paquete.** El asistente pasa al paso «Paquete de corrección» y enseña el script del equipo.
   Ahí no hay que hacer nada más: pulsa **Hecho: vuelve a probar el equipo** para cerrarlo.
4. **Ejecutarlo en el equipo, como root.** En el laboratorio el «administrador del cliente» eres tú.
   **Una sola vez por terminal**, pega esta función (baja el paquete del equipo y lo ejecuta en él):
   ```bash
   alta() { [ -n "$1" ] || { echo "Uso: alta <equipo>   (por ejemplo: alta core-db)"; return 1; }
     curl -s "http://127.0.0.1:8787/api/conectividad/paquete?equipo=$1&formato=script" \
     | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit('No se generó el paquete de '+sys.argv[1]+': '+d['error']) if 'error' in d else open('/tmp/alta-'+sys.argv[1]+'.sh','w').write(d['contenido'])" "$1" \
     && docker exec -i clab-banco-$1 sh < /tmp/alta-$1.sh; }
   # variante B (token): añade  -H "Authorization: Bearer PEGA-AQUI-EL-TOKEN"  detrás de  curl -s
   ```
   Y para cada equipo, **con su nombre**:
   ```bash
   alta web-banking
   ```
   Funciona desde cualquier carpeta. Si prefieres no usar la terminal para bajarlo: **Copiar** o
   **Descargar** en el paso 3, guárdalo como `/tmp/alta-web-banking.sh` y ejecuta
   `docker exec -i clab-banco-web-banking sh < /tmp/alta-web-banking.sh`.
   **Salida esperada:** varios `aviso: ss/tc/service no está instalado; se omite la regla…` (normal en
   el banco, ver G5), «Alta lista. Huella de la clave del host» y dos líneas `SHA256:…`.
   **Apunta la huella ED25519.**
5. **Fijar la clave del host.** En el inspector, sección **Fijar la clave del host** → **Leer la clave
   del equipo**. Compara la huella con la que apuntaste.
   - **Si no coincide, para:** alguien está en medio.
   - Si coincide: marca **Coincide con la que imprimió el equipo** → **Fijar esta clave**.
6. **Probar.** Abajo del inspector → **Probar sin guardar**.
   **Esperado:** **verificada**, con los tres pasos en verde (entra y ejecuta un comando del catálogo;
   sudo deniega lo que está fuera; lo que sudo permite coincide con su papel: «X de Y reglas
   presentes; faltan N»). En la tabla, «Reglas en el equipo» sale **incompletas**: en el banco es lo
   esperado (G5). Lo que **no** debe salir nunca es **no coinciden** (sobra algo).
7. **Siguiente equipo.** Entre dos pruebas del mismo equipo hay que esperar 10 s (el panel lo avisa).

### 3.2 Datos de cada equipo

IPs y zonas ya las trae el perfil. Puerto `22` y usuario `triaje` (por defecto) en todos.

| Equipo | IP | Zona | Papel | Cuentas | Por qué |
|---|---|---|---|---|---|
| web-banking | 10.10.0.10 | DMZ | Servidor | **cualquier cuenta** | Recibe bloquear IP, cortar conexiones, limitar banda y bloquear la cuenta que crea el atacante (`backdoor`) |
| api-movil | 10.20.0.10 | DMZ | Servidor | | Bloquear IP |
| swift-alliance | 10.30.0.10 | DMZ | Servidor | | Bloquear IP |
| middleware | 10.40.0.10 | Core | Servidor | | Bloquear IP |
| core-db | 10.50.0.10 | Core | Servidor | **cualquier cuenta** | Bloquear IP y el caso de abuso de cuenta del banco |
| hsm | 10.60.0.10 | Core | Servidor | | Bloquear IP |
| atm | 10.210.0.10 | Sucursal | Puesto | | Bloquear IP |
| taquilla | 10.200.0.10 | Sucursal | Puesto | | Bloquear IP |
| fw-core | 10.0.0.1 | — | Cortafuegos o borde | | Ejecuta el aislamiento y el bloqueo de destino de los equipos de dentro |
| fw-edge | 10.0.0.254 | — | Cortafuegos o borde | | Borde exterior |
| mdr-siem | 10.100.0.10 | SOC | — | — | Canal de gestión del MDR: protegido, no se toca |

«Servicios que se pueden parar» queda **vacío en todos**: los equipos del banco no tienen `service`.

**Cualquier cuenta salvo las del sistema:** el sudoers de `passwd` admite cualquier cuenta (como el
aprovisionamiento clásico) y el motor veta root, las cuentas de servicio y la del conector. Sirve para
las cuentas que crea el atacante, cuyo nombre no se conoce de antemano.

### 3.3 Al terminar la fase 3

- **Probar todos:** «Los 11 equipos verificados» (10 del banco y el auditor).
- Cabecera: «Conexión verificada» igual a «Equipos contenibles», y «Sin aprovisionar» en 0.

---

## Fase 4 · Dar de alta el equipo nuevo, pagos-qr (10 min)

1. **+ Añadir equipo.**
2. **Inventario:** nombre `pagos-qr`, IP `10.70.0.10`, zona **DMZ**, función «Pagos con código QR»,
   criticidad **alta**, interfaz `eth1`, depende de **middleware**. **Siguiente: papel y reglas.**
3. **Papel y reglas:** **Servidor**, acciones que trae, sin servicios ni cuentas.
   **Generar el paquete de alta.** El equipo queda **alta pendiente** en la tabla: el motor aún no lo ve.
4. **Paquete de alta:** ejecútalo con `alta pagos-qr` (la función del paso 3.1).
   Apunta la huella. **Ya está ejecutado.**
5. **Verificar y dar de alta:** **Leer la clave del equipo**, compara la huella, marca **Coincide…** →
   **Dar de alta pagos-qr**.

**Esperado:** la prueba completa en verde y pagos-qr pasa a **verificada**, en la zona DMZ. Desde ese
momento el motor lo ve (aparece en **Red**) y puede contener en él.

---

## Fase 5 · Comprobar que el MDR contiene de verdad (30 min)

### 5.1 Contenciones reales

```bash
sh lab/banco/banco.sh atacar auto -q     # la tanda completa: 13 ataques, una vez
```

Espera un minuto (Wazuh → MDR) y mira en el visor:
- **Decisiones:** bloqueos de IP **contenidos** en atm y web-banking.
- **Aprobaciones:** quedan para un humano el bloqueo de cuenta, la limitación de banda, el aislamiento y
  el bloqueo de destino. El de cuenta **no** debe salir vetado (gracias a «cualquier cuenta»).
- Aprueba el **aislamiento** y el **bloqueo de destino**: se ejecutan en **fw-core** y deben quedar
  **contenidos** (comprobación: `docker exec clab-banco-fw-core iptables -S FORWARD`).

**Fallos esperados, que no son del aprovisionamiento:**
- Algunos bloqueos en web-banking salen **fallidos**: la tanda incluye el caso **E1** («la víctima no
  responde al MDR»), que añade en web-banking una regla que descarta el SSH del nodo de gestión para
  forzar la escalada a fw-core.
- **Cortar conexión** y **limitar banda** fallan en el banco porque no hay `ss` ni `tc` (G5).

Al acabar: `sh lab/banco/banco.sh restaurar` (quita los bloqueos de la tanda, también la regla de E1).

### 5.2 El papel acota al motor

1. En web-banking → **Editar**, desmarca «Cualquier cuenta» y deja la lista vacía. Guarda.
2. Lanza otra vez la tanda (o solo el ataque de abuso de cuenta del menú `sh lab/banco/banco.sh atacar`).
3. **Esperado:** esa decisión sale **vetada** con el motivo «web-banking no admite bloquear la cuenta
   backdoor: no está en su lista».
4. Vuelve a marcar «Cualquier cuenta».

### 5.3 Deriva del sudoers

1. Añade una regla de más a mano:
   ```bash
   docker exec clab-banco-hsm sh -c "echo 'triaje ALL=(root) NOPASSWD: /bin/cat *' > /etc/sudoers.d/extra && chmod 440 /etc/sudoers.d/extra"
   ```
2. **Probar sin guardar** en hsm. **Esperado:** «no coinciden», con `+ cat *` como sobrante.
3. **Generar paquete de corrección** y ejecútalo en hsm. **Esperado:** «sudoers anterior apartado
   (copia en /root): /etc/sudoers.d/extra». Vuelve a probar: «incompletas» otra vez, sin sobrantes.

Si el fichero mezclara reglas de otros usuarios, el paquete no lo toca y avisa «revísalo a mano».

### 5.4 Casos que deben fallar

| Prueba | Cómo | Esperado |
|---|---|---|
| Puerto equivocado | En un equipo, Puerto `2222` → **Probar y guardar** | La prueba falla («sin acceso») y **no se guarda**. **Descartar** |
| Probar dos veces seguidas | **Probar sin guardar** dos veces en menos de 10 s | Aviso «espera N s» |
| Huella que no coincide | En 3.1 paso 5, no marques la casilla | **Fijar esta clave** sigue desactivado |
| Sin permisos | Rearranca el daemon **sin** `TRIAJE_CONECTIVIDAD_ABIERTA` ni tokens | Franja «Consola abierta… exige un token», botones con candado |

### 5.5 Persistencia

Para el daemon (Ctrl+C) y vuelve a arrancarlo con el mismo comando de la fase 1.1. **Esperado:** cada
equipo conserva su papel, su clave del host y su última prueba, con la antigüedad.

---

## Fase 6 · Rotar la clave del conector (10 min)

Con todos los equipos verificados (si uno no responde, la rotación no se puede finalizar).

1. **Rotar la clave del conector…** → **Iniciar: generar el par nuevo**.
2. **Añadir y probar en todos.** Todas las filas en «sí» y «pasa».
3. **Retirar la clave vieja en N equipos…** → confirmar.
4. **Finalizar.** La huella de «Clave del conector» cambia; la anterior queda como copia en el nodo.
5. **Probar todos:** los 12 siguen verificados.

Si algo falla antes del paso 3, **Cancelar la rotación** lo deja todo como estaba.

---

## Si hay que volver al script

El script escribe su sudoers en `/etc/sudoers.d/conector-triaje` y el panel en `mdr-triaje`; sudo
suma los dos. Para volver al aprovisionamiento clásico sin mezclar: fase 0 de nuevo (`down` + `up`) y
`sh lab/banco/banco.sh aprovisionar`. (El revés también funciona: un paquete del panel aparta el
sudoers que dejó el script.)

---

## Lo que queda abierto

Los huecos de código que tenía la primera versión de este plan están resueltos:

| | Hueco | Estado |
|---|---|---|
| G1 | El panel no generaba la clave del conector | **Resuelto:** «Generar la clave del conector» |
| G2 | La primera clave del host pasaba por «Clave del host cambiada» | **Resuelto:** sección «Fijar la clave del host» |
| G3 | No había un equipo nuevo en el banco | **Resuelto:** `pagos-qr` en la topología (fase 4) |
| G4 | La lista de cuentas no cubría las que crea el atacante | **Resuelto:** «Cualquier cuenta salvo las del sistema» |
| G6 | El paquete de corrección no retiraba reglas añadidas a mano | **Resuelto:** aparta cualquier fichero que solo dé permisos al conector |
| G7 | Sin `TRIAJE_SSH_MODO=clave` la vista quedaba bloqueada | **Resuelto:** la vista ofrece generar la clave y el conector la toma sin reiniciar |
| G8 | Pruebas viejas en `run/` parecían vigentes | **Resuelto:** una prueba hecha con otra clave del conector o del host deja de mostrarse |

Siguen abiertos:

| | Asunto | Efecto |
|---|---|---|
| G5 | Los equipos del banco no tienen `ss`, `tc` ni `service` | Cortar conexiones, limitar banda y parar servicios no se ejecutan en el banco; las reglas salen «incompletas». Arreglarlo es cambiar la imagen `banco-nodo` (iproute2), con su efecto en el resto de pruebas del banco |
| G9 | Puntos de seguridad de la vista | Ver [CONECTIVIDAD-PENDIENTE-REVISION.md](CONECTIVIDAD-PENDIENTE-REVISION.md): auditoría fuera de la traza firmada, bloqueo solo en proceso, etc. |

---

## Hoja de seguimiento

| Equipo | Papel | Paquete ejecutado | Huella fijada | Verificada | Reglas |
|---|---|---|---|---|---|
| auditor (ensayo) | Puesto | ☐ | ☐ | ☐ | |
| web-banking | Servidor · cualquier cuenta | ☐ | ☐ | ☐ | |
| api-movil | Servidor | ☐ | ☐ | ☐ | |
| swift-alliance | Servidor | ☐ | ☐ | ☐ | |
| middleware | Servidor | ☐ | ☐ | ☐ | |
| core-db | Servidor · cualquier cuenta | ☐ | ☐ | ☐ | |
| hsm | Servidor | ☐ | ☐ | ☐ | |
| atm | Puesto | ☐ | ☐ | ☐ | |
| taquilla | Puesto | ☐ | ☐ | ☐ | |
| fw-core | Cortafuegos | ☐ | ☐ | ☐ | |
| fw-edge | Cortafuegos | ☐ | ☐ | ☐ | |
| pagos-qr (alta nueva) | Servidor | ☐ | ☐ | ☐ | |

| Prueba | Resultado |
|---|---|
| 1.3 Clave del conector generada desde el panel | |
| 4 Alta completa de pagos-qr | |
| 5.1 Contenciones reales (atm, web-banking, fw-core) | |
| 5.2 El papel veta el bloqueo de cuenta sin «cualquier cuenta» | |
| 5.3 Deriva detectada y corregida con el paquete | |
| 5.4 Puerto equivocado / freno / huella / sin permisos | |
| 5.5 Persistencia tras reiniciar | |
| 6 Rotación completa | |
