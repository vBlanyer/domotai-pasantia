# Diseño: la reversión, visible donde se cuenta la historia de la decisión

**Estado:** aprobado (23/11/2026; el usuario eligió A + B en la conversación).

## Por qué

La traza guardaba entero cada registro de reversión: quién, cuándo, el motivo, la acción, el equipo, el
comando exacto y su resultado. Pero la consola solo decía «aplicada en core-db». Y una decisión revertida
seguía saliendo en Decisiones como «contenida», aunque esa contención ya no existía.

## Qué se hace

- **A. Trazas:** el inspector de una reversión enseña quién (y la hora), por qué, qué deshace, el comando,
  el resultado con su código y, si falló, la salida del equipo. La decisión revertida enlaza su reversión
  por la **posición en la cadena** (antes, por el id, que se repite entre reinicios).
- **B. Decisiones:** el desenlace «revertida» (violeta) y el filtro «Revertidas», que la saca de
  «Contenidas». El paso «Ejecución» dice «contenida en X y revertida a las HH:MM por Y (motivo)».
- **Backend:** el resumen de una reversión añade `motivo_reversion`, `comando_ejecutado`,
  `codigo_salida` y `salida` (acotada a 500). Cada decisión revertida con éxito lleva `reversion`
  {timestamp, operador, motivo, indice}, casada por índice de la cadena. **`contencion` no cambia:** las
  métricas y las demás vistas siguen igual.

## Descartado

- **C. «Revertidas recientemente» en Contenciones:** repetiría el chip «Reversiones» de Trazas. La vista
  Contenciones es «lo que está activo ahora».
