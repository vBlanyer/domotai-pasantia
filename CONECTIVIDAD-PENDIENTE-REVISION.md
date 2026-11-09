# ⚠ Vista «Conectividad»: pendiente de revisión de seguridad

> **Estado (4 nov 2026):** integrada y funcionando, con alta de equipos, papeles, deriva del sudoers y
> rotación de la clave validados en vivo contra el laboratorio. **No apta para producción** hasta cerrar los
> puntos abiertos de este documento.
>
> Es la vista más delicada del visor: gestiona cómo el MDR entra por SSH a los equipos del cliente.
> Un error aquí puede filtrar datos de la red o permitir que alguien redirija o bloquee el conector.

## Qué es

Vista del grupo **Configurar** del visor que permite, sin tocar código:

- ver el modo del conector, la huella de su clave y la clave del host fijada de cada equipo;
- cambiar el **puerto** y el **usuario** SSH de cada equipo, y el **usuario por defecto**;
- **probar** la conexión a un equipo: entra, ejecuta un comando del catálogo, comprueba que sudo deniega
  un testigo inocuo (`true`) y compara lo que sudo permite con el **papel** del equipo (deriva);
- **aceptar una clave del host nueva** cuando un equipo la cambia;
- **dar de alta un equipo** (asistente en cuatro pasos: inventario, papel y reglas, paquete de alta que
  ejecuta el administrador del cliente, y verificar la huella y probar). El MDR no ve nunca una
  credencial de administrador;
- declarar el **papel y las reglas** de un equipo existente y generar su **paquete de corrección**;
- **generar la clave del conector** cuando no hay ninguna (despliegue nuevo, sin el script); si el daemon
  arrancó sin clave, el conector la toma en cuanto existe, sin reiniciar y sin caer nunca a la contraseña;
- **fijar la clave del host por primera vez**, comparando la huella que imprime el paquete en el equipo;
- **rotar la clave del conector** en tres fases (añadir y probar la nueva, retirar la vieja, finalizar),
  con cancelación mientras no se haya retirado la vieja en ningún equipo.

Ficheros que escribe el daemon, junto a la salida: `conectividad-operativa.yml` (ajustes, el conector los
lee por encima del entorno vía `TRIAJE_CONECTIVIDAD`), `inventario-operativo.yml` (equipos dados de alta y
papeles, fusionado en el perfil vivo: el motor lo ve), `conectividad-pruebas.json` (última prueba de cada
equipo), `conectividad-rotacion.json` (rotación en curso) y `conectividad-auditoria.jsonl` (cada prueba,
lectura y cambio, con el operador).

## Ficheros

| Capa | Fichero |
|---|---|
| Lógica (ajustes, prueba, huellas, known_hosts) | `prototipo/accion/conectividad.py` |
| Uso de los ajustes en el SSH real | `prototipo/accion/conector.py` (`_ajustes`, `modo_actual`, `ejecutor_con`, `correr_donde_las_claves`) |
| API web | `prototipo/servicio/conectividad_web.py` y las rutas `/api/conectividad*` en `prototipo/servicio/tablero.py` |
| Ruta del fichero de ajustes | `prototipo/servicio/stream.py` (fija `TRIAJE_CONECTIVIDAD`) |
| Visor | `visor/src/components/Conectividad.tsx`, `visor/src/conectividad.ts`, funciones en `visor/src/api.ts` |
| Inventario operativo y papeles | `prototipo/servicio/inventario_store.py`; papeles del catálogo en `prototipo/accion/catalogo.py` (`PAPELES`, `reglas_de_equipo`) |
| Veto por papel en el motor | `prototipo/motor/perfil.py` (`papel_deniega`, dentro de `filtrar`; sin papel declarado no cambia nada) |
| Asistente de alta y rotación | `visor/src/components/AltaEquipo.tsx`, `visor/src/components/RotacionClave.tsx`, `visor/src/components/ConectividadUi.tsx` |
| Tests | `prototipo/tests/test_conectividad.py`, `prototipo/tests/test_conectividad_web.py`, `prototipo/tests/test_perfil.py` (papel), `visor/src/components/Conectividad.test.tsx`, `visor/src/conectividad.test.ts` |

