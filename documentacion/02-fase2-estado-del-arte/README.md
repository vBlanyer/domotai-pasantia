# Fase 2 — Revisión del estado del arte

**Objetivo (plan de trabajo, objetivo 2):** analizar las soluciones MDR/XDR existentes y las
aplicaciones de modelos de lenguaje en ciberseguridad, identificar las necesidades no cubiertas por
las herramientas actuales, y derivar de ahí los requisitos funcionales y no funcionales del
prototipo.

---

## Resumen

La fase cubre las **dos mitades** del objetivo: el mercado de MDR/XDR y el uso de modelos de
lenguaje en seguridad, más la comparación entre enfoques de reglas y asistidos por IA que el
roadmap pide como actividad propia.

Del análisis de mercado sale el hueco que el proyecto ocupa. Las plataformas líderes ya incorporan
asistentes basados en modelos de lenguaje, pero todos siguen el mismo patrón —**el modelo redacta,
la persona decide**— y todos son servicios en la nube del proveedor. Eso valida el diseño del
prototipo y a la vez señala su oportunidad: hacer lo mismo **en local**, sobre hardware modesto y
sin que la alerta salga de la red del cliente.

Un ajuste de encuadre relevante: las fuentes apuntan repetidamente a las **PYMEs** como segmento
peor cubierto, pero el plan declara ese despliegue fuera de alcance. El destinatario del prototipo
es el cliente modelado en la [Fase 1](../01-fase1-analisis-del-modulo/), y **lo que lo define no es
su tamaño sino su restricción de continuidad** — un problema que ninguna plataforma del mercado
resuelve hoy, porque ninguna sabe si la respuesta que propone va a cortar un servicio.

Del análisis de modelos de lenguaje salen los límites que el diseño tiene que respetar: separar
clasificar de justificar, exigir anclaje verificable contra la alucinación, tratar los campos de la
alerta como **datos y nunca como instrucciones** —la inyección de prompt no es hipotética cuando el
log lo escribe quien ataca—, y degradar a cola manual antes que descartar en silencio.

Todo ello aterriza en un [**registro único de 34 requisitos**](requisitos.md)
([20 funcionales](requisitos.md#requisitos-funcionales) y [14 no funcionales](requisitos.md#requisitos-no-funcionales)),
cada uno trazado a lo que lo motiva. Que la lista viva en un solo sitio es deliberado: ya ocurrió
una vez que requisitos nuevos quedaran anotados en un documento aparte que la tabla maestra nunca
recogió.

---

## Documentos

### Estado del arte

- [MDR y XDR en el mercado](mdr-xdr.md) — panorama, plataformas y proveedores líderes, tendencias y métricas de éxito.
- [Limitaciones de XDR](limitacionesDeXDR.md) — las diez limitaciones documentadas en implementación y operación, qué hueco deja cada una, y a quién va dirigido el prototipo.
- [Modelos de lenguaje aplicados a la seguridad](llm-en-seguridad.md) — enfoques de aplicación al triaje, modelos especializados, riesgos propios del componente de IA y la comparación **reglas frente a análisis asistido**.

### Requisitos

- [**Requisitos del prototipo**](requisitos.md) — **registro único**. Si un requisito no está aquí, no existe.
- [Revisión frente al contexto del cliente](revision-requisitos-contexto.md) — el recorrido requisito a requisito que verificó la vigencia de la lista original tras el cambio de contexto; resuelve I-5. Registro histórico: sus conclusiones ya están en el registro único.

---

## Entradas y salidas

**Consume:** de la [Fase 1](../01-fase1-analisis-del-modulo/), las restricciones operativas del
cliente ([C1, C3, C6](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#52-operativas-del-cliente--lo-que-el-prototipo-debe-respetar)) y los puntos de variabilidad ([V1–V5](../01-fase1-analisis-del-modulo/modelo-de-cliente-generico.md#6-puntos-de-variabilidad)), que se convierten en
[RF-17 a RF-20 y RNF-14](requisitos.md).

**Entrega a:** todas las fases posteriores. Los requisitos son el criterio contra el que la
[Fase 4](../04-fase4-diseno-de-arquitectura/) diseña, la [Fase 5](../05-fase5-implementacion-del-prototipo/)
implementa y la [Fase 6](../06-fase6-evaluacion-del-prototipo/) mide.

---

## Estado

**Completa.** Ambas mitades del objetivo están cubiertas y los requisitos que producen están
consolidados.

**Deuda conocida:** las cifras de mercado proceden de informes de firmas analistas de acceso
restringido, recogidos de forma indirecta. Están marcadas como **pendientes de verificación
directa** antes de llegar al informe de la [Fase 7](../07-fase7-documentacion-e-informe-final/).
Lo mismo aplica a las capacidades concretas de los productos citados, que cambian con frecuencia.
