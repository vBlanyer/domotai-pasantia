"""`mdr configurar`: el asistente que deja /etc/mdr/triaje.env bien escrito y el servicio en marcha.

Pregunta lo imprescindible (el perfil, cómo llegan las alertas del SIEM y, si ya se descargaron, las
bases de DB-IP), genera la clave de la traza la primera vez, y arranca. Se puede repetir: cada
pregunta propone lo que ya hay, y lo que no pregunta (analistas, recortes…) no lo toca.
"""
import ipaddress
import os
import secrets
import shutil
import subprocess
import sys
import time

from prototipo.herramientas import entorno

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLANTILLA_PERFIL = os.path.join(RAIZ, "deploy", "perfil.ejemplo.yml")
PLANTILLA_ENV = os.path.join(RAIZ, "deploy", "triaje.env.ejemplo")
ALERTS_WAZUH = "/var/ossec/logs/alerts/alerts.json"


def _preguntar_consola(texto, defecto=""):
    r = input(f"  {texto}{f' [{defecto}]' if defecto else ''}: ").strip()
    return r or defecto


def _ips_validas(texto):
    ips = [x.strip() for x in texto.split(",") if x.strip()]
    for ip in ips:
        ipaddress.ip_address(ip)                     # ValueError si no lo es
    return ips


def _instalar_base(origen, destino, tipo):
    from prototipo.herramientas import instalar_geoip
    return instalar_geoip.instalar(origen, destino, tipo)


def _salud_http(puerto):
    from prototipo.herramientas import estado_instalacion
    return estado_instalacion._salud_http(puerto)


def _dar_a_triaje(ruta):
    """root:triaje 0640, para que el servicio lo lea y no lo cambie. Fuera de root no hace nada."""
    if os.geteuid() != 0:
        return
    import grp
    try:
        os.chown(ruta, 0, grp.getgrnam("triaje").gr_gid)
        os.chmod(ruta, 0o640)
    except KeyError:
        pass


