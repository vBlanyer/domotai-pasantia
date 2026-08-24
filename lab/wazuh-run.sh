#!/bin/sh
# Levanta el Wazuh manager SOLO (sin indexer ni dashboard) conectado al bridge
# de gestion del laboratorio (red docker "clab"). Escribe las alertas en un
# volumen para poder leer alerts.json desde fuera.
#
# No es un nodo de containerlab: la imagen es demasiado pesada y tiene su propio
# entrypoint. Vive en el plano de gestion, junto al auditor, sin tocar el plano
# de datos. Ver documentacion/04-.../flujo-edr-playbook-sandbox.md
#
# Uso:   sh lab/wazuh-run.sh up | down | logs | alerts | mem
set -e
IMG=wazuh/wazuh-manager:4.14.7
NAME=clab-fttx-lab-wazuh
NET=clab

case "${1:-up}" in
  up)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker run -d --name "$NAME" --network "$NET" \
      --hostname wazuh \
      -p 1514:1514 -p 1515:1515 -p 514:514/udp -p 55000:55000 \
      "$IMG"
    echo "Wazuh manager arrancando..."
    # Esperar a analysisd y HABILITAR la recepcion de syslog remoto (no viene
    # activa de fabrica). Sin esto, el manager ignora todo el syslog del lab.
    until docker exec "$NAME" sh -c '/var/ossec/bin/wazuh-control status 2>/dev/null | grep -q "wazuh-analysisd is running"' 2>/dev/null; do sleep 4; done
    docker exec "$NAME" sh -c '
      grep -q "<connection>syslog" /var/ossec/etc/ossec.conf 2>/dev/null || \
      sed -i "s|</ossec_config>|  <remote>\n    <connection>syslog</connection>\n    <port>514</port>\n    <protocol>udp</protocol>\n    <allowed-ips>172.20.20.0/24</allowed-ips>\n  </remote>\n</ossec_config>|" /var/ossec/etc/ossec.conf
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
