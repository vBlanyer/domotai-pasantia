# Las dos variantes de AWS en dos carpetas — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `infra/aws/mdr/` (producción) y `infra/aws/laboratorio/` (pruebas), autosuficientes, sobre un módulo común `infra/aws/modulos/base/`; quitar una variante es borrar su carpeta.

**Architecture:** Se extrae a `modulos/base/` lo común (red, endpoints, NAT opcional, grupo de seguridad de la instancia, rol y perfil IAM, disco de la traza, AMI de Amazon Linux). Cada variante es una configuración raíz que llama al módulo y crea su instancia, el enganche del disco, sus salidas y lo suyo (la GPU solo en `mdr/`). El emulador común descubre los escenarios que aporta cada carpeta.

**Tech Stack:** OpenTofu (módulos locales), sh POSIX, Python 3 `unittest`, AWS Emulator.

**Spec:** [diseno-aws-dos-carpetas.md](diseno-aws-dos-carpetas.md)

## Global Constraints

- **El arranque de cada instancia no cambia ni un byte:** la huella `user_data` del MDR en los planes A–D y la del laboratorio en E son las mismas que antes (planes de referencia: los JSON de la última ejecución del emulador; si no están, se regeneran desde `66902a3` antes de empezar).
- Desaparece `variante`. El laboratorio no tiene `egreso_bootstrap`, ni GPU, ni `perfil_url`/`red_cliente_cidrs`; su precondición de versión (≠ `1.9.1`) y la de `laboratorio_commit` se quedan con sus mensajes exactos.
- Lo propio de la GPU (rol, perfil, política de modelos, grupo de seguridad 8080/8082) vive en `mdr/` y lleva `count = var.llm_habilitado ? 1 : 0`.
- Escenarios: A, B, C, D en `mdr/`; E y **F** (antes G: laboratorio con 1.9.1, rechazado) en `laboratorio/`. El antiguo F desaparece.
- Autosuficiencia: nada de `mdr/` ni de `modulos/` referencia `laboratorio/` y viceversa, salvo pruebas marcadas para saltarse si la otra carpeta no existe.
- Los documentos históricos (planes y diseños anteriores, CHANGELOG ya publicado, OBSERVACIONES-REVISION) **no se corrigen**; los vivos que enlacen ficheros movidos, sí.
- `.terraform.lock.hcl` va a cada carpeta raíz; el `terraform.tfstate` vacío (0 bytes) de `infra/aws/` se borra.
- Emulador sin telemetría ni credenciales reales. Commits locales en `main` con `git commit -F`; sin push; nunca el PDF del informe.
- Las notas publicadas de la release v1.9.2 solo se tocan con el visto bueno del usuario (tarea 5).

## Review Focus

1. **Un `tofu plan` sin `-var-file` en cada carpeta** (lo primero que hará alguien): debe fallar solo por lo que falta de verdad (en `laboratorio/`, `laboratorio_commit`), no por variables de la otra variante. Prueba en las tareas 1 y 2.
2. **Copiar una carpeta fuera del repositorio** (un cliente que solo quiere `mdr/`): se rompe por la ruta relativa al módulo. Se documenta en el README de cada carpeta qué hay que copiar (`modulos/base/` también). Comprobación en la tarea 4.
3. **Estado de OpenTofu de las dos en el mismo bucket:** cada `backend.tf.ejemplo` usa su propia clave (`…/prod`, `…/laboratorio`). Prueba en la tarea 4.
4. **Una letra de escenario de una variante borrada** (`probar.sh E` sin `laboratorio/`): mensaje claro, no un fallo raro. Prueba en la tarea 3.
5. **Un enlace del índice a una carpeta borrada:** la prueba del índice lo detecta (tarea 4).

---

### Tarea 1: módulo base y carpeta `mdr/`

**Files:**
- Create: `infra/aws/modulos/base/{main.tf,variables.tf,outputs.tf}`, `infra/aws/mdr/{main.tf,variables.tf,mdr.tf,llm.tf,outputs.tf}`, `infra/aws/mdr/pruebas/test_mdr.py`
- Move (git mv): `templates/mdr_user_data.sh.tftpl` y `templates/llm_user_data.sh.tftpl` → `mdr/templates/`; `.terraform.lock.hcl` → `mdr/` (y copia a `laboratorio/` en la tarea 2)
- Modify: `prototipo/tests/test_infra_aws.py` (queda lo común + descubrimiento)

