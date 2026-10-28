variable "region" {
  description = "Región de AWS (acordar con el tutor industrial)."
  type        = string
  default     = "eu-west-1"
}

variable "proyecto" {
  description = "Prefijo de nombres/etiquetas."
  type        = string
  default     = "mdr-triaje"
}

variable "entorno" {
  description = "Etiqueta de entorno (demo/pruebas/prod)."
  type        = string
  default     = "demo"
}

variable "vpc_cidr" {
  description = "CIDR de la VPC."
  type        = string
  default     = "10.90.0.0/16"
}

variable "subred_privada_cidr" {
  description = "CIDR de la subred privada (sin IP pública)."
  type        = string
  default     = "10.90.1.0/24"
}

variable "subred_publica_cidr" {
  description = "CIDR de la subred pública (solo si egreso_bootstrap = true: aloja el NAT gateway)."
  type        = string
  default     = "10.90.2.0/24"
}

variable "egreso_bootstrap" {
  description = <<-EOT
    Egreso a Internet para el PRIMER ARRANQUE (dnf install, git clone, descarga del modelo). El
    RUNTIME del daemon no llama a Internet pase lo que pase (RNF-01 es propiedad del producto, no de
    la subred). true => crea IGW + subred pública + NAT y una ruta por defecto de la subred privada al
    NAT. false (def.) => SIN salida: desplegar desde una AMI horneada o artefactos en S3 (el git
    clone/curl del cloud-init NO funcionará).
  EOT
  type        = bool
  default     = false
}

variable "mdr_tipo" {
  description = "Tipo de instancia del daemon + visor (sin GPU)."
  type        = string
  default     = "t3.small"
}

variable "mdr_disco_gb" {
  description = "Tamaño del EBS cifrado de la traza (--salida)."
  type        = number
  default     = 20
}

variable "repo_url" {
  description = "Repositorio a clonar en el arranque (cloud-init)."
  type        = string
  default     = "https://github.com/vBlanyer/domotai-pasantia.git"
}

variable "repo_rama" {
  description = "Rama/etiqueta a desplegar."
  type        = string
  default     = "v1.4"
}

# --- LLM justificador (OPCIONAL: es el grueso del coste; apagado por defecto) ---
variable "llm_habilitado" {
  description = "Si true, crea la instancia GPU con el LLM justificador. Apagado por defecto (coste)."
  type        = bool
  default     = false
}

variable "llm_tipo" {
  description = "Tipo de instancia GPU para el LLM (requiere cuota de la cuenta)."
  type        = string
  default     = "g4dn.xlarge"
}

variable "llm_modelo_url" {
  description = "URL de los pesos del modelo que el arranque de la GPU descarga (vacío = se aporta aparte)."
  type        = string
  default     = ""
}

variable "secretos_arns" {
  description = "ARNs de Secrets Manager que las instancias podrán LEER (HMAC de la traza, token del visor, clave SSH del conector). Se gestionan fuera de este código; aquí solo se concede el permiso de lectura."
  type        = list(string)
  default     = []
}
