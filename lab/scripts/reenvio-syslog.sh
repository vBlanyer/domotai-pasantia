#!/bin/sh
# Arranca en el objetivo un reenviador de auth.log hacia el Wazuh manager.
#
# Por que hace falta: el syslogd de Metasploitable (2007) reenvia SIN la cabecera
# "MES DIA HH:MM:SS host" que el decodificador sshd de Wazuh necesita para
# clasificar. auth.log SI tiene esa cabecera, asi que reenviamos el fichero linea
# a linea, anteponiendo la prioridad syslog. Asi Wazuh decodifica y alerta.
#
# Se ejecuta despues de cada 'containerlab deploy': el proceso vive dentro del
# contenedor y no sobrevive a un redespliegue.
#
# Uso:  sh lab/reenvio-syslog.sh [IP_DEL_MANAGER]   (por defecto la descubre)

WAZUH="${1:-$(docker inspect clab-fttx-lab-wazuh --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)}"
[ -z "$WAZUH" ] && { echo "No encuentro el manager de Wazuh. Arrancalo con: sh lab/wazuh-run.sh up"; exit 1; }
echo "Reenviando auth.log del objetivo -> Wazuh ($WAZUH:514)"

# Escribir el reenviador como fichero dentro del contenedor
docker exec clab-fttx-lab-objetivo-vuln sh -c "cat > /usr/local/bin/reenvio.sh <<SCRIPT
#!/bin/sh
tail -n0 -f /var/log/auth.log | while IFS= read -r l; do
  printf '<38>%s\\n' \"\\\$l\" | nc -u -w1 $WAZUH 514
done
SCRIPT
chmod +x /usr/local/bin/reenvio.sh
pkill -f /usr/local/bin/reenvio.sh 2>/dev/null || true"

# Lanzarlo con -d en PRIMER PLANO dentro del exec (asi persiste; un & interno no)
docker exec -d clab-fttx-lab-objetivo-vuln /usr/local/bin/reenvio.sh
sleep 2

if docker exec clab-fttx-lab-objetivo-vuln sh -c 'ps aux | grep -q "[r]eenvio.sh"' 2>/dev/null; then
  echo "  reenvio activo"
  echo "Prueba:  docker exec clab-fttx-lab-objetivo-vuln sh -c 'logger -p auth.info -t \"sshd[9]\" \"Failed password for root from 1.2.3.4 port 22 ssh2\"'"
else
  echo "  AVISO: el reenviador no arranco; reintenta este script"
fi
