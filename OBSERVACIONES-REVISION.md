# Observaciones de la revisión (15/11/2026)

Detalles encontrados al recorrer el código para explicar las tecnologías, el RAG, MITRE/D3FEND y el
almacenamiento. **No se ha cambiado nada del código**: esto es solo una lista para revisar.

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
