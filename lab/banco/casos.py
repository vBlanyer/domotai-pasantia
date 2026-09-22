"""Catálogo de casos del banco de pruebas: qué se comprueba, cómo se prepara/ataca y qué se espera.

No importa nada de ejecución (subprocess, prototipo, etc.); solo define datos y el helper para
construir el comando de fuerza bruta que usan varios casos.

Niveles (ver plan del banco de pruebas):
    decision   — decisión pura del prototipo, sin laboratorio.
    inyectada  — alerta inyectada directamente, sin ataque real.
    perfil     — variación de perfil/catálogo.
    vivo       — ataque real contra la red del laboratorio (los cinco casos de la guía manual).
"""

NIVELES = ("decision", "inyectada", "perfil", "vivo")

K1_CAEN = {"middleware", "web-banking", "api-movil", "atm"}


def _fuerza_bruta(origen, destino_ip):
    return (origen, "for i in $(seq 1 10); do sshpass -p mal_$i ssh -o StrictHostKeyChecking=no "
                    "-o ConnectTimeout=4 -o PubkeyAuthentication=no -o PreferredAuthentications=password "
                    f"cliente@{destino_ip} id >/dev/null 2>&1; done; true")


CASOS = [
    {"nivel": "vivo", "id": "CASCADA", "titulo": "Tumbar core-db (sin el prototipo): cascada real del laboratorio",
     "preparar": [("core-db", "pkill -f 'servicio.py --nombre core-db'")],
     "esperado": {"caen": K1_CAEN | {"core-db"}},
     "deshacer": [("core-db", "REARRANCAR")]},
    {"nivel": "vivo", "id": "D1", "titulo": "Atacante externo contra web-banking: bloqueo automatico",
     "ataque": _fuerza_bruta("internet", "10.10.0.10"), "origen": "198.51.100.10",
     "esperado": {"requiere_humano": False, "accion_final": "BLOQUEAR_IP", "preguntas": 0,
                  "regla": ("web-banking", "-A INPUT -s 198.51.100.10/32 -j DROP"), "caen": set()},
     "deshacer": [("web-banking", "iptables -D INPUT -s 198.51.100.10 -j DROP")]},
    {"nivel": "vivo", "id": "A1", "titulo": "Equipo interno (taquilla) contra web-banking: retenida, el analista rechaza",
     "ataque": _fuerza_bruta("taquilla", "10.10.0.10"), "origen": "10.200.0.10", "menu": "2",
     "esperado": {"requiere_humano": True, "veredicto": "rechazar", "preguntas": 1,
                  "sin_reglas": True, "caen": set()},
     "deshacer": []},
    {"nivel": "vivo", "id": "K1", "titulo": "middleware comprometido contra core-db: aprobado; cascada no avisada (fallo conocido K1)",
     "ataque": _fuerza_bruta("middleware", "10.50.0.10"), "origen": "10.40.0.10", "menu": "1",
     "esperado": {"requiere_humano": True, "veredicto": "aprobar", "preguntas": 1, "prediccion_cascada": [],
                  "regla": ("core-db", "-A INPUT -s 10.40.0.10/32 -j DROP"), "caen": K1_CAEN},
     "deshacer": [("core-db", "iptables -D INPUT -s 10.40.0.10 -j DROP")]},
    {"nivel": "vivo", "id": "E1", "titulo": "La victima no responde al MDR: escalada a fw-core, aprobada",
     "preparar": [("web-banking", "iptables -I INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP")],
     "ataque": _fuerza_bruta("internet", "10.10.0.10"), "origen": "198.51.100.10", "escalada": "s",
     "esperado": {"escalado": True, "dispositivo_ejecutor": "fw-core",
                  "regla": ("fw-core", "-A FORWARD -s 198.51.100.10/32 -j DROP"), "caen": set()},
     "deshacer": [("fw-core", "iptables -D FORWARD -s 198.51.100.10 -j DROP"),
                  ("web-banking", "iptables -D INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP"),
                  ("web-banking", "iptables -D INPUT -s 198.51.100.10 -j DROP")]},
]
