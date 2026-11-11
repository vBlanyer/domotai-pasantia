# Recomendaciones del informe: qué son, en qué orden y cómo abordarlas

> Documento de trabajo del 10/11/2026. Recoge las recomendaciones de
> [`ip7_conclusiones.tex`](../report/ip7_conclusiones.tex) (§Recomendaciones) y propone un orden. Lo que se
> decida aplazar a después de la entrega se anota además en [v2-trabajo-aplazado.md](v2-trabajo-aplazado.md).

## 1. Las recomendaciones

| # | Recomendación | Estado hoy | Quién la desbloquea | ¿Mueve las cifras del informe? | Tamaño |
|---|---|---|---|---|---|
| R1 | Ampliar el dataset con casos cuya verdad no venga de la heurística | Experimento del ataque lento hecho (resultado negativo) y aviso de vigilancia adoptado; falta variedad: más activos, más servicios, legítimos desde orígenes no declarados | Nosotros + laboratorio | **Sí** (dataset, partición, métricas) | Grande |
| R2 | Completar la clase propia del reconocimiento: rebajar su prioridad | Nombre y pregunta propios hechos; prioridad igual que un intento de acceso | Nosotros | **Sí** (priorización: Spearman, acierto ±1) | Pequeño en código, grande en re-evaluación |
| R3 | Mantener el corpus de descarte al ritmo de las clases | Invariante con prueba automática | Nadie: es una regla continua | No | — |
| R4 | Medir la justificación con un revisor independiente | Material listo: guía, hojas ciegas, `puntuar_revision.py` (~1,5 h de revisor) | **Otra persona** | No (es una medida aparte) | Pequeño |
| R5 | Contraste del agente con un modelo local capaz | Sonnet (sustituto) 3/3; Llama 3.1 8B local 0/3 | **Máquina con GPU** | No | Pequeño–medio |
| R6 | Almacenamiento en PostgreSQL | Plan escrito: [plan-almacenamiento-postgresql.md](../05-fase5-implementacion-del-prototipo/plan-almacenamiento-postgresql.md) (9 tareas) | Nosotros | No | Grande |
| R7 | Política de la empresa en `politica.yml` | **Hecho (11/11/2026):** [plan-politica-empresa.md](../05-fase5-implementacion-del-prototipo/plan-politica-empresa.md) (6 tareas) | Nosotros | No | Medio |
| R8 | Validar en el laboratorio los recortes ante fallos | Implementados y probados, apagados ([plan-manejo-fallos-contencion.md](../05-fase5-implementacion-del-prototipo/plan-manejo-fallos-contencion.md)) | Nosotros + laboratorio del banco | No | Medio |
| R9 | Sistema de logs propietario de Domotai | Sin respuesta | **Domotai** | No | Desconocido (adaptador CEF ya analizado) |
| R10 | Equipo de borde con firmware real | OpenWrt intentado y aparcado; acciones verificadas sobre el sustituto | **Hardware** (un router con OpenWrt) | No | Medio |
| R11 | Requisitos que dependen del cliente | Plantillas listas ([requisitos-del-cliente-y-gobernanza.md](../04-fase4-diseno-de-arquitectura/requisitos-del-cliente-y-gobernanza.md)) | **Un cliente real** | No | — |

## 2. Lo que condiciona el orden

1. **La entrega del informe.** R1 y R2 cambian las cifras canónicas y obligan a reescribir el capítulo de
   resultados. Hacerlas antes de entregar reabre el informe entero; hacerlas después es «v2».
2. **Lo externo tarda y no depende de nosotros.** R4, R5, R9 y R10 esperan a otra persona, a una máquina o
   a la empresa. Cuanto antes se pidan, antes llegan; pedirlas no cuesta nada.
