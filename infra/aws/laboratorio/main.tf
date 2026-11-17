# Variante LABORATORIO (PRUEBAS): una máquina con el laboratorio del banco (Containerlab), su Wazuh y el
# MDR, como en local, para que la empresa pruebe el MDR antes de ponerlo delante de un cliente. NO se
# conecta a ningún cliente. Lo común (red, permisos de la instancia, disco de la traza) está en
# ../modulos/base. Diseño: documentacion/05-fase5-implementacion-del-prototipo/diseno-aws-laboratorio.md.
#
# ESTADO: validado (tofu validate, pruebas estáticas y AWS Emulator; el laboratorio, en vivo en local).
# Sin apply real.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
  # Estado LOCAL por defecto. Para un equipo: backend "s3" con bloqueo (backend.tf.ejemplo).
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Proyecto = var.proyecto
      Gestion  = "opentofu"
      Entorno  = var.entorno
    }
  }
}

locals {
  paquete_url = var.mdr_paquete_url != "" ? var.mdr_paquete_url : (
    "https://github.com/vBlanyer/domotai-pasantia/releases/download/v${var.mdr_version}/mdr-${var.mdr_version}.tar.gz"
  )
  secretos   = compact([var.secreto_traza_arn, var.secreto_operadores_arn])
  objetos_s3 = [for u in [local.paquete_url] : replace(u, "s3://", "arn:aws:s3:::") if startswith(u, "s3://")]
}

# Siempre con egreso: el arranque descarga Docker, Containerlab, la imagen de Wazuh y el repositorio.
module "base" {
  source              = "../modulos/base"
  proyecto            = var.proyecto
  region              = var.region
  vpc_cidr            = var.vpc_cidr
  subred_privada_cidr = var.subred_privada_cidr
  subred_publica_cidr = var.subred_publica_cidr
  egreso              = true
  secretos            = local.secretos
  objetos_s3          = local.objetos_s3
  disco_traza_gb      = var.mdr_disco_gb
}
