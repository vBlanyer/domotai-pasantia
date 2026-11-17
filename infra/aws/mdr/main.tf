# Variante MDR (PRODUCCIÓN): el MDR (daemon + consola) + el modelo de lenguaje en GPU, opcional, en AWS.
# Lo común (red, permisos de la instancia, disco de la traza) está en ../modulos/base.
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

# Lectura de secretos (solo los indicados: HMAC de la traza, analistas, clave SSH…) y de los objetos de S3
# que lee el arranque del MDR (paquete y perfil) y el de la GPU (modelos), si vienen de S3.
locals {
  secretos       = compact(concat(var.secretos_arns, [var.secreto_traza_arn, var.secreto_operadores_arn]))
  objetos_s3     = [for u in [local.paquete_url, var.perfil_url] : replace(u, "s3://", "arn:aws:s3:::") if startswith(u, "s3://")]
  objetos_s3_gpu = [for u in [var.llm_modelo_url, var.embed_modelo_url] : replace(u, "s3://", "arn:aws:s3:::") if startswith(u, "s3://")]
}

module "base" {
  source              = "../modulos/base"
  proyecto            = var.proyecto
  region              = var.region
  vpc_cidr            = var.vpc_cidr
  subred_privada_cidr = var.subred_privada_cidr
  subred_publica_cidr = var.subred_publica_cidr
  egreso              = var.egreso_bootstrap
  secretos            = local.secretos
  objetos_s3          = local.objetos_s3
  disco_traza_gb      = var.mdr_disco_gb
}
