# Inventario de lo que crea la variante laboratorio

Generado con `infra/aws/emulador/inventario.py` a partir de los planes de `probar.sh` contra AWS
Emulator. Es lo que `tofu apply` crearía en cada escenario; sirve para revisar el despliegue y
para la estimación de [costes](../COSTES.md). Los identificadores reales los pone AWS al aplicar.

## Escenario E · 23 recursos

La variante laboratorio: una máquina (t3.xlarge, con egreso) que levanta el banco, Wazuh y el MDR (>= 1.9.2). No se conecta a ningún cliente.

| Recurso | Tipo | Por qué existe |
|---|---|---|
| `aws_instance.laboratorio` | `aws_instance` | La máquina del laboratorio: el banco (Containerlab), su Wazuh y el MDR. |
| `aws_volume_attachment.traza` | `aws_volume_attachment` | Engancha el disco de la traza al MDR (destroy apaga antes de soltarlo). |
| `module.base.aws_ebs_volume.traza` | `aws_ebs_volume` | Disco cifrado de la traza y del estado del MDR (/var/lib/mdr). |
| `module.base.aws_eip.nat[0]` | `aws_eip` | IP pública del NAT (solo con egreso). |
| `module.base.aws_iam_instance_profile.instancia` | `aws_iam_instance_profile` | Perfil que asocia el rol a la instancia del MDR. |
| `module.base.aws_iam_role.instancia` | `aws_iam_role` | Rol del MDR. |
| `module.base.aws_iam_role_policy_attachment.ssm` | `aws_iam_role_policy_attachment` | El MDR se gestiona por SSM. |
| `module.base.aws_internet_gateway.igw[0]` | `aws_internet_gateway` | Salida a Internet de la subred pública (solo con egreso). |
| `module.base.aws_nat_gateway.nat[0]` | `aws_nat_gateway` | NAT para que el primer arranque descargue paquetes (solo con egreso); se cobra mientras exista. |
| `module.base.aws_route.privada_egreso[0]` | `aws_route` | Salida de la subred privada por el NAT: la usa el primer arranque, y queda mientras haya egreso. |
| `module.base.aws_route_table.privada` | `aws_route_table` | Rutas de la subred privada (sin salida a Internet salvo el NAT). |
| `module.base.aws_route_table.publica[0]` | `aws_route_table` | Rutas de la subred pública hacia el internet gateway. |
| `module.base.aws_route_table_association.privada` | `aws_route_table_association` | Asocia la subred privada a sus rutas. |
| `module.base.aws_route_table_association.publica[0]` | `aws_route_table_association` | Asocia la subred pública a sus rutas. |
| `module.base.aws_security_group.endpoints` | `aws_security_group` | Cortafuegos de los endpoints: 443 desde la VPC. |
| `module.base.aws_security_group.mdr` | `aws_security_group` | Cortafuegos del MDR: sin entradas; salida libre. |
| `module.base.aws_subnet.privada` | `aws_subnet` | Subred sin IP pública donde viven las instancias. |
| `module.base.aws_subnet.publica[0]` | `aws_subnet` | Subred pública que solo aloja el NAT del primer arranque. |
| `module.base.aws_vpc.main` | `aws_vpc` | Red privada del MDR. |
| `module.base.aws_vpc_endpoint.s3` | `aws_vpc_endpoint` | Endpoint de S3: paquete, perfil y modelos sin salir a Internet. |
| `module.base.aws_vpc_endpoint.ssm["ec2messages"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |
| `module.base.aws_vpc_endpoint.ssm["ssm"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |
| `module.base.aws_vpc_endpoint.ssm["ssmmessages"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |
