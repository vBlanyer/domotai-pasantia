# Inventario de lo que crea infra/aws

Generado con `infra/aws/emulador/inventario.py` a partir de los planes de `probar.sh` contra AWS
Emulator. Es lo que `tofu apply` crearía en cada escenario; sirve para revisar el despliegue y
para la estimación de [costes](../COSTES.md). Los identificadores reales los pone AWS al aplicar.

## Escenario A · 27 recursos

Con egreso para el primer arranque (NAT), paquete del release de GitHub, sin secretos ni GPU.

| Recurso | Tipo | Por qué existe |
|---|---|---|
| `aws_ebs_volume.traza` | `aws_ebs_volume` | Disco cifrado de la traza y del estado del MDR (/var/lib/mdr). |
| `aws_eip.nat[0]` | `aws_eip` | IP pública del NAT (solo con egreso). |
| `aws_iam_instance_profile.gpu` | `aws_iam_instance_profile` | Perfil que asocia el rol de la GPU a su instancia. Se crea aunque no haya GPU (sin coste). |
| `aws_iam_instance_profile.instancia` | `aws_iam_instance_profile` | Perfil que asocia el rol a la instancia del MDR. |
| `aws_iam_role.gpu` | `aws_iam_role` | Rol propio de la GPU (sin acceso a los secretos del MDR). Se crea aunque no haya GPU (sin coste). |
| `aws_iam_role.instancia` | `aws_iam_role` | Rol del MDR. |
| `aws_iam_role_policy_attachment.gpu_ssm` | `aws_iam_role_policy_attachment` | La GPU se gestiona por SSM. Se crea aunque no haya GPU (sin coste). |
| `aws_iam_role_policy_attachment.ssm` | `aws_iam_role_policy_attachment` | El MDR se gestiona por SSM. |
| `aws_instance.mdr` | `aws_instance` | El MDR (daemon y consola). |
| `aws_internet_gateway.igw[0]` | `aws_internet_gateway` | Salida a Internet de la subred pública (solo con egreso). |
| `aws_nat_gateway.nat[0]` | `aws_nat_gateway` | NAT para que el primer arranque descargue paquetes (solo con egreso); se cobra mientras exista. |
| `aws_route.privada_egreso[0]` | `aws_route` | Salida de la subred privada por el NAT: la usa el primer arranque, y queda mientras egreso_bootstrap = true. |
| `aws_route_table.privada` | `aws_route_table` | Rutas de la subred privada (sin salida a Internet salvo el NAT). |
| `aws_route_table.publica[0]` | `aws_route_table` | Rutas de la subred pública hacia el internet gateway. |
| `aws_route_table_association.privada` | `aws_route_table_association` | Asocia la subred privada a sus rutas. |
| `aws_route_table_association.publica[0]` | `aws_route_table_association` | Asocia la subred pública a sus rutas. |
| `aws_security_group.endpoints` | `aws_security_group` | Cortafuegos de los endpoints: 443 desde la VPC. |
| `aws_security_group.llm` | `aws_security_group` | Cortafuegos de la GPU: solo el MDR entra, al 8080 y al 8082. Se crea aunque no haya GPU (sin coste). |
| `aws_security_group.mdr` | `aws_security_group` | Cortafuegos del MDR: sin entradas; salida libre. |
| `aws_subnet.privada` | `aws_subnet` | Subred sin IP pública donde viven las instancias. |
| `aws_subnet.publica[0]` | `aws_subnet` | Subred pública que solo aloja el NAT del primer arranque. |
| `aws_volume_attachment.traza` | `aws_volume_attachment` | Engancha el disco de la traza al MDR (destroy apaga antes de soltarlo). |
| `aws_vpc.main` | `aws_vpc` | Red privada del MDR. |
| `aws_vpc_endpoint.s3` | `aws_vpc_endpoint` | Endpoint de S3: paquete, perfil y modelos sin salir a Internet. |
| `aws_vpc_endpoint.ssm["ec2messages"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |
| `aws_vpc_endpoint.ssm["ssm"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |
| `aws_vpc_endpoint.ssm["ssmmessages"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |

## Escenario B · 23 recursos

Sin egreso: paquete en S3, los dos secretos en Secrets Manager; sin NAT ni GPU. El de producción recomendado.

| Recurso | Tipo | Por qué existe |
|---|---|---|
| `aws_ebs_volume.traza` | `aws_ebs_volume` | Disco cifrado de la traza y del estado del MDR (/var/lib/mdr). |
| `aws_iam_instance_profile.gpu` | `aws_iam_instance_profile` | Perfil que asocia el rol de la GPU a su instancia. Se crea aunque no haya GPU (sin coste). |
| `aws_iam_instance_profile.instancia` | `aws_iam_instance_profile` | Perfil que asocia el rol a la instancia del MDR. |
| `aws_iam_role.gpu` | `aws_iam_role` | Rol propio de la GPU (sin acceso a los secretos del MDR). Se crea aunque no haya GPU (sin coste). |
| `aws_iam_role.instancia` | `aws_iam_role` | Rol del MDR. |
| `aws_iam_role_policy.leer_s3[0]` | `aws_iam_role_policy` | El MDR lee el paquete y el perfil de S3. |
| `aws_iam_role_policy.leer_secretos[0]` | `aws_iam_role_policy` | El MDR lee la clave de la traza y los analistas. |
| `aws_iam_role_policy_attachment.gpu_ssm` | `aws_iam_role_policy_attachment` | La GPU se gestiona por SSM. Se crea aunque no haya GPU (sin coste). |
| `aws_iam_role_policy_attachment.ssm` | `aws_iam_role_policy_attachment` | El MDR se gestiona por SSM. |
| `aws_instance.mdr` | `aws_instance` | El MDR (daemon y consola). |
| `aws_route_table.privada` | `aws_route_table` | Rutas de la subred privada (sin salida a Internet salvo el NAT). |
| `aws_route_table_association.privada` | `aws_route_table_association` | Asocia la subred privada a sus rutas. |
| `aws_security_group.endpoints` | `aws_security_group` | Cortafuegos de los endpoints: 443 desde la VPC. |
| `aws_security_group.llm` | `aws_security_group` | Cortafuegos de la GPU: solo el MDR entra, al 8080 y al 8082. Se crea aunque no haya GPU (sin coste). |
| `aws_security_group.mdr` | `aws_security_group` | Cortafuegos del MDR: sin entradas; salida libre. |
| `aws_subnet.privada` | `aws_subnet` | Subred sin IP pública donde viven las instancias. |
| `aws_volume_attachment.traza` | `aws_volume_attachment` | Engancha el disco de la traza al MDR (destroy apaga antes de soltarlo). |
| `aws_vpc.main` | `aws_vpc` | Red privada del MDR. |
| `aws_vpc_endpoint.s3` | `aws_vpc_endpoint` | Endpoint de S3: paquete, perfil y modelos sin salir a Internet. |
| `aws_vpc_endpoint.secretsmanager[0]` | `aws_vpc_endpoint` | Endpoint de Secrets Manager: el arranque lee los secretos sin Internet. |
| `aws_vpc_endpoint.ssm["ec2messages"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |
| `aws_vpc_endpoint.ssm["ssm"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |
| `aws_vpc_endpoint.ssm["ssmmessages"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |

## Escenario D · 29 recursos

Como A, más la GPU con el modelo y el embedder (MDR >= 1.9.2).

| Recurso | Tipo | Por qué existe |
|---|---|---|
| `aws_ebs_volume.traza` | `aws_ebs_volume` | Disco cifrado de la traza y del estado del MDR (/var/lib/mdr). |
| `aws_eip.nat[0]` | `aws_eip` | IP pública del NAT (solo con egreso). |
| `aws_iam_instance_profile.gpu` | `aws_iam_instance_profile` | Perfil que asocia el rol de la GPU a su instancia. Se crea aunque no haya GPU (sin coste). |
| `aws_iam_instance_profile.instancia` | `aws_iam_instance_profile` | Perfil que asocia el rol a la instancia del MDR. |
| `aws_iam_role.gpu` | `aws_iam_role` | Rol propio de la GPU (sin acceso a los secretos del MDR). Se crea aunque no haya GPU (sin coste). |
| `aws_iam_role.instancia` | `aws_iam_role` | Rol del MDR. |
| `aws_iam_role_policy.gpu_s3[0]` | `aws_iam_role_policy` | La GPU lee los dos modelos de S3. |
| `aws_iam_role_policy_attachment.gpu_ssm` | `aws_iam_role_policy_attachment` | La GPU se gestiona por SSM. Se crea aunque no haya GPU (sin coste). |
| `aws_iam_role_policy_attachment.ssm` | `aws_iam_role_policy_attachment` | El MDR se gestiona por SSM. |
| `aws_instance.llm[0]` | `aws_instance` | La GPU con el modelo de lenguaje y el embedder del RAG. |
| `aws_instance.mdr` | `aws_instance` | El MDR (daemon y consola). |
| `aws_internet_gateway.igw[0]` | `aws_internet_gateway` | Salida a Internet de la subred pública (solo con egreso). |
| `aws_nat_gateway.nat[0]` | `aws_nat_gateway` | NAT para que el primer arranque descargue paquetes (solo con egreso); se cobra mientras exista. |
| `aws_route.privada_egreso[0]` | `aws_route` | Salida de la subred privada por el NAT: la usa el primer arranque, y queda mientras egreso_bootstrap = true. |
| `aws_route_table.privada` | `aws_route_table` | Rutas de la subred privada (sin salida a Internet salvo el NAT). |
| `aws_route_table.publica[0]` | `aws_route_table` | Rutas de la subred pública hacia el internet gateway. |
| `aws_route_table_association.privada` | `aws_route_table_association` | Asocia la subred privada a sus rutas. |
| `aws_route_table_association.publica[0]` | `aws_route_table_association` | Asocia la subred pública a sus rutas. |
| `aws_security_group.endpoints` | `aws_security_group` | Cortafuegos de los endpoints: 443 desde la VPC. |
| `aws_security_group.llm` | `aws_security_group` | Cortafuegos de la GPU: solo el MDR entra, al 8080 y al 8082. Se crea aunque no haya GPU (sin coste). |
| `aws_security_group.mdr` | `aws_security_group` | Cortafuegos del MDR: sin entradas; salida libre. |
| `aws_subnet.privada` | `aws_subnet` | Subred sin IP pública donde viven las instancias. |
| `aws_subnet.publica[0]` | `aws_subnet` | Subred pública que solo aloja el NAT del primer arranque. |
| `aws_volume_attachment.traza` | `aws_volume_attachment` | Engancha el disco de la traza al MDR (destroy apaga antes de soltarlo). |
| `aws_vpc.main` | `aws_vpc` | Red privada del MDR. |
| `aws_vpc_endpoint.s3` | `aws_vpc_endpoint` | Endpoint de S3: paquete, perfil y modelos sin salir a Internet. |
| `aws_vpc_endpoint.ssm["ec2messages"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |
| `aws_vpc_endpoint.ssm["ssm"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |
| `aws_vpc_endpoint.ssm["ssmmessages"]` | `aws_vpc_endpoint` | Endpoints de SSM: el analista entra por túnel, sin puertos abiertos. |
