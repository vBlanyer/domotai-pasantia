# Diseño: identificadores de decisión estructurados

**Estado:** aprobado (23/11/2026; el usuario eligió la opción B′, «fecha + secuencia con prefijo del
cliente», y sustituye el número solo del plan de PostgreSQL del 10/11).

## Por qué

`s23` se repetía entre ficheros de traza (42 en `run/`, casi todos con su `s1`) y entre instalaciones. No
decía cuándo pasó ni de qué cliente era, y convivía con otros esquemas sueltos (`p5`, `s23~sup`).

## Formato

- **Decisión:** `BCO-20261123-0042`, es decir, prefijo del cliente, fecha (UTC, `AAAAMMDD`) y secuencia del
  día (al menos 4 cifras). Sin prefijo configurado, `20261123-0042`.
- **Actividad propia del MDR:** `BCO-20261123-P0005`, con su propia secuencia diaria, para no dejar huecos
  en la numeración de las decisiones.
- **Derivados:** conservan su sufijo, como `BCO-20261123-0042~sup` y `BCO-20261123-0042~tope`.

## Reglas

- **Prefijo:** `prefijo_id` en el perfil del cliente, de 1 a 8 letras o cifras (se pasa a mayúsculas). Uno
  no válido se avisa al cargar el perfil y se ignora (sin prefijo).
- **Secuencia:** vuelve a `0001` cada día (UTC). Al retomar una traza sigue desde el mayor número de ese día
  en la traza, para decisiones y actividad propia por separado.
- **Trazas antiguas:** `s23` se siguen leyendo y verificando; no se reescriben, porque son evidencia
  firmada.
- **Evaluación:** el triaje por lotes (`d4`) no cambia, así que las cifras canónicas no se mueven.

## Dónde

- **`prototipo/servicio/identificador.py`:** el numerador (`siguiente()` para decisiones y
  `siguiente("P")` para actividad propia) y su reconstrucción desde la traza.
- **Integración:** `stream.ejecutar` recibe el numerador; `main` lo reconstruye de la traza que retoma.
- **Perfil:** `perfil.validar` avisa de un prefijo inválido. El perfil del banco declara `prefijo_id: BCO`
  y el de ejemplo lo documenta.
