# Secretos del MDR (#19): la clave HMAC de la traza y los analistas de la consola se pasan como ARNs de
# AWS Secrets Manager (`secreto_traza_arn`, `secreto_operadores_arn`); la clave SSH del conector u otros,
# en `secretos_arns`. Sus VALORES nunca quedan en la IaC ni en el estado de OpenTofu.
#
# iam.tf concede a las instancias solo `secretsmanager:GetSecretValue` sobre esos ARNs, y el arranque
# (templates/mdr_user_data.sh.tftpl) los lee con el rol de la instancia. Si un secreto indicado no se
# puede leer, el arranque se para. Sin ARNs, el arranque genera la clave de la traza y da de alta a un
# analista «admin» (su token queda en /root/mdr-token-admin, legible por SSM): vale para una demo.
