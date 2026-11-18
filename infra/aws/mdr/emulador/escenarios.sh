# Escenarios de la variante MDR para infra/aws/emulador/probar.sh (se carga con «.»; $COMUNES y $ZEROS
# los define probar.sh). Borrar la carpeta mdr/ los quita del emulador.
LETRAS="A B C D"
INSTANCIA=aws_instance.mdr

vars_de() {
  case "$1" in
    A) echo "$COMUNES -var egreso_bootstrap=true" ;;
    B) echo "$COMUNES -var egreso_bootstrap=false -var mdr_paquete_url=s3://mdr-prueba/mdr-1.9.1.tar.gz \
-var secreto_traza_arn=arn:aws:secretsmanager:us-east-1:000000000000:secret:mdr/traza-clave \
-var secreto_operadores_arn=arn:aws:secretsmanager:us-east-1:000000000000:secret:mdr/operadores" ;;
    C) echo "$COMUNES -var egreso_bootstrap=true -var llm_habilitado=true -var mdr_version=1.9.1 \
-var llm_modelo_url=s3://mdr-prueba/generador.gguf -var llm_modelo_sha256=$ZEROS \
-var embed_modelo_url=s3://mdr-prueba/bge-m3.gguf -var embed_modelo_sha256=$ZEROS" ;;
    D) echo "$COMUNES -var egreso_bootstrap=true -var llm_habilitado=true -var mdr_version=1.9.2 -var mdr_paquete_sha256=$ZEROS \
-var llm_modelo_url=s3://mdr-prueba/generador.gguf -var llm_modelo_sha256=$ZEROS \
-var embed_modelo_url=s3://mdr-prueba/bge-m3.gguf -var embed_modelo_sha256=$ZEROS" ;;
  esac
}

# Los que la configuración debe RECHAZAR en el plan (precondición), sin crear nada.
rechazo_de() {
  case "$1" in
    C) echo "El paquete 1.9.1 no activa el modelo" ;;
  esac
}

# Huecos del emulador (v1.0.492) que se suplen solo en la copia: RunInstances no hereda la zona de la
# subred, y no existe la Deep Learning AMI de la GPU (se usa la de Amazon Linux).
override_extra() {
  cat <<'HCL'
resource "aws_instance" "mdr" {
  availability_zone = module.base.zona
}
resource "aws_instance" "llm" {
  availability_zone = module.base.zona
}
data "aws_ami" "gpu" {
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}
HCL
}
