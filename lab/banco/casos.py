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


def _loop_ssh(destino_ip, bind=None):
    """El bucle de fuerza bruta SSH. Si `bind`, ata el cliente a esa IP de origen (`ssh -b`)."""
    b = f"-b {bind} " if bind else ""
    return ("for i in $(seq 1 10); do sshpass -p mal_$i ssh " + b + "-o StrictHostKeyChecking=no "
            "-o ConnectTimeout=4 -o PubkeyAuthentication=no -o PreferredAuthentications=password "
            f"cliente@{destino_ip} id >/dev/null 2>&1; done; true")


def _fuerza_bruta(origen, destino_ip):
    return (origen, _loop_ssh(destino_ip))


def fuerza_bruta_atada(origen, destino_ip, src_ip, iface="eth1"):
    """Fuerza bruta desde una IP de origen NUEVA: añade el alias en la interfaz de datos del nodo y
    ata el cliente SSH a esa IP, para que Wazuh registre un origen distinto en cada lanzamiento
    (esquiva la supresión del MDR y el bloqueo previo, como un atacante que rota IPs)."""
    alias = f"ip addr add {src_ip}/24 dev {iface} 2>/dev/null; "
    return (origen, alias + _loop_ssh(destino_ip, bind=src_ip))


def _dec(id_, titulo, alerta, esperado, rafaga=None):
    a = {"familia": "acceso_credenciales", **alerta}
    c = {"id": id_, "titulo": titulo, "nivel": "decision", "alerta": a, "esperado": esperado}
    if rafaga is not None:
        c["rafaga_60s"] = rafaga
    return c


