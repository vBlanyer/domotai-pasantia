# Despliegue del MDR (daemon + visor) + LLM justificador opcional en AWS, con OpenTofu.
# Plano: documentacion/04-fase4-diseno-de-arquitectura/despliegue-aws-opentofu.md
#
# ESTADO: validado (tofu validate, pruebas estáticas y simulacro del arranque; ver README.md). Sin apply
# real. NO aplicar en una cuenta real sin acordar alcance/coste (la GPU del modelo es el grueso).
#
# Propiedades que se preservan en la nube: todo en SUBRED PRIVADA (sin IP pública, RNF-01 sin egreso),
# traza en EBS cifrado, acceso del analista por SSM (sin puerto público), secretos fuera del código.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
  # Estado LOCAL por defecto (tesis). Para equipo/producción: backend "s3" con bloqueo (ver README).
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
