#!/bin/sh
# Levanta el Wazuh manager SOLO (sin indexer ni dashboard) conectado al bridge
# de gestion del laboratorio (red docker "clab"). Escribe las alertas en un
# volumen para poder leer alerts.json desde fuera.
#
# No es un nodo de containerlab: la imagen es demasiado pesada y tiene su propio
# entrypoint. Vive en el plano de gestion, junto al auditor, sin tocar el plano
# de datos. Ver documentacion/04-.../flujo-edr-playbook-sandbox.md
#
# Uso:   sh lab/scripts/wazuh-run.sh up | down | logs | alerts | mem
set -e
IMG=wazuh/wazuh-manager:4.14.7
# Parametrizable para reusarlo FUERA del laboratorio clab (única fuente del arranque del manager:
# la demo portátil lo llama con WAZUH_NOMBRE=portatil-wazuh WAZUH_RED=portatil_default
# WAZUH_PERMITIR=172.18.0.0/16). Sin variables, los defaults de siempre: nada cambia para el lab.
NAME="${WAZUH_NOMBRE:-clab-red-cliente-wazuh}"
NET="${WAZUH_RED:-clab}"
PERMITIR="${WAZUH_PERMITIR:-172.20.20.0/24}"
# Puertos publicados en el host: dos managers a la vez (lab + portátil) chocarían aquí. La
# variante portátil los vacía (WAZUH_PUERTOS="") porque su syslog viaja por la red de compose.
PUERTOS="${WAZUH_PUERTOS--p 1514:1514 -p 1515:1515 -p 514:514/udp -p 55000:55000}"

case "${1:-up}" in
  up)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    # $PUERTOS sin comillas a propósito: son varios argumentos -p (o ninguno, WAZUH_PUERTOS="").
    docker run -d --name "$NAME" --network "$NET" \
      --hostname wazuh \
      $PUERTOS \
      "$IMG"
    echo "Wazuh manager arrancando..."
    # Esperar a analysisd y HABILITAR la recepcion de syslog remoto (no viene
    # activa de fabrica). Sin esto, el manager ignora todo el syslog del lab.
    until docker exec "$NAME" sh -c '/var/ossec/bin/wazuh-control status 2>/dev/null | grep -q "wazuh-analysisd is running"' 2>/dev/null; do sleep 4; done
    docker cp "$(dirname "$0")/../wazuh/local_decoder_telnetd.xml" "$NAME":/tmp/local_decoder_telnetd.xml
    docker cp "$(dirname "$0")/../wazuh/local_rules_banco.xml" "$NAME":/tmp/local_rules_banco.xml
    docker cp "$(dirname "$0")/../wazuh/local_decoder_banco.xml" "$NAME":/tmp/local_decoder_banco.xml
    docker exec -e PERMITIR="$PERMITIR" "$NAME" sh -c '
      grep -q "<connection>syslog" /var/ossec/etc/ossec.conf 2>/dev/null || \
      sed -i "s|</ossec_config>|  <remote>\n    <connection>syslog</connection>\n    <port>514</port>\n    <protocol>udp</protocol>\n    <allowed-ips>${PERMITIR}</allowed-ips>\n  </remote>\n</ossec_config>|" /var/ossec/etc/ossec.conf
      # Regla local del ANCLA de la traza (prototipo/traza.py): el servicio envia el hash de cada
      # registro como syslog y el manager lo guarda en alerts.json, fuera del alcance de quien
      # pueda tocar el fichero de la traza. program_name, no match: el pre-decodificador quita el
      # nombre del programa del cuerpo. Sin el "--" en el comentario: es XML invalido.
      grep -q "id=\"100100\"" /var/ossec/etc/rules/local_rules.xml 2>/dev/null || cat >> /var/ossec/etc/rules/local_rules.xml <<'XML'

<group name="triaje,">
  <!-- Ancla de la traza encadenada del triaje asistido (prototipo/traza.py, TRIAJE_ANCLA). -->
  <rule id="100100" level="3">
    <program_name>^triaje-ancla$</program_name>
    <description>Triaje asistido: ancla de la traza (hash del ultimo registro)</description>
  </rule>
  <rule id="100101" level="5">
    <program_name>^triaje-rotacion$</program_name>
    <description>Triaje asistido: rotacion de la clave del conector</description>
  </rule>
</group>
XML
      # Decodificadores de telnetd propios (lab/wazuh/local_decoder_telnetd.xml): el in.telnetd de
      # Metasploitable pasa por tcpd y el hijo de fabrica no extrae el srcip. Se excluye el fichero
      # de fabrica y se provee el conjunto completo, con el formato de tcpd primero.
      grep -q "0335-telnet_decoders" /var/ossec/etc/ossec.conf || \
      sed -i "s|<decoder_dir>etc/decoders</decoder_dir>|<decoder_dir>etc/decoders</decoder_dir>\n    <decoder_exclude>ruleset/decoders/0335-telnet_decoders.xml</decoder_exclude>|" /var/ossec/etc/ossec.conf
      grep -q "telnetd-ip-tcpd" /var/ossec/etc/decoders/local_decoder.xml || cat /tmp/local_decoder_telnetd.xml >> /var/ossec/etc/decoders/local_decoder.xml
      # Reglas y decoder del banco para las otras familias (recon por sshd sin banner, telnet):
      # que Wazuh detecte, además de la fuerza bruta, reconocimiento y servicio_expuesto.
      grep -q "id=\"100200\"" /var/ossec/etc/rules/local_rules.xml || cat /tmp/local_rules_banco.xml >> /var/ossec/etc/rules/local_rules.xml
      grep -q "sshd-banner-scan" /var/ossec/etc/decoders/local_decoder.xml || cat /tmp/local_decoder_banco.xml >> /var/ossec/etc/decoders/local_decoder.xml
      /var/ossec/bin/wazuh-control restart >/dev/null 2>&1
    '
    until docker exec "$NAME" sh -c '/var/ossec/bin/wazuh-control status 2>/dev/null | grep -q "wazuh-analysisd is running"' 2>/dev/null; do sleep 4; done
    echo "Wazuh listo, recepcion de syslog activa. IP de gestion:"
    docker inspect "$NAME" --format "  {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"
    ;;
  down)  docker rm -f "$NAME" ;;
  logs)  docker logs --tail 40 "$NAME" ;;
  alerts)
    docker exec "$NAME" sh -c 'tail -n 20 /var/ossec/logs/alerts/alerts.json 2>/dev/null || echo "aun sin alertas"' ;;
  mem)
    docker stats --no-stream --format '  {{.Name}}: {{.MemUsage}}  CPU {{.CPUPerc}}' "$NAME" ;;
  *) echo "uso: $0 up|down|logs|alerts|mem" ;;
esac