## Protecciones que ya tiene

- **La clave privada no se lee ni se devuelve nunca.** Solo la pública (`.pub`) y el known_hosts. El paquete
  de alta lleva solo la clave **pública** del conector.
- **Probar, leer la clave del host, editar, dar de alta y rotar exigen un operador identificado** por el mapa
  de tokens (`TRIAJE_CONSOLA_OPERADORES`). Sin mapa, nada de eso salvo con el opt-in de laboratorio
  `TRIAJE_CONECTIVIDAD_ABIERTA=1`. Ver la configuración basta con haber entrado en la consola. La vista dice
  en una franja qué puede hacer cada sesión, y cada acción bloqueada lleva candado y motivo.
- **Freno por equipo:** una prueba o lectura de la clave del mismo equipo como mucho cada 10 s (429).
- **Cada prueba, lectura y cambio queda registrado** con el operador.
- **Testigo inocuo:** la prueba comprueba la denegación con `true`, que no lee nada (antes `cat /etc/shadow`).
- **Temporal aleatorio:** la lectura sin `ssh-keyscan` usa `mktemp -d` y lo borra entero.
- **known_hosts atómico:** se escribe a un temporal, se guarda copia del anterior y se renombra.
- **La última prueba sobrevive al reinicio** y la vista enseña su antigüedad; si cambia el papel del equipo, se olvida.
- **Un ajuste solo se guarda si la prueba con ese ajuste pasa.**
- **Una clave del host nueva solo se acepta** si su huella es exactamente la que el analista vio y confirmó.
- **Un alta solo se completa** con la clave del host fijada (la huella que imprimió el propio equipo al
  ejecutar el paquete) y la prueba completa en verde. Hasta entonces el equipo es «pendiente» y el motor no lo ve.
- **Bloqueo de cuentas «cualquiera salvo las del sistema»:** para las cuentas que crea el atacante. OJO:
  con esta opción el sudoers de `passwd` lleva el comodín (como el aprovisionamiento clásico) y la frontera
  «salvo root y las cuentas de servicio» la pone el **motor**, no sudo. Con la lista cerrada, la pone sudo.
- **El papel acota al motor:** si el equipo de ejecución declara papel y la acción no está en él (o el
  servicio o la cuenta no está en su lista), el filtro la veta con el motivo. Sin papel, nada cambia.
- **El paquete sustituye el sudoers anterior del MDR** (apartado con copia en `/root`), porque sudo suma ficheros.
- **Rotación sin dejar a nadie fuera:** mientras dura, el conector ofrece las dos claves; la vieja solo se
  retira donde la nueva ya entra, y no se finaliza mientras quede algún equipo con solo la vieja.
- **Entradas validadas antes de llegar a ssh**, comandos sin shell local, claves públicas validadas por
  patrón antes de ir en un comando remoto.
- **El modo del conector es de solo lectura**, el modo contraseña de laboratorio no admite nada de esto, y
  **el canal de gestión del MDR (`ip_gestion`) está protegido.**
- **El daemon escucha solo en 127.0.0.1**, los POST pasan el control anti-CSRF de `Origin`, y los ficheros se
  escriben de forma atómica con permisos 0600.

## Lo que hay que revisar antes de producción

Cerrados el 4 nov 2026: probar y leer exigen operador con freno por equipo (antes punto 2), testigo inocuo
(3), temporal aleatorio (4), known_hosts atómico (6) y última prueba persistente (9). El punto 1 queda
**decidido**: ver la configuración exige haber entrado; con la consola abierta el daemon no puede saber
quién lee, igual que el resto de la API.

Siguen abiertos, por gravedad:

1. **El registro de auditoría no está encadenado.** `conectividad-auditoria.jsonl` no entra en la cadena de
   hashes de la traza. Un alta, un cambio de clave del host o una rotación deberían quedar en la traza firmada.
