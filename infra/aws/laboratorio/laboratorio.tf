# La instancia del laboratorio: Amazon Linux 2023 con el banco, Wazuh y el MDR. El arranque (cloud-init,
# una vez) instala lo necesario y deja la unidad mdr-laboratorio, que rehace el laboratorio en CADA
# encendido (lab/banco/servicio-mdr.sh).
resource "aws_instance" "laboratorio" {
  ami                    = module.base.ami_al2023
  instance_type          = var.laboratorio_tipo
  subnet_id              = module.base.subred_privada_id
  vpc_security_group_ids = [module.base.sg_instancia_id]
  iam_instance_profile   = module.base.perfil_instancia
  # Subred privada: sin IP pública. El acceso es por SSM.
  associate_public_ip_address = false

  metadata_options {
    http_tokens = "required" # IMDSv2 obligatorio
  }
  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = var.laboratorio_disco_gb
  }
  user_data = templatefile("${path.module}/templates/laboratorio_user_data.sh.tftpl", {
    region                 = var.region
    mdr_version            = var.mdr_version
    laboratorio_commit     = var.laboratorio_commit
    paquete_url            = local.paquete_url
    paquete_sha256         = var.mdr_paquete_sha256
    secreto_traza_arn      = var.secreto_traza_arn
    secreto_operadores_arn = var.secreto_operadores_arn
    volumen                = module.base.volumen_traza_nvme
  })
  # Cambiar el arranque (otra versión, otro commit) recrea la instancia; la traza sigue en su EBS.
  user_data_replace_on_change = true

  # Los permisos que el arranque usa (secretos, S3) deben existir antes: el arranque se ejecuta una vez.
  depends_on = [module.base]

  lifecycle {
    precondition {
      condition     = var.mdr_version != "1.9.1"
      error_message = "La variante laboratorio necesita un MDR >= 1.9.2: la 1.9.1 no trae los arreglos del laboratorio."
    }
    precondition {
      condition     = can(regex("^[0-9a-f]{40}$", var.laboratorio_commit))
      error_message = "laboratorio_commit: los 40 caracteres hexadecimales del commit de la etiqueta v<mdr_version>."
    }
  }
  tags = { Name = "${var.proyecto}-laboratorio" }
}

# El disco de la traza está en ../modulos/base; aquí se engancha a la instancia.
resource "aws_volume_attachment" "traza" {
  device_name = "/dev/sdf"
  volume_id   = module.base.volumen_traza_id
  instance_id = aws_instance.laboratorio.id
  # El MDR escribe ahí la traza: destroy apaga la instancia antes de soltar el disco.
  stop_instance_before_detaching = true
}
