#!/bin/sh
# Simulacro del laboratorio en AWS, sin cuenta ni coste: el arranque REAL de la variante laboratorio
# (templates/laboratorio_user_data.sh.tftpl, renderizado con OpenTofu como en un apply) ejecutado en una
# «máquina» Amazon Linux 2023 vacía con systemd de verdad: un contenedor privilegiado, aislado del equipo
# (su propia red y su propio Docker; nunca la red ni el Docker del equipo). Comprueba que la máquina se monta
# sola —Docker, Containerlab 0.79.0, la v1.9.2 clonada y verificada, la imagen del banco, la clave y el token,
# la unidad mdr-laboratorio— y que levanta banco + Wazuh + MDR; después contiene un ataque, se reinicia
# (parar y encender) y vuelve a contener.
#
# Qué no prueba (solo un apply real): IAM, la red de AWS y el túnel SSM. Hueco del contenedor: al encender,
# no le llega el aviso del disco de la traza, así que el simulacro lo monta y arranca la unidad, lo que en
# AWS hace systemd solo.
#
# Uso:  sh infra/aws/laboratorio/simulacro/simulacro.sh             simulacro completo y limpieza (~30–40 min)
#       sh infra/aws/laboratorio/simulacro/simulacro.sh --mantener  deja la máquina para ver la consola
#       sh infra/aws/laboratorio/simulacro/simulacro.sh down        la limpia
# Necesita docker, tofu, red (dnf, GitHub, Docker Hub) y el paquete dist/mdr-1.9.2.tar.gz. El laboratorio
# usa ~3–4 GB de memoria: baja antes el banco local si está levantado.
set -eu
RAIZ=$(CDPATH= cd -- "$(dirname -- "$0")/../../../.." && pwd)
LAB="$RAIZ/infra/aws/laboratorio"
VERSION=1.9.2
COMMIT=2c64820df320f0eab32583f7de1b4f2d99546d78     # el de la etiqueta v1.9.2
MAQUINA=mdr-simulacro-lab
IMAGEN=mdr-simulacro-al2023:local
VOLUMEN=mdr-simulacro-lab-docker
PUERTO=18787                                          # la consola, en el equipo (tu 8787 no se toca)
TRAZA=/var/lib/mdr/trazas-laboratorio.jsonl
ESPERA_MAX=${SIMULACRO_ESPERA_MAX:-2700}              # tope de cada espera al MDR, en segundos

dentro() { docker exec "$MAQUINA" bash -c "$1"; }

limpiar() {
  # el disco de bucle vive en el núcleo del equipo: se suelta siempre, o cada pasada deja uno enganchado
  docker exec "$MAQUINA" bash -c 'umount /var/lib/mdr 2>/dev/null; [ -s /simulacro/disco ] && losetup -d "$(cat /simulacro/disco)"' >/dev/null 2>&1 || :
  docker rm -f "$MAQUINA" >/dev/null 2>&1 || :
  docker volume rm "$VOLUMEN" >/dev/null 2>&1 || :
}

if [ "${1:-}" = down ]; then limpiar; echo "Simulacro del laboratorio limpiado."; exit 0; fi
MANTENER=""
[ "${1:-}" = --mantener ] && MANTENER=si
PAQ="$RAIZ/dist/mdr-$VERSION.tar.gz"
[ -f "$PAQ" ] || { echo "falta el paquete $PAQ (descárgalo del release v$VERSION o genéralo con sh deploy/empaquetar.sh)"; exit 2; }
SHA=$(sha256sum "$PAQ" | cut -d' ' -f1)

TRABAJO=$(mktemp -d)
fin() {
  rm -rf -- "$TRABAJO"
  if [ -n "$MANTENER" ]; then
    echo "La máquina sigue en marcha (--mantener). Consola: http://127.0.0.1:$PUERTO"
    echo "  token:    docker exec $MAQUINA cat /root/mdr-token-admin"
    echo "  entrar:   docker exec -it $MAQUINA bash   (el laboratorio está en /opt/mdr-laboratorio)"
    echo "  limpiar:  sh infra/aws/laboratorio/simulacro/simulacro.sh down"
  else
    limpiar
  fi
}
trap fin EXIT
trap 'exit 130' INT TERM