3. **Lo que no mueve cifras puede hacerse en cualquier momento** y deja el producto mejor: R6, R7 y R8.
4. **Dependencias entre ellas:**
   - R1 y R2 van juntas: las dos exigen repetir la evaluación, así que se hace una sola vez.
   - R7 conviene antes que R8: si los recortes se activan, el sitio natural para encenderlos es la política.
   - R6 es independiente, pero es la más grande; sus dos tareas previas (ids numéricos y rotación mensual
     de la traza) tocan la consola y conviene no mezclarlas con R7.
   - R5 es la única que puede cambiar una decisión de producto: activar el modo agente fuera del laboratorio.

## 3. Orden propuesto

| Fase | Qué | Por qué en este punto | Esfuerzo estimado |
|---|---|---|---|
| **0 · Ya, sin código** | Pedir a Domotai: respuesta sobre los logs propietarios (R9), un router con OpenWrt (R10), acceso a una máquina con GPU (R5) y un revisor de 1,5 h (R4) | Desbloquea cuatro recomendaciones; es un correo | Una hora |
| **1 · Antes de entregar, si hay tiempo** | R8: validar los recortes en el banco y decidir cuáles encender | No mueve cifras; convierte «experimental» en «validado» | 1–2 días |
| **2 · Producto** | R7: `politica.yml` | Plan y mockup listos; mejora lo que más cuesta al cliente, configurar | 3–4 días |
| **3 · Cuando llegue la GPU** | R5: los tres escenarios del agente con un modelo local capaz (p. ej. Llama 3.1 70B o Qwen2.5 32B, según memoria de la GPU) | Si pasa, el modo agente puede ofrecerse; si no, queda documentado | 1 día |
| **4 · Antes del primer cliente grande** | R6: PostgreSQL | Grande y sin urgencia mientras no haya volumen bancario | 2–3 semanas |
| **5 · Después de la entrega (v2)** | R1 + R2 juntas, con una sola re-evaluación y la actualización del informe o de su anexo | Mueven las cifras; mejor no reabrir el informe entregado | 1–2 semanas |
| **Continuo** | R3 (cada clase nueva con su ficha); R4 cada vez que cambie el modelo o el enunciado | Son reglas, no tareas | — |
| **Con cliente** | R11 | Solo existe con un cliente concreto | — |

## 4. Cómo abordar cada una

- **R8 — recortes ante fallos.** Levantar el banco, provocar las causas F1–F10 una a una (equipo caído,
  sin aprovisionar, credencial rechazada, efecto no verificado…) con cada interruptor apagado y encendido,
  y comparar: tiempo hasta la contención, pasos omitidos y si alguna contención se pierde. Criterio para
  encender un recorte: nunca pierde una contención y ahorra tiempo medible. Resultado: tabla en el plan de
  fallos y, si procede, los interruptores encendidos por defecto en la plantilla de producción.
- **R7 — política de la empresa.** Ejecutar el plan tal cual (traductor → carga → órdenes `mdr` → API →
  vista → instalación), con la condición de cierre: `evaluacion/tests` sigue dando las mismas cifras.
- **R5 — agente con modelo local.** Seguir `docs/pruebas/evaluar-llm-en-gpu.md`, servir el modelo con
  `llm-server.sh` a temperatura 0 y correr los tres escenarios del banco con `--agente`. Anotar por
  escenario: opción elegida, si degradó y tiempo. Repetir dos veces para comprobar reproducibilidad.
- **R6 — PostgreSQL.** Ejecutar el plan, empezando por sus dos tareas previas.
- **R1 + R2 — re-evaluación.** Diseñar las campañas nuevas con verdad declarada por el experimento
  (activos y servicios nuevos, legítimos desde orígenes no declarados), reforzar con variedad antes de
  adoptar cualquier regla, rebajar la prioridad del reconocimiento y repetir la campaña canónica. Publicar
  las cifras nuevas junto a las antiguas, sin sustituirlas en silencio.
- **R4 — revisor.** Entregarle `guia-revision-independiente.md` y las dos hojas ciegas; puntuar con
  `evaluacion/puntuar_revision.py`. Si la revisión se hace sobre el sistema actual, regenerar antes las
  justificaciones con el modelo que se vaya a desplegar.