**Interfaces:**
- Produces `module "base"` (`source = "../modulos/base"`). Variables: `proyecto`, `region`, `vpc_cidr`, `subred_privada_cidr`, `subred_publica_cidr`, `egreso` (bool), `secretos` (list(string), ARN), `objetos_s3` (list(string), `arn:aws:s3:::…`), `disco_traza_gb` (number). Salidas: `vpc_id`, `vpc_cidr`, `subred_privada_id`, `zona`, `sg_instancia_id`, `perfil_instancia`, `ami_al2023`, `volumen_traza_id`, `volumen_traza_nvme` (`replace(id, "-", "")`). Dentro conserva los nombres de recurso de hoy (`aws_vpc.main`, `aws_security_group.mdr`, `aws_ebs_volume.traza`, `aws_iam_role.instancia`…); el endpoint de Secrets Manager con `count = length(var.secretos) > 0 ? 1 : 0`.
- Produces en `mdr/`: `aws_instance.mdr` (con `depends_on = [module.base]`), `aws_volume_attachment.traza`, la GPU (`aws_instance.llm`, `aws_iam_role.gpu`, `aws_iam_instance_profile.gpu`, `aws_iam_role_policy_attachment.gpu_ssm`, `aws_iam_role_policy.gpu_s3`, `aws_security_group.llm`, todos con `count` por `llm_habilitado`), las variables de hoy salvo `variante` y `laboratorio_*`, y las salidas `vpc_id`, `mdr_instance_id`, `llm_instance_id`, `comando_tunel_visor`, `comando_token_admin`.
- Produces en `test_infra_aws.py`: `load_tests` que añade las pruebas de cada `infra/aws/*/pruebas/test_*.py` que exista (cargadas con `unittest.defaultTestLoader.discover(carpeta, top_level_dir=carpeta)`).

- [ ] **Paso 1: pruebas que fallan** — mover a `mdr/pruebas/test_mdr.py` las clases de hoy que son del MDR (`TestArranqueMdr`, `TestGpu`, `TestRevisionFinal`, `TestDespliegueProduccion`, `TestRevisionEmulador`), con `_leer` relativo a `infra/aws/mdr/` y las de red leyendo `../modulos/base/`. Nuevas: `test_sin_variante` (ninguna `variable "variante"` ni `laboratorio_` en `mdr/variables.tf`); `test_gpu_solo_con_llm` (los seis recursos de la GPU tienen `count` por `var.llm_habilitado`); `test_usa_el_modulo_base` (`source = "../modulos/base"`); `test_plan_sin_variables_no_pide_nada` (Review Focus 1: todas las variables de `mdr/variables.tf` tienen `default`). En `test_infra_aws.py`: `test_descubre_las_pruebas_de_cada_variante`.
- [ ] **Paso 2:** `python3 -m unittest prototipo.tests.test_infra_aws` → FALLAN (no existe `mdr/`).
- [ ] **Paso 3:** crear el módulo y la carpeta; borrar de `infra/aws/` los `.tf` y plantillas movidos, `variante` incluida.
- [ ] **Paso 4:** `cd infra/aws/mdr && tofu init -backend=false && tofu fmt -check -recursive .. && tofu validate` → `Success!`; las pruebas pasan.
- [ ] **Paso 5: commit** `refactor(aws): módulo base y la variante MDR en infra/aws/mdr`.

### Tarea 2: carpeta `laboratorio/`

**Files:**
- Create: `infra/aws/laboratorio/{main.tf,variables.tf,laboratorio.tf,outputs.tf}`, `infra/aws/laboratorio/pruebas/test_laboratorio.py`
- Move: `templates/laboratorio_user_data.sh.tftpl` → `laboratorio/templates/`

**Interfaces:**
- Consumes: `module "base"` (tarea 1) con `egreso = true`.
- Produces: `aws_instance.laboratorio` (tipo `var.laboratorio_tipo`, raíz `var.laboratorio_disco_gb`, `tags.Name = "${var.proyecto}-laboratorio"`, `user_data_replace_on_change = true`, `depends_on = [module.base]`), `aws_volume_attachment.traza` (`stop_instance_before_detaching = true`). Variables: `region`, `proyecto` (por defecto `"mdr-laboratorio"`), `entorno` (`"pruebas"`), `vpc_cidr`, `subred_privada_cidr`, `subred_publica_cidr`, `mdr_version` (`"1.9.2"`), `mdr_paquete_url`, `mdr_paquete_sha256` (la de 1.9.2), `mdr_disco_gb` (20), `laboratorio_tipo`, `laboratorio_disco_gb`, `laboratorio_commit` (sin `default`: es lo único obligatorio), `secreto_traza_arn`, `secreto_operadores_arn`. Precondiciones: las dos de hoy (versión y commit) con sus mensajes exactos. Salidas: `vpc_id`, `laboratorio_instance_id`, `comando_tunel_visor`, `comando_token_admin`.