FALLOS=0
comprobar() { # comprobar NOMBRE ORDEN (se ejecuta dentro de la máquina)
  if dentro "$2" >/dev/null 2>&1; then echo "   ok     $1"; else echo "   FALLO  $1"; FALLOS=1; fi
}
# El diario de la ejecución EN CURSO de la unidad, no el del arranque (-b): dentro de un contenedor el arranque
# es el del núcleo del equipo y no cambia al reiniciar, así que mezclaría las ejecuciones.
DIARIO='I=$(systemctl show -p InvocationID --value mdr-laboratorio); [ -n "$I" ] && journalctl _SYSTEMD_INVOCATION_ID=$I --no-pager'
esperar_mdr() { # esperar_mdr ETIQUETA → 0 cuando la ejecución en curso de la unidad escribe «MDR en marcha»
  t=0
  while [ "$t" -lt "$ESPERA_MAX" ]; do
    if dentro "$DIARIO | grep -q 'MDR en marcha'"; then
      echo "   ok     $1: MDR en marcha (${t} s)"; return 0
    fi
    if [ "$(dentro 'systemctl show -p NRestarts --value mdr-laboratorio' 2>/dev/null)" != 0 ]; then
      echo "   FALLO  $1: la unidad mdr-laboratorio falló y systemd la reinició; últimas líneas:"
      dentro 'journalctl -u mdr-laboratorio --no-pager | tail -25' | sed 's/^/          /'
      FALLOS=1; return 1
    fi
    sleep 15; t=$((t + 15))
  done
  echo "   FALLO  $1: el MDR no arrancó en $ESPERA_MAX s"; FALLOS=1; return 1
}
consola() { # reenvía la consola (127.0.0.1:8787 dentro) al puerto publicado; una unidad transitoria por arranque
  dentro "systemd-run --unit=consola-simulacro -p Restart=always socat TCP-LISTEN:$PUERTO,fork,reuseaddr TCP:127.0.0.1:8787" >/dev/null 2>&1 || :
}
atacar() { # atacar → D1 (atacante externo contra web-banking: bloqueo automático), como desde el menú
  dentro 'cd /opt/mdr-laboratorio && printf "2\n\n0\n" | timeout 180 sh lab/banco/banco.sh atacar' >/dev/null 2>&1 || :
}
contenidas() { # contenidas → id_decision de las decisiones con BLOQUEAR_IP ejecutado y verificado
  dentro "python3 -c 'import json
for l in open(\"$TRAZA\"):
    r = json.loads(l)
    if r.get(\"tipo\") in (None, \"decision\") and r.get(\"accion_final\") == \"BLOQUEAR_IP\" \
       and (r.get(\"ejecucion\") or {}).get(\"exito\") and (r.get(\"verificacion\") or {}).get(\"verificado\"):
        print(r[\"id_decision\"])'" 2>/dev/null
}
esperar_contencion() { # esperar_contencion ID → la decisión ID aparece contenida (tope 3 min)
  for _ in $(seq 1 36); do contenidas | grep -qx "$1" && return 0; sleep 5; done
  return 1
}

echo "== 1. La máquina: Amazon Linux 2023 con systemd"
docker build -q -t "$IMAGEN" "$LAB/simulacro" >/dev/null
limpiar
docker run -d --name "$MAQUINA" --hostname laboratorio --privileged --cgroupns=private \
  --tmpfs /run --tmpfs /run/lock -v "$VOLUMEN":/var/lib/docker -v "$(dirname "$PAQ")":/paquete:ro \
  -p "127.0.0.1:$PUERTO:$PUERTO" "$IMAGEN" >/dev/null
for _ in $(seq 1 30); do
  case "$(dentro 'systemctl is-system-running' 2>/dev/null)" in running|degraded|starting) break ;; esac
  sleep 2
done
echo "   ok     systemd en marcha"

echo "== 2. El arranque de AWS (cloud-init), renderizado con OpenTofu"
(cd "$LAB" && tofu init -backend=false -input=false >/dev/null)
printf 'templatefile("templates/laboratorio_user_data.sh.tftpl", {region="eu-west-1", mdr_version="%s", laboratorio_commit="%s", paquete_url="file:///paquete/%s", paquete_sha256="%s", secreto_traza_arn="", secreto_operadores_arn="", volumen="vol0simulacro"})\n' \
  "$VERSION" "$COMMIT" "$(basename "$PAQ")" "$SHA" | (cd "$LAB" && tofu console) | sed '1d;$d' > "$TRABAJO/arranque.sh"
dentro 'mkdir -p /simulacro'
docker cp "$TRABAJO/arranque.sh" "$MAQUINA:/simulacro/arranque.sh"
# El disco de la traza: un disco de bucle (el nodo del siguiente loop libre puede no existir en el contenedor).
dentro 'truncate -s 2G /simulacro/disco.img && D=$(losetup -f) && { [ -b "$D" ] || mknod "$D" b 7 "${D#/dev/loop}"; } && losetup "$D" /simulacro/disco.img && echo "$D" > /simulacro/disco'
if dentro 'MDR_DISCOS=$(cat /simulacro/disco) MDR_ESPERA_DISCO=5 bash /simulacro/arranque.sh' > "$TRABAJO/arranque.log" 2>&1; then
  echo "   ok     el arranque terminó bien"
else
  echo "   FALLO  el arranque se paró; últimas líneas:"; tail -20 "$TRABAJO/arranque.log" | sed 's/^/          /'
  exit 1
fi
consola
comprobar "el código del laboratorio es el commit de v$VERSION" "[ \"\$(git -C /opt/mdr-laboratorio rev-parse HEAD)\" = $COMMIT ]"
comprobar "Docker y Containerlab 0.79.0 instalados" 'systemctl is-active -q docker && containerlab version | grep -q 0.79.0'
comprobar "la consola compilada vino del paquete" '[ -f /opt/mdr-laboratorio/visor/dist/index.html ]'
comprobar "el disco de la traza está montado en /var/lib/mdr" 'mountpoint -q /var/lib/mdr'
comprobar "la traza se firma (clave HMAC de 64 hex)" 'grep -Eq "^TRIAJE_TRAZA_CLAVE=[0-9a-f]{64}$" /etc/mdr/triaje.env'
comprobar "la consola exige token (admin en /root, 0600)" \
  'grep -q "^TRIAJE_CONSOLA_OPERADORES=" /etc/mdr/triaje.env && [ "$(stat -c %a /root/mdr-token-admin)" = 600 ]'
comprobar "la unidad mdr-laboratorio queda habilitada" '[ "$(systemctl is-enabled mdr-laboratorio)" = enabled ]'

echo "== 3. La unidad levanta el laboratorio (banco, Wazuh y MDR)"
if esperar_mdr "primer arranque"; then
  comprobar "banco.sh test pasó" "! { $DIARIO | grep -q 'banco.sh test:'; }"
  comprobar "Wazuh genera alertas (comprobar-alertas)" "$DIARIO | grep -q 'OK: Wazuh generó la alerta 100200'"
  comprobar "los 15 equipos del banco y Wazuh, en el Docker de la máquina" \
    '[ "$(docker ps --format "{{.Names}}" | grep -c "^clab-banco-")" -eq 15 ] && docker ps --format "{{.Names}}" | grep -q wazuh'
  comprobar "/healthz responde dentro de la máquina" 'curl -s -m 5 http://127.0.0.1:8787/healthz | grep -q "\"ok\": true"'
  if curl -s -m 5 "http://127.0.0.1:$PUERTO/healthz" | grep -q '"ok": true'; then
    echo "   ok     la consola se ve desde el equipo (http://127.0.0.1:$PUERTO)"
  else echo "   FALLO  la consola no responde en http://127.0.0.1:$PUERTO"; FALLOS=1; fi

  echo "== 4. Un ataque (D1, fuerza bruta externa contra web-banking)"
  atacar
  if esperar_contencion s1; then echo "   ok     s1: BLOQUEAR_IP ejecutado y verificado"
  else echo "   FALLO  el ataque no quedó contenido"; FALLOS=1; fi

  echo "== 5. Parar y encender la máquina"
  docker restart "$MAQUINA" >/dev/null
  for _ in $(seq 1 30); do
    case "$(dentro 'systemctl is-system-running' 2>/dev/null)" in running|degraded|starting) break ;; esac
    sleep 2
  done
  # Hueco del contenedor: en AWS, al encender, systemd recibe el aviso del disco de la traza, lo monta y
  # arranca la unidad que lo exige. En el contenedor ese aviso no llega (la unidad queda cancelada): el
  # simulacro hace su papel, montarlo y arrancar la unidad.
  dentro 'mount /var/lib/mdr' >/dev/null 2>&1 || :
  dentro 'systemctl start --no-block mdr-laboratorio'
  consola
  if esperar_mdr "tras encender"; then
    comprobar "la contención anterior se anota como revertida (los equipos se recrearon)" \
      "$DIARIO | grep -q '1 contención(es) de la traza anotadas como revertidas'"
    atacar
    if esperar_contencion s2; then echo "   ok     el mismo ataque, decidido y contenido otra vez: s2"
    else echo "   FALLO  tras encender, el ataque no quedó contenido como s2"; FALLOS=1; fi
    comprobar "sin identificadores de decisión repetidos" \
      "python3 -c 'import json,sys
ids=[json.loads(l).get(\"id_decision\") for l in open(\"$TRAZA\") if json.loads(l).get(\"tipo\") in (None,\"decision\")]
sys.exit(len(ids)!=len(set(ids)))'"
    comprobar "la cadena firmada de la traza es válida" \
      "set -a; . /etc/mdr/triaje.env; set +a; cd /opt/mdr-laboratorio && python3 -m prototipo.servicio.traza --verificar $TRAZA | grep -q 'cadena valida'"
  fi
fi

[ "$FALLOS" -eq 0 ] && echo "SIMULACRO DEL LABORATORIO: todo como se esperaba" || { echo "SIMULACRO DEL LABORATORIO: hay fallos"; exit 1; }
