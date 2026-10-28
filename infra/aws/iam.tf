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

# Lectura de secretos (solo si se indican ARNs): HMAC de la traza, token del visor, clave SSH.
data "aws_iam_policy_document" "leer_secretos" {
  count = length(var.secretos_arns) > 0 ? 1 : 0
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.secretos_arns
  }
}

resource "aws_iam_role_policy" "leer_secretos" {
  count  = length(var.secretos_arns) > 0 ? 1 : 0
  name   = "leer-secretos"
  role   = aws_iam_role.instancia.id
  policy = data.aws_iam_policy_document.leer_secretos[0].json
}

resource "aws_iam_instance_profile" "instancia" {
  name_prefix = "${var.proyecto}-ec2-"
  role        = aws_iam_role.instancia.name
}