CASOS = [
    {"nivel": "vivo", "id": "CASCADA", "titulo": "Tumbar core-db (sin el prototipo): cascada real del laboratorio",
     "preparar": [("core-db", "pkill -f 'servicio.py --nombre core-db'")],
     "esperado": {"caen": K1_CAEN | {"core-db"}},
     "deshacer": [("core-db", "REARRANCAR")]},
    {"nivel": "vivo", "id": "D1", "titulo": "Atacante externo contra web-banking: bloqueo automatico",
     "ataque": _fuerza_bruta("internet", "10.10.0.10"), "origen": "198.51.100.10", "destino_ip": "10.10.0.10",
     "esperado": {"requiere_humano": False, "accion_final": "BLOQUEAR_IP", "preguntas": 0,
                  "regla": ("web-banking", "-A INPUT -s 198.51.100.10/32 -j DROP"), "caen": set()},
     "deshacer": [("web-banking", "iptables -D INPUT -s 198.51.100.10 -j DROP")]},
    {"nivel": "vivo", "id": "A1", "titulo": "Equipo interno (taquilla) contra web-banking: retenida, el analista rechaza",
     "ataque": _fuerza_bruta("taquilla", "10.10.0.10"), "origen": "10.200.0.10", "destino_ip": "10.10.0.10", "menu": "2",
     "esperado": {"requiere_humano": True, "veredicto": "rechazar", "preguntas": 1,
                  "sin_reglas": True, "caen": set()},
     "deshacer": []},
    {"nivel": "vivo", "id": "K1", "titulo": "middleware comprometido contra core-db: aprobado; cascada no avisada (fallo conocido K1)",
     "ataque": _fuerza_bruta("middleware", "10.50.0.10"), "origen": "10.40.0.10", "destino_ip": "10.50.0.10", "menu": "1",
     "esperado": {"requiere_humano": True, "veredicto": "aprobar", "preguntas": 1, "prediccion_cascada": [],
                  "regla": ("core-db", "-A INPUT -s 10.40.0.10/32 -j DROP"), "caen": K1_CAEN},
     "deshacer": [("core-db", "iptables -D INPUT -s 10.40.0.10 -j DROP")]},
    {"nivel": "vivo", "id": "E1", "titulo": "La victima no responde al MDR: escalada a fw-core, aprobada",
     "preparar": [("web-banking", "iptables -I INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP")],
     "ataque": _fuerza_bruta("internet", "10.10.0.10"), "origen": "198.51.100.10", "destino_ip": "10.10.0.10", "escalada": "s",
     "esperado": {"escalado": True, "dispositivo_ejecutor": "fw-core",
                  "regla": ("fw-core", "-A FORWARD -s 198.51.100.10/32 -j DROP"), "caen": set()},
     "deshacer": [("fw-core", "iptables -D FORWARD -s 198.51.100.10 -j DROP"),
                  ("web-banking", "iptables -D INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP"),
                  ("web-banking", "iptables -D INPUT -s 198.51.100.10 -j DROP")]},

    _dec("D2", "Servicio no expuesto según el auditor -> FP exposición inexistente",
         {"origen_ip": "203.0.113.9", "activo": "web-banking", "servicio": "rdp", "regla_id": "5763"},
         {"clase": "fp_exposicion_inexistente", "accion_final": None}),
    # D3: sin ráfaga, el origen legítimo (gestión) cae en fp_actividad_legitima SIN acción propuesta
    # (resultado_filtro "sin_accion"): perfil.filtrar devuelve _res("sin_accion", None, False) antes
    # de llegar a la conciencia de actores, así que requiere_humano es SIEMPRE False en ese camino.
    # El diseño original esperaba True; corregido a False tras verificar contra el motor real (informe).
    _dec("D3", "Origen legítimo (gestión) -> FP actividad legítima",
         {"origen_ip": "10.100.0.10", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"clase": "fp_actividad_legitima", "accion_final": None, "requiere_humano": False}),
    _dec("D4", "Ráfaga desde origen legítimo -> VP conf 0.6, humano",
         {"origen_ip": "10.100.0.10", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"clase": "vp_intento_acceso", "confianza": 0.6, "requiere_humano": True}, rafaga=12),
    _dec("D6", "Familia no soportada -> no_soportada",
         {"origen_ip": "203.0.113.9", "activo": "web-banking", "servicio": "desconocido",
          "familia": "plataforma", "regla_id": "502"},
         {"clase": "no_soportada", "accion_final": None}),
    _dec("A2", "Origen aparente = un cortafuegos -> retenida, alcanza_servicio",
         {"origen_ip": "10.0.0.1", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"requiere_humano": True, "accion_final": "BLOQUEAR_IP"}),
    _dec("A3", "Origen aparente = la gestión -> veto duro",
         {"origen_ip": "10.100.0.10", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"requiere_humano": True, "accion_final": None}, rafaga=12),
    _dec("A4", "IP interna no inventariada -> activo interno, humano",
         {"origen_ip": "10.77.3.9", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"requiere_humano": True, "accion_final": "BLOQUEAR_IP"}),
    _dec("K5", "Ataque desde taquilla (nadie depende de ella) -> humano, sin cascada",
         {"origen_ip": "10.200.0.10", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"requiere_humano": True, "prediccion_cascada": []}),

    {"id": "C1", "titulo": "BLOQUEAR_PUERTO 1521 en core-db (excepción nunca_automatica) -> degrada a BLOQUEAR_IP",
     "nivel": "inyectada", "accion": "BLOQUEAR_PUERTO", "params": {"puerto": 1521, "ip": "203.0.113.9"},
     "activo": "core-db", "servicio": "sql", "confianza": 0.99,
     "esperado": {"filtro_resultado": "degrada", "accion_final": "BLOQUEAR_IP"}},
    {"id": "C2", "titulo": "BLOQUEAR_PUERTO 8443 en middleware -> degrada a BLOQUEAR_IP",
     "nivel": "inyectada", "accion": "BLOQUEAR_PUERTO", "params": {"puerto": 8443, "ip": "203.0.113.9"},
     "activo": "middleware", "servicio": "https", "confianza": 0.99,
     "esperado": {"filtro_resultado": "degrada", "accion_final": "BLOQUEAR_IP"}},
    {"id": "C3", "titulo": "AISLAR_NODO de web-banking (alcanza servicio) -> humano",
     "nivel": "inyectada", "accion": "AISLAR_NODO", "params": {}, "activo": "web-banking",
     "servicio": "https", "confianza": 0.99, "esperado": {"requiere_humano": True}},
    {"id": "K2", "titulo": "AISLAR_NODO de core-db -> predice la cascada transitiva",
     "nivel": "inyectada", "accion": "AISLAR_NODO", "params": {}, "activo": "core-db",
     "servicio": "sql", "confianza": 0.99,
     "esperado": {"requiere_humano": True, "prediccion_cascada": ["api-movil", "middleware", "web-banking"]}},
    {"id": "K3", "titulo": "AISLAR_NODO de middleware -> la cascada NO incluye atm (dependencia no declarada)",
     "nivel": "inyectada", "accion": "AISLAR_NODO", "params": {}, "activo": "middleware",
     "servicio": "https", "confianza": 0.99,
     "esperado": {"prediccion_cascada": ["api-movil", "web-banking"]}},
    {"id": "A5", "titulo": "AISLAR_NODO del nodo de gestión (mdr-siem) -> veto duro",
     "nivel": "inyectada", "accion": "AISLAR_NODO", "params": {"ip_nodo": "10.100.0.10"},
     "activo": "mdr-siem", "servicio": "ssh", "confianza": 0.99,
     "esperado": {"filtro_resultado": "veta", "accion_final": None}},
    {"id": "C5", "titulo": "Acción sin reversión definida (OBS_PROCESOS) -> se veta como contención",
     "nivel": "perfil", "comprobacion": "sin_reversion", "accion": "OBS_PROCESOS", "activo": "core-db",
     "esperado": {"filtro_resultado": "veta"}},
    {"id": "K4", "titulo": "afectados_en_cascada termina aunque haya dependencias (guardia de ciclos)",
     "nivel": "perfil", "comprobacion": "ciclo_depende_de", "activo": "a",
     # bancario.yml no tiene un ciclo real en depende_de (es un DAG); este perfil sintetico a->b->a
     # ejercita de verdad la guardia de ciclos de impacto.afectados_en_cascada.
     "perfil_sintetico": {"activos": {"a": {"depende_de": ["b"]}, "b": {"depende_de": ["a"]}}},
     "esperado": {"termina": True}},
]
