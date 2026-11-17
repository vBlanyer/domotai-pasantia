# Diseño: las dos variantes de AWS en dos carpetas

17/11/2026 · Estado: aprobado por el usuario (con carpetas autosuficientes y «Cómo probarla»). Sustituye la variable `variante` de
[diseno-aws-laboratorio.md](diseno-aws-laboratorio.md); todo lo demás de ese diseño sigue igual.

## Para qué

El usuario quiere las dos variantes **bien separadas, una en cada carpeta**: que cada una se lea,
configure, despliegue y documente por su cuenta, sin una variable que las mezcle y sin riesgo de
confundirlas en una cuenta real.

## Enfoques considerados

- **(A) Dos carpetas y un módulo común — elegido por el usuario.** `infra/aws/mdr/` y
  `infra/aws/laboratorio/` son dos configuraciones independientes (cada una con sus variables, su estado
  y su guía) que usan un módulo `infra/aws/modulos/base/` con lo común. La red y los permisos se escriben
  una vez: un arreglo llega a las dos.
- (B) Dos carpetas independientes, cada una con su copia de la red y los permisos: más fácil de leer por
  separado, pero todo duplicado y los arreglos pueden llegar a una sola.

## Estructura

Cada variante es **autosuficiente**: quitarla es borrar su carpeta y nada más (la otra sigue funcionando).

```
infra/aws/
├── README.md                 índice: qué es cada variante, cuál usar; enlaza las carpetas
├── modulos/base/             red (VPC, subred privada, endpoints SSM y S3, NAT si hay egreso,
│                             endpoint de Secrets Manager si hay secretos sin egreso), grupo de
│                             seguridad de la instancia, rol y perfil IAM (SSM, secretos, S3) y el
│                             disco cifrado de la traza
├── mdr/                      PRODUCCIÓN: el MDR (+ GPU opcional)
│   ├── *.tf, templates/ (mdr, llm)
│   ├── README.md (con «Cómo probarla»), DESPLIEGUE.md, COSTES.md, inventario/
│   ├── produccion.tfvars.ejemplo, backend.tf.ejemplo (clave …/prod)
│   ├── emulador/escenarios.sh   sus escenarios (A–D) y comprobaciones
│   └── pruebas/test_mdr.py      sus pruebas estáticas
├── laboratorio/              PRUEBAS: banco + Wazuh + MDR en una máquina; no se conecta a ningún cliente
│   ├── *.tf, templates/ (laboratorio)
│   ├── README.md (con «Cómo probarla»), DESPLIEGUE.md, COSTES.md, inventario/
│   ├── laboratorio.tfvars.ejemplo, backend.tf.ejemplo (clave …/laboratorio)
│   ├── emulador/escenarios.sh   sus escenarios (E, F) y comprobaciones
│   └── pruebas/test_laboratorio.py
├── emulador/                 común: probar.sh descubre las variantes que existan; acepta
│                             «mdr», «laboratorio», letras o nada (todas); inventario.py
└── simulacro/                el arranque del MDR en amazonlinux:2023 (como hoy)
```

- `prototipo/tests/test_infra_aws.py` queda con lo común (módulo base, emulador, índice) y **descubre** las
  pruebas de cada `infra/aws/*/pruebas/`: la suite de siempre las ejecuta y, si una carpeta no está, no
  falla.
- Una prueba **simula el borrado** de cada variante (copia temporal sin ella) y comprueba que la otra
  sigue pasando `tofu validate`, sus pruebas y su lista de escenarios, y que el índice no enlaza
  carpetas que no existen.
- Los scripts del laboratorio (`lab/banco/servicio-mdr.sh`, `comprobar-alertas`) se quedan en `lab/`:
  también sirven sin AWS.

## Decisiones

- **Desaparece `variante`.** Cada carpeta tiene solo sus variables. El laboratorio no tiene
  `egreso_bootstrap` (siempre lo necesita) ni nada de GPU, perfil del cliente o red del cliente.
- **Lo propio de la GPU vive en `mdr/`** (rol IAM propio, grupo de seguridad 8080/8082) y solo se crea con
  `llm_habilitado = true`. Hoy se crean siempre, aunque no cuesten: el inventario de producción queda
  más corto y sin «se crea aunque no haya GPU».
- **El arranque del MDR no cambia ni un byte** (misma plantilla, mismos valores). El del laboratorio
  tampoco. Lo que cambia son las direcciones de los recursos (`module.base.aws_vpc.main`…): no hay
  ningún `apply` real, así que no hay estado que migrar.
- **Escenarios del emulador:** A, B, C y D sobre `mdr/` (igual que hoy). E sobre `laboratorio/`.
  El antiguo F (laboratorio sin egreso) desaparece porque ya no se puede pedir; el antiguo G
  (laboratorio con la 1.9.1, rechazado) pasa a ser **F**.
- **Guías:** `mdr/DESPLIEGUE.md` (la de hoy sin la sección del laboratorio) y
  `laboratorio/DESPLIEGUE.md` (esa sección, completa por su cuenta: cuotas, artefactos, plan/apply,
  esperar, atacar, parar y encender, apagar). `COSTES.md` sigue siendo uno, común.
- **Release v1.9.2:** sus notas mencionan `variante = "laboratorio"`; se retocan (con el visto bueno del
  usuario: es una página publicada). El paquete no cambia (no incluye `infra/`).

## Fuera de alcance

- Cambiar qué crea cada variante o cómo arranca (solo se reorganiza).
- Un `apply` real.

## Comprobación

Las pruebas estáticas, el simulacro y el emulador (A–F) pasan sobre la nueva estructura; los
inventarios se regeneran y se revisan; el arranque de cada instancia es el mismo que antes.
