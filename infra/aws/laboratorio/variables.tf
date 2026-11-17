variable "region" {
  description = "Región AWS."
  type        = string
  default     = "eu-west-1"
}

variable "proyecto" {
  description = "Prefijo de nombres y etiquetas (distinto del de producción para no confundirlos)."
  type        = string
  default     = "mdr-laboratorio"
}

variable "entorno" {
  description = "Etiqueta de entorno."
  type        = string
  default     = "pruebas"
}

variable "vpc_cidr" {
  description = "CIDR de la VPC."
  type        = string
  default     = "10.91.0.0/16"
}

variable "subred_privada_cidr" {
  description = "Subred privada (sin IP pública), donde vive la instancia."
  type        = string
  default     = "10.91.1.0/24"
}

variable "subred_publica_cidr" {
  description = "Subred pública (solo aloja el NAT)."
  type        = string
  default     = "10.91.2.0/24"
}

variable "mdr_version" {
  description = "Versión del MDR (release de GitHub vX.Y.Z): de su etiqueta salen el laboratorio y la consola. >= 1.9.2."
  type        = string
  default     = "1.9.2"
}

variable "mdr_paquete_url" {
  description = "URL del paquete mdr-<versión>.tar.gz (https:// o s3://), del que sale la consola compilada. Vacío = el asset del release de GitHub."
  type        = string
  default     = ""
}

variable "mdr_paquete_sha256" {
  description = "SHA-256 del paquete. El arranque se para si no coincide. El valor por defecto es el de mdr-1.9.2.tar.gz del release v1.9.2."
  type        = string
  default     = "e35afcd4f4e70725ffb59585ed4353a3ebed273dcf6a29fe5dee4a676983aba0"
  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.mdr_paquete_sha256))
    error_message = "mdr_paquete_sha256 debe ser un SHA-256 en hexadecimal (64 caracteres)."
  }
}

variable "mdr_disco_gb" {
  description = "Disco cifrado de la traza (/var/lib/mdr), en GB."
  type        = number
  default     = 20
}

variable "laboratorio_tipo" {
  description = "Tipo de instancia (4 vCPU y 16 GB, como el portátil donde se validó)."
  type        = string
  default     = "t3.xlarge"
}

variable "laboratorio_disco_gb" {
  description = "Disco raíz, en GB (imágenes de Docker: la de Wazuh ocupa 2,5 GB)."
  type        = number
  default     = 40
}

variable "laboratorio_commit" {
  description = "Commit (40 caracteres) de la etiqueta v<mdr_version>: el arranque clona la etiqueta y se para si el commit no es este. Para v1.9.2: 2c64820df320f0eab32583f7de1b4f2d99546d78."
  type        = string
  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.laboratorio_commit))
    error_message = "laboratorio_commit debe ser un commit completo en hexadecimal (40 caracteres)."
  }
}

variable "secreto_traza_arn" {
  description = "ARN del secreto con la clave HMAC de la traza. Vacío = se genera en la instancia."
  type        = string
  default     = ""
}

variable "secreto_operadores_arn" {
  description = "ARN del secreto con los analistas {\"<token>\": \"<nombre>\"}. Vacío = un analista admin (token en /root/mdr-token-admin)."
  type        = string
  default     = ""
}
