# infra/aws — el MDR en AWS (OpenTofu)

Dos variantes, cada una en su carpeta y autosuficiente (se despliega, prueba y documenta por su cuenta;
quitar una es borrar su carpeta). **Para instalar, empieza por [INSTALAR.md](INSTALAR.md).**

| Variante | Para qué | Carpeta |
|---|---|---|
| **MDR** (producción) | El MDR (y, opcional, el modelo en GPU) conectado al SIEM y a la red de un cliente | [mdr/](mdr/README.md) |
| **Laboratorio** (pruebas) | El banco de pruebas, su Wazuh y el MDR en una máquina, para probar el MDR antes de un cliente; no se conecta a ninguno | [laboratorio/](laboratorio/README.md) |

Lo común a las dos (red, permisos de la instancia, disco de la traza) está en el módulo
[modulos/base/](modulos/base/). Diseño:
[despliegue-aws-opentofu.md](../../documentacion/04-fase4-diseno-de-arquitectura/despliegue-aws-opentofu.md),
[diseno-aws-laboratorio.md](../../documentacion/05-fase5-implementacion-del-prototipo/diseno-aws-laboratorio.md) y
[diseno-aws-dos-carpetas.md](../../documentacion/05-fase5-implementacion-del-prototipo/diseno-aws-dos-carpetas.md).

> **Estado (17/11/2026):** las dos probadas sin cuenta; el laboratorio, además, en vivo en local. **Sin
> `apply` real todavía.** El MDR que instalan es la v1.9.2 publicada.

## Cómo probar las dos

```sh
python3 -m unittest prototipo.tests.test_infra_aws   # pruebas estáticas de las dos variantes
sh infra/aws/emulador/probar.sh --listar             # las variantes y sus escenarios
sh infra/aws/emulador/probar.sh                      # todos los escenarios contra AWS Emulator (~12 min)
sh infra/aws/emulador/probar.sh mdr                  # o los de una variante
```

`ok` y «rechazado como se esperaba» son los resultados buenos: algunos escenarios comprueban que
OpenTofu **se niega** a crear una configuración que fallaría (por ejemplo, con el paquete 1.9.1).
[AWS Emulator](https://docs.aws.amazon.com/emulator/) emula en local la API de AWS (en memoria, sin
telemetría); `probar.sh` aplica los `.tf` reales en una copia temporal con un *override* que apunta el
proveedor al emulador, y suple dos huecos suyos (v1.0.492): `RunInstances` no hereda la zona de la
subred, y no trae la Deep Learning AMI de la GPU.

## Qué prueba cada capa

| Capa | Qué comprueba | Qué no |
|---|---|---|
| `tofu validate` + pruebas estáticas | Sintaxis, tipos, que las plantillas y los `.tf` dicen lo que deben | Nada se ejecuta |
| Simulacro (`simulacro/`) | El arranque del MDR de verdad en `amazonlinux:2023`: instala, firma la traza, monta el disco, y se para cuando falta algo | AWS: ni red, ni IAM, ni la GPU |
| AWS Emulator (`emulador/`) | El grafo de recursos entero, en orden, las precondiciones y lo que llega a cada instancia | No arranca máquinas ni evalúa IAM |

**Qué no prueba ninguna** (solo un despliegue real):

- que la búsqueda de la AMI encuentre Amazon Linux 2023 y la Deep Learning AMI en la región;
- la evaluación real de IAM y su retraso de propagación;
- el arranque en una instancia Nitro de verdad (nombres NVMe, cloud-init, systemd);
- la red real: `dnf` sin egreso, el DNS privado de los endpoints, el túnel SSM;
- la GPU: drivers, CUDA, la compilación de llama.cpp y la memoria;
- las cuotas y los costes de la cuenta.

## Herramientas comunes

- [emulador/](emulador/): `probar.sh` (descubre los escenarios de cada variante), `comun.py` (lo común de
  las comprobaciones) e `inventario.py` (genera el `inventario/` de una variante a partir de los planes).
- [simulacro/](simulacro/): el arranque del MDR en `amazonlinux:2023` con Docker.
