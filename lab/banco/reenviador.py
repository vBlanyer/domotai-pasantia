"""Sigue los logs de un nodo del banco (sshd y accesos web) y los envia por syslog UDP al manager de
Wazuh, con el nombre del nodo como host (Wazuh deriva de ahi el activo, RF-16). El formato es el que
Wazuh ya decodifica en la red pequena (lab/lab.sh test). Autonomo (biblioteca estandar).

Si Wazuh no decodifica el web por syslog, D5 queda marcado con su limite (plan, R3).
"""
import argparse
import re
import socket
import time

_SSHD = re.compile(r"sshd\[(\d+)\]:\s?(.*)$")


def linea_syslog(prioridad, nodo, programa, mensaje, instante):
    cabecera = time.strftime("%b %d %H:%M:%S", time.gmtime(instante))
    cuerpo = f"{programa}: {mensaje}" if programa else mensaje
    return f"<{prioridad}>{cabecera} {nodo} {cuerpo}"


def desde_sshd(nodo, linea, instante):
    linea = linea.rstrip("\n")
    m = _SSHD.search(linea)
    pid, msg = (m.group(1), m.group(2)) if m else ("0", linea.strip())
    return linea_syslog(38, nodo, f"sshd[{pid}]", msg, instante)


def desde_web(nodo, linea, instante):
    return linea_syslog(30, nodo, "apache", linea.rstrip("\n"), instante)

def desde_telnet(nodo, linea, instante):
    # El señuelo telnet (telnet_expuesto.py) registra "connect from <ip>"; se envia con programa
    # in.telnetd para que el telnet decoder de Wazuh saque el srcip (familia servicio_expuesto).
    return linea_syslog(38, nodo, "in.telnetd", linea.rstrip("\n"), instante)


def seguir(rutas_y_formateadores, enviar, dormir=time.sleep, parar=lambda: False):
    """Como tail -F sobre varios ficheros: desde el final, envia cada linea nueva formateada."""
    abiertos = []
    for ruta, fmt in rutas_y_formateadores:
        while True:
            try:
                f = open(ruta, encoding="utf-8", errors="replace")
                break
            except FileNotFoundError:
                dormir(0.5)
        f.seek(0, 2)
        abiertos.append((f, fmt))
    while not parar():
        nada = True
        for f, fmt in abiertos:
            linea = f.readline()
            if linea:
                nada = False
                enviar(fmt(linea, time.time()))
        if nada:
            dormir(0.2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reenvia los logs de un nodo del banco a Wazuh")
    ap.add_argument("--nodo", required=True)
    ap.add_argument("--destino", required=True, help="host:puerto del syslog de Wazuh")
    ap.add_argument("--sshd", default=None)
    ap.add_argument("--web", default=None)
    ap.add_argument("--telnet", default=None)
    a = ap.parse_args(argv)
    host, puerto = a.destino.rsplit(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    fuentes = []
    if a.sshd:
        fuentes.append((a.sshd, lambda l, t: desde_sshd(a.nodo, l, t)))
    if a.web:
        fuentes.append((a.web, lambda l, t: desde_web(a.nodo, l, t)))
    if a.telnet:
        fuentes.append((a.telnet, lambda l, t: desde_telnet(a.nodo, l, t)))
    seguir(fuentes, lambda linea: sock.sendto(linea.encode(), (host, int(puerto))))


if __name__ == "__main__":
    main()
