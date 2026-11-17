# Diseño: variante «laboratorio» del despliegue en AWS

17/11/2026 · Estado: decisiones del usuario incorporadas (arreglos del laboratorio en v1.9.2; parar y encender).

## Para qué

Hoy `infra/aws` despliega **solo el MDR**: es la variante de producción, que se conecta al SIEM y a la
red reales del cliente. La empresa quiere además poder **probar el MDR en AWS antes de ponerlo delante
de un cliente**, sin depender de ninguno: con su Wazuh, una red con equipos que atacar y el MDR
conteniendo de verdad. Eso ya existe y está validado en local: el **laboratorio del banco**
([lab/banco/](../../lab/banco/), [RUNBOOK.md](../../RUNBOOK.md) §2). Esta variante lo lleva a AWS.

Con las dos, la empresa elige según el caso: `variante = "mdr"` (producción, lo de hoy) o
`variante = "laboratorio"` (entorno de pruebas completo).

Como el resto de `infra/aws`, se prueba **sin cuenta ni coste** contra AWS Emulator, y queda lista para
aplicarla en una cuenta real cuando la empresa lo decida.

## Objetivos

- Una variable `variante` en `infra/aws`: `"mdr"` por defecto (nada cambia para quien ya la usa) o
  `"laboratorio"`.
- Con `"laboratorio"`, la instancia del MDR se convierte en una máquina más grande cuyo arranque levanta
  **lo mismo que en el portátil**: los 15 nodos del banco en Containerlab, el Wazuh del laboratorio, el
  monitor de salud, el conector aprovisionado y el daemon del MDR con la consola, leyendo las alertas de
  Wazuh.
- La empresa entra igual que en la variante MDR: túnel SSM a la consola (`127.0.0.1:8787`) y sesión SSM
  para lanzar ataques (`sh lab/banco/banco.sh atacar`, `atacar continuo`, `restaurar`, `vigilar`).
- Pruebas: escenarios nuevos en `infra/aws/emulador/probar.sh`, inventario, costes, guía.

## Fuera de alcance

- La GPU en la variante laboratorio (el justificador va por plantilla, como en la demo por defecto).
  `tofu plan` lo rechaza con un mensaje claro.
- La tercera opción que se descartó: MDR de producción en su máquina más un «cliente falso» en otra,
  conectados por la red de la VPC. Es la más fiel, pero exige enrutar hasta la red de Containerlab y
  envío de Wazuh por red, nada de eso probado. Queda como mejora futura.
- Probar el arranque del laboratorio en el simulacro: necesitaría Containerlab dentro de un contenedor
  (Docker dentro de Docker con privilegios). El arranque se comprueba con `bash -n`, las pruebas
  estáticas y el emulador; el laboratorio en sí ya está validado en local.
- La red pequeña, la demo portátil y el laboratorio de oficina: solo el banco.

## Lo que no puede pasar (anti-objetivos)

- Que la variante laboratorio cambie la de producción: con `variante = "mdr"` el plan debe ser
  **idéntico** al de hoy (mismos recursos, mismo script de arranque).
- Que se confunda una con otra en una cuenta real: el laboratorio se nombra como tal (etiquetas,
  `nombre`), y la guía avisa de que **no** se conecta a ningún cliente.
- Un arranque que «termina» sin el laboratorio sano: si Containerlab, Wazuh o el aprovisionamiento
  fallan, el arranque se para con el motivo en su registro, como el del MDR.

## Restricciones

- Lo que ya está: VPC privada sin puertos abiertos, acceso solo por SSM, IMDSv2, discos cifrados,
  `set -euo pipefail`, reintentos en las descargas, fallo cerrado.
- **Necesita egreso** (`egreso_bootstrap = true`): descarga Docker, Containerlab, la imagen de Wazuh
  (2,5 GB) y construye la imagen de los nodos. `tofu plan` lo exige.
