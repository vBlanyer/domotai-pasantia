# Fase 1 — Análisis del módulo propietario

**Objetivo (plan de trabajo, objetivo 1):** analizar la solución actual del cliente para recepción
y análisis de datos, identificar sus limitaciones y necesidades no cubiertas, y definir el caso de
uso acotado sobre el que se construirá el prototipo.

---

## Resumen

Esta fase no dispone de un módulo real que analizar: **no hay cliente ni proveedor definidos**, y
el encargo fue diseñar un entorno genérico. En lugar de dejarla bloqueada —y con ella la raíz de
la que dependen las fases 3, 4 y 6— se ejecuta **por modelado**: se define un cliente genérico de
referencia y de ahí se derivan las limitaciones y el caso de uso.

Modelar no es un sustituto de menor calidad. Es lo que obliga a separar **qué puede asumir el
prototipo de cualquier cliente** de **qué cambia de uno a otro**, y esa frontera —los cinco puntos
de variabilidad [**V1–V5**](modelo-de-cliente-generico.md#6-puntos-de-variabilidad)— es el resultado central de la fase: convierte «el prototipo se adapta a
varios clientes» en una afirmación comprobable.

El arquetipo es una **organización con red propia** que quiere protegerse sin interrumpir lo que
presta. El alcance empieza en el punto de entrega del proveedor y sigue hacia dentro. De su sistema
actual el prototipo asume solo tres cosas: que emite alertas normalizables, que expone un canal de
acción acotado, y que declara qué no puede interrumpirse.

Las limitaciones se documentan en **dos familias con dueños distintos**: las del sistema base
([L1–L5](modelo-de-cliente-generico.md#51-del-sistema-base--lo-que-el-prototipo-viene-a-cubrir)), que son la brecha que el prototipo viene a cubrir, y las operativas del cliente
([C1–C6](modelo-de-cliente-generico.md#52-operativas-del-cliente--lo-que-el-prototipo-debe-respetar)),
que debe respetar sin resolverlas. La distinción importa: una mejora del triaje que corte un
servicio del cliente no es una mejora.

El caso de uso queda acotado a **acceso no autorizado a servicios de gestión expuestos**, por
familia de alerta y no por tipo de equipo — porque la superficie de administración remota aparece
en todas las capas y el patrón se parece a sí mismo esté donde esté. Toda alerta fuera de ese
perímetro se marca **«no soportada»** en vez de recibir una clasificación no fundamentada.

El plan de trabajo y el roadmap no se modifican: el objetivo 1 se cumple por reinterpretación
documentada, igual que la decisión **D10** resolvió el playbook.

---

## Documentos

- [Modelo de cliente genérico](modelo-de-cliente-generico.md) — el arquetipo capa a capa, los tres
  supuestos, las dos familias de limitaciones y el detalle de los cinco puntos de variabilidad.
- [Caso de uso acotado](caso-de-uso-acotado.md) — perímetro dentro y fuera, regla de «no
  soportada», categorías de clasificación, criticidad de activos, respuestas aplicables y política
  de continuidad.

---

## Entradas y salidas

**Consume:** nada. Es la raíz del proyecto.

**Entrega a:**

| Fase | Qué se lleva |
|------|--------------|
| [2](../02-fase2-estado-del-arte/) | Las restricciones [C1, C3 y C6](modelo-de-cliente-generico.md#52-operativas-del-cliente--lo-que-el-prototipo-debe-respetar) y los puntos [V1–V5](modelo-de-cliente-generico.md#6-puntos-de-variabilidad), que se convierten en [RF-17 a RF-20 y RNF-14](../02-fase2-estado-del-arte/requisitos.md) |
| [3](../03-fase3-entorno-de-pruebas/) | El arquetipo de red que el laboratorio instancia |
| [4](../04-fase4-diseno-de-arquitectura/) | El perímetro, las clases, la criticidad de activos y la política de continuidad |
| [5](../05-fase5-implementacion-del-prototipo/) | El caso de uso que el objetivo 5 manda construir |
| [6](../06-fase6-evaluacion-del-prototipo/) | Las métricas de continuidad y el ámbito sobre el que se mide |

---

## Estado

**Completa por sustitución.** El criterio de cierre del roadmap —operar un módulo propietario que
no existe— se reescribe así: *el equipo opera una fuente de alertas equivalente a la del cliente
modelado, tiene documentadas las limitaciones que el prototipo debe cubrir y las que debe respetar,
y el caso de uso acotado está definido con su perímetro explícito.* Los tres se cumplen.

Reflejado ya en [estado-y-riesgos.md](../00-general/estado-y-riesgos.md): la fase consta como
«completa por modelado» y **I-4** queda como *parcial* — solo sigue abierta la pregunta de identidad
del módulo, que depende de la empresa.
