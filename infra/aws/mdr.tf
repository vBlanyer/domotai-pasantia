# EC2 del daemon MDR + consola. Amazon Linux 2023; el arranque (cloud-init) instala el paquete del release
# verificado con instalar.sh, monta el disco de la traza y configura firma y acceso (templates/).
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
  # URLs privadas del modelo y del embedder del RAG (si la GPU está habilitada); vacías => justificación
  # de plantilla (determinista). El motor no depende del modelo.
  llm_url       = var.llm_habilitado ? "http://${aws_instance.llm[0].private_ip}:8080" : ""
  llm_embed_url = var.llm_habilitado ? "http://${aws_instance.llm[0].private_ip}:8082" : ""
  paquete_url = var.mdr_paquete_url != "" ? var.mdr_paquete_url : (
    "https://github.com/vBlanyer/domotai-pasantia/releases/download/v${var.mdr_version}/mdr-${var.mdr_version}.tar.gz"
  )
  red_cidrs = length(var.red_cliente_cidrs) > 0 ? var.red_cliente_cidrs : [var.vpc_cidr]

  # Variante laboratorio: la misma instancia, otro tipo, otro disco y otro arranque (el banco, Wazuh y
  # el MDR, como en local). Con "mdr", todo queda exactamente como antes.
  laboratorio = var.variante == "laboratorio"
  volumen     = replace(aws_ebs_volume.traza.id, "-", "")
  arranque_mdr = local.laboratorio ? "" : templatefile("${path.module}/templates/mdr_user_data.sh.tftpl", {
    region                 = var.region
    paquete_url            = local.paquete_url
    paquete_sha256         = var.mdr_paquete_sha256
    perfil_url             = var.perfil_url
    rangos                 = join(" ", [for c in local.red_cidrs : "--rango ${c}"])
    secreto_traza_arn      = var.secreto_traza_arn
    secreto_operadores_arn = var.secreto_operadores_arn
    llm_url                = local.llm_url
    llm_embed_url          = local.llm_embed_url
    # El arranque busca el EBS de la traza por su id (/dev/disk/by-id/…vol0123…), nunca un disco efímero.
    volumen = local.volumen
  })
  arranque_laboratorio = local.laboratorio ? templatefile("${path.module}/templates/laboratorio_user_data.sh.tftpl", {
    region                 = var.region
    mdr_version            = var.mdr_version
    laboratorio_commit     = var.laboratorio_commit
    paquete_url            = local.paquete_url
    paquete_sha256         = var.mdr_paquete_sha256
    secreto_traza_arn      = var.secreto_traza_arn
    secreto_operadores_arn = var.secreto_operadores_arn
    volumen                = local.volumen
  }) : ""
}

resource "aws_instance" "mdr" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = local.laboratorio ? var.laboratorio_tipo : var.mdr_tipo
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
    volume_size = local.laboratorio ? var.laboratorio_disco_gb : 12
  }
  user_data = local.laboratorio ? local.arranque_laboratorio : local.arranque_mdr
  # Cambiar el arranque (otra versión, otro perfil) recrea la instancia; la traza sigue en su EBS. Lo que
  # vive en /etc/mdr (perfil, clave, analistas) se rehace: para algo más que una demo, perfil_url y los
  # dos secretos (README).
  user_data_replace_on_change = true

  # Los permisos que el arranque usa (secretos, S3) deben existir antes: el arranque se ejecuta una vez.
  depends_on = [aws_iam_role_policy.leer_secretos, aws_iam_role_policy.leer_s3]

  lifecycle {
    # Sin egreso, lo que el arranque descarga tiene que venir de S3 (endpoint de la VPC).
    precondition {
      condition     = var.egreso_bootstrap || startswith(local.paquete_url, "s3://") && (var.perfil_url == "" || startswith(var.perfil_url, "s3://"))
      error_message = "Sin egreso_bootstrap, mdr_paquete_url (y perfil_url, si se indica) deben ser s3://: el arranque no sale a Internet."
    }
    # Variante laboratorio (diseno-aws-laboratorio.md).
    precondition {
      condition     = !local.laboratorio || var.egreso_bootstrap
      error_message = "La variante laboratorio necesita egreso_bootstrap = true (descarga Docker, Containerlab y la imagen de Wazuh)."
    }
    precondition {
      condition     = !local.laboratorio || var.mdr_version != "1.9.1"
      error_message = "La variante laboratorio necesita un MDR >= 1.9.2: la 1.9.1 no trae los arreglos del laboratorio."
    }
    precondition {
      condition     = !local.laboratorio || !var.llm_habilitado
      error_message = "La variante laboratorio no lleva GPU (llm_habilitado = false)."
    }
    precondition {
      condition     = !local.laboratorio || can(regex("^[0-9a-f]{40}$", var.laboratorio_commit))
      error_message = "laboratorio_commit: los 40 caracteres hexadecimales del commit de la etiqueta v<mdr_version>."
    }
  }
  tags = { Name = local.laboratorio ? "${var.proyecto}-laboratorio" : "${var.proyecto}-mdr" }
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
  # El MDR escribe ahí la traza: desmontarlo en caliente puede dejarlo «busy» y colgar el destroy (#12).
  stop_instance_before_detaching = true
}
