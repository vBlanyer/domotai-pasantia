# infra/aws/laboratorio — el laboratorio de pruebas en AWS (OpenTofu)

La variante de **pruebas**: una máquina con el **laboratorio del banco** (15 equipos en Containerlab), su
**Wazuh** y el **MDR**, como en local, para que la empresa pruebe el MDR antes de ponerlo delante de un
cliente. **No se conecta a ningún cliente**: los ataques, las alertas y las contenciones ocurren dentro de
la máquina. La variante de producción y el índice están en [infra/aws/](../README.md); la guía corta de
instalación, en [../INSTALAR.md](../INSTALAR.md).

> **Estado (17/11/2026):** probado sin cuenta (validación, pruebas estáticas y AWS Emulator) y el
> laboratorio, en vivo en un equipo local (dos arranques sobre la misma traza). **Sin `apply` real.**

Guía completa: [DESPLIEGUE.md](DESPLIEGUE.md) · costes: [COSTES.md](COSTES.md) · lo que se crea:
[inventario/](inventario/) · variables: [laboratorio.tfvars.ejemplo](laboratorio.tfvars.ejemplo) ·
estado remoto: [backend.tf.ejemplo](backend.tf.ejemplo).

**Esta carpeta usa el módulo común [`../modulos/base`](../modulos/base/)** (red, permisos de la instancia y
disco de la traza). Si la copias fuera del repositorio, lleva también `modulos/base/` en la misma posición
relativa (`../modulos/base`).

## Qué crea

- La red común (VPC con subred privada, endpoints de SSM y S3) y, **siempre**, el NAT: el primer arranque
  descarga Docker, Containerlab y la imagen de Wazuh.
- Una EC2 `t3.xlarge` (4 vCPU, 16 GB, 40 GB de disco) con Amazon Linux 2023. Su arranque, una vez:
  1. monta el **disco cifrado de la traza** en `/var/lib/mdr` (el mismo bloque que la variante MDR);
  2. instala Docker y **Containerlab 0.79.0** (comprobado por su huella);
  3. clona el repositorio en la etiqueta `v<mdr_version>` y **se para si el commit no es
     `laboratorio_commit`**; toma la consola compilada del paquete del release (comprobado por su huella);
  4. construye la imagen de los nodos, escribe la clave de la traza y el acceso a la consola con token, e
     instala la unidad **`mdr-laboratorio`**.
- La unidad `mdr-laboratorio` (`lab/banco/servicio-mdr.sh`) se ejecuta en **cada encendido**: rehace el
  banco desde cero, aprovisiona el conector, comprueba que todo está sano y que Wazuh genera alertas,
  anota como revertidas las contenciones de la sesión anterior y arranca el MDR. Por eso se puede parar
  y encender la máquina para ahorrar.

## Variables (`variables.tf`)

| Variable | Por defecto | Para qué |
|---|---|---|
| `laboratorio_commit` | — (**obligatoria**) | Commit de la etiqueta `v<mdr_version>`; para v1.9.2, `2c64820df320f0eab32583f7de1b4f2d99546d78` |
| `region` | `eu-west-1` | Región |
| `mdr_version` | `1.9.2` | Versión del MDR (≥ 1.9.2) |
| `mdr_paquete_url`, `mdr_paquete_sha256` | release de GitHub, huella de 1.9.2 | Paquete del que sale la consola |
| `laboratorio_tipo`, `laboratorio_disco_gb` | `t3.xlarge`, `40` | Máquina y disco raíz |
| `secreto_traza_arn`, `secreto_operadores_arn` | (se generan) | Clave de la traza y analistas en Secrets Manager |
| `proyecto`, `vpc_cidr` | `mdr-laboratorio`, `10.91.0.0/16` | Nombres y red (distintos de producción) |

## Cómo probarla

Todo sin cuenta ni coste, desde la raíz del repositorio:

```sh
(cd infra/aws/laboratorio && tofu init -backend=false && tofu validate)   # sintaxis y tipos
python3 -m unittest prototipo.tests.test_infra_aws                         # pruebas estáticas
python3 -m unittest lab.banco.tests.test_arranque_desatendido              # scripts del banco (docker falso)
sh infra/aws/emulador/probar.sh laboratorio                                # E y F contra AWS Emulator (~3 min)
```

| Escenario | Qué es | Qué se espera |
|---|---|---|
| E | El laboratorio (MDR ≥ 1.9.2) | se crea; 16 comprobaciones |
| F | El laboratorio con el paquete 1.9.1 | **rechazado** por la precondición (es lo correcto) |

**En vivo, en un equipo local** (baja y levanta el banco y Wazuh de ese equipo):

```sh
sh lab/banco/banco.sh comprobar-alertas                          # con el banco levantado: Wazuh de punta a punta
TRIAJE_SALIDA=/tmp/prueba.jsonl bash lab/banco/servicio-mdr.sh   # lo que hará la máquina en AWS; Ctrl+C para parar
```

Las comprobaciones del escenario están en [emulador/comprobar.py](emulador/comprobar.py) y sus variables
en [emulador/escenarios.sh](emulador/escenarios.sh).