- [ ] **Paso 1: pruebas que fallan** — mover `TestLaboratorio` a `laboratorio/pruebas/test_laboratorio.py` (sin la precondición de egreso ni la de GPU, que ya no existen). Nuevas: `test_siempre_con_egreso` (`egreso = true` en la llamada al módulo y ninguna variable `egreso_bootstrap`); `test_solo_falta_el_commit` (Review Focus 1: la única variable sin `default` es `laboratorio_commit`); `test_mismo_disco_que_el_mdr` se salta con `skipUnless` si no existe `../mdr/`.
- [ ] **Paso 2:** ejecutarlas → FALLAN.
- [ ] **Paso 3:** crear la carpeta; copiar `.terraform.lock.hcl` de `mdr/`.
- [ ] **Paso 4:** `cd infra/aws/laboratorio && tofu init -backend=false && tofu validate` → `Success!`; pruebas OK.
- [ ] **Paso 5: commit** `refactor(aws): la variante laboratorio en infra/aws/laboratorio`.

### Tarea 3: emulador común con escenarios por carpeta

**Files:**
- Create: `infra/aws/emulador/comun.py`, `infra/aws/{mdr,laboratorio}/emulador/{escenarios.sh,comprobar.py}`
- Modify: `infra/aws/emulador/probar.sh`, `infra/aws/emulador/inventario.py`; borrar `infra/aws/emulador/comprobar.py`
- Regenerate: `infra/aws/{mdr,laboratorio}/inventario/`; borrar `infra/aws/inventario/`

**Interfaces:**
- Produces `escenarios.sh` (se carga con `.` desde `probar.sh`): define `LETRAS` (`"A B C D"` / `"E F"`), `INSTANCIA` (`aws_instance.mdr` / `aws_instance.laboratorio`), `vars_de LETRA`, `rechazo_de LETRA` (vacío si no se rechaza; C: `El paquete 1.9.1 no activa el modelo`; F: `La variante laboratorio necesita un MDR >= 1.9.2`) y `override_extra` (HCL añadido al override: la zona de sus instancias y, en `mdr/`, la AMI de la GPU).
- Produces `comprobar.py` por carpeta: `ESCENARIOS: dict[str, str]` (letra → descripción) y `comprobaciones(escenario, estado) -> list[tuple[str, bool]]`; las de hoy, repartidas. `comun.py`: `recursos(estado)`, `user_data(recursos, instancia)`, `bash_n(texto)`, `comprobaciones_base(rs, instancia)` (disco, EBS por id, endpoints, destroy).
- Produces `probar.sh`: descubre `infra/aws/*/emulador/escenarios.sh`; argumentos: nada (todas), nombre de carpeta (`mdr`, `laboratorio`), letras, o `--listar` (imprime `carpeta: letras` por línea y sale). Una letra que ninguna carpeta aporta → `== X: escenario desconocido (ninguna variante lo define)` y fallo.
- Produces `inventario.py <dir_planes> <carpeta>`: lee `ESCENARIOS` de `<carpeta>/emulador/comprobar.py` y escribe `<carpeta>/inventario/`. `POR_QUE` admite direcciones con el prefijo `module.base.`.

- [ ] **Paso 1: pruebas que fallan** (en `test_infra_aws.py`, comunes): `test_listar_variantes` (`sh probar.sh --listar` → `mdr: A B C D` y `laboratorio: E F`); `test_letra_de_variante_inexistente` (Review Focus 4: con una copia temporal de `infra/aws` sin `laboratorio/`, `probar.sh --listar` no la lista y `probar.sh E` sale ≠ 0 con `escenario desconocido`, sin arrancar el emulador: la letra se valida antes).
- [ ] **Paso 2:** ejecutarlas → FALLAN.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** `MDR_INVENTARIO=<scratchpad> sh infra/aws/emulador/probar.sh` → `EMULADOR: todo como se esperaba` (A 11/11, B 12/12, C y F rechazados, D 14/14, E 16/16, o el recuento nuevo si cambian los recursos de la GPU). Comparar la huella `user_data` de `aws_instance.mdr` (A, B, D) y de la instancia del laboratorio (E) con los planes de referencia → iguales.
- [ ] **Paso 5:** regenerar los dos inventarios (`inventario.py` por carpeta); A y B pierden los cuatro recursos de GPU que hoy se crean siempre; anotar los recuentos.
- [ ] **Paso 6: commit** `test(aws): el emulador descubre los escenarios de cada variante`.