- El código del laboratorio **no va en el paquete del release** (`mdr-<versión>.tar.gz` solo lleva el
  producto). El repositorio es público en GitHub: el arranque lo clona en la etiqueta de la versión
  (`v<mdr_version>`) y **comprueba que el commit es el esperado** (`laboratorio_commit`), igual que el
  paquete se comprueba por su huella. Si no coincide, se para.
- **Necesita un MDR ≥ 1.9.2**: los arreglos del laboratorio (abajo) no están en la 1.9.1. `tofu plan`
  rechaza la 1.9.1 con laboratorio, igual que con la GPU. Una sola publicación (v1.9.2) sirve a las dos.
- La consola compilada (`visor/dist`) **no está en git**: sale del paquete del release, verificado por
  su huella con las mismas variables de la variante MDR (`mdr_paquete_url`, `mdr_paquete_sha256`). Así
  el código del clon y la consola son de la misma versión.
- No tocar el banco ni el Wazuh del equipo local del usuario durante las pruebas (el emulador no
  levanta nada; el simulacro no se usa para esta variante).

## Enfoques considerados

1. **Una variable en `infra/aws` y una sola máquina con todo** — elegido por el usuario. Reutiliza la
   red, el acceso SSM, el disco de la traza, las salidas, el emulador y las pruebas; dentro de la
   máquina el laboratorio corre exactamente como en local, que es lo validado.
2. **Una carpeta aparte (`infra/aws-laboratorio`)**: aislada de producción, pero duplica red, IAM,
   endpoints y pruebas.
3. **Dos máquinas (MDR de producción + cliente falso)**: la más fiel a producción, pero terreno nuevo
   (rutas hacia la red de Containerlab, Wazuh enviando por red). Mejora futura.

## Cómo (lo decidido)

- **Misma instancia, otro arranque.** `aws_instance.mdr` cambia de tipo, de disco raíz y de plantilla de
  arranque según `variante`. Todo lo demás (EBS de la traza, endpoints SSM, rol, salidas
  `comando_tunel_visor` y `comando_token_admin`) se reutiliza tal cual.
- **Variables nuevas:** `variante` (`"mdr"` | `"laboratorio"`, validada), `laboratorio_tipo`
  (por defecto `t3.xlarge`: 4 vCPU y 16 GB, como el portátil donde se validó), `laboratorio_disco_gb`
  (raíz, por defecto 40 GB: la imagen de Wazuh ocupa 2,5 GB) y `laboratorio_commit` (los 40 caracteres
  del commit de la etiqueta; obligatorio con laboratorio).
- **Precondiciones:** laboratorio exige `egreso_bootstrap = true`, `llm_habilitado = false`,
  `mdr_version` distinta de `1.9.1` y un `laboratorio_commit` de 40 caracteres hexadecimales.

### Arreglos en el laboratorio (repositorio, entran en la v1.9.2)

Que cada script termine con error claro cuando algo falla, para que el arranque se pare con el motivo.
Cada uno con su prueba escrita antes del cambio; en el equipo local se usan igual que hoy.

1. **`banco.sh test` falla de verdad:** cuenta las comprobaciones fallidas y termina con `exit 1` y un
   resumen si hubo alguna. La salida por pantalla no cambia.
2. **Esperas a Wazuh con tope:** una sola función de espera (tope por defecto 10 min) que usan las tres
   esperas de hoy (`wazuh-run.sh` ×2 y `lab.sh`). Si se agota, enseña el final del registro de Wazuh y
   termina con error.
3. **`banco.sh comprobar-alertas`:** provoca un evento inofensivo que dispara una regla propia del
   banco, espera (con tope) a verlo en `alerts.json` y falla si no llega; deja el banco como estaba.
   Comprueba la cadena Wazuh → alertas de punta a punta (también útil antes de una demo en local).
