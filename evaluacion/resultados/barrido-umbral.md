# Barrido del umbral de confianza (RF-07) — perfil empresarial
n = 300 alertas. La clasificación (recall/FP) no depende del umbral (control: constante); el umbral solo mueve el escalado al humano y los bloqueos automáticos indebidos.

| umbral | escalado | auto. | indebidos | recall | tasa FP |
|--------|----------|-------|-----------|--------|---------|
| 0.0 | 0.297 | 0 | 0 | 1.000 | 0.009 |
| 0.1 | 0.297 | 0 | 0 | 1.000 | 0.009 |
| 0.2 | 0.297 | 0 | 0 | 1.000 | 0.009 |
| 0.3 | 0.297 | 0 | 0 | 1.000 | 0.009 |
| 0.4 | 0.297 | 0 | 0 | 1.000 | 0.009 |
| 0.5 | 0.297 | 0 | 0 | 1.000 | 0.009 |
| 0.6 | 0.297 | 0 | 0 | 1.000 | 0.009 |
| 0.7 | 0.297 | 0 | 0 | 1.000 | 0.009 |
| 0.8 | 0.297 | 0 | 0 | 1.000 | 0.009 |
| 0.9 | 0.297 | 0 | 0 | 1.000 | 0.009 |
| 1.0 | 0.297 | 0 | 0 | 1.000 | 0.009 |

## Cómo leer
La curva es **constante**: el umbral NO cambia el desenlace en este perfil. La continuidad (0 bloqueos indebidos) no la garantiza el umbral de confianza sino la **política de actores** (D16/C1): bloquear una IP interna, de red o de gestión exige humano siempre, y un atacante externo se bloquea con 0 colateral. El umbral solo mordería en una acción LOCALIZADA de baja confianza contra un actor EXTERNO, de las que esta partición no tiene ninguna (los VP externos tienen confianza 1.0 por postura confirmada; los de confianza 0.5/0.6 recaen sobre activos propios, que la política de actores escala por sí sola). Mecanismo verificado aparte: un caso externo sintético de confianza 0.5 sí cambia de automático a humano al cruzar el umbral.

**Conclusión RF-07:** el valor por defecto (0.7) es seguro y el sistema es robusto a su elección en este perfil; el umbral es un salvavidas secundario, no el control activo de la continuidad.
