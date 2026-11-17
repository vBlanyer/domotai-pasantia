# Rol de instancia con el MÍNIMO: SSM Session Manager (acceso del analista) + lectura de los secretos
# que se le indiquen. Sin claves en la AMI ni en el estado.
data "aws_iam_policy_document" "asume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instancia" {
  name_prefix        = "${var.proyecto}-ec2-"
  assume_role_policy = data.aws_iam_policy_document.asume_ec2.json
  tags               = { Name = "${var.proyecto}-rol-ec2" }
}

# SSM Session Manager (gestionada por AWS): acceso sin abrir puertos.
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.instancia.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Lectura de secretos (solo los indicados): HMAC de la traza, analistas de la consola, clave SSH.
locals {
  secretos = compact(concat(var.secretos_arns, [var.secreto_traza_arn, var.secreto_operadores_arn]))
  # Objetos de S3 que lee el arranque (paquete y perfil), si vienen de S3.
  objetos_s3 = [for u in [local.paquete_url, var.perfil_url, var.llm_modelo_url, var.embed_modelo_url] :
  replace(u, "s3://", "arn:aws:s3:::") if startswith(u, "s3://")]
}

data "aws_iam_policy_document" "leer_secretos" {
  count = length(local.secretos) > 0 ? 1 : 0
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = local.secretos
  }
}

resource "aws_iam_role_policy" "leer_secretos" {
  count  = length(local.secretos) > 0 ? 1 : 0
  name   = "leer-secretos"
  role   = aws_iam_role.instancia.id
  policy = data.aws_iam_policy_document.leer_secretos[0].json
}

data "aws_iam_policy_document" "leer_s3" {
  count = length(local.objetos_s3) > 0 ? 1 : 0
  statement {
    actions   = ["s3:GetObject"]
    resources = local.objetos_s3
  }
}

resource "aws_iam_role_policy" "leer_s3" {
  count  = length(local.objetos_s3) > 0 ? 1 : 0
  name   = "leer-paquete-y-perfil"
  role   = aws_iam_role.instancia.id
  policy = data.aws_iam_policy_document.leer_s3[0].json
}

resource "aws_iam_instance_profile" "instancia" {
  name_prefix = "${var.proyecto}-ec2-"
  role        = aws_iam_role.instancia.name
}