4. **`lab/banco/servicio-mdr.sh`** (nuevo; `reiniciar.sh` no se toca, sigue siendo el de la terminal):
   en cada encendido rehace el laboratorio (`down` → `up` → `aprovisionar` → `test` →
   `comprobar-alertas`) y arranca el daemon con las mismas variables que `reiniciar.sh`
   (`TRIAJE_NODO_GESTION`, `TRIAJE_SALUD_CONTENEDOR`, bases de geolocalización de muestra), pero con la
   traza en un **fichero fijo** de `/var/lib/mdr`: la cadena firmada sigue entre encendidos.

### Arranque de la máquina (`templates/laboratorio_user_data.sh.tftpl`, solo la primera vez)

En orden, cada paso con reintentos y parando si falla:

1. monta el EBS de la traza en `/var/lib/mdr` (mismo bloque que la plantilla del MDR);
2. instala Docker, Containerlab (versión fijada), Python 3 + PyYAML y git;
3. clona el repositorio en `v<mdr_version>` en `/opt/mdr-laboratorio` y comprueba `laboratorio_commit`;
   descarga el paquete, comprueba su huella y copia su `visor/dist` al clon;
4. `construir-imagen.sh`;
5. genera la clave de la traza y el token del analista `admin` en `/root/mdr-token-admin` (o los lee de
   Secrets Manager si se dan los ARN, igual que la variante MDR), para que `comando_token_admin` valga;
6. instala y arranca la unidad de systemd `mdr-laboratorio`, que ejecuta `servicio-mdr.sh` en **cada**
   encendido y lo reinicia si se cae. El daemon corre como root (necesita `docker exec` en `mdr-siem`).

### Encender y apagar

Se admiten las tres formas de uso, y la guía las explica con su coste (orientativo, `eu-west-1`, a
recalcular con los precios del día):

| Uso | Coste aproximado | Cómo |
|---|---|---|
| Encendido 24/7 | ≈ 200 $/mes | — |
| Parar y encender (8 h × 22 días laborables) | ≈ 100 $/mes | `aws ec2 stop-instances` / `start-instances`; al encender, `mdr-laboratorio` rehace el laboratorio en unos minutos antes de arrancar el MDR |
| `destroy` al terminar | solo las horas de uso | cada vez, arranque completo (descargas e instalación) y se pierde la traza |

Parada sigue cobrando unos 68 $/mes (sobre todo el NAT y los endpoints de SSM).

### Pruebas y entregables

- **Emulador:** escenario **E** (laboratorio: tipo de instancia, disco, script de arranque con el clon
  en la etiqueta y la comprobación del commit, Containerlab, la unidad; sin GPU) y **F** (laboratorio sin
  egreso, y laboratorio con 1.9.1 → rechazados). A–D no cambian: con `variante = "mdr"` el plan es el
  mismo que hoy.
- **Pruebas estáticas** de la plantilla nueva (como las de la del MDR) y de los arreglos del laboratorio.
- **Entregables:** inventario `escenario-e.json`, escenario E en `COSTES.md`, sección en
  `DESPLIEGUE.md` («Variante laboratorio: entrar, atacar, restaurar, parar y encender, apagar»; avisa de
  que no se conecta a ningún cliente), README y CHANGELOG.

## Decisiones del constructor (revisables)

- `t3.xlarge` y 40 GB de raíz; tope de espera de 10 min.
- La variante laboratorio ignora `perfil_url` y `red_cliente_cidrs` (usa el perfil del banco).
- El nombre de los recursos y las etiquetas llevan «laboratorio» cuando `variante = "laboratorio"`.

## Lo que queda al constructor

- La forma exacta de instalar Containerlab en Amazon Linux 2023 (repositorio RPM oficial o su script),
  fijando la versión.
- Qué evento inofensivo usa `comprobar-alertas` y qué regla del banco dispara.
- Qué comprobaciones exactas lleva `comprobar.py` para E y F, siguiendo el estilo de A–D.
- Vigilar el límite de 16 KB del script de arranque.
