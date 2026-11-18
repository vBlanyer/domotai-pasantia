# Despliegue del laboratorio en AWS (entorno de pruebas)

Guía completa de la variante laboratorio (`infra/aws/laboratorio/`; la guía corta para empezar es
[../INSTALAR.md](../INSTALAR.md)).

Con `variante = "laboratorio"` la misma instancia levanta **el laboratorio del banco** (15 equipos en
Containerlab), **su Wazuh** y **el MDR**, como en local, para probar el MDR antes de ponerlo delante de un
cliente. **No se conecta a ningún cliente**: los ataques, las alertas y las contenciones ocurren dentro de
la máquina. Qué se crea: el [inventario](inventario/); cuánto cuesta: [COSTES.md](COSTES.md).

Necesitas OpenTofu ≥ 1.10, AWS CLI v2 con el plugin de Session Manager y acceso a la cuenta con permisos
para crear VPC, EC2 e IAM (y Secrets Manager o S3 si los usas).

## 1. Cuotas de la cuenta

| Cuota | Código | Mínimo necesario |
|---|---|---|
| Instancias bajo demanda estándar (vCPU) | `ec2` · `L-1216C47A` | 4 (`t3.xlarge`) |
| IP elásticas | `ec2` · `L-0263D0A3` | 1 (la del NAT) |
| VPC por región | `vpc` · `L-F678F1CE` | 1 libre |
| Endpoints de interfaz por VPC | `vpc` · `L-29B6F2EB` | 3 (SSM) |

```sh
aws service-quotas get-service-quota --region <region> --service-code ec2 --quota-code L-1216C47A \
    --query 'Quota.Value'
```

## 2. Requisitos y variables


- un MDR **≥ 1.9.2** publicado (la 1.9.1 no trae los arreglos del laboratorio; `tofu plan` lo rechaza);
- `laboratorio_commit`, el commit de su etiqueta (`git rev-parse v1.9.2^{commit}` en el repositorio);
  para la v1.9.2 es `2c64820df320f0eab32583f7de1b4f2d99546d78`. El arranque clona la etiqueta y **se para** si el commit no es ese;
- salida a Internet en el primer arranque (descarga Docker, Containerlab y la imagen de Wazuh): la
  configuración crea el NAT siempre. Sin GPU.

Copia `laboratorio.tfvars.ejemplo` a `laboratorio.tfvars` (git lo ignora) y rellena la región. Para la
v1.9.2 no hace falta nada más: la versión, la huella del paquete y el commit ya vienen puestos. Los
secretos (clave de la traza y analistas) son opcionales: sin ellos se generan en la máquina. Para un
equipo, el estado de OpenTofu en S3: copia `backend.tf.ejemplo` a `backend.tf`.

## 3. Crear

```sh
cd infra/aws/laboratorio
tofu init
tofu plan  -var-file=laboratorio.tfvars -out laboratorio.plan     # compáralo con el inventario
tofu apply laboratorio.plan
```

## 4. Esperar a que esté listo

 El arranque instala lo necesario y deja en marcha la unidad
`mdr-laboratorio`, que levanta el banco, aprovisiona el conector, comprueba que todo está sano y que Wazuh
genera alertas (`banco.sh test` y `banco.sh comprobar-alertas`) y arranca el MDR. Tarda unos minutos:

```sh
aws ssm start-session --region <region> --target "$(tofu output -raw laboratorio_instance_id)"
sudo journalctl -u mdr-laboratorio -f        # listo cuando aparece «MDR en marcha»
```

## 5. Entrar a la consola

```sh
eval "$(tofu output -raw comando_tunel_visor)"   # deja abierto el túnel y entra en http://127.0.0.1:8787
tofu output -raw comando_token_admin              # cómo leer el token (o el de un analista de tu secreto)
```

## 6. Atacar y observar

 (en la sesión SSM, como root, desde `/opt/mdr-laboratorio`):

```sh
sudo -i
cd /opt/mdr-laboratorio
sh lab/banco/banco.sh atacar             # menú de ataques de las 10 familias
sh lab/banco/banco.sh atacar continuo    # ataques variados sin fin (Ctrl+C para parar)
sh lab/banco/banco.sh vigilar            # servicios en verde/rojo
sh lab/banco/banco.sh restaurar          # deja el banco sano tras una prueba
sh lab/banco/banco.sh comprobar-alertas  # Wazuh sigue generando alertas
```

## 7. Parar y encender

 para ahorrar (el disco de la traza se conserva y la cadena continúa):

```sh
aws ec2 stop-instances  --region <region> --instance-ids "$(tofu output -raw laboratorio_instance_id)"
aws ec2 start-instances --region <region> --instance-ids "$(tofu output -raw laboratorio_instance_id)"
```

Al encender, `mdr-laboratorio` rehace el laboratorio desde cero (la red de Containerlab y Wazuh no
sobreviven a un reinicio) antes de arrancar el MDR: unos minutos. Las contenciones de la sesión anterior
ya no existen (los equipos se recrean), así que se anotan como revertidas en la traza: el MDR vuelve a
decidir los ataques repetidos y la consola no las lista como activas. Si algo falla, la unidad lo
reintenta (cada 30 s, hasta 5 veces en 2 h) y el motivo queda en `journalctl -u mdr-laboratorio`.

**En la instancia, no uses `reiniciar.sh`, `lab.sh up`/`down` ni `banco.sh down`**: el servicio ya
gestiona el laboratorio y el daemon, y esas órdenes lo cortan a medias. Para reiniciarlo todo:
`sudo systemctl restart mdr-laboratorio`.

## 8. Apagar del todo

```sh
tofu destroy -var-file=laboratorio.tfvars
```

`destroy` apaga la instancia antes de soltar el disco de la traza, y el disco se borra. Lo que sigue
cobrándose después: los secretos que hayas creado y el bucket del estado, si lo usas.

## Qué se comprueba por primera vez en el despliegue real

Las pruebas locales (`tofu validate`, pruebas estáticas, AWS Emulator y el laboratorio en vivo en un equipo
local) no pueden comprobar: la evaluación real de IAM, que Docker y Containerlab 0.79.0 se instalen en
Amazon Linux 2023, el arranque en una instancia real ni el túnel SSM. Si el primer arranque falla, el
motivo está en `/var/log/mdr-arranque.log` y en `journalctl -u mdr-laboratorio`; tras corregir, se recrea
la máquina con `tofu apply -replace=aws_instance.laboratorio -var-file=laboratorio.tfvars`.
