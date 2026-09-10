# Fase 7 — Documentación técnica e informe final

**Objetivo (plan de trabajo, objetivo 7):** consolidar la arquitectura, las decisiones de diseño,
los resultados, las limitaciones y las líneas de trabajo futuro en un informe técnico completo.

---

## Resumen

Esta fase **no genera conocimiento nuevo: lo consolida.** Buena parte del informe ya estaba escrita
y repartida por las carpetas de fase — el estado del arte, el modelo de cliente, el caso de uso, la
arquitectura, las decisiones y sus alternativas descartadas. El trabajo fue reunirlo, darle un hilo
único y añadir lo que solo existe al final: los resultados y su lectura.

Tres cosas que el informe **no** se deja, porque son las que más se pierden al consolidar y las que
un lector externo va a buscar:

**Las alternativas descartadas y por qué.** Containerlab frente a Packet Tracer y CML; SSH frente a
TR-069 y TR-369; el encoder frente a pedirle la clasificación al generativo; Nmap frente a
Greenbone.

**Las reinterpretaciones documentadas.** La Fase 1 se ejecutó por modelado porque no había cliente;
el módulo de ingesta ocupa el papel del playbook; Wazuh ocupa el del sistema de logs y aporta el
baseline.

**Las limitaciones, sin suavizar.** El auditor no es infalible; el modelo tiene corte de
conocimiento; el corpus del RAG no se puede crecer con el embedder actual; la señal que separa al
administrador del atacante se apoya en una IP suplantable; el equipo de borde del laboratorio fue
provisional; y las cifras de mercado de la Fase 2 vienen de informes de acceso restringido, por lo
que el informe las trata de forma cualitativa y **no las cita como fuente verificada**.

---

## El informe

Vive en **[`documentacion/report/`](../report/)**, en LaTeX, formateado según las *Normas generales
para la redacción y presentación del libro final de los proyectos de grado y pasantías* del
Decanato de Estudios Profesionales de la USB.

| Fichero | Contenido |
|---------|-----------|
| `ip1_main.tex` | Documento maestro: formato, carátula, portada, numeración |
| `ip0_resumen.tex` | Resumen (250 palabras, un párrafo) y palabras clave |
| `ip0_simbolos.tex` · `ip0_abreviaturas.tex` | Listas de símbolos y de abreviaturas |
| `ip2_introduccion.tex` | Antecedentes, justificación, planteamiento, objetivos, estructura |
| `ip3_empresa.tex` | Capítulo 1 — Descripción de la empresa |
| `ip4_marco_teorico.tex` | Capítulo 2 — Marco teórico (11 secciones) |
| `ip5_metodologia.tex` | Capítulo 3 — Metodología por fases, con las decisiones fechadas |
| `ip6_resultados.tex` | Capítulo 4 — Resultados y discusión |
| `ip7_conclusiones.tex` | Conclusiones, recomendaciones y trabajo futuro |
| `ip8_referencias.bib` | Bibliografía (11 fuentes verificadas, estilo `unsrt`/IEEE) |

**Compilar:** `latexmk -pdf ip1_main.tex` desde ese directorio, o `tectonic -X compile ip1_main.tex`
si se prefiere un motor autocontenido. Verificado el 10/09/2026: **44 páginas, sin errores**, sin
citas ni referencias sin resolver y sin cajas desbordadas.

Se versionan solo las **fuentes** (`.tex`, `.bib`), las imágenes y el **PDF final**; los artefactos
de compilación están en `.gitignore`.

---

## Decisiones tomadas al redactarlo

**El título es una abreviación fiel del oficial.** El plan CCT-002-2026 lo enuncia con 159
caracteres y la norma 3.2 topa en 100, así que no cabe literalmente. Se conservan los cuatro
elementos que lo identifican —prototipo, detección y respuesta, asistencia por modelos de lenguaje,
entornos empresariales— y se retiran las siglas sueltas, que la norma 2.4 obligaría a explicar en su
primera aparición. El razonamiento queda escrito en un comentario de `ip1_main.tex`, junto al título
oficial completo.

**El informe lista siete objetivos específicos, no seis.** El plan oficial omite por error el
objetivo de implementar el prototipo; su propio cronograma sí incluye la actividad. Ver la
incongruencia **I-13** en [estado-y-riesgos.md](../00-general/estado-y-riesgos.md).

**Las cifras están sincronizadas con la Fase 6 posterior a RF-03** (precisión 1.000, tasa de FP
0.000), y el capítulo 4 **reporta también la primera medición** (0.556 / 0.041) en una sección
propia, porque la diferencia entre ambas —qué señal faltaba y cómo se incorporó— es el hallazgo más
instructivo de la evaluación.

---

## Entradas y salidas

**Consume:** todas las fases anteriores. En particular los resultados y el análisis de errores de
la [Fase 6](../06-fase6-evaluacion-del-prototipo/), y el registro de decisiones y contradicciones
de [estado-y-riesgos.md](../00-general/estado-y-riesgos.md).

**Entrega a:** nadie dentro del proyecto. Es la salida.

---

## Estado

**Borrador completo y consistente.** El informe cubre las siete fases, compila sin errores, lleva
los datos administrativos del plan oficial (estudiante, ambos tutores, carrera, sede) y sus cifras
coinciden con las de la Fase 6.

Lo que queda **no depende del proyecto**, sino de terceros y del calendario:

- La **revisión de contenido** por el tutor académico y el tutor industrial.
- El **Acta de Evaluación de Pasantía**, que emite la Coordinación de Cooperación Técnica con las
  firmas originales del jurado; `ip1_main.tex` ya reserva su página.
- El **mes de la portada**, hoy fijado en febrero de 2027 según el período declarado en el plan
  (octubre–febrero); ajustar al de la entrega efectiva.

**Criterio de cierre** (roadmap): la documentación está completa y lista para entrega o
presentación. **Cumplido** en lo que atañe al proyecto.
