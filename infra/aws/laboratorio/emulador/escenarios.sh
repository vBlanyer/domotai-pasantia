# Escenarios de la variante laboratorio para infra/aws/emulador/probar.sh (se carga con «.»; $COMUNES y
# $ZEROS los define probar.sh). Borrar la carpeta laboratorio/ los quita del emulador.
LETRAS="E F"
INSTANCIA=aws_instance.laboratorio
COMMIT_PRUEBA=0000000000000000000000000000000000000000

vars_de() {
  case "$1" in
    E) echo "$COMUNES -var mdr_version=1.9.2 -var mdr_paquete_sha256=$ZEROS -var laboratorio_commit=$COMMIT_PRUEBA" ;;
    F) echo "$COMUNES -var mdr_version=1.9.1 -var laboratorio_commit=$COMMIT_PRUEBA" ;;
  esac
}

rechazo_de() {
  case "$1" in
    F) echo "La variante laboratorio necesita un MDR >= 1.9.2" ;;
  esac
}

# Hueco del emulador (v1.0.492): RunInstances no hereda la zona de la subred.
override_extra() {
  cat <<'HCL'
resource "aws_instance" "laboratorio" {
  availability_zone = module.base.zona
}
HCL
}
