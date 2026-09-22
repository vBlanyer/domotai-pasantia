"""Servicio minimo del laboratorio del banco: responde HTTP en su puerto nominal y expone /salud,
que solo esta sano si el servicio Y todas sus dependencias lo estan. Como cada dependencia consulta a
su vez su /salud, una caida se propaga en cascada de verdad (spec §5.2). Autonomo: solo biblioteca
estandar, porque se copia tal cual a la imagen banco-nodo.
"""
import argparse
import http.server
import json
import threading
import time
import urllib.request


def comprobar_dependencias(dependencias, abrir=urllib.request.urlopen, plazo=1.0):
    """Las dependencias ("host:puerto") cuyo /salud no responde 200."""
    fallan = []
    for dep in dependencias:
        try:
            with abrir(f"http://{dep}/salud", timeout=plazo) as r:
                if r.status != 200:
                    fallan.append(dep)
        except Exception:
            fallan.append(dep)
    return fallan


def linea_acceso(ip, metodo, ruta, estado, tamano, agente, instante):
    """Registro de accesos en formato Apache combined (el que decodifica Wazuh)."""
    fecha = time.strftime("%d/%b/%Y:%H:%M:%S +0000", time.gmtime(instante))
    return f'{ip} - - [{fecha}] "{metodo} {ruta} HTTP/1.1" {estado} {tamano} "-" "{agente}"'


def crear_servidor(nombre, puerto, dependencias, registrar):
    class Manejador(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/salud":
                fallan = comprobar_dependencias(dependencias)
                cuerpo = {"servicio": nombre, "estado": "degradado" if fallan else "ok", "falla": fallan}
                estado = 503 if fallan else 200
            else:
                cuerpo, estado = {"servicio": nombre}, 200
            datos = json.dumps(cuerpo).encode()
            self.send_response(estado)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)
            if self.path != "/salud":
                registrar(linea_acceso(self.client_address[0], "GET", self.path, estado, len(datos),
                                       self.headers.get("User-Agent", "-"), time.time()))

        def log_message(self, *args):   # el registro propio sustituye al de stderr
            pass

    return http.server.ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Servicio minimo del laboratorio del banco")
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--puerto", type=int, action="append", required=True)
    ap.add_argument("--depende", action="append", default=[])
    ap.add_argument("--registro", default=None, help="fichero del registro de accesos")
    a = ap.parse_args(argv)
    cerrojo = threading.Lock()

    def registrar(linea):
        if not a.registro:
            return
        with cerrojo, open(a.registro, "a", encoding="utf-8") as f:
            f.write(linea + "\n")

    servidores = [crear_servidor(a.nombre, p, a.depende, registrar) for p in a.puerto]
    for s in servidores[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    servidores[0].serve_forever()


if __name__ == "__main__":
    main()
