# Barrido del umbral de confianza (RF-07) — perfil empresarial
n = 356 alertas. La clasificación (recall/FP) no depende del umbral (control: constante); el umbral solo mueve el escalado al humano y los bloqueos automáticos indebidos.

| umbral | escalado | auto. | indebidos | recall | tasa FP |
|--------|----------|-------|-----------|--------|---------|
| 0.0 | 0.292 | 27 | 4 | 1.000 | 0.038 |
| 0.1 | 0.292 | 27 | 4 | 1.000 | 0.038 |
| 0.2 | 0.292 | 27 | 4 | 1.000 | 0.038 |
| 0.3 | 0.292 | 27 | 4 | 1.000 | 0.038 |
| 0.4 | 0.292 | 27 | 4 | 1.000 | 0.038 |
| 0.5 | 0.292 | 27 | 4 | 1.000 | 0.038 |
| 0.6 | 0.292 | 27 | 4 | 1.000 | 0.038 |
| 0.7 | 0.292 | 27 | 4 | 1.000 | 0.038 |
| 0.8 | 0.292 | 27 | 4 | 1.000 | 0.038 |
| 0.9 | 0.292 | 27 | 4 | 1.000 | 0.038 |
| 1.0 | 0.292 | 27 | 4 | 1.000 | 0.038 |

## Cómo leer
La curva es **constante**: el umbral NO cambia el desenlace en este perfil. Lo que protege la continuidad no es el umbral de confianza sino la **política de actores** (D16/C1): bloquear una IP interna, de red o de gestión exige humano siempre, y un atacante externo se bloquea con 0 colateral. El umbral solo mordería en una acción LOCALIZADA de baja confianza contra un actor EXTERNO, de las que esta partición no tiene ninguna (los VP externos tienen confianza 1.0 por postura confirmada; los de confianza 0.5/0.6 recaen sobre activos propios, que la política de actores escala por sí sola). Mecanismo verificado aparte: un caso externo sintético de confianza 0.5 sí cambia de automático a humano al cruzar el umbral.

Los **4 bloqueos automáticos indebidos** no dependen del umbral: son un origen EXTERNO legítimo (en la ampliación del 11/11/2026, el técnico del proveedor que se equivoca y entra) clasificado con confianza alta. Ni el umbral ni la política de actores lo retienen; el control previsto es declararlo en `terceros_confiables` del perfil, que nunca se bloquea sin un analista.

**Conclusión RF-07:** el valor por defecto (0.7) es seguro y el sistema es robusto a su elección en este perfil; el umbral es un salvavidas secundario, no el control activo de la continuidad.
