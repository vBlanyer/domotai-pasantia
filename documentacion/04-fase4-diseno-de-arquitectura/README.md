# Fase 4 — Diseño de la arquitectura del sistema

**Objetivo (plan de trabajo, objetivo 4):** definir el flujo de acciones, las reglas de decisión y
umbrales, las formas de interacción con el sistema del cliente y las herramientas auxiliares, el
formato del razonamiento explicable y los puntos de validación humana, junto con las métricas de
evaluación y el método tradicional de referencia.

---

## Resumen

El diseño descansa en una idea repetida tres veces: **el prototipo no se acopla a lo que no
controla, lo esconde tras un adaptador.** La fuente de alertas queda detrás del módulo de ingesta,
el modelo detrás de la interfaz `clasificar`/`justificar`, y el canal hacia los equipos detrás del
conector. Cambiar cualquiera de los tres es escribir un adaptador nuevo, no tocar la lógica de
decisión.

El flujo es cerrado: la actividad genera alertas, la ingesta las normaliza, el análisis las
clasifica y justifica, la decisión se retiene o se ejecuta, el conector actúa, el auditor
reescanea para verificar, y todo queda en la traza. El auditor aparece **dos veces con papeles
distintos** — antes de decidir aporta la postura del activo como contexto, y después de actuar
comprueba que la exposición se cerró de verdad.

Dos decisiones acotan el radio de impacto. El canal es **SSH**, elegido por cubrir todos los nodos
sin desarrollo previo y por ser auditable orden a orden; y sobre él el motor **no emite comandos,
selecciona acciones de un catálogo cerrado y enumerado**. Es lo que impide que el canal degenere en
ejecución remota arbitraria. TR-069 y TR-369 quedan documentados como la evolución natural.

El modelo se resuelve en **dos perfiles** por el presupuesto de memoria: el A, híbrido y ejecutable
en el equipo actual, con un encoder para clasificar, un modelo pequeño en línea para la
justificación breve que la validación humana necesita, y uno mayor en lote para la extensa; y el B,
de un solo modelo, para cuando haya hardware. Los resultados de ambos **no son comparables entre
sí**, y una campaña de evaluación fija su perfil y no lo cambia a mitad.

La evaluación se mide contra el **nivel de regla de Wazuh** como método tradicional de referencia.
No es un rival débil: es el método que hoy está en producción en la mayoría de organizaciones, y
comparar contra él es lo único que responde a la pregunta del proyecto.

---

## Documentos

- [Flujo de operación](flujo-triaje-playbook-sandbox.md) — componentes, quién existe y quién se construye, contratos entre piezas y dónde encaja la validación humana.
- [Protocolos de comunicación con el sandbox](protocolos-comunicacion-sandbox.md) — comparativa por tramo de red y la decisión de SSH.
- [Catálogo cerrado de acciones](catalogo-de-acciones.md) — qué puede ordenar el motor, con precondición, efecto, reversibilidad, verificación y validación humana.
- [Auditoría de vulnerabilidades](auditoria-de-vulnerabilidades-del-sandbox.md) — alcance, herramientas, salida normalizada y los tres papeles del auditor.
- [Selección del modelo de análisis](seleccion-del-modelo.md) — criterios, perfiles A y B, e interfaz `clasificar`/`justificar`.
- [Métricas y plan de evaluación](metricas-y-evaluacion.md) — baseline, ground truth, fórmulas y condiciones de una campaña válida.
- [Arquitectura consolidada](arquitectura-consolidada.md) — vista única: componentes, planos, flujo y los tres puntos de aislamiento.

**Material de referencia:** [EDR, XDR, MDR y telemetría](edr-xdr-mdr-telemetria.md) — encaje de las
tres siglas y por qué el componente central es un motor de triaje y no un EDR. El material superado
por el cambio de contexto está en [documentacion/archivo/](../archivo/).

---

## Entradas y salidas

**Consume:** el perímetro, las clases y la política de continuidad de la
[Fase 1](../01-fase1-analisis-del-modulo/); los 34 requisitos de la
[Fase 2](../02-fase2-estado-del-arte/requisitos.md); y las restricciones reales medidas en la
[Fase 3](../03-fase3-entorno-de-pruebas/).

**Entrega a:** la [Fase 5](../05-fase5-implementacion-del-prototipo/), que codifica este diseño, y
la [Fase 6](../06-fase6-evaluacion-del-prototipo/), que aplica sus métricas y su baseline.

---

## Estado

**Cerrada, con una revisión pendiente.** El diseño está completo y es suficiente para empezar a
implementar; la vista de conjunto está en [arquitectura consolidada](arquitectura-consolidada.md).

Queda por absorber lo que la Fase 1 produjo después de cerrarla:

- [**RF-17**](../02-fase2-estado-del-arte/requisitos.md) (declarar el impacto sobre el servicio de cada acción) y [**RF-20**](../02-fase2-estado-del-arte/requisitos.md) (métricas de
  continuidad) no tienen reflejo en el contrato de la orden de acción ni en el plan de métricas.
- [**RF-18**](../02-fase2-estado-del-arte/requisitos.md) (sin reversión verificable no se propone) y [**RF-19**](../02-fase2-estado-del-arte/requisitos.md) (rechazar lo que dejaría el
  activo fuera del plano de gestión) cuestionan varias entradas del catálogo. El
  [caso de uso §9](../01-fase1-analisis-del-modulo/caso-de-uso-acotado.md) ya señala `BLOQUEAR_PUERTO`
  y `LIMITAR_BANDA` como probablemente mal clasificadas.
- [**RNF-14**](../02-fase2-estado-del-arte/requisitos.md) (adaptarse a un cliente nuevo configurando [V1–V5](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad), sin tocar código) no tiene artefacto
  de diseño para la política de continuidad ni para el inventario de criticidad.
- No existe todavía la **regla que traduce clasificación en acción**, que el roadmap pide en esta
  fase como «reglas de decisión y umbrales».

Otros dos huecos, ya conocidos: el catálogo no se ha podido probar sobre un equipo de borde con
firmware real, y los umbrales de escalado se calibran en la Fase 6 — la implementación arranca con
valores declarados y recalibrables.
