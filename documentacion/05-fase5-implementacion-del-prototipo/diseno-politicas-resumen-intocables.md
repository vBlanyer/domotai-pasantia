# Diseño: Políticas, «Resumen» en tres columnas e intocables sin pestaña propia

**Estado:** propuesto (23/11/2026). Mockups: https://claude.ai/artifact/5HirZcbp1Zk78KwJwq9d4j
(elegidos: **Resumen A** e **Intocables C**).

## Por qué

En la vista Políticas, la pestaña «Resumen» eran 11 frases sueltas: sin orden y con nombres internos
(`abuso_de_cuenta`, «plano de gestión»). Además, los puertos no decían de qué equipo eran y no se veía de un
vistazo qué hace el MDR solo y qué no. La pestaña «Intocables» mezclaba cuatro cosas distintas, sin decir el
porqué, y repetía los candados de «Por tipo de ataque». El usuario quiere entender la política de un
vistazo, sin abrir el YAML y sin ver lo mismo dos veces.

## Qué cambia

**Resumen (propuesta A).** Primera pestaña, la que se abre al entrar.
- **Frase de arriba:** «De N tipos de ataque, el MDR contiene X solo (si está seguro), deja Y a un analista
  y Z nunca los toca solo. Todo lo que hace se puede deshacer.»
- **Tres columnas** (verde, ámbar y rojo), con nombres legibles:
  - **Lo contiene solo:** las familias en automático, con su acción en palabras («bloquea el origen»,
    «corta la sesión») y la certeza mínima. Al pie: «Pasa a un analista si la acción toca un servicio o un
    equipo propio».
  - **Espera a un analista:** las familias que piden humano, bloquear equipos propios o dispositivos de red
    (si la política lo exige), cada servicio intocable (equipo, qué es y puerto) y las alertas que el MDR
    no reconoce desde el nivel N.
  - **Nunca lo hace solo:** las familias con freno duro (código) y «cortar su propia conexión con los
    equipos».
- **Pie:** en quién confía (administradores y la ráfaga que lo anula), con enlaces a «Confianza» y «Por
  tipo de ataque».
- **El texto completo,** lo que imprime `mdr explicar-politica` y firma Seguridad, queda en un desplegable
  «Ver la política en texto».

**Intocables (propuesta C).** Desaparece la pestaña.
- En «Por zona y dispositivo», la fila de cada equipo con servicios intocables lleva un candado:
  «puerto 1521: siempre con analista». Al lado, lo que caería en cascada.
- Las reglas generales (canal de gestión, equipos propios, frenos) ya salen en el Resumen.
- Los frenos siguen con su candado en «Por tipo de ataque».

## Cómo

- **Todo en el visor:** sale de `/api/politica`, que ya trae familias, zonas con cascada, confianza e
  intocables. Lógica pura en `visor/src/politicas.ts` (columnas, frase, nombres legibles de familia y de
  acción) y probada en seco.
- **Un solo cambio de backend:** cada intocable gana `funcion` (la del inventario del perfil), para decir
  qué es el equipo.
- **No cambia el motor ni la política;** solo cómo se enseña. Se actualizan los manuales (y sus PDF) y el
  CHANGELOG.

## Decisiones mías (a revisar)

1. **El texto en frases no se tira:** pasa a un desplegable. Es lo que firma Seguridad y lo mismo que da
   `mdr explicar-politica`.
2. **Sin la línea «respuestas que solo observan»:** `/api/politica` no trae esa regla. Añadirla obligaría
   a ampliar la API para una línea de poco valor.
3. **Intocables fuera de las zonas:** un servicio intocable de un equipo que no está en ninguna zona solo
   sale en el Resumen (columna ámbar). Nunca desaparece.
4. **Nombres legibles de las 10 familias** en una tabla del visor. Una familia nueva sin nombre sale con
   su identificador.
