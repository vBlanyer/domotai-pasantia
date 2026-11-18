#!/bin/sh
# Prueba de las variantes de infra/aws contra AWS Emulator: plan, apply y destroy de la infraestructura
# REAL (los .tf de cada variante y el módulo común, sin tocarlos) contra un emulador local de la API de
# AWS. Sin cuenta ni coste. Comprueba que el grafo de recursos se crea entero y en orden y que las
# precondiciones frenan lo que deben. NO es un despliegue real: no arranca máquinas ni evalúa IAM (ver
# infra/aws/README.md).
#
# Cada variante aporta sus escenarios en infra/aws/<variante>/emulador/escenarios.sh (y sus
# comprobaciones en comprobar.py): este script descubre las que existan.
#
# Uso:  sh infra/aws/emulador/probar.sh              todas las variantes
#       sh infra/aws/emulador/probar.sh mdr          los escenarios de una variante
#       sh infra/aws/emulador/probar.sh A C          solo esos escenarios
#       sh infra/aws/emulador/probar.sh --listar     las variantes y sus escenarios, sin arrancar nada
#       MDR_INVENTARIO=<dir> sh …                    además guarda el plan en JSON de cada escenario
#       MDR_ESTADOS=<dir> sh …                       además guarda el estado tras el apply
#       MDR_MCP=1 sh …                               además consulta cada escenario por MCP (servidor de API
#                                                    de AWS en solo lectura; necesita uv): emulador/mcp_cliente.py
# Necesita aws-emulator (se arranca si no está en marcha, sin telemetría) y tofu.
set -eu
RAIZ=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
INFRA="$RAIZ/infra/aws"
EMU="$HOME/.aws/emulator/9297"
URL=https://127.0.0.1:9297
COMUNES="-var region=us-east-1"
ZEROS=0000000000000000000000000000000000000000000000000000000000000000

# --- Variantes y escenarios (antes de arrancar nada) ---
VARIANTES=""
for f in "$INFRA"/*/emulador/escenarios.sh; do
  [ -f "$f" ] && VARIANTES="$VARIANTES $(basename "$(dirname "$(dirname "$f")")")"
done
letras_de() { (. "$INFRA/$1/emulador/escenarios.sh" && echo "$LETRAS"); }
duena_de() { # duena_de LETRA → la variante que define ese escenario (vacío si ninguna)
  for v in $VARIANTES; do
    case " $(letras_de "$v") " in *" $1 "*) echo "$v"; return ;; esac
  done
}

if [ "${1:-}" = "--listar" ]; then
  for v in $VARIANTES; do echo "$v: $(letras_de "$v")"; done
  exit 0
fi

PEDIDOS=""
if [ $# -eq 0 ]; then
  for v in $VARIANTES; do PEDIDOS="$PEDIDOS $(letras_de "$v")"; done
else
  for a in "$@"; do
    if [ -f "$INFRA/$a/emulador/escenarios.sh" ]; then PEDIDOS="$PEDIDOS $(letras_de "$a")"; else PEDIDOS="$PEDIDOS $a"; fi
  done
fi
FALLOS=0
ESCENARIOS=""
for e in $PEDIDOS; do
  if [ -n "$(duena_de "$e")" ]; then
    ESCENARIOS="$ESCENARIOS $e"
  else
    echo "== $e: escenario desconocido (ninguna variante lo define; variantes:$VARIANTES)"
    FALLOS=1
  fi
done
[ -n "$ESCENARIOS" ] || { echo "EMULADOR: hay fallos"; exit 1; }

salud() { curl -s -m 3 --cacert "$EMU/ca.pem" "$URL/__admin/health" 2>/dev/null | grep -q ok; }

TRABAJO=$(mktemp -d)
ARRANCADO=""
limpiar() {
  for w in "$TRABAJO"/esc-*/*; do
    [ -f "$w/terraform.tfstate" ] && (cd "$w" && tofu destroy -auto-approve -input=false -no-color $(cat vars) >/dev/null 2>&1)
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

preparar() { # preparar ESCENARIO VARIANTE → copia (módulo común + variante) con el override del emulador
  d="$TRABAJO/esc-$1"
  w="$d/$2"
  mkdir -p "$d"
  cp -r "$INFRA/modulos" "$d/"
  cp -r "$INFRA/$2" "$d/"
  # ni el estado ni la caché locales, ni el backend de producción (DESPLIEGUE.md), ni pruebas o inventario
  rm -rf "$w/.terraform" "$w/terraform.tfstate" "$w/backend.tf" "$w/pruebas" "$w/inventario"
  cat > "$w/override.tf" <<EOF
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
EOF
  override_extra >> "$w/override.tf"
  # Un override solo modifica bloques existentes: lo nuevo para comprobar va en su propio fichero.
  cat > "$w/emulador_comprobar.tf" <<EOF
# Para comprobar el script de arranque tal como lo guardó «AWS» (el estado solo guarda su huella).
data "aws_instance" "comprobar" {
  instance_id   = $INSTANCIA.id
  get_user_data = true
}
EOF
  (cd "$w" && tofu init -backend=false -input=false -no-color > init.log 2>&1) || { cat "$w/init.log" >&2; return 1; }
  echo "$w"
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

for e in $ESCENARIOS; do
  var=$(duena_de "$e")
  . "$INFRA/$var/emulador/escenarios.sh"
  w=$(preparar "$e" "$var")
  v=$(vars_de "$e")
  echo "$v" > "$w/vars"
  cd "$w"
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
  [ -n "${MDR_ESTADOS:-}" ] && mkdir -p "$MDR_ESTADOS" && cp estado.json "$MDR_ESTADOS/estado-$e.json"
  if python3 "$INFRA/$var/emulador/comprobar.py" "$e" estado.json; then :; else FALLOS=1; fi
  if [ -n "${MDR_MCP:-}" ]; then
    # Lo creado, consultado por MCP como lo haría un asistente (solo lectura; nunca contra AWS real).
    if command -v uv >/dev/null 2>&1 || [ -x "$HOME/.local/bin/uv" ]; then
      (PATH="$HOME/.local/bin:$PATH" uv run --quiet --python 3.12 --with mcp python "$INFRA/emulador/mcp_cliente.py" 2> mcp.log) || {
        FALLOS=1; tail -5 mcp.log; }
    else
      echo "   FALLO  MDR_MCP=1 necesita uv (https://docs.astral.sh/uv/)"; FALLOS=1
    fi
  fi
  if tofu destroy -input=false -no-color -auto-approve $v > destroy.log 2>&1 && [ "$(tofu state list | wc -l)" -eq 0 ]; then
    echo "   ok     destroy lo quita todo"
    rm -f terraform.tfstate
  else
    echo "   FALLO  destroy"; grep -E "Error" destroy.log | head -5; FALLOS=1
  fi
  cd "$RAIZ"
done
[ "$FALLOS" -eq 0 ] && echo "EMULADOR: todo como se esperaba" || { echo "EMULADOR: hay fallos"; exit 1; }