def configurar(ruta_env, preguntar=_preguntar_consola, decir=print, ejecutar=subprocess.run,
               plantilla_perfil=PLANTILLA_PERFIL, salud=_salud_http, instalar_base=_instalar_base, esperar=time.sleep):
    if not os.path.exists(ruta_env):
        shutil.copy(PLANTILLA_ENV, ruta_env)
        os.chmod(ruta_env, 0o600)
    v = entorno.leer(ruta_env)
    cambios = {}
    decir("MDR · configuración (Enter acepta el valor entre corchetes)\n")

    # 1 · perfil
    decir("1/4 · El perfil del cliente (su red: equipos, cortafuegos, dependencias)")
    perfil = preguntar("Ruta del perfil", v.get("TRIAJE_PERFIL") or "/etc/mdr/perfil.yml")
    perfil_listo = True
    if not os.path.isfile(perfil):
        if preguntar("No existe. ¿Copio ahí la plantilla para que la adaptes? (s/n)", "s").lower().startswith("s"):
            shutil.copy(plantilla_perfil, perfil)
            _dar_a_triaje(perfil)
            decir(f"  Plantilla copiada en {perfil}. Edítala con la red del cliente; el servicio no arrancará "
                  "hasta entonces.")
        perfil_listo = False
    else:
        from prototipo.motor import perfil as perfilm
        try:
            avisos = list(perfilm.validar(perfilm.cargar(perfil)))
        except Exception as e:
            avisos = [f"no se puede leer: {e}"]
        for a in avisos:
            decir(f"  aviso: {a}")
        if avisos and not preguntar("El perfil tiene avisos. ¿Sigo de todas formas? (s/n)", "n").lower().startswith("s"):
            return 1
        if not avisos:
            decir("  perfil sin avisos")
    cambios["TRIAJE_PERFIL"] = perfil

    # 2 · alertas
    decir("\n2/4 · Cómo llegan las alertas del SIEM")
    modo = preguntar("1) un alerts.json legible en este equipo   2) por la red desde el SIEM",
                     "2" if v.get("TRIAJE_ESCUCHAR") else "1")
    if modo.strip() == "2":
        puerto = preguntar("Puerto en el que escucha el MDR", (v.get("TRIAJE_ESCUCHAR") or ":6514").rsplit(":", 1)[1])
        while True:
            texto = preguntar("IPs del SIEM que pueden enviar, separadas por comas", v.get("TRIAJE_PERMITIR", ""))
            try:
                ips = _ips_validas(texto)
                if ips:
                    break
                decir("  hace falta al menos una IP")
            except ValueError:
                decir(f"  «{texto}» no es una lista de IPs válida")
        cert = preguntar("Certificado TLS del MDR (vacío = sin TLS)", v.get("TRIAJE_TLS_CERT", ""))
        clave = ca = ""
        if cert:
            while not clave:
                clave = preguntar("Clave privada de ese certificado", v.get("TRIAJE_TLS_CLAVE", ""))
            ca = preguntar("CA que firma el certificado del SIEM (vacío = no exigirlo)", v.get("TRIAJE_TLS_CA", ""))
        else:
            decir("  aviso: sin TLS, las alertas viajan en claro; solo la lista de IPs protege el puerto")
        cambios.update({"TRIAJE_ESCUCHAR": f"0.0.0.0:{puerto}", "TRIAJE_PERMITIR": ",".join(ips),
                        "TRIAJE_TLS_CERT": cert or None, "TRIAJE_TLS_CLAVE": clave or None, "TRIAJE_TLS_CA": ca or None})
    else:
        ruta = preguntar("Ruta del alerts.json", v.get("TRIAJE_ALERTS") or ALERTS_WAZUH)
        if not os.path.exists(ruta):
            decir(f"  aviso: {ruta} no existe todavía; el servicio lo esperará")
        cambios.update({"TRIAJE_ALERTS": ruta, "TRIAJE_ESCUCHAR": None, "TRIAJE_PERMITIR": None,
                        "TRIAJE_TLS_CERT": None, "TRIAJE_TLS_CLAVE": None, "TRIAJE_TLS_CA": None})

    # 3 · bases de DB-IP
    decir("\n3/4 · Bases de países y organizaciones (DB-IP Lite, descargadas de db-ip.com)")
    for tipo, var, nombre in (("pais", "TRIAJE_GEOIP", "países"), ("asn", "TRIAJE_ASN", "organizaciones (ASN)")):
        destino = v.get(var) or f"/var/lib/mdr/dbip-{'country' if tipo == 'pais' else 'asn'}-lite.csv.gz"
        ya = " (ya hay una instalada)" if os.path.isfile(destino) else ""
        origen = preguntar(f"Fichero de {nombre} descargado{ya} (vacío = ahora no)", "")
        if origen:
            try:
                r = instalar_base(origen, destino, tipo)
                decir(f"  instalada: {r['rangos']:,} rangos".replace(",", "."))
            except SystemExit as e:
                decir(f"  no instalada: {e}")
        cambios[var] = destino

    # 4 · lo fijo, la clave de la traza y el arranque
    if not v.get("TRIAJE_SSH_MODO"):
        cambios["TRIAJE_SSH_MODO"] = "directo"
    nueva_clave = None
    if not v.get("TRIAJE_TRAZA_CLAVE"):
        nueva_clave = cambios["TRIAJE_TRAZA_CLAVE"] = secrets.token_hex(32)
    entorno.escribir(ruta_env, cambios)
    decir(f"\n4/4 · Configuración guardada en {ruta_env}")
    if nueva_clave:
        decir(f"  Clave de la traza generada. Guárdala FUERA de este equipo (sin ella no se puede verificar la "
              f"traza):\n\n    {nueva_clave}\n")
    if not perfil_listo:
        decir(f"Cuando el perfil esté listo, vuelve a ejecutar «sudo mdr configurar» para arrancar.")
        return 0
    ejecutar(["systemctl", "enable", "mdr-triaje"], capture_output=True)
    ejecutar(["systemctl", "restart", "mdr-triaje"], capture_output=True)
    puerto_web = int(entorno.leer(ruta_env).get("TRIAJE_WEB_PUERTO") or 8787)
    for _ in range(20):
        if salud(puerto_web):
            break
        esperar(1)
    else:
        decir("El servicio no responde. Mira: journalctl -u mdr-triaje -n 50")
        return 1
    decir("Servicio en marcha.\n\nSiguientes pasos:")
    if not entorno.operadores(entorno.leer(ruta_env)):
        decir("  · sudo mdr analista alta <nombre> --clave-ssh <su-clave.pub>   (sin analistas la consola está abierta)")
    decir("  · en la consola, Conectividad: genera la clave del conector y da de alta los equipos")
    decir("  · sudo mdr escanear   (la postura; sin ella nada se automatiza)")
    decir("  · sudo mdr estado     (comprueba que no falta nada)")
    return 0


def _main():
    if os.geteuid() != 0:
        print("mdr configurar: ejecútalo con sudo", file=sys.stderr)
        return 1
    try:
        return configurar(os.environ.get("MDR_ENV", "/etc/mdr/triaje.env"))
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado: triaje.env no se ha cambiado (lo ya hecho antes de cancelar, como copiar la "
              "plantilla del perfil o instalar una base, se conserva).")
        return 1


if __name__ == "__main__":
    sys.exit(_main())
