# Observaciones de la revisión (15/11/2026)

Detalles encontrados al recorrer el código para explicar las tecnologías, el RAG, MITRE/D3FEND y el
almacenamiento. El estado de cada punto tras los arreglos del 16/11 está en [Estado](#estado-16112026).

Cada punto indica cómo se comprobó, porque no todos se han probado en vivo.

| # | Observación | Gravedad | Afecta a decisiones | Comprobado |
|---|---|---|---|---|
| 1 | Las aprobaciones pendientes de la consola web se pierden al reiniciar, sin dejar rastro | **Media** | No (pero se pierde una aprobación) | Lectura de código |
| 2 | El índice del RAG está desactualizado (32 de 35 fichas) | Media-baja | No (solo la explicación) | Comparación de ficheros |
| 3 | El corpus del RAG no cubre las técnicas de las 6 familias nuevas | Media-baja | No (solo la explicación) | Comparación de ficheros |
| 4 | Cifras desfasadas en la documentación | Baja | No | Ejecución de tests + lectura |
| 5 | La reconstrucción al reiniciar solo lee el segmento activo de la traza | Baja (ya conocida) | No hoy | Lectura de código |
| 6 | IaC de AWS: el LLM nunca se activaría aunque `llm_habilitado = true` | **Media** | No (se queda en plantilla) | Lectura de código + grep |
| 7 | IaC de AWS: despliega `v1.4` por defecto (la última etiqueta es `v1.8`) | Media | Sí (versión antigua del motor) | `git tag` |
| 8 | IaC de AWS: el RAG no tendría embedder en la instancia del MDR | Baja | No (explicación sin RAG) | Lectura de código |
| 9 | IaC de AWS: la instancia GPU es un esquema y no arrancaría el LLM | Media (si se activa) | No | Lectura de la plantilla |
| 10 | IaC de AWS: si el disco tarda en adjuntarse, la traza va al disco raíz sin avisar | Baja | No | Lectura de la plantilla |
| 11 | La consola web compilada (`visor/dist`) no está en git: en AWS (y en cualquier clon nuevo) la consola no carga | **Alta** para AWS | No (el motor funciona, la consola no) | **Reproducido** en contenedor `amazonlinux:2023` (404 en `/`) |
| 12 | IaC de AWS: `tofu destroy` puede quedarse colgado al desmontar el EBS de la traza | Baja | No | Comportamiento conocido de AWS, **no probado** |
| 13 | Las reglas `sudo` del conector aceptan argumentos extra (`iptables … --modprobe=…` → root; `passwd -l root`) | **Alta** | — | **Comprobado** con `sudo -l` en contenedor (sin ejecutar) |
| 14 | La consola no envía cabeceras anti-clickjacking | Media-baja | — | `grep` |
| 15 | El daemon no avisa al arrancar si la consola está abierta (sin tokens) | Baja | — | Lectura de código |
| 16 | La traza activa crece sin límite: la retención nunca la poda y la API la relee entera | Media (a largo plazo) | — | Lectura de código |
| 17 | Prueba inestable (`test_receptor`) → **CI en rojo en `main`** | Media (CI) | — | Log de la CI + 8/8 OK en local |
| 18 | AWS: el código queda en manos del usuario del servicio (`chown -R triaje /opt/mdr`) | Media | — | Lectura de la plantilla |
| 19 | AWS: sin `TRIAJE_TRAZA_CLAVE` ni analistas → traza sin firma y consola sin autenticación | Media | — | Lectura de la plantilla |
| 20 | Unidad systemd poco endurecida (`systemd-analyze security`: 8.5 EXPOSED) | Baja-media | — | `systemd-analyze` offline |
| 21 | Sin copias de seguridad, sonda de salud ni retención automatizadas | Baja-media | — | Lectura de `deploy/` e `infra/` |
| 22 | La API responde 500 (no 400) a un cuerpo JSON que no es un objeto | Muy baja | — | Log de la CI |
| 23 | La CI no tiene lint de Python, ShellCheck, escaneo de secretos ni auditoría de dependencias | Baja | — | `ci.yml` |

## Estado (16/11/2026)

Aplicado en `main` (commits locales) según el plan
[`plan-revision-15-11.md`](documentacion/05-fase5-implementacion-del-prototipo/plan-revision-15-11.md):

| # | Estado | Commit |
|---|---|---|
| 1 | **Hecho**: registro `pendiente` al encolar; `pendiente_perdida` y aviso `[inicio]` al arrancar | `2e84bc9` |
| 2 | **Hecho**: índice reindexado (35 fichas) y `test_rag_indice` lo vigila. Recuperación fija sobre las 16 simulaciones: MRR 0,611 → 0,684, acierto en la 1.ª posición 0,375 → 0,500. La agéntica se midió después con cinco generadores (Llama 1B, Qwen 3B, Foundation-Sec-8B, Claude Haiku y Sonnet): ninguno mejora con claridad la consulta fija; informe, `tab:modelos` | `9404c01`, `84b2a65`, `9df3daf` |
| 4 | **Hecho**: comentario de `attack.ts` (10 familias) y cifras del README (1467 tests del motor, 70 de la evaluación, 492 del visor) | `ee810e4`, docs |
| 13 | **Hecho**: envoltorio `/usr/local/sbin/mdr-accion` generado desde el catálogo; el sudoers solo lo permite a él; conector, prueba de Conectividad, paquete de alta y aprovisionamiento lo usan. Verificado en vivo: banco aprovisionado (10/10 nodos, `--modprobe` denegado) y un ataque D1 contenido y verificado a través del envoltorio | `95cb506`, `61aac59` |
| 14 | **Hecho**: `X-Frame-Options: DENY` y `frame-ancestors 'none'` en toda respuesta | `ee810e4` |
| 15 | **Hecho**: aviso `[inicio] consola SIN autenticación` al arrancar | `ee810e4` |
| 17 | **Hecho**: la prueba reintenta hasta un plazo | `ee810e4` |
| 22 | **Hecho**: cuerpo que no es un objeto (o JSON inválido) → 400 | `ee810e4` |
| — | **Revisión final de la rama** (revisor independiente): sin críticos; 3 importantes corregidos (alta antigua mal diagnosticada, testigo de sudo y ruta exacta del envoltorio) y los 8 menores también (IP sin prefijo, usuario del conector protegido, valores sin «-», `limite_banda` validado, temporales del alta, permisos de `/usr/local/sbin`, Ansible aparta sudoers antiguos) | `56f301d`, `56cc1d8` |
| 3, 5, 16, 20, 21, 23 | Recomendación, sin cambios | — |
| 6 | **Hecho**: `TRIAJE_CON_LLM=1` arranca el daemon con `--con-llm`; el arranque de AWS escribe `LLAMA_URL`, `LLAMA_EMBED_URL` y `TRIAJE_CON_LLM` si hay GPU | `75dc63e`, `82a4edd` |
| 7 | **Hecho**: se instala el release `mdr_version` (por defecto 1.9.1), con su huella SHA-256 | `82a4edd` |
| 8, 9 | **Hecho**: la GPU parte de la AMI con driver NVIDIA, compila llama.cpp (etiqueta fija) con CUDA y sirve el generador (8080) y bge-m3 (8082), modelos verificados; sin modelos no se crea. **No probado** sin GPU | `40dec6a` |
| 10 | **Hecho**: el disco de la traza es obligatorio (si no aparece, el arranque se para) y la unidad exige el montaje | `82a4edd` |
| 11, 18 | **Hecho**: el arranque instala el paquete del release con `instalar.sh` (consola incluida, código de root en solo lectura) | `82a4edd` |
| 12 | **Hecho**: `stop_instance_before_detaching = true` | `82a4edd` |
| 19 | **Hecho**: clave de la traza y analistas de Secrets Manager (un fallo al leerlos para el arranque) o generados, con el token de admin en `/root/mdr-token-admin` | `82a4edd` |
| — | **Además**: el arranque anterior fallaba por sintaxis en el bucle del disco (doble dólar que `templatefile` no escapa), y no instalaba `openssh-clients`, que `instalar.sh` exige (lo destapó el simulacro). Simulacro del arranque en `amazonlinux:2023` en `infra/aws/simulacro/` | `82a4edd`, tarea 4 |

## Prioridades recomendadas

1. **#13 — sudoers del conector:** es el único punto que convierte un robo de credenciales en root en
   los equipos del cliente.
2. **#17 — prueba inestable:** tiene la CI en rojo en `main`. Mientras tanto, relanzar el job.
3. **Antes de la prueba en AWS:** #7 (versión), #11 (consola), #18 y #19 (permisos y secretos en AWS).
4. **#1 — aprobaciones pendientes perdidas al reiniciar** y **#16 — traza sin límite:** afectan al uso
   continuado en producción.
5. Lo demás (#2–#6, #8–#10, #12, #14, #15, #20–#23), cuando haya hueco.

**Pendiente de decisión:** ejecutar `npm audit` (envía la lista de dependencias al registro de npm).

---

## 1. Las aprobaciones pendientes solo viven en memoria

**Qué pasa.** En modo web, cuando una decisión necesita aprobación humana, va a una cola en memoria
(`EstadoTablero._pendientes` / `_cola`, [tablero.py:49-66](prototipo/servicio/tablero.py#L49-L66)) y **no
se escribe en la traza hasta que el analista la resuelve**:

- [stream.py:454](prototipo/servicio/stream.py#L454): `if d.get("en_cola"): # … se resolverá y trazará al aprobar` → `return d` sin `cadena.escribir`.
- [stream.py:723](prototipo/servicio/stream.py#L723): `encolar()` solo llama a `estado_web.encolar_decision(...)`.

**Consecuencia.** Si el daemon se reinicia mientras hay tarjetas en *Aprobaciones*, esas decisiones
desaparecen sin ningún registro: no están en la traza ni se reconstruyen al arrancar. La unidad systemd
usa `Restart=always` ([mdr-triaje.service](deploy/mdr-triaje.service)), así que esto puede ocurrir solo
(por ejemplo, si se corta la fuente de alertas) sin que nadie lo note.

Contrasta con el desalojo por el tope de la cola, que **sí** se traza "para que nada desaparezca en
silencio" ([stream.py:744-745](prototipo/servicio/stream.py#L744-L745)).

**Matiz.** Si el atacante sigue activo, sus alertas nuevas vuelven a generar tarjeta, porque las
decisiones en cola tampoco entran en la memoria de supresión. El caso que se pierde es el de una alerta
puntual que no se repite.

**Posibles arreglos (de menor a mayor esfuerzo):**
1. Al encolar, escribir en la traza un registro `pendiente` (sin ejecutar nada). Al arrancar, listar
   los `pendiente` sin resolución posterior y avisarlo en la consola.
2. Además, reconstruir la cola desde esos registros al reiniciar, de modo que las tarjetas vuelvan a
   *Aprobaciones*.

**Comprobado:** leyendo el código. **No** se ha reproducido en vivo. Para confirmarlo: levantar el
banco, provocar una decisión que pida aprobación, reiniciar con `sh reiniciar.sh` y mirar si la tarjeta
sigue y si aparece en la traza.

---

## 2. El índice del RAG está desactualizado

- [corpus.jsonl](prototipo/corpus/corpus.jsonl) tiene **35** fichas; [indice.json](prototipo/corpus/indice.json) tiene **32**.
- Faltan en el índice: `mapeo-acceso_consumado`, `mapeo-denegacion_servicio` y `mapeo-integridad_fichero`.
- Se añadieron al corpus el 14/10 junto con las familias 6.ª, 7.ª y 8.ª (commits `3bc615e`, `257cdd0` y
  `73309c8`), pero no se reindexó. El índice es del 10/09.

**Consecuencia.** El RAG nunca puede recuperar esas tres fichas, así que las explicaciones LLM de esas
familias se escriben sin su mapeo de contramedida. No cambia ninguna decisión.

**Arreglo.** En la máquina que tenga llama.cpp y `bge-m3-q8.gguf`:
```bash
python3 -m prototipo.explicacion.rag --indexar
```
**Sugerencia:** un test que compare los `id` del corpus con los del índice y falle si difieren. Así
el desfase se habría detectado en la CI, porque comparar ids no necesita el modelo.

---

## 3. Huecos de cobertura MITRE/D3FEND en el corpus del RAG

El corpus se construyó para las 4 familias originales. Las 6 que se añadieron después
([familias.yml](prototipo/familias.yml)) tienen poca o ninguna ficha:

- **Técnicas ATT&CK sin ficha `mitre`:** T1548, T1136, T1098 (abuso_de_cuenta) · T1565, T1070
  (integridad_fichero) · T1498, T1499 (denegacion_servicio) · T1041, T1071 (exfiltracion) · T1014,
  T1486 (malware). La lista permitida `TECNICAS_PERIMETRO` de
  [extraer_attack.py](prototipo/explicacion/extraer_attack.py) solo tiene las 15 técnicas originales.
- **Familias sin ficha `mapeo`:** `abuso_de_cuenta`, `exfiltracion` y `malware`.
- **Contramedidas sin ficha `d3fend`:** solo existen D3-NTF, D3-ITF, D3-AL y D3-NI. Faltan las que
  corresponden a `LIMITAR_BANDA` (DoS), `MATAR_CONEXION` (expulsar la sesión) y `BLOQUEAR_DESTINO`
  (filtrar el tráfico de salida).

**Consecuencia.** Para esas familias, el RAG recupera las fichas "menos malas" (por ejemplo, fuerza
bruta para una exfiltración) y la explicación queda pobre o desenfocada. El anclaje sigue impidiendo
que se cite una técnica ajena, y la decisión no cambia.

**Arreglo.** Ampliar `TECNICAS_PERIMETRO`, regenerar las fichas `mitre` desde el bundle STIX, escribir
en `curado.jsonl` los `mapeo` y `d3fend` que faltan y reindexar (punto 2). Conviene también un test
que compruebe que **cada familia de `familias.yml` tiene su ficha `mapeo`**, igual que ya existe
`verificar_cobertura_descarte` para las clases sin amenaza ([rag.py:47](prototipo/explicacion/rag.py#L47)).

---

## 4. Cifras desfasadas en la documentación

- [README.md:73](README.md#L73) dice que el motor tiene **957 tests**. Hoy son **1290** (ejecutado:
  `python3 -m unittest discover -s prototipo/tests` → `Ran 1290 tests … OK`), y la línea 23 del mismo
  README ya dice 1290.
- [visor/src/attack.ts:4](visor/src/attack.ts#L4): el comentario habla de "las 8 familias", y las
  líneas 7 y 35 del mismo fichero dicen 10.

---

## 5. La reconstrucción al reiniciar solo lee el segmento activo de la traza (ya conocido)

[stream.py:1352-1361](prototipo/servicio/stream.py#L1352-L1361) reconstruye la memoria de supresión
leyendo solo el fichero activo (`traza.leer_registros`), no la familia de segmentos
(`traza.leer_familia`). Hoy no hay rotación en caliente, así que no tiene efecto práctico. El propio
código lo deja anotado como pendiente ("Opción B de #6"). Se apunta aquí solo para tenerlo presente
si se activa la rotación de trazas.

---

## 6–10. Infraestructura de AWS ([infra/aws/](infra/aws/))

Encontrados al revisar si un emulador de AWS serviría para probar el despliegue. **Ninguno de estos
fallos lo detectaría un emulador ni `tofu validate`**, porque están dentro del script de arranque
(cloud-init) o en cómo se conectan las variables con el código.

### 6. El LLM nunca se activaría aunque `llm_habilitado = true`

- La plantilla [mdr_user_data.sh.tftpl](infra/aws/templates/mdr_user_data.sh.tftpl) escribe
  `TRIAJE_LLM_URL=...` en `/etc/mdr/triaje.env`, pero el código lee **`LLAMA_URL`**
  ([justificador_llm.py:286](prototipo/explicacion/justificador_llm.py#L286)). `TRIAJE_LLM_URL` no
  aparece en ningún sitio de `prototipo/`.
- Además, [arrancar-mdr.sh](deploy/arrancar-mdr.sh) nunca pasa `--con-llm` al daemon, así que aunque
  la variable fuera la correcta, el justificador seguiría siendo la plantilla.
- **Arreglo:** escribir `LLAMA_URL` en la plantilla y que `arrancar-mdr.sh` añada `--con-llm` cuando
  esa variable venga definida (por ejemplo, con una variable `TRIAJE_CON_LLM=1`).

### 7. Despliega una versión antigua

`repo_rama` tiene como valor por defecto **`v1.4`** ([variables.tf](infra/aws/variables.tf)), pero ya
existen `v1.5` … `v1.8`, y los commits de cierre (seguridad de conectividad, instalación simplificada)
son posteriores. Un `apply` sin `-var repo_rama=...` desplegaría el motor viejo. **Arreglo:** subir el
valor por defecto a la última etiqueta o hacerlo obligatorio (sin valor por defecto).

### 8. El RAG no tendría embedder en AWS

El RAG busca el embedder en `127.0.0.1:8082` (`LLAMA_EMBED_URL`) de la **propia máquina del MDR** o,
si no responde, en el binario `llama-embedding` con `bge-m3`. En la instancia del MDR no se instala
ninguna de las dos cosas, y la instancia GPU arranca un solo `llama-server` con un único modelo (no
puede servir a la vez el generador y bge-m3). Resultado: la explicación funcionaría **sin RAG**.
**Arreglo:** un segundo `llama-server --embedding` con bge-m3 en la instancia GPU (otro puerto
abierto en el SG) y `LLAMA_EMBED_URL` apuntando a él.

### 9. La instancia GPU es un esquema, no un arranque funcional

[llm_user_data.sh.tftpl](infra/aws/templates/llm_user_data.sh.tftpl) clona llama.cpp pero **no lo
compila** (el `ExecStart` apunta a `build/bin/llama-server`, que no existe), no instala el driver
NVIDIA y no arranca el servicio. Muchos pasos terminan en `|| true`, así que **falla en silencio**. El
propio fichero dice que es un esquema. Hay que completarlo antes de activar la GPU (lo más sencillo:
partir de una *Deep Learning AMI* y compilar con CUDA).

### 10. La traza puede acabar en el disco raíz sin avisar

El arranque espera hasta 60 s a que aparezca el EBS de la traza. Si tarda más, sigue adelante sin
montarlo y el MDR escribe la traza en `/mnt/traza` **del disco raíz**. Si después se monta el EBS
encima, esa traza queda oculta y el MDR empieza una cadena nueva. **Arreglo:** si no aparece el disco,
fallar (`exit 1`) o que la unidad systemd exija el montaje (`RequiresMountsFor=/mnt/traza`).

### 11. La consola web compilada no está en el repositorio

- `visor/dist` está en [.gitignore](.gitignore) (líneas 55 y 59) y en `visor/.gitignore`:
  `git ls-files visor/dist` no devuelve nada, ni en `HEAD` ni en la etiqueta `v1.4`.
- El daemon sirve la consola desde `visor/dist` ([tablero.py:817](prototipo/servicio/tablero.py#L817)).
  Si no existe, responde `404 {"error": "no encontrado"}`
  ([tablero.py:1040](prototipo/servicio/tablero.py#L1040)). La API y `/healthz` siguen funcionando.
- El arranque de AWS hace `git clone`, así que **la consola no cargaría en AWS**. Lo mismo le pasa a
  cualquiera que clone el repo y siga el camino "completo" del README, que dice
  ([README.md:37](README.md#L37)) que el visor "ya viene construido en `visor/dist`": es cierto en tu
  máquina, no en un clon.
- [empaquetar.sh](deploy/empaquetar.sh) sí incluye `visor/dist` en el paquete `.tar.gz`, así que la
  instalación por paquete no tiene este problema. Solo lo tiene el camino `git clone`.
- **Arreglos posibles:** (a) que el arranque de AWS instale el paquete de `empaquetar.sh` (subido a S3
  o adjuntado a una *release* de GitHub) en vez de clonar; (b) publicar `visor/dist` como artefacto de
  cada *release*; (c) instalar Node en la instancia y compilar (más lento y más dependencias). Corregir
  también la frase del README.

### 12. `tofu destroy` puede colgarse al desmontar el disco de la traza (posible, no probado)

`aws_volume_attachment.traza` ([mdr.tf](infra/aws/mdr.tf)) desmonta el EBS **con la instancia
encendida y el disco montado y en uso** (el MDR escribe ahí la traza). AWS puede dejar el volumen en
estado `busy` y OpenTofu esperar hasta agotar el tiempo (`Error waiting for Volume … to detach`).
**Arreglo:** añadir `stop_instance_before_detaching = true` al recurso, que apaga la instancia antes de
desmontar.

---

## Comprobado y correcto (para no repetirlo)

Probado el 15/11 en un contenedor `amazonlinux:2023`, la misma distribución que usa la AMI de AWS:

- `dnf install python3 python3-pyyaml git` funciona (los nombres de paquete del arranque son correctos).
- La distribución trae **Python 3.9.25**. Las suites pasan: `prototipo` **1290 OK** (2 omitidos) y
  `evaluacion` **63 OK**.
- El daemon en modo `--web` arranca, `/healthz` responde `ok`, procesa la alerta de muestra y la deja
  en `/api/pendientes` esperando aprobación (perfil bancario: `BLOQUEAR_IP` retenida).
- `git clone --depth 1 --branch v1.8` del repositorio público: **1,4 s, 15 MB**.

Lo que esto **no** prueba: systemd, el montaje del EBS, SSM ni la red de AWS. Para eso hace falta la
VM de Amazon Linux o AWS real.

---

# Anexo: simulacro de despliegue en AWS (pasos, tiempos y errores posibles)

Escenario: una prueba de humo de una tarde, **sin GPU** (`llm_habilitado=false`), con salida a Internet
temporal (`egreso_bootstrap=true`) y **todo destruido al final**. Región de ejemplo: `eu-west-1`.

## A. Pasos

**Fase 0 — Antes de empezar (una sola vez)**
1. Pedir al tutor:
   - acceso a la cuenta de la empresa con permisos para VPC, EC2, EBS, endpoints, NAT y **IAM**
     (`iam:CreateRole` e `iam:PassRole` suelen estar restringidos: pedirlos explícitamente);
   - la región y quién paga;
   - una alerta de presupuesto de 5–10 USD en *AWS Budgets*.
2. Instalar AWS CLI v2, el *Session Manager plugin* y OpenTofu.
3. `aws configure sso` (o `aws configure`), `export AWS_PROFILE=<perfil>` y `aws sts get-caller-identity`
   para comprobar que es la cuenta correcta.

**Fase 1 — Preparar el código:** corregir #7 (versión) y #11 (consola), o usar los atajos (§C).

**Fase 2 — Plan (gratis)**
```bash
cd infra/aws && tofu init
tofu plan -var 'region=eu-west-1' -var 'llm_habilitado=false' \
          -var 'egreso_bootstrap=true' -var 'repo_rama=v1.8' -out plan.tfplan
```
Debe decir `Plan: 24 to add, 0 to change, 0 to destroy`. Si aparece `aws_instance.llm`, parar.

**Fase 3 — Crear:** `tofu apply plan.tfplan` y `tofu output`. **Guardar `terraform.tfstate`**: sin él,
los recursos hay que borrarlos a mano.

**Fase 4 — Comprobar el arranque.** Entrar con `aws ssm start-session --target <mdr_instance_id>` y
ejecutar:
```bash
sudo cloud-init status --wait          # status: done
sudo tail -50 /var/log/cloud-init-output.log
systemctl status mdr-triaje            # active (running)
curl -s 127.0.0.1:8787/healthz         # {"ok": true, ...}
findmnt /mnt/traza                     # debe mostrar el EBS (#10)
```

**Fase 5 — Consola:** en tu máquina, `$(tofu output -raw comando_tunel_visor)` y abrir
`http://127.0.0.1:8787`.

**Fase 6 — Alerta de prueba (dentro de la instancia):**
```bash
sudo -u triaje sh -c 'cat /opt/mdr/lab/portatil/alerta-muestra.jsonl >> /opt/mdr/run/alerts.json'
```
Lo esperable: la decisión queda pendiente de aprobación (`BLOQUEAR_IP` retenida por el perfil
bancario), la justificación es de plantilla y no se ejecuta ninguna contención porque no hay conector.

**Fase 7 — Resistencia:**
- `sudo systemctl restart mdr-triaje` y `sudo reboot`: comprobar que la traza continúa y que el disco
  se vuelve a montar.
- Desde tu máquina, comprobar que no hay IP pública: `aws ec2 describe-instances --instance-ids <id>
  --query 'Reservations[].Instances[].PublicIpAddress'` → `[]`.

**Fase 8 — Destruir:**
- `tofu destroy` con las mismas `-var`;
- borrar el bucket temporal si se usó;
- comprobar que no quedan NAT activos (`aws ec2 describe-nat-gateways --filter
  Name=state,Values=available` → vacío);
- revisar *Cost Explorer* al día siguiente.

## B. Tiempos estimados

| Fase | Tiempo | Quién |
|---|---|---|
| Acceso y permisos de la cuenta (una vez) | Horas o días | Tutor |
| Herramientas y credenciales (una vez) | 20–30 min | Tú |
| Corregir #7 y #11 (una vez) | ~1 h | Tú o Claude |
| `tofu init` + `plan` | 1–2 min | Tu máquina |
| `tofu apply` | 4–6 min (el NAT y los endpoints son lo más lento) | AWS |
| Arranque hasta que el MDR responde | 3–5 min (`dnf` 1–2 min; `git clone` ~1,4 s / 15 MB) | AWS |
| Registro de SSM | 2–5 min más | AWS |
| Comprobaciones, consola y alerta | 15–30 min | Tú |
| `tofu destroy` | 5–10 min | AWS |
| **Total** | **1,5–2,5 h la primera vez; 30–45 min las siguientes** | |

**Coste aproximado (eu-west-1):**

| Recurso | ≈ USD/h |
|---|---|
| NAT | 0,048 |
| 3 endpoints de SSM | 0,033 |
| t3.small | 0,023 |
| IP pública + EBS | 0,01 |
| **Total** | **≈ 0,11 USD/h** |

Una tarde de pruebas cuesta menos de 1 USD. **Olvidar el `destroy` cuesta ~80 USD/mes.** Son precios
aproximados: comprobarlos en la calculadora de AWS.

## C. Errores posibles y qué hacer

**Seguros si no se corrigen antes**

| Error | Causa | Solución |
|---|---|---|
| La consola responde `404 {"error": "no encontrado"}` | #11 (reproducido en Amazon Linux 2023) | Corregir #11, o atajo: compilar en local (`npm ci && npm run build`), subir `dist.tgz` a un bucket temporal, `aws s3 presign` y descargarlo con `curl` en `/opt/mdr/visor` (la URL firmada evita dar permisos de S3 al rol) |
| Se despliega una versión vieja | #7 (`repo_rama = "v1.4"`) | `-var 'repo_rama=v1.8'` |
| El arranque falla en el `git clone` | `egreso_bootstrap=false` (valor por defecto) | Poner `egreso_bootstrap=true` |

**Permisos (los más probables en una cuenta de empresa)**

| Mensaje | Solución |
|---|---|
| `ExpiredToken` / `The SSO session has expired` | `aws sso login` |
| `UnauthorizedOperation` | Pedir permisos de EC2/VPC |
| `AccessDenied … iam:CreateRole` / `iam:PassRole` | Pedir el permiso o un rol ya creado |
| `… explicit deny in a service control policy` | La empresa prohíbe esa región o ese tipo de máquina: cambiarlo |
| Rechazo por etiquetas obligatorias (p. ej. `CostCenter`) | Añadirlas en `default_tags` de [main.tf](infra/aws/main.tf) |

**Límites de la cuenta**

| Mensaje | Solución |
|---|---|
| `VpcLimitExceeded` (5 por región) | Liberar VPC o pedir más cuota |
| `AddressLimitExceeded` (5 IP elásticas) | Liberar IP o pedir más cuota |

**Pasajeros de AWS**

| Mensaje | Qué hacer |
|---|---|
| `Invalid IAM Instance Profile name` | AWS aún no "ve" el perfil recién creado: repetir `tofu apply` |
| `TargetNotConnected` (SSM) | Esperar 2–3 min |
| El `apply` falla a mitad | No borrar a mano: corregir y repetir `apply`, o `destroy` |

**Al arrancar**

| Síntoma | Qué significa |
|---|---|
| `findmnt /mnt/traza` vacío | #10: reiniciar la máquina |
| `[ERROR] conector sin clave` en el log | **Normal**: no hay equipos que contener (falla cerrado) |

**En tu máquina**

| Síntoma | Solución |
|---|---|
| `SessionManagerPlugin is not found` | Instalar el plugin |
| El túnel no abre el puerto 8787 | El daemon del laboratorio está usando ese puerto en local: pararlo o usar otro puerto local |

**Al destruir**

| Síntoma | Solución |
|---|---|
| Espera infinita en `Volume … to detach` | #12: parar la instancia y repetir `destroy` |
| `DependencyViolation` | Repetir `tofu destroy` |

**Conclusión:** con #7 y #11 corregidos, lo que queda son sobre todo problemas de permisos de la
cuenta y errores pasajeros de AWS. El código del MDR ya se probó en la distribución de destino.
Solo AWS real puede validar systemd, el EBS, SSM y la red.

---

# Auditoría de permisos, validaciones, pruebas, seguridad, logs y mantenimiento (15/11)

Revisión **de solo lectura**: no se cambió código ni configuración. Las comprobaciones activas se
hicieron en contenedores desechables (`amazonlinux:2023`, `alpine:3.20`, ShellCheck) o en local.

## Resultado de las pruebas

| Suite | Resultado | Dónde |
|---|---|---|
| `prototipo` (motor) | 1290 OK | Local y Amazon Linux 2023 (Python 3.9) |
| `evaluacion` | 63 OK | Local y Amazon Linux 2023 |
| `lab/dataset` | 39 OK | Local |
| `lab/banco` | 157 OK | Local |
| `lab/portatil` | 14 OK | Local |
| `lab/geo_demo` | 12 OK | Local |
| Visor (React/TS) | 466 OK, typecheck y build OK | CI (run `43795604398`) |
| OpenTofu | `tofu validate` OK | CI |
| ShellCheck (todos los `.sh` y `bin/mdr`) | 0 problemas reales (4 falsos positivos SC1007 por el idiom `CDPATH= cd`) | Contenedor |

## Lo que está bien hecho (no hace falta tocar)

- **Permisos en disco:**
  - traza en 0600 (`abrir_append`), `/var/lib/mdr` en 0700 y `/etc/mdr` en 0750 `root:triaje`;
  - `triaje.env` en 0600 y `UMask=0077`;
  - el código queda de root y en solo lectura para el servicio ([instalar.sh](deploy/instalar.sh)).
- **Cuentas de analista:** solo pueden abrir el túnel (`PermitOpen 127.0.0.1:<puerto>`,
  `ForceCommand /usr/sbin/nologin`, sin TTY ni reenvíos), y `sshd -t` se valida antes de recargar
  ([analistas.py](prototipo/herramientas/analistas.py)).
- **API web** ([tablero.py](prototipo/servicio/tablero.py)):
  - escucha solo en 127.0.0.1 y comprueba el Host (anti DNS-rebinding) y el Origin en cada POST
    (anti-CSRF);
  - CORS restringido a su propio origen;
  - cuerpo limitado a 64 KiB y `Content-Length` negativo rechazado;
  - tokens comparados con `hmac.compare_digest` y bloqueo tras varios intentos fallidos;
  - sin travesía de rutas en los ficheros estáticos.
- **Código:** sin `shell=True`, `eval`, `exec` ni `pickle`; YAML siempre con `safe_load`; el conector
  valida los parámetros y falla cerrado si no hay clave.
- **SSH:** `StrictHostKeyChecking=yes` en producción y `accept-new` solo al dar de alta un equipo. El
  `=no` existe únicamente en el ejecutor del laboratorio.
- **Secretos:** nada real en git ni en el historial. Solo hay credenciales de laboratorio puestas a
  propósito (`Cliente2026`, `msfadmin`) y una cabecera de clave falsa en un test.
- **Traza:** cadena de hashes, HMAC y ancla en Wazuh; `flock` y `flush` en cada escritura; la
  retención verifica la cadena antes de podar.
- **Mantenimiento:**
  - las actualizaciones guardan la versión anterior en `/opt/mdr.anterior`;
  - `mdr estado`, `validar-perfil`, `verificar-traza` y `podar-trazas`;
  - la rotación de la clave del conector revoca la vieja (paso 4 de
    [rotar-clave-conector.sh](lab/scripts/rotar-clave-conector.sh); la variable `PUB_VIEJA` sin usar
    no tiene efecto).
- **AWS:** rol de IAM mínimo (SSM y lectura de secretos), IMDSv2 obligatorio, EBS cifrado y sin IP
  pública.

## 13. Las reglas `sudo` del conector aceptan argumentos extra — **Alta**

El sudoers se genera desde el catálogo (`python3 -m prototipo.accion.catalogo --sudoers`) con
comodines, por ejemplo `triaje ALL=(root) NOPASSWD: /sbin/iptables -A INPUT -s * -j DROP`. En sudoers,
**`*` también admite espacios** (sudoers(5): los argumentos se comparan como una sola cadena y el
comodín cruza los límites entre palabras). Comprobado en un contenedor `alpine:3.20` con `sudo -n -l`
(pregunta si se permitiría, **sin ejecutar nada**):

| Comando | Resultado |
|---|---|
| `iptables -A INPUT -s 1.2.3.4 -j DROP` (el legítimo) | Permitido |
| `iptables -A INPUT -s 1.2.3.4 --modprobe=/tmp/x -j DROP` | **Permitido** |
| `iptables -A INPUT -s 1.2.3.4 -j ACCEPT -j DROP` | **Permitido** |
| `passwd -l root` | **Permitido** |
| `iptables -F INPUT …` / `iptables -L` / `service ../../tmp/x stop` | Denegado |

`--modprobe=<programa>` hace que iptables ejecute ese programa para cargar módulos del kernel, aquí
como root. **Consecuencia:** quien obtenga la clave del conector (o comprometa el MDR) no queda
limitado al catálogo: puede obtener root en **todos** los equipos dados de alta, o bloquear la cuenta
de root. El MDR valida los parámetros antes de enviarlos, pero el sudoers es la última barrera en el
equipo y hoy no cumple lo que promete ("la frontera de privilegio es exactamente el catálogo").

**Arreglos:**
1. **Envoltorio** (*wrapper*) propiedad de root, por ejemplo `/usr/local/sbin/mdr-accion`, que reciba
   `ACCION IP` y valide cada argumento (IP con `ipaddress`, usuario distinto de root, servicio en
   una lista permitida). El sudoers permitiría solo ese envoltorio.
2. Con sudo ≥ 1.9.10, usar expresiones regulares ancladas
   (`^-A INPUT -s [0-9.]+(/[0-9]+)? -j DROP$`).

En ambos casos, añadir una prueba que verifique con `sudo -l` que `--modprobe` y `root` quedan
denegados.

## 14. La consola no envía cabeceras anti-clickjacking — Media-baja

No hay `X-Frame-Options` ni `Content-Security-Policy: frame-ancestors` (`grep` sin resultados en
[tablero.py](prototipo/servicio/tablero.py)). Una página maliciosa que el analista visite podría
cargar `http://127.0.0.1:8787` dentro de un *iframe* invisible y engañarle para que pulse "aprobar" o
el *kill switch*. Los clics dentro del iframe son del mismo origen, así que la comprobación del Origin
no lo frena. **Arreglo:** enviar `X-Frame-Options: DENY` y `Content-Security-Policy: frame-ancestors
'none'` en todas las respuestas.

## 15. El daemon no avisa al arrancar si la consola está abierta — Baja

El banner de arranque avisa si la traza no tiene firma HMAC o ancla
([stream.py:1222-1226](prototipo/servicio/stream.py#L1222-L1226)), pero no si no hay
`TRIAJE_CONSOLA_TOKEN` ni `TRIAJE_CONSOLA_OPERADORES` (la consola queda sin autenticación). Solo lo
detecta `mdr estado`. **Arreglo:** una línea `[inicio] consola SIN autenticación` en el banner.

## 16. La traza activa crece sin límite — Media (a largo plazo)

- En producción `TRIAJE_SALIDA` es una ruta **fija** y no hay rotación en caliente (lo dice el
  propio código en `traza.familia`).
- `retener_trazas` solo poda **otros** ficheros `trazas-*.jsonl` y nunca el activo. Con un único
  fichero no poda **nada**.
- La API vuelve a leer y cargar en memoria **toda** la traza cada vez que cambia
  ([tablero.py:719](prototipo/servicio/tablero.py#L719)), es decir, con cada decisión nueva.

**Consecuencia:** tras meses de uso, más disco, más memoria y una consola cada vez más lenta.
**Arreglo:** rotación por tamaño o por fecha (el sistema ya está preparado para segmentos
`<base>.<N>.jsonl`, la "Opción B de #6"), y que la API lea de forma incremental.

## 17. Prueba inestable → CI en rojo en `main` — Media (CI)

Run `43795604398` (el push del 15/11, que solo añadía este `.md`): falla
`test_receptor.TestAgotamientoDeSlots.test_una_ip_no_monopoliza_los_slots`
([test_receptor.py:108](prototipo/tests/test_receptor.py#L108)). La prueba cierra la primera conexión
y envía la segunda **sin esperar** a que el receptor libere el cupo de esa IP. En los servidores de
GitHub, más lentos, a veces aún no lo ha liberado. En local pasa 8 de 8 veces. **Arreglo:** que la
prueba reintente el envío hasta un plazo en lugar de suponer que la liberación es instantánea.
**Mientras tanto,** relanzar el job deja la CI en verde.

## 18. AWS: el código queda en manos del usuario del servicio — Media

[mdr_user_data.sh.tftpl](infra/aws/templates/mdr_user_data.sh.tftpl) hace `chown -R triaje:triaje
/opt/mdr`. Así el servicio puede **modificar su propio código** (persistencia si se compromete). Es
justo lo que [instalar.sh](deploy/instalar.sh) evita (código de root y en solo lectura). **Arreglo:**
que el arranque de AWS use `instalar.sh` con el paquete de `empaquetar.sh`, lo que de paso resuelve
el punto 11.

## 19. AWS: traza sin firma y consola sin autenticación — Media

El arranque de AWS no define `TRIAJE_TRAZA_CLAVE` ni analistas (`mdr configurar` y `mdr analista` no
se ejecutan). La traza queda sin HMAC y la consola abierta a cualquiera que tenga acceso SSM a la
instancia. **Arreglo:** leer la clave y los tokens de Secrets Manager (el permiso ya existe en
[iam.tf](infra/aws/iam.tf)), o ejecutar `mdr configurar` en el arranque.

## 20. Unidad systemd poco endurecida — Baja-media

`systemd-analyze security --offline=true deploy/mdr-triaje.service` → **8.5 EXPOSED**. Ya tiene
`NoNewPrivileges`, `ProtectSystem=full`, `PrivateTmp` y `UMask`. Le faltan, entre otros:
`CapabilityBoundingSet=` (vacío), `ProtectHome=yes`, `PrivateDevices=yes`, `ProtectKernel*`,
`RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX`, `SystemCallFilter=@system-service` y
`ProtectSystem=strict` con `ReadWritePaths`. **Cuidado:** el daemon lanza `ssh` y `tail`, así que
cada restricción hay que probarla con el banco antes de darla por buena.

## 21. Sin copias de seguridad, sonda de salud ni retención automatizadas — Baja-media

- Los *snapshots* del EBS de la traza solo aparecen como comentario en [mdr.tf](infra/aws/mdr.tf); no
  hay `aws_dlm_lifecycle_policy` ni copia de seguridad en la instalación local.
- La sonda de `/healthz` y el cron de retención solo existen como **ejemplos** en
  [deploy/README.md](deploy/README.md) (líneas 92 y 110-120); `instalar.sh` no los instala. Si el
  daemon se queda en bucle de reinicios, nadie recibe aviso.
- En AWS no hay agente de CloudWatch: los logs (journald) se pierden si se pierde la instancia (la
  traza, en el EBS, sí se conserva).

**Arreglo:** que `instalar.sh` instale un *timer* de systemd para la sonda y otro para la retención,
y en AWS una política de snapshots (DLM).

## 22. La API responde 500 a un cuerpo JSON que no es un objeto — Muy baja

En el log de la CI: `error interno en /api/pausa: AttributeError: 'list' object has no attribute
'get'`. Está controlado (no tumba nada), pero debería ser un 400. Otros endpoints ya lo comprueban
(`isinstance(cuerpo, dict)`, [tablero.py:1153](prototipo/servicio/tablero.py#L1153)). **Arreglo:**
comprobarlo una sola vez, justo después del `json.loads` del POST.

## 23. Huecos en la CI — Baja

[ci.yml](.github/workflows/ci.yml) ejecuta pruebas, typecheck, build y `tofu validate`, pero no tiene:
- lint de Python (por ejemplo ruff);
- ShellCheck (hoy pasa limpio, pero nada lo vigila);
- escaneo de secretos (por ejemplo gitleaks);
- auditoría de dependencias (`npm audit`).

Además, las pruebas emiten `ResourceWarning` por ficheros sin cerrar (por ejemplo
[test_triaje.py:308](prototipo/tests/test_triaje.py#L308)).

## No revisado (requiere red o entorno real)

- `npm audit` (envía el árbol de dependencias al registro de npm): pendiente de tu visto bueno.
- Comportamiento real de systemd, SSM y el EBS: solo en una VM de Amazon Linux o en AWS.
- La explotación real de `--modprobe` (punto 13): se comprobó el permiso, no se ejecutó.
