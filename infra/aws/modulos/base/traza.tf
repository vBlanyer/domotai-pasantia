# Disco cifrado de la traza y del estado del MDR (/var/lib/mdr). Lo engancha a su instancia cada variante
# (aws_volume_attachment, que necesita la instancia). Instantáneas = retención/copia (#9).
resource "aws_ebs_volume" "traza" {
  availability_zone = aws_subnet.privada.availability_zone
  size              = var.disco_traza_gb
  type              = "gp3"
  encrypted         = true
  tags              = { Name = "${var.proyecto}-traza" }
}

# Amazon Linux 2023, la AMI de la instancia de las dos variantes.
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
