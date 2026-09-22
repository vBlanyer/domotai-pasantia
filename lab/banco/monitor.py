"""Monitor de salud del laboratorio del banco: consulta /salud de cada servicio cada pocos segundos y
escribe una linea de tiempo JSONL. Es el juez de los casos de continuidad y cascada (spec §5.2):
lo que la prediccion avisa se compara con lo que el monitor ve caer. Autonomo (biblioteca estandar).
"""
import argparse
import json
import time
import urllib.error
import urllib.request


def parsear_servicios(args):
    return dict(a.split("=", 1) for a in args)


def sondear(servicios, abrir=urllib.request.urlopen, plazo=1.0):
    estados = {}
    for nombre, destino in servicios.items():
        try:
            with abrir(f"http://{destino}/salud", timeout=plazo) as r:
                estados[nombre] = "ok" if r.status == 200 else "caido"
        except urllib.error.HTTPError as e:
            e.close()
            estados[nombre] = "caido"
        except Exception:
            estados[nombre] = "caido"
    return estados


def cambios(anterior, actual):
    return {"caen": sorted(n for n, e in actual.items() if e == "caido" and anterior.get(n) == "ok"),
            "vuelven": sorted(n for n, e in actual.items() if e == "ok" and anterior.get(n) == "caido")}


def registro(estados, instante):
    return json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(instante)), "estados": estados},
                      sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Monitor de salud del laboratorio del banco")
    ap.add_argument("--intervalo", type=float, default=2.0)
    ap.add_argument("--salida", required=True)
    ap.add_argument("servicios", nargs="+", help="nombre=ip:puerto")
    a = ap.parse_args(argv)
    servicios = parsear_servicios(a.servicios)
    while True:
        with open(a.salida, "a", encoding="utf-8") as f:
            f.write(registro(sondear(servicios), time.time()) + "\n")
        time.sleep(a.intervalo)


if __name__ == "__main__":
    main()
