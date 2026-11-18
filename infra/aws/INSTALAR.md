# Instalar el MDR en AWS, paso a paso

Guía corta para tener el MDR funcionando en una cuenta de AWS. Hay dos formas de instalarlo; elige una:

| Quiero… | Variante | Carpeta | Coste aproximado (`eu-west-1`) |
|---|---|---|---|
| **Probar el MDR** con ataques reales, sin ningún cliente | Laboratorio: el banco de pruebas, su Wazuh y el MDR en una máquina | [`laboratorio/`](laboratorio/) | 0,28 $/h · ≈ 2,20 $ una prueba de 8 h |
| **Ponerlo en producción** para un cliente | MDR: solo el MDR, conectado al SIEM y a la red del cliente | [`mdr/`](mdr/) | 0,07–0,11 $/h · ≈ 52–82 $/mes |

> **Estado:** todo está probado sin cuenta (validación, pruebas, simulacro del arranque y un emulador de
> AWS), y el laboratorio, en vivo en un equipo local. **Aún no se ha hecho una instalación en una cuenta
> real**: si algo falla la primera vez, el motivo queda en el registro de arranque (ver «Si algo falla»).

## 1. Lo que necesitas (una vez)

- Una cuenta de AWS con permisos para crear VPC, EC2, IAM y (en producción) S3 y Secrets Manager.
- En tu equipo:
  - [OpenTofu](https://opentofu.org/docs/intro/install/) 1.10 o superior: `tofu version`;
  - [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html): `aws --version`;
  - el [plugin de Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) de la AWS CLI (para entrar a la máquina y abrir la consola sin puertos abiertos).
- Las credenciales de AWS en la terminal (por ejemplo `aws configure sso` y `export AWS_PROFILE=<perfil>`).
  Comprueba que funcionan: `aws sts get-caller-identity`.
- Este repositorio clonado: `git clone https://github.com/vBlanyer/domotai-pasantia.git`.

## 2a. Laboratorio (para probar el MDR)

Cinco órdenes. No hace falta subir nada a S3 ni crear secretos: descarga el MDR v1.9.2 del release de
GitHub y comprueba su huella.

```sh
cd domotai-pasantia/infra/aws/laboratorio

# 1. Variables: la región y el commit de la versión (el de v1.9.2)
cat > laboratorio.tfvars <<'EOF'
region             = "eu-west-1"
laboratorio_commit = "2c64820df320f0eab32583f7de1b4f2d99546d78"
EOF

# 2. Crear (unos 3 minutos; pide confirmación: escribe «yes»)
tofu init
tofu apply -var-file=laboratorio.tfvars

# 3. Esperar a que el laboratorio esté listo (unos 15–20 minutos la primera vez)
aws ssm start-session --region eu-west-1 --target "$(tofu output -raw laboratorio_instance_id)"
#    dentro de la sesión:
sudo journalctl -u mdr-laboratorio -f        # listo cuando aparece «MDR en marcha»; Ctrl+C y «exit»

# 4. Abrir la consola: deja esta orden abierta y entra en http://127.0.0.1:8787
eval "$(tofu output -raw comando_tunel_visor)"
#    el token de acceso (en otra terminal):
tofu output -raw comando_token_admin         # te dice cómo leerlo: sudo cat /root/mdr-token-admin

# 5. Atacar y ver cómo responde el MDR (en una sesión SSM, como en el paso 3)
sudo -i
cd /opt/mdr-laboratorio
sh lab/banco/banco.sh atacar                 # menú con los ataques de las 10 familias
```

**Para ahorrar** cuando no lo uses, para la máquina y vuelve a encenderla después (el laboratorio se
rehace solo al encender, en unos minutos):

```sh
aws ec2 stop-instances  --region eu-west-1 --instance-ids "$(tofu output -raw laboratorio_instance_id)"
aws ec2 start-instances --region eu-west-1 --instance-ids "$(tofu output -raw laboratorio_instance_id)"
```

**Para borrarlo todo:** `tofu destroy -var-file=laboratorio.tfvars`. Más detalle (secretos, cuotas,
costes): [laboratorio/DESPLIEGUE.md](laboratorio/DESPLIEGUE.md).

## 2b. MDR (producción)

**La forma rápida**, para una demostración: con salida a Internet, el MDR v1.9.2 del release de GitHub y
un analista `admin` generado en la máquina.

```sh
cd domotai-pasantia/infra/aws/mdr
tofu init
tofu apply -var region=eu-west-1 -var egreso_bootstrap=true     # unos 3 minutos; escribe «yes»

# El arranque tarda unos minutos más. Después, la consola:
eval "$(tofu output -raw comando_tunel_visor)"                  # y abre http://127.0.0.1:8787
tofu output -raw comando_token_admin                            # cómo leer el token de acceso
```

**Para producción de verdad** sigue [mdr/DESPLIEGUE.md](mdr/DESPLIEGUE.md): sin salida a Internet (el
paquete en S3), la clave de la traza y los analistas en Secrets Manager, el estado de OpenTofu en S3 y
las cuotas. Además, para que el MDR reciba las alertas y pueda contener, la VPC tiene que llegar a la red
del cliente (una VPN o un enlace privado), que esta configuración **no** crea.

## Si algo falla

- **`tofu apply` se para con un mensaje en español** (por ejemplo, «La variante laboratorio necesita un
  MDR >= 1.9.2»): es una protección; el mensaje dice qué cambiar. No se ha creado nada.
- **Error de cuota** (`VcpuLimitExceeded`): la cuenta no permite esa máquina. El laboratorio necesita
  4 vCPU estándar; la GPU, 4 vCPU de instancias G (en cuentas nuevas suele ser 0). Se piden en la consola
  de *Service Quotas* (la guía de cada variante trae los códigos).
- **La consola no responde** tras el apply: el arranque aún no ha terminado o ha fallado. Entra por SSM y
  mira el registro: `sudo tail -50 /var/log/mdr-arranque.log` y, en el laboratorio,
  `sudo journalctl -u mdr-laboratorio`. El arranque se ejecuta una vez: tras corregir, se recrea la
  máquina con `tofu apply -replace=aws_instance.laboratorio …` (o `aws_instance.mdr`).
- **Al terminar, no olvides el `destroy`**: lo que queda encendido se cobra por hora.