### Tarea 4: documentación por carpeta, índice y autosuficiencia

**Files:**
- Create: `infra/aws/{mdr,laboratorio}/{README.md,DESPLIEGUE.md,COSTES.md,backend.tf.ejemplo}`, `infra/aws/laboratorio/laboratorio.tfvars.ejemplo`
- Move: `produccion.tfvars.ejemplo` → `mdr/`
- Modify: `infra/aws/README.md` (índice), `lab/banco/README.md` y otros documentos vivos que enlacen ficheros movidos
- Delete: `infra/aws/{DESPLIEGUE.md,COSTES.md,backend.tf.ejemplo,terraform.tfstate}`
- Test: `prototipo/tests/test_infra_aws.py`

**Interfaces:**
- Produces en `test_infra_aws.py`: `enlaces_rotos(raiz: str) -> list[str]` (enlaces relativos de `infra/aws/README.md` y de los README de cada carpeta que no existen).

- [ ] **Paso 1: pruebas que fallan**: `test_indice_enlaza_cada_variante_y_nada_roto` (cada carpeta con `escenarios.sh` está enlazada en el índice y `enlaces_rotos` está vacío); `test_borrar_una_variante` (para cada variante: copia temporal de `infra/aws` sin ella → `enlaces_rotos` devuelve solo los enlaces a la carpeta borrada; las pruebas de la otra pasan con `unittest discover`; ningún fichero de la otra ni de `modulos/` menciona la borrada fuera de las pruebas con `skipUnless`); `test_como_probarla` (cada README tiene la sección `## Cómo probarla` con `probar.sh <carpeta>` y `tofu validate`); `test_estado_separado` (Review Focus 3: las claves de los dos `backend.tf.ejemplo` son distintas); `test_copiar_una_carpeta` (Review Focus 2: cada README dice que hay que llevar también `modulos/base/`); y en `test_mdr.py`/`test_laboratorio.py`, las pruebas de guía y costes de hoy apuntando a sus ficheros.
- [ ] **Paso 2:** ejecutarlas → FALLAN.
- [ ] **Paso 3:** escribir. `mdr/DESPLIEGUE.md` = la guía de hoy sin la sección del laboratorio; `laboratorio/DESPLIEGUE.md` = esa sección completa por su cuenta (cuotas, paquete, opcionalmente secretos, `laboratorio.tfvars`, plan/apply, esperar, atacar, parar y encender, apagar); `COSTES.md` de cada una con su tabla de precios (la misma, con fuente y fecha) y sus escenarios (A, B, D / E con sus tres formas de uso). Índice: qué es cada variante, cuál usar, «Cómo probar las dos». Buscar con `grep -rn 'infra/aws/\(DESPLIEGUE\|COSTES\|inventario\|produccion\|backend\)'` los enlaces vivos y corregirlos.
- [ ] **Paso 4:** todas las suites: `python3 -m unittest prototipo.tests.test_infra_aws`, `python3 -m unittest discover -s prototipo/tests -t .`, `python3 -m unittest discover -s lab/banco/tests -t .` → OK; `tofu validate` en las dos carpetas.
- [ ] **Paso 5: commit** `docs(aws): una guía por variante, índice y prueba de borrado`.

### Tarea 5: CHANGELOG y notas de la release

- [ ] **Paso 1:** `CHANGELOG.md` `[Sin publicar]` → «Cambiado: las dos variantes de AWS en dos carpetas…».
- [ ] **Paso 2: commit** `docs: changelog de la reorganización de infra/aws`.
- [ ] **Paso 3 (PARADA):** proponer al usuario el texto nuevo de las notas de v1.9.2 (cambia `variante = "laboratorio"` por la carpeta `infra/aws/laboratorio/`, y aclara que la reorganización llega después de la etiqueta) y editarlas solo con su visto bueno (`gh release edit v1.9.2 --notes-file …`).
