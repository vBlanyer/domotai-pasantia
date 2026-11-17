#!/bin/sh
# Prueba de infra/aws contra AWS Emulator: plan, apply y destroy de la infraestructura REAL (los .tf de
# infra/aws, sin tocarlos) contra un emulador local de la API de AWS. Sin cuenta ni coste. Comprueba que
# el grafo de recursos se crea entero y en orden y que las precondiciones frenan lo que deben. NO es un
# despliegue real: no arranca máquinas ni evalúa IAM (ver infra/aws/README.md, «Qué prueba cada capa»).
#
# Uso:  sh infra/aws/emulador/probar.sh            todos los escenarios (A–G)
#       sh infra/aws/emulador/probar.sh A C        solo esos
#       MDR_INVENTARIO=<dir> sh …                  además guarda el plan en JSON de cada escenario
# Necesita aws-emulator (se arranca si no está en marcha, sin telemetría) y tofu.
set -eu
RAIZ=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
INFRA="$RAIZ/infra/aws"
EMU="$HOME/.aws/emulator/9297"
URL=https://127.0.0.1:9297
ESCENARIOS=${*:-A B C D E F G}

salud() { curl -s -m 3 --cacert "$EMU/ca.pem" "$URL/__admin/health" 2>/dev/null | grep -q ok; }

TRABAJO=$(mktemp -d)
ARRANCADO=""
limpiar() {
  for d in "$TRABAJO"/esc-*; do
    [ -f "$d/terraform.tfstate" ] && (cd "$d" && tofu destroy -auto-approve -input=false -no-color $(cat vars) >/dev/null 2>&1)
  done
  [ -n "$ARRANCADO" ] && kill "$ARRANCADO" 2>/dev/null
  rm -rf -- "$TRABAJO"
}
trap limpiar EXIT

if ! salud; then
  command -v aws-emulator >/dev/null || { echo "falta aws-emulator (ver el plan, tarea 0)"; exit 2; }
  EMULATOR_TELEMETRY=off aws-emulator --telemetry off --idle-timeout 900 > "$TRABAJO/emulador.log" 2>&1 &
  ARRANCADO=$!
  for _ in $(seq 1 30); do salud && break; sleep 1; done
  salud || { echo "el emulador no responde"; cat "$TRABAJO/emulador.log"; exit 2; }
fi

# Credenciales reales fuera: todo va al emulador.
unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
export AWS_CONFIG_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true TF_IN_AUTOMATION=1
export TF_PLUGIN_CACHE_DIR="$TRABAJO/plugins"
mkdir -p "$TF_PLUGIN_CACHE_DIR"

