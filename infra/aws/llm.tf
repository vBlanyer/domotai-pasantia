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
  count                       = var.llm_habilitado ? 1 : 0
  ami                         = data.aws_ami.gpu[0].id
  instance_type               = var.llm_tipo
  subnet_id                   = aws_subnet.privada.id
  vpc_security_group_ids      = [aws_security_group.llm.id]
  iam_instance_profile        = aws_iam_instance_profile.instancia.name
  associate_public_ip_address = false

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
  }
  tags = { Name = "${var.proyecto}-llm" }
}
