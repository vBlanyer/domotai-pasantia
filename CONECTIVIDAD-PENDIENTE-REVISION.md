# ⚠ Vista «Conectividad»: pendiente de revisión de seguridad

> **Estado (4 nov 2026):** integrada y funcionando, **sin commit**, y **no apta para producción** hasta
> cerrar los puntos de este documento. Se mantiene por ahora para el laboratorio.
>
> Es la vista más delicada del visor: gestiona cómo el MDR entra por SSH a los equipos del cliente.
> Un error aquí puede filtrar datos de la red o permitir que alguien redirija o bloquee el conector.

## Qué es

Vista del grupo **Configurar** del visor que permite, sin tocar código:

- ver el modo del conector, la huella de su clave y la clave del host fijada de cada equipo;
- cambiar el **puerto** y el **usuario** SSH de cada equipo, y el **usuario por defecto**;
- **probar** la conexión a un equipo, comprobando que el sudo del catálogo funciona y que todo lo demás se deniega;
- **aceptar una clave del host nueva** cuando un equipo la cambia.

Los ajustes se guardan en `conectividad-operativa.yml`, junto a la salida del daemon, y el conector los
lee por encima de las variables de entorno (`TRIAJE_CONECTIVIDAD`). Cada cambio queda en
`conectividad-auditoria.jsonl`.

## Ficheros

| Capa | Fichero |
|---|---|
| Lógica (ajustes, prueba, huellas, known_hosts) | `prototipo/accion/conectividad.py` |
| Uso de los ajustes en el SSH real | `prototipo/accion/conector.py` (`_ajustes`, `modo_actual`, `ejecutor_con`, `correr_donde_las_claves`) |
| API web | `prototipo/servicio/conectividad_web.py` y las rutas `/api/conectividad*` en `prototipo/servicio/tablero.py` |
| Ruta del fichero de ajustes | `prototipo/servicio/stream.py` (fija `TRIAJE_CONECTIVIDAD`) |
| Visor | `visor/src/components/Conectividad.tsx`, `visor/src/conectividad.ts`, funciones en `visor/src/api.ts` |
| Tests | `prototipo/tests/test_conectividad.py`, `prototipo/tests/test_conectividad_web.py`, `visor/src/components/Conectividad.test.tsx`, `visor/src/conectividad.test.ts` |

## Protecciones que ya tiene

- **La clave privada no se lee ni se devuelve nunca.** Solo se leen la clave pública (`.pub`) y el known_hosts.
- **Editar exige un operador identificado** por el mapa de tokens (`TRIAJE_CONSOLA_OPERADORES`). Sin mapa, la vista es de solo lectura salvo con el opt-in de laboratorio `TRIAJE_CONECTIVIDAD_ABIERTA=1`.
- **Un ajuste solo se guarda si la prueba de conexión con ese ajuste pasa.**
- **Una clave del host nueva solo se acepta** si su huella es exactamente la que el analista vio y confirmó. Si cambió entre la lectura y la confirmación, no se escribe nada.
- **Entradas validadas antes de llegar a ssh.** La IP pasa por `ipaddress`, el puerto tiene que ser un entero entre 1 y 65535 y el usuario debe cumplir `^[a-z_][a-z0-9_-]{0,31}$`. Los comandos se lanzan como lista de argumentos, sin shell.
- **El modo del conector es de solo lectura** y el modo contraseña de laboratorio no admite ajustes.
- **El equipo de `ip_gestion` (canal de gestión del MDR) está protegido**: no se configura desde aquí.
- **El daemon escucha solo en 127.0.0.1** y los POST pasan el control anti-CSRF de `Origin`.
- **El fichero de ajustes se escribe de forma atómica con permisos 0600.**

## Lo que hay que revisar antes de producción

Ordenado por gravedad.

1. **El GET es legible sin token cuando la consola está abierta.** `GET /api/conectividad` devuelve IPs, usuarios, puertos, rutas de clave, huellas de host y la clave pública del conector. No son secretos, pero son un mapa de reconocimiento de la red. Decidir si este endpoint debe exigir token **siempre**, aunque el resto de la consola esté abierta.
2. **Probar y leer la clave del host no exigen operador.** Cualquiera con acceso a la consola puede lanzar conexiones SSH a todos los equipos a voluntad. Valorar exigir operador también aquí y poner un límite de frecuencia por equipo.
3. **El comando prohibido de la prueba es `cat /etc/shadow`.** Si un equipo está mal aprovisionado y sudo lo permite, el contenido de `/etc/shadow` pasa por la memoria del daemon. No se devuelve ni se registra, pero el diseño debería evitarlo. Cambiarlo por un comando fuera del catálogo que **no lea nada sensible**, por ejemplo `sudo -n true` o `sudo -n id`, comprobando que sigue siendo un buen testigo de «sudo deniega lo que no está en el catálogo».
4. **Fichero temporal con nombre predecible.** Si el nodo de gestión no tiene `ssh-keyscan`, la lectura de la clave del host escribe en `/tmp/mdr-escaneo-<ip>-<puerto>` dentro de ese nodo. En un `/tmp` compartido eso admite un ataque por enlace simbólico. Usar `mktemp` en un directorio propio con permisos 0700, o instalar `ssh-keyscan` en el nodo y quitar el recurso.
5. **El registro de auditoría no está encadenado.** `conectividad-auditoria.jsonl` es un JSONL simple, igual que el de Políticas, y no entra en la cadena de hashes de la traza. Un cambio de clave del host o de usuario debería quedar en la traza firmada.
6. **La escritura del known_hosts no es atómica.** Se hace con `tee` sobre el fichero real en el nodo de gestión. Un corte a mitad dejaría el known_hosts truncado y el conector sin entrar a ningún equipo. Escribir a un temporal y renombrar, y guardar una copia del anterior.
7. **El bloqueo es solo dentro del proceso.** Dos daemons, o una edición a mano del fichero mientras la vista guarda, pueden pisarse. Añadir un bloqueo de fichero o una comprobación de versión.
8. **`TRIAJE_CONECTIVIDAD` decide qué fichero lee el conector.** Si alguien controla el entorno del daemon puede apuntarlo a otro fichero. Es el mismo modelo de confianza que el resto de variables `TRIAJE_*`, pero conviene documentarlo y validar que la ruta está dentro del directorio de salida.
9. **La última prueba vive solo en memoria.** Se pierde al reiniciar y la vista vuelve a «sin probar». No es un riesgo, pero puede inducir a error tras un reinicio.
10. **No hay forma de apagar la vista sin tocar código.** Añadir una variable, por ejemplo `TRIAJE_CONECTIVIDAD_DESACTIVADA=1`, que oculte la entrada del menú y responda 404 en las rutas.

## Cómo dejarla de solo lectura ahora mismo

Con el código actual, basta con **no** definir `TRIAJE_CONECTIVIDAD_ABIERTA` y **no** tener operadores
con token. Así nadie puede guardar ni aceptar claves. Ojo: probar, leer la clave del host y el GET siguen
disponibles, como se explica en los puntos 1 y 2.

## Observación del laboratorio

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

- Mockup aprobado: https://claude.ai/artifact/9YauiBV2KXPEygzMYXz2sd
- Aprovisionamiento del mínimo privilegio: `lab/scripts/aprovisionar-minimo-privilegio.sh`
- Patrón que sigue (overlay + auditoría + fail-closed): editor de Políticas, `POST /api/politica`
