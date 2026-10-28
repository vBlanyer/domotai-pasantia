# EC2 con GPU para el LLM justificador. OPCIONAL (var.llm_habilitado): es el grueso del coste, así que
# por defecto NO se crea (count = 0). Vive en la subred privada; solo el MDR le habla (SG llm).
# Mitigaciones de coste: apagar cuando no se justifica, instancias Spot, o degradar al justificador de
# plantilla (el motor no depende del LLM).
resource "aws_instance" "llm" {
  count                       = var.llm_habilitado ? 1 : 0
  ami                         = data.aws_ami.al2023.id
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
    modelo_url = var.llm_modelo_url
  })
  tags = { Name = "${var.proyecto}-llm" }
}
