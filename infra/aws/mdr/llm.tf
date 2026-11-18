# EC2 con GPU para el LLM justificador. OPCIONAL (var.llm_habilitado): es el grueso del coste, así que
# por defecto NO se crea (count = 0). Vive en la subred privada; solo el MDR le habla (SG llm).
# Mitigaciones de coste: apagar cuando no se justifica, instancias Spot, o degradar al justificador de
# plantilla (el motor no depende del LLM).
# AMI de AWS con el driver NVIDIA y CUDA ya instalados (el arranque solo compila llama.cpp).
data "aws_ami" "gpu" {
  count       = var.llm_habilitado ? 1 : 0
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["Deep Learning Base OSS Nvidia Driver GPU AMI (Amazon Linux 2023)*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

resource "aws_instance" "llm" {
  count                  = var.llm_habilitado ? 1 : 0
  ami                    = data.aws_ami.gpu[0].id
  instance_type          = var.llm_tipo
  subnet_id              = module.base.subred_privada_id
  vpc_security_group_ids = [aws_security_group.llm[0].id]
  # Rol propio: SSM y los modelos de S3, nunca los secretos del MDR (clave de la traza, tokens).
  iam_instance_profile        = aws_iam_instance_profile.gpu[0].name
  associate_public_ip_address = false
  # Su primer arranque clona llama.cpp: necesita el NAT (y el resto de la red) ya creados.
  depends_on = [module.base, aws_iam_role_policy.gpu_s3]

  metadata_options {
    http_tokens = "required"
  }
  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = 100 # pesos del modelo
  }
  user_data = templatefile("${path.module}/templates/llm_user_data.sh.tftpl", {
    region        = var.region
    llama_cpp_ref = var.llama_cpp_ref
    modelo_url    = var.llm_modelo_url
    modelo_sha256 = var.llm_modelo_sha256
    embed_url     = var.embed_modelo_url
    embed_sha256  = var.embed_modelo_sha256
  })
  user_data_replace_on_change = true

  lifecycle {
    # Sin modelos verificados no se crea una GPU que no arranca (y que se paga igual).
    precondition {
      condition     = alltrue([for v in [var.llm_modelo_url, var.llm_modelo_sha256, var.embed_modelo_url, var.embed_modelo_sha256] : v != ""])
      error_message = "Con llm_habilitado = true hacen falta llm_modelo_url, llm_modelo_sha256, embed_modelo_url y embed_modelo_sha256."
    }
    # El paquete 1.9.1 no lee TRIAJE_CON_LLM (llegó después): con él la GPU se pagaría sin usarse.
    precondition {
      condition     = var.mdr_version != "1.9.1"
      error_message = "El paquete 1.9.1 no activa el modelo de lenguaje: usa una versión del MDR >= 1.9.2 (mdr_version y mdr_paquete_sha256)."
    }
    # El arranque de la GPU clona y compila llama.cpp: necesita salir a Internet.
    precondition {
      condition     = var.egreso_bootstrap
      error_message = "La GPU necesita egreso_bootstrap = true (clona llama.cpp de GitHub en su primer arranque)."
    }
  }
  tags = { Name = "${var.proyecto}-llm" }
}

# LLM: solo acepta del SG del MDR (la URL privada del justificador). Nada público.
resource "aws_security_group" "llm" {
  count       = var.llm_habilitado ? 1 : 0
  name_prefix = "${var.proyecto}-llm-"
  description = "LLM justificador (solo desde el MDR)"
  vpc_id      = module.base.vpc_id

  ingress {
    description     = "generador (llama-server) desde el MDR"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [module.base.sg_instancia_id]
  }
  ingress {
    description     = "embedder bge-m3 del RAG desde el MDR"
    from_port       = 8082
    to_port         = 8082
    protocol        = "tcp"
    security_groups = [module.base.sg_instancia_id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.proyecto}-sg-llm" }
}

data "aws_iam_policy_document" "asume_ec2_gpu" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

# Rol de la GPU, aparte: SSM y los modelos de S3. Nunca los secretos del MDR: la GPU compila código de
# GitHub y escucha en la red; si se comprometiera no debe poder leer la clave de la traza ni los tokens.
resource "aws_iam_role" "gpu" {
  count              = var.llm_habilitado ? 1 : 0
  name_prefix        = "${var.proyecto}-gpu-"
  assume_role_policy = data.aws_iam_policy_document.asume_ec2_gpu.json
  tags               = { Name = "${var.proyecto}-rol-gpu" }
}

resource "aws_iam_role_policy_attachment" "gpu_ssm" {
  count      = var.llm_habilitado ? 1 : 0
  role       = aws_iam_role.gpu[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "gpu_s3" {
  count = var.llm_habilitado && length(local.objetos_s3_gpu) > 0 ? 1 : 0
  statement {
    actions   = ["s3:GetObject"]
    resources = local.objetos_s3_gpu
  }
}

resource "aws_iam_role_policy" "gpu_s3" {
  count  = var.llm_habilitado && length(local.objetos_s3_gpu) > 0 ? 1 : 0
  name   = "leer-modelos"
  role   = aws_iam_role.gpu[0].id
  policy = data.aws_iam_policy_document.gpu_s3[0].json
}

resource "aws_iam_instance_profile" "gpu" {
  count       = var.llm_habilitado ? 1 : 0
  name_prefix = "${var.proyecto}-gpu-"
  role        = aws_iam_role.gpu[0].name
}
