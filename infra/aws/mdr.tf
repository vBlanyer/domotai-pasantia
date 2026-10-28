# EC2 del daemon MDR + visor. Amazon Linux 2023; el arranque (cloud-init) instala dependencias, clona
# el repo y levanta la unidad systemd de deploy/. El visor lo sirve el propio daemon (dist ya construido).
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  # URL privada del LLM justificador (si está habilitado); vacío => el daemon usa el justificador de
  # plantilla (determinista). El motor no depende del LLM.
  llm_url = var.llm_habilitado ? "http://${aws_instance.llm[0].private_ip}:8080" : ""
}

resource "aws_instance" "mdr" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.mdr_tipo
  subnet_id              = aws_subnet.privada.id
  vpc_security_group_ids = [aws_security_group.mdr.id]
  iam_instance_profile   = aws_iam_instance_profile.instancia.name
  # Subred privada: sin IP pública. El acceso es por SSM.
  associate_public_ip_address = false

  metadata_options {
    http_tokens = "required" # IMDSv2 obligatorio
  }
  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = 12
  }
  user_data = templatefile("${path.module}/templates/mdr_user_data.sh.tftpl", {
    repo_url  = var.repo_url
    repo_rama = var.repo_rama
    salida    = "/mnt/traza/trazas-bancario.jsonl" # ruta FIJA en el EBS (retoma estado al reiniciar, #4)
    llm_url   = local.llm_url
  })
  tags = { Name = "${var.proyecto}-mdr" }
}

# EBS cifrado para la traza (--salida fija). Snapshots = retención/backup (#9).
resource "aws_ebs_volume" "traza" {
  availability_zone = aws_subnet.privada.availability_zone
  size              = var.mdr_disco_gb
  type              = "gp3"
  encrypted         = true
  tags              = { Name = "${var.proyecto}-traza" }
}

resource "aws_volume_attachment" "traza" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.traza.id
  instance_id = aws_instance.mdr.id
}
