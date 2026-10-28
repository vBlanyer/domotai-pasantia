"""Generador de la campaña SINTÉTICA de la demo de geolocalización (ver el paquete).

Fabrica alertas Wazuh CRUDAS (el formato que normaliza el daemon `stream`) con IPs de origen públicas
de varios países. Funciones PURAS (la E/S está en `emitir`); el motor no se toca.
"""
import ipaddress
import json
import random
import sys
import time

from prototipo.motor import actores

# Activos internos del perfil bancario que reciben los ataques (objetivos verosímiles).
OBJETIVOS = ["web-banking", "api-movil", "swift-alliance", "middleware", "core-db", "hsm", "taquilla", "atm"]

# Familias de ORIGEN EXTERNO: el atacante es la IP de origen (srcip) y por tanto geolocaliza. Cada una
# se mapea a los grupos de regla Wazuh que la disparan en el adaptador (`adaptador_wazuh.familia_de`):
#   familia -> (grupos, regla_id, nivel, técnicas MITRE, programa, descripción)
# No se usan familias como exfiltración/C2 (ahí el origen es el host INTERNO y el destino el malicioso;
# geolocalizarían la 10.x interna, no el extranjero) ni las intrínsecamente internas (FIM, cuentas).
_GRUPOS = {
    "reconocimiento":       (["recon"],                   "5706",  6,  ["T1595"], "nmap",     "escaneo de puertos / reconocimiento"),
    "acceso_credenciales":  (["authentication_failures"], "5712",  10, ["T1110"], "sshd",     "múltiples fallos de autenticación (fuerza bruta)"),
    "denegacion_servicio":  (["dos"],                     "40101", 12, ["T1498"], "kernel",   "flood volumétrico (denegación de servicio)"),
    "explotacion_conocida": (["exploit"],                 "5710",  12, ["T1190"], "suricata", "intento de explotación de vulnerabilidad conocida"),
}
FAMILIAS = list(_GRUPOS)


def pool_publico(tabla=None):
    """IPs públicas de muestra, una por bloque de la MISMA tabla que usa el enriquecimiento
    (`corpus/geoip-muestra.json`): `[(ip, pais, codigo), …]`. La IP es un host DENTRO del CIDR
    (el desplazamiento se acota al tamaño del bloque, así un /30 o /32 no se sale del rango)."""
    tabla = actores._tabla_geoip() if tabla is None else tabla
    pool = []
    for e in tabla:
        try:
            red = ipaddress.ip_network(e["cidr"], strict=False)
        except (ValueError, KeyError):
            continue
        offset = 10 if red.num_addresses > 11 else red.num_addresses - 1   # nunca fuera del CIDR
        ip = str(red.network_address + offset)
        pool.append((ip, e.get("pais"), e.get("codigo")))
    return pool


def alerta_cruda(ip, familia, activo, i=0, ts=None):
    """Una alerta Wazuh CRUDA para `familia` con `srcip=ip` contra `activo`. El evento crudo va
    marcado «[DEMO SINTÉTICA]» para que nunca se confunda con tráfico real."""
    if familia not in _GRUPOS:
        raise ValueError(f"familia no soportada para la demo: {familia!r} (de {FAMILIAS})")
    grupos, rid, nivel, mitre, programa, descripcion = _GRUPOS[familia]
    return {
        "id": f"geo-demo-{familia}-{ip}-{i}",
        "timestamp": ts or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "rule": {"id": rid, "level": nivel, "groups": list(grupos),
                 "description": descripcion, "mitre": {"id": list(mitre)}},
        "data": {"srcip": ip},
        "predecoder": {"hostname": activo, "program_name": programa},
        "location": f"/var/log/{programa or 'secure'}",
        "full_log": f"[DEMO SINTÉTICA] {descripcion}: src={ip} -> {activo}",
    }


def campaña_mundial(semilla=0, por_pais=1, familias=None, objetivos=None):
    """Una campaña: para cada país del pool, `por_pais` ataques de familia/objetivo barajados de forma
    REPRODUCIBLE (misma semilla → misma campaña, RNF-03). Cubre todos los países del pool."""
    rnd = random.Random(semilla)
    familias = familias or FAMILIAS
    objetivos = objetivos or OBJETIVOS
    alertas = []
    for k, (ip, _pais, _codigo) in enumerate(pool_publico()):
        for j in range(por_pais):
            alertas.append(alerta_cruda(ip, rnd.choice(familias), rnd.choice(objetivos), i=f"{k}-{j}"))
    return alertas


def emitir(alertas, salida=sys.stdout, pausa=0.8):
    """Escribe cada alerta como una línea JSON (lo que lee `stream -`), con una `pausa` entre líneas
    para que el mapa se vaya poblando ante los ojos. `pausa=0` no duerme (tests/volcado)."""
    for a in alertas:
        salida.write(json.dumps(a, ensure_ascii=False) + "\n")
        salida.flush()
        if pausa:
            time.sleep(pausa)


def main(argv):
    pausa, semilla, por_pais, continuo = 0.8, 0, 1, False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--pausa":    i += 1; pausa = float(argv[i])
        elif a == "--semilla": i += 1; semilla = int(argv[i])
        elif a == "--por-pais": i += 1; por_pais = int(argv[i])
        elif a == "--continuo": continuo = True      # repite la campaña sin fin (soak de la demo)
        elif a in ("-h", "--help"):
            print("uso: python3 -m lab.geo_demo.generador [--pausa S] [--semilla N] [--por-pais N] [--continuo]")
            print("  emite alertas Wazuh crudas por stdout; canalízalas a stream - … --web")
            return 0
        i += 1
    vuelta = semilla
    while True:
        emitir(campaña_mundial(semilla=vuelta, por_pais=por_pais), pausa=pausa)
        if not continuo:
            return 0
        vuelta += 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
