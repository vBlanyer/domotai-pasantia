# Secretos del MDR (#9): clave HMAC de la traza (TRIAJE_TRAZA_CLAVE), token del visor (#6) y clave SSH
# del conector. Se gestionan FUERA de este código, en AWS Secrets Manager (o SSM Parameter Store), para
# que sus VALORES nunca queden en la IaC ni en el estado de OpenTofu.
#
# Aquí solo se concede el PERMISO DE LECTURA a las instancias: pasa los ARNs de los secretos en la
# variable `secretos_arns` y `iam.tf` crea la política `secretsmanager:GetSecretValue` sobre ellos.
# El arranque (cloud-init) los recupera en la instancia con el rol (ver la nota en
# templates/mdr_user_data.sh.tftpl). Sin ARNs, el MDR arranca con el justificador de plantilla y sin
# conector (fail-closed), útil para una demo.
