# Módulo común de las dos variantes de AWS (infra/aws/mdr y infra/aws/laboratorio): red, permisos de la
# instancia y disco de la traza. Cada variante crea su instancia encima.
terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

variable "proyecto" {
  description = "Prefijo de nombres y etiquetas."
  type        = string
}

variable "region" {
  description = "Región (nombres de servicio de los endpoints)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR de la VPC."
  type        = string
}

variable "subred_privada_cidr" {
  description = "CIDR de la subred privada (sin IP pública), donde viven las instancias."
  type        = string
}

variable "subred_publica_cidr" {
  description = "CIDR de la subred pública; solo se usa con egreso (aloja el NAT)."
  type        = string
}

variable "egreso" {
  description = "true => IGW + subred pública + NAT y una ruta por defecto de la subred privada al NAT (primer arranque)."
  type        = bool
}

variable "secretos" {
  description = "ARN de Secrets Manager que la instancia puede LEER. Con alguno, se crea el endpoint de Secrets Manager."
  type        = list(string)
  default     = []
}

variable "objetos_s3" {
  description = "Objetos de S3 (arn:aws:s3:::bucket/clave) que lee el arranque de la instancia."
  type        = list(string)
  default     = []
}

variable "disco_traza_gb" {
  description = "Tamaño del disco cifrado de la traza, en GB."
  type        = number
}