preparar() { # preparar ESCENARIO → copia de infra/aws con el override que apunta al emulador
  d="$TRABAJO/esc-$1"
  mkdir -p "$d"
  cp "$INFRA"/*.tf "$d/"
  rm -f "$d/backend.tf" # el backend de producción (DESPLIEGUE.md, paso 3) no se usa contra el emulador
  cp -r "$INFRA/templates" "$d/"
  cat > "$d/override.tf" <<EOF
# Solo en la copia temporal: el proveedor apunta al emulador.
provider "aws" {
  shared_credentials_files = ["$EMU/emulator_credentials"]
  custom_ca_bundle         = "$EMU/ca.pem"
  endpoints {
    ec2            = "$URL"
    iam            = "$URL"
    sts            = "$URL"
    s3             = "$URL"
    secretsmanager = "$URL"
    ssm            = "$URL"
  }
}

# Hueco del emulador (17/11, v1.0.492): RunInstances no hereda la zona de la subred y falla con
# «Invalid value '' for availabilityZone». En AWS la instancia la toma de su subred: aquí se pasa explícita.
resource "aws_instance" "mdr" {
  availability_zone = aws_subnet.privada.availability_zone
}
resource "aws_instance" "llm" {
  availability_zone = aws_subnet.privada.availability_zone
}

# La Deep Learning AMI de la GPU no existe en el emulador: se busca la de Amazon Linux en su lugar.
data "aws_ami" "gpu" {
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}
EOF
  # Un override solo modifica bloques existentes: lo nuevo para comprobar va en su propio fichero.
  cat > "$d/emulador_comprobar.tf" <<EOF
# Para comprobar el script de arranque tal como lo guardó «AWS» (el estado solo guarda su huella).
data "aws_instance" "comprobar_mdr" {
  instance_id   = aws_instance.mdr.id
  get_user_data = true
}
EOF
  (cd "$d" && tofu init -backend=false -input=false -no-color > init.log 2>&1) || { cat "$d/init.log" >&2; return 1; }
  echo "$d"
}

ZEROS=0000000000000000000000000000000000000000000000000000000000000000
LAB="-var variante=laboratorio -var laboratorio_commit=0000000000000000000000000000000000000000"
COMUNES="-var region=us-east-1"
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
    E) echo "$COMUNES -var egreso_bootstrap=true $LAB -var mdr_version=1.9.2 -var mdr_paquete_sha256=$ZEROS" ;;
    F) echo "$COMUNES -var egreso_bootstrap=false $LAB -var mdr_version=1.9.2 -var mdr_paquete_sha256=$ZEROS \
-var mdr_paquete_url=s3://mdr-prueba/mdr-1.9.2.tar.gz" ;;
    G) echo "$COMUNES -var egreso_bootstrap=true $LAB -var mdr_version=1.9.1" ;;
  esac
}

# Escenarios que la configuración debe RECHAZAR en el plan (precondición), sin crear nada.
rechazo_de() {
  case "$1" in
    C) echo "El paquete 1.9.1 no activa el modelo" ;;
    F) echo "La variante laboratorio necesita egreso_bootstrap = true" ;;
    G) echo "La variante laboratorio necesita un MDR >= 1.9.2" ;;
  esac
}
rechazado() { # rechazado ESCENARIO "mensaje" (en el directorio del escenario, con $v)
  if tofu plan -input=false -no-color $v > plan.log 2>&1; then
    echo "== $1: NO como se esperaba (el plan pasó)"; FALLOS=1
  # OpenTofu parte los mensajes largos en varias líneas con «│»: se buscan en el texto aplanado.
  elif sed 's/^[│ ]*//' plan.log | tr '\n' ' ' | tr -s ' ' | grep -qF "$2"; then
    echo "== $1: rechazado como se esperaba ($2)"
  else
    echo "== $1: NO como se esperaba (falló por otra cosa)"; tail -15 plan.log; FALLOS=1
  fi
}

FALLOS=0
for e in $ESCENARIOS; do
  case "$e" in [A-G]) ;; *) echo "== $e: escenario desconocido (A–G)"; FALLOS=1; continue ;; esac
  d=$(preparar "$e")
  v=$(vars_de "$e")
  echo "$v" > "$d/vars"
  cd "$d"
  if [ -n "$(rechazo_de "$e")" ]; then
    rechazado "$e" "$(rechazo_de "$e")"
    cd "$RAIZ"; continue
  fi
  if ! tofu plan -input=false -no-color -out plan.bin $v > plan.log 2>&1; then
    echo "== $e: el plan falló"; tail -25 plan.log; FALLOS=1; cd "$RAIZ"; continue
  fi
  [ -n "${MDR_INVENTARIO:-}" ] && mkdir -p "$MDR_INVENTARIO" && tofu show -json plan.bin > "$MDR_INVENTARIO/plan-$e.json"
  if ! tofu apply -input=false -no-color -auto-approve plan.bin > apply.log 2>&1; then
    echo "== $e: el apply falló"; grep -E "Error|NotImplemented|501" apply.log | head -10; FALLOS=1; cd "$RAIZ"; continue
  fi
  tofu show -json > estado.json
  if python3 "$INFRA/emulador/comprobar.py" "$e" estado.json; then :; else FALLOS=1; fi
  if tofu destroy -input=false -no-color -auto-approve $v > destroy.log 2>&1 && [ "$(tofu state list | wc -l)" -eq 0 ]; then
    echo "   ok     destroy lo quita todo"
    rm -f terraform.tfstate
  else
    echo "   FALLO  destroy"; grep -E "Error" destroy.log | head -5; FALLOS=1
  fi
  cd "$RAIZ"
done
[ "$FALLOS" -eq 0 ] && echo "EMULADOR: todo como se esperaba" || { echo "EMULADOR: hay fallos"; exit 1; }
