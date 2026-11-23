# Diseño: «Revertir y vigilar» que se vea y, si la política lo pide, que decida

**Estado:** aprobado (23/11/2026; el usuario eligió A + B en la conversación).

## Por qué

«Revertir y vigilar» revierte la contención y añade la IP a la watchlist, y su texto promete que «cualquier
alerta nueva salte a la vista». Pero la marca ⚑ solo salía en Red, en el perfil del atacante y en la vista
Watchlist. Ni Aprobaciones, ni Decisiones, ni la Consola, ni el motor sabían que un origen estaba vigilado:
si el atacante volvía, se decidía como cualquier otro y, si era externo, se bloqueaba solo, sin el analista
que lo había querido vigilar.

## Qué se hace

**A. Que se vea donde trabaja el analista** (solo consola):
- **Aprobaciones y Decisiones:** el bloque de origen (común a las dos) muestra «⚑ en vigilancia» con la
  nota y desde cuándo. Las filas de las dos listas llevan ⚑.
- **Consola:** cada incidente de un origen vigilado deja la línea
  `⚑ origen en vigilancia: IP → equipo · nota`, en el grupo «Avisos».
- **El texto bajo «Revertir y vigilar»** dice exactamente lo que hace.

**B. Que vigilar cambie lo que decide el MDR, si la política lo pide** (apagado por defecto):
- **Política:** `respuesta_automatica.origenes_vigilados: con_analista` en `politica.yml`, que se traduce
  a `continuidad.vigilados: humano_siempre` en el perfil.
- **Efecto:** una contención contra la IP de un origen vigilado espera siempre a un analista, con el
  motivo en la tarjeta. Solo endurece.
- **De dónde sale la lista:** el motor la recibe en el perfil (`origenes_vigilados`), que el servicio
  rellena desde `watchlist.json` en cada incidente. El motor sigue sin leer ficheros (contrato de capas).
- **Dónde se enseña:** en el Resumen de Políticas, en «Espera a un analista», y en
  `mdr explicar-politica`.

## Decisiones

- **Coincidencias:** el motor compara IP o CIDR con `actores._coincide`. La consola usa `enWatchlist`
  (IP exacta o /24), que es lo que ofrece la vista Watchlist.
- **Sin la política activa,** B no cambia nada: las métricas canónicas no se mueven.
- **La vigilancia vale desde que se añade:** afecta a las decisiones nuevas, no reescribe las pasadas.