- **R9, R10, R11.** Sin trabajo nuestro hasta que haya respuesta; el diseño ya prevé dónde encajan
  (segunda fuente por el módulo de ingesta, acciones del catálogo, plantillas del cliente).

## 5. Decisiones (11/11/2026)

1. **La entrega es el último paso.** Cuando el informe esté listo se entrega y **no se vuelve a tocar el
   código ni nada más**. No hay una «v2» de código: lo que no se haga antes queda en el informe como
   recomendación para quien continúe el trabajo. Cada recomendación es, por tanto, «se hace antes de
   entregar» o «queda escrita como recomendación».
2. **Domotai tiene una máquina pequeña donde ejecuta IA en local**: candidata para R5. Falta saber su
   memoria de GPU; con menos de ~24 GB solo caben modelos del tamaño del 8B, que ya falló (0/3), y el
   resultado probable sería el mismo.
3. **R1 + R2 se hacen antes de la entrega**, para que sus resultados entren en el informe. Condición
   aceptada de antemano: las cifras pueden empeorar; se publican junto a las actuales como un paso más
   de la progresión (`sec:progresion-rf03`), nunca sustituyéndolas en silencio.

## 6. Orden acordado

| Paso | Qué | Notas |
|---|---|---|
| 0 | Correo a Domotai: especificaciones y acceso a su máquina de IA (R5), revisor de 1,5 h (R4), router con OpenWrt (R10), respuesta sobre los logs propietarios (R9) | Lo externo se pide primero porque tarda |
| 1 | ~~R8 — validar los recortes ante fallos en el banco~~ | **Hecho (11/11):** los cinco validados y encendidos por defecto; [resultados](../../evaluacion/resultados/validacion-recortes-2026-11-11/README.md). En el informe, R8 pasa de recomendación a resultado en la pasada final |
| 2 | ~~R1 + R2 — campañas nuevas con verdad declarada, prioridad propia del reconocimiento y re-evaluación~~ | **Hecho (11/11)** en el laboratorio pequeño (comparable con el anterior), con los ataques lentos del experimento: n=417, 209 soportadas; P 0,931, R 0,667, F1 0,777 (baseline 0,800), FP 0,038; sin los lentos, R 1,000 y F1 0,964; 4 automáticas indebidas. Más una evaluación aparte en el banco (perfil bancario): 40/2/3/0, los 2 FP son los legítimos y uno se bloquea solo. [Diseño y resultados](../06-fase6-evaluacion-del-prototipo/ampliacion-dataset-2026-11.md) |
| 3 | R5 — agente con un modelo local en la máquina de Domotai | En cuanto haya acceso; puede ir en paralelo al paso 2 |
| 4 | R4 — revisión independiente sobre las justificaciones del sistema final | Después del paso 2, para revisar lo que se entrega |
| 5 | ~~R7 — `politica.yml`~~ | **Hecho (11/11):** las seis tareas del [plan](../05-fase5-implementacion-del-prototipo/plan-politica-empresa.md); `evaluacion/tests` da las mismas cifras. En el informe, R7 pasa de recomendación a resultado en la pasada final |
| 6 | ~~R6 — PostgreSQL~~ | **No se hace (11/11):** complicaría la instalación en el equipo de IA local de Domotai. Queda en el informe como recomendación, con su plan escrito; sin base de datos el MDR funciona igual que hoy |
| 7 | Informe: una sola pasada final con las cifras nuevas, las recomendaciones hechas pasadas a resultados, y recompilación | Al final, para no reescribirlo varias veces |
| 8 | **Entrega.** Commit y push finales; a partir de aquí no se toca nada | Último paso |

Lo que dependa de terceros y no haya llegado al paso 7 (R4, R5, R9, R10) se queda en el informe como
recomendación, con el material preparado para hacerla.
