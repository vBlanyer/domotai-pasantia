# Espera con tope a que el Wazuh manager esté listo (analysisd en marcha). Se carga con «.» desde
# wazuh-run.sh y lab.sh:
#
#   . lab/scripts/esperar-wazuh.sh
#   esperar_wazuh <contenedor>      # 0 cuando está listo; 1 (con el final de su registro) si se agota
#
# WAZUH_ESPERA_MAX (segundos, 600 por defecto) y WAZUH_ESPERA_PASO (4). Sin tope, un Wazuh que no
# arranca dejaba el script colgado para siempre: en un arranque desatendido nadie lo ve.
esperar_wazuh() {
  _max=${WAZUH_ESPERA_MAX:-600}
  _paso=${WAZUH_ESPERA_PASO:-4}
  _t=0
  until docker exec "$1" sh -c '/var/ossec/bin/wazuh-control status 2>/dev/null | grep -q "wazuh-analysisd is running"' 2>/dev/null; do
    if [ "$_t" -ge "$_max" ]; then
      echo "Wazuh ($1) no arrancó en $_max s. Final de su registro:" >&2
      docker logs --tail 30 "$1" >&2 2>&1 || :
      return 1
    fi
    sleep "$_paso"
    _t=$((_t + _paso))
  done
}
