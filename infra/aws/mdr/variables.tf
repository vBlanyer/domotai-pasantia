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

# --- Qué se instala: el PAQUETE del release, verificado por su huella (no un git clone: #7, #11, #18) ---
variable "mdr_version" {
  description = "Versión del MDR a instalar (release de GitHub vX.Y.Z)."
  type        = string
  default     = "1.9.2"
}

variable "mdr_paquete_url" {
  description = "URL del paquete mdr-<versión>.tar.gz (https:// o s3://). Vacío = el asset del release de GitHub de mdr_version (necesita egreso_bootstrap); sin egreso, súbelo a S3."
  type        = string
  default     = ""
}

variable "mdr_paquete_sha256" {
  description = "SHA-256 del paquete. El arranque se para si no coincide. El valor por defecto es el de mdr-1.9.2.tar.gz publicado en el release v1.9.2: cámbialo junto con mdr_version."
  type        = string
  default     = "e35afcd4f4e70725ffb59585ed4353a3ebed273dcf6a29fe5dee4a676983aba0"
  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.mdr_paquete_sha256))
    error_message = "mdr_paquete_sha256 debe ser un SHA-256 en hexadecimal (64 caracteres)."
  }
}

variable "perfil_url" {
  description = "Perfil del cliente (https:// o s3://). Vacío = perfil mínimo con la IP del MDR y red_cliente_cidrs, para empezar con el asistente de red."
  type        = string
  default     = ""
}

variable "red_cliente_cidrs" {
  description = "Rangos de la red del cliente para el perfil mínimo. Vacío = la VPC."
  type        = list(string)
  default     = []
}

# --- Secretos (#19): solo ARNs; los valores viven en Secrets Manager, nunca aquí ni en el estado ---
variable "secreto_traza_arn" {
  description = "ARN del secreto con la clave HMAC de la traza (texto). Vacío = se genera una en la instancia (vale para una demo; si se recrea la instancia, la cadena anterior ya no se verifica)."
  type        = string
  default     = ""
}

variable "secreto_operadores_arn" {
  description = "ARN del secreto con los analistas de la consola (JSON {\"<token>\": \"<nombre>\"}). Vacío = un analista «admin» con su token en /root/mdr-token-admin."
  type        = string
  default     = ""
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
  description = "URL (https:// o s3://) del .gguf del generador, p. ej. Foundation-Sec-8B-Instruct Q4_K_M. Obligatoria con llm_habilitado."
  type        = string
  default     = ""
}

variable "llm_modelo_sha256" {
  description = "SHA-256 del .gguf del generador. Obligatoria con llm_habilitado."
  type        = string
  default     = ""
  validation {
    condition     = var.llm_modelo_sha256 == "" || can(regex("^[0-9a-f]{64}$", var.llm_modelo_sha256))
    error_message = "llm_modelo_sha256 debe ser un SHA-256 en hexadecimal (64 caracteres)."
  }
}

variable "embed_modelo_url" {
  description = "URL (https:// o s3://) del .gguf de bge-m3, el embedder del RAG. Obligatoria con llm_habilitado."
  type        = string
  default     = ""
}

variable "embed_modelo_sha256" {
  description = "SHA-256 del .gguf de bge-m3. Obligatoria con llm_habilitado."
  type        = string
  default     = ""
  validation {
    condition     = var.embed_modelo_sha256 == "" || can(regex("^[0-9a-f]{64}$", var.embed_modelo_sha256))
    error_message = "embed_modelo_sha256 debe ser un SHA-256 en hexadecimal (64 caracteres)."
  }
}

variable "llama_cpp_ref" {
  description = "Etiqueta de llama.cpp que se compila en la GPU (fija: nunca master)."
  type        = string
  default     = "b12445"
}

variable "secretos_arns" {
  description = "ARNs de Secrets Manager que las instancias podrán LEER (HMAC de la traza, token del visor, clave SSH del conector). Se gestionan fuera de este código; aquí solo se concede el permiso de lectura."
  type        = list(string)
  default     = []
}
