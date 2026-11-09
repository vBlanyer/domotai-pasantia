"""`mdr estado`: comprueba de una vez que la instalación del MDR está completa y sana, y dice qué
hacer con lo que falte. Sale con 1 si algo impide trabajar (un «✗»); los avisos («!») no.

Lee /etc/mdr/triaje.env (o MDR_ENV) y los ficheros a los que apunta. No modifica nada.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

MARCAS = {"ok": "✔", "aviso": "!", "fallo": "✗"}
DIAS_BASE = 45                      # DB-IP publica cada mes: más de mes y medio es una base atrasada


def _c(tema, nivel, texto, remedio=""):
    return {"tema": tema, "nivel": nivel, "texto": texto, "remedio": remedio}


def _salud_http(puerto):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{puerto}/healthz", headers={"Host": f"127.0.0.1:{puerto}"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode())
    except (OSError, ValueError):
        return None


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, TypeError):
        return None


def _hace(segundos):
    if segundos is None:
        return "sin alertas desde que arrancó"
    if segundos < 120:
        return f"última alerta hace {int(segundos)} s"
    if segundos < 7200:
        return f"última alerta hace {int(segundos // 60)} min"
    return f"última alerta hace {int(segundos // 3600)} h"


def comprobar(env, ejecutar=subprocess.run, salud=_salud_http, ahora=None):
    ahora = ahora or time.time()
    out = []

    activo = ejecutar(["systemctl", "is-active", "--quiet", "mdr-triaje"], capture_output=True).returncode == 0
    habilitado = ejecutar(["systemctl", "is-enabled", "--quiet", "mdr-triaje"], capture_output=True).returncode == 0
    if activo and habilitado:
        out.append(_c("servicio", "ok", "activo y habilitado"))
    elif activo:
        out.append(_c("servicio", "aviso", "activo, pero no arrancará con el equipo", "sudo systemctl enable mdr-triaje"))
    else:
        out.append(_c("servicio", "fallo", "parado", "sudo mdr configurar  (o: journalctl -u mdr-triaje -n 50)"))

    puerto = int(env.get("TRIAJE_WEB_PUERTO") or 8787)
    h = salud(puerto) if activo else None
    if not h:
        out.append(_c("salud", "fallo", f"no responde en 127.0.0.1:{puerto}/healthz", "journalctl -u mdr-triaje -n 50"))
    elif not h.get("ok"):
        out.append(_c("salud", "fallo", "el lazo de decisión no avanza", "sudo systemctl restart mdr-triaje"))
    else:
        out.append(_c("salud", "ok", f"lazo vivo · {_hace(h.get('ingesta_silencio_s'))} · {h.get('alertas', 0)} alertas"))

    ruta_perfil = env.get("TRIAJE_PERFIL")
    if not ruta_perfil or not os.path.isfile(ruta_perfil):
        out.append(_c("perfil", "fallo", f"no existe {ruta_perfil or '(TRIAJE_PERFIL sin fijar)'}", "sudo mdr configurar"))
        perfil = {}
    else:
        from prototipo.motor import perfil as perfilm
        try:
            perfil = perfilm.cargar(ruta_perfil)
            avisos = list(perfilm.validar(perfil))
            out.append(_c("perfil", "aviso" if avisos else "ok",
                          f"{len(avisos)} aviso(s)" if avisos else f"sin avisos · {len(perfil.get('activos') or {})} equipos",
                          "sudo mdr validar-perfil" if avisos else ""))
        except Exception as e:                                   # YAML roto: lo dice, no revienta
            perfil = {}
            out.append(_c("perfil", "fallo", f"no se puede leer: {e}", "sudo mdr validar-perfil"))

    if env.get("TRIAJE_ESCUCHAR"):
        if env.get("TRIAJE_PERMITIR") or env["TRIAJE_ESCUCHAR"].startswith("127."):
            tls = " con TLS" if env.get("TRIAJE_TLS_CERT") else " sin TLS"
            out.append(_c("alertas", "ok" if env.get("TRIAJE_TLS_CERT") else "aviso",
                          f"por la red en {env['TRIAJE_ESCUCHAR']}{tls}, desde {env.get('TRIAJE_PERMITIR', 'loopback')}",
                          "" if env.get("TRIAJE_TLS_CERT") else "sudo mdr configurar (activa TLS)"))
        else:
            out.append(_c("alertas", "fallo", "se escucha por la red sin TRIAJE_PERMITIR", "sudo mdr configurar"))
    elif env.get("TRIAJE_ALERTS") and os.path.exists(env["TRIAJE_ALERTS"]):
        out.append(_c("alertas", "ok", f"siguiendo {env['TRIAJE_ALERTS']}"))
    else:
        out.append(_c("alertas", "fallo", f"no existe {env.get('TRIAJE_ALERTS') or '(sin fuente)'}", "sudo mdr configurar"))

    try:
        from prototipo.herramientas import entorno
        n = len(set(entorno.operadores(env).values()))
        out.append(_c("analistas", "ok", f"{n} con token") if n else
                   _c("analistas", "fallo", "ninguno: la consola está abierta a cualquiera en el equipo",
                      "sudo mdr analista alta <nombre>"))
    except ValueError:
        out.append(_c("analistas", "fallo", "TRIAJE_CONSOLA_OPERADORES no es un JSON válido", "sudo mdr analista lista"))

    out.append(_c("traza", "ok", "firmada (HMAC)") if env.get("TRIAJE_TRAZA_CLAVE") else
               _c("traza", "aviso", "sin firma HMAC", "sudo mdr configurar (genera la clave)"))

    h = _leer_json(env.get("TRIAJE_HALLAZGOS"))
    nodos = (h or {}).get("nodos") if isinstance(h, dict) else None
    if nodos is None:
        out.append(_c("postura", "fallo", f"no se puede leer {env.get('TRIAJE_HALLAZGOS')}", "sudo mdr escanear"))
    elif not nodos:
        out.append(_c("postura", "aviso", "vacía: nada que dependa de la confianza se automatiza",
                      "sudo mdr escanear && sudo systemctl restart mdr-triaje"))
    else:
        out.append(_c("postura", "ok", f"{len(nodos)} equipos escaneados"))

    for tema, var, orden in (("países", "TRIAJE_GEOIP", "instalar-geoip"), ("ASN", "TRIAJE_ASN", "instalar-asn")):
        ruta = env.get(var)
        if not ruta or not os.path.isfile(ruta):
            out.append(_c(tema, "aviso", "sin base: los orígenes salen sin " + ("país" if tema == "países" else "organización"),
                          f"sudo mdr {orden} <fichero de DB-IP>"))
            continue
        dias = int((ahora - os.path.getmtime(ruta)) // 86400)
        out.append(_c(tema, "aviso" if dias > DIAS_BASE else "ok", f"base instalada hace {dias} días",
                      f"descarga la de este mes y: sudo mdr {orden} <fichero>" if dias > DIAS_BASE else ""))

    if env.get("TRIAJE_SSH_MODO") != "directo":
        out.append(_c("conector", "fallo", f"TRIAJE_SSH_MODO={env.get('TRIAJE_SSH_MODO') or '(sin fijar)'}; en producción, directo",
                      "sudo mdr configurar"))
    elif not os.path.isfile(env.get("TRIAJE_SSH_CLAVE") or ""):
        out.append(_c("conector", "aviso", "sin clave: no se contiene nada", "en la consola, Conectividad → «Generar la clave del conector»"))
    else:
        out.append(_c("conector", "ok", "clave generada"))

    ips = {t.get("ip") for t in (perfil.get("topologia") or {}).values() if isinstance(t, dict) and t.get("ip")}
    pruebas = _leer_json(os.path.join(os.path.dirname(env.get("TRIAJE_SALIDA") or "."), "conectividad-pruebas.json")) or {}
    ok = sum(1 for ip in ips if (pruebas.get(ip) or {}).get("estado") == "verificada")
    if ips:
        out.append(_c("equipos", "ok" if ok == len(ips) else "aviso", f"{ok} de {len(ips)} contenibles verificados",
                      "" if ok == len(ips) else "en la consola, Conectividad: da de alta o prueba los que faltan"))
    return out


def informe(comprobaciones):
    """(líneas, código de salida): 1 si hay algún fallo."""
    ancho = max(len(c["tema"]) for c in comprobaciones)
    lineas = ["MDR · estado de la instalación", ""]
    for c in comprobaciones:
        lineas.append(f"  {MARCAS[c['nivel']]} {c['tema'].ljust(ancho)}  {c['texto']}")
        if c["remedio"] and c["nivel"] != "ok":
            lineas.append(f"    {' ' * ancho}  → {c['remedio']}")
    fallos = sum(c["nivel"] == "fallo" for c in comprobaciones)
    avisos = sum(c["nivel"] == "aviso" for c in comprobaciones)
    lineas += ["", "Todo en orden." if not (fallos or avisos) else f"{fallos} fallo(s), {avisos} aviso(s)."]
    return lineas, 1 if fallos else 0


def _main():
    from prototipo.herramientas import entorno
    ruta = os.environ.get("MDR_ENV", "/etc/mdr/triaje.env")
    if not os.access(ruta, os.R_OK):
        print(f"mdr estado: no se puede leer {ruta} (ejecútalo con sudo)", file=sys.stderr)
        return 1
    lineas, rc = informe(comprobar(entorno.leer(ruta)))
    print("\n".join(lineas))
    return rc


if __name__ == "__main__":
    sys.exit(_main())