2. **El bloqueo es solo dentro del proceso.** Dos daemons, o una edición a mano de los ficheros mientras la
   vista guarda, pueden pisarse. Añadir un bloqueo de fichero o una comprobación de versión.
3. **`TRIAJE_CONECTIVIDAD` decide qué ficheros lee el conector** (ajustes y rotación). Si alguien controla el
   entorno del daemon puede apuntarlo a otro sitio. Documentarlo y validar que la ruta está dentro del
   directorio de salida.
4. **No hay forma de apagar la vista sin tocar código.** Añadir, por ejemplo, `TRIAJE_CONECTIVIDAD_DESACTIVADA=1`.
5. **La rotación escribe en los equipos** (el `authorized_keys` del propio conector, sin sudo). Es una
   capacidad nueva del conector: revisar con el cliente si la acepta, o si prefiere rotar con su gestión de
   configuración a partir del paquete.
6. **«Cualquier cuenta» deja la frontera de cuentas en el motor.** Con esa opción, un conector comprometido
   podría bloquear root vía sudo. Valorar una lista de exclusión en el sudoers (con sus límites conocidos) o
   restringirla a equipos donde el riesgo se acepte por escrito.
7. **Las reglas «que faltan» no distinguen** un binario no instalado de una regla quitada a mano. Hoy es solo
   un aviso; con un inventario de binarios por equipo podría afinarse.

## Cómo dejarla de solo lectura ahora mismo

Basta con **no** definir `TRIAJE_CONECTIVIDAD_ABIERTA` y **no** tener operadores con token: nadie puede
probar, leer claves, dar de alta, rotar ni cambiar nada. Solo se ve la configuración.

## Observación del laboratorio

La regla de web-banking que descarta el SSH del nodo de gestión (`-A INPUT -s 10.100.0.10/32 -p tcp --dport 22
-j DROP`) la pone **a propósito** el caso E1 del banco («la víctima no responde al MDR»), incluido en la tanda
de ataques, para forzar la escalada a fw-core. `sh lab/banco/banco.sh restaurar` la quita.

El 9 nov 2026 se validó el plan [PLAN-PRUEBA-CONECTIVIDAD-SIN-SCRIPT.md](PLAN-PRUEBA-CONECTIVIDAD-SIN-SCRIPT.md)
de punta a punta: banco recién desplegado sin `aprovisionar`, clave generada desde la vista, 12 equipos
verificados (incluido el equipo nuevo `pagos-qr`, dado de alta desde la vista), contenciones reales y rotación
completa.


El daemon que corre en `:8787` arrancó sin `TRIAJE_SSH_MODO` y con el nodo de gestión por defecto, así que
la vista lo muestra como **«sin configurar»**: hoy no ejecutaría ninguna contención real. La validación en
vivo se hizo con una instancia aparte de solo lectura, en `:8799`, arrancada así:

```
TRIAJE_NODO_GESTION=clab-banco-mdr-siem TRIAJE_SSH_MODO=clave
```

## Cómo verificar tras tocarla

```
PYTHONPATH=. python3 -m unittest prototipo.tests.test_conectividad prototipo.tests.test_conectividad_web prototipo.tests.test_conector prototipo.tests.test_arquitectura
cd visor && npx vitest run src/conectividad.test.ts src/components/Conectividad.test.tsx
```

Y una prueba en vivo de solo lectura contra el laboratorio: `POST /api/conectividad/probar` y
`POST /api/conectividad/leer-clave-host` sobre un equipo, comprobando después que no quedan ficheros
`/tmp/mdr-escaneo-*` en el nodo de gestión.

## Referencias

- Mockup aprobado (vista): https://claude.ai/artifact/9YauiBV2KXPEygzMYXz2sd
- Mockup aprobado (alta de equipos, papeles, deriva y rotación): https://claude.ai/artifact/9Zw1ppJBNYBSoFpsr1GpMj
- Aprovisionamiento del mínimo privilegio: `lab/scripts/aprovisionar-minimo-privilegio.sh`
- Patrón que sigue (overlay + auditoría + fail-closed): editor de Políticas, `POST /api/politica`
