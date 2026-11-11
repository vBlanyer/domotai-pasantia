"""Validación en el banco de los recortes ante fallos de contención (plan de fallos, fases 4–6).

    python3 -m lab.banco.validar_recortes [--parte a|b|ab] [--solo e1,sshd,...] [--salida DIR]

Para cada modo (los cinco interruptores a "0" y a "1") levanta un daemon propio en :8791, con su traza
aparte, provoca un fallo en un equipo, lanza un ataque real desde una IP de origen nueva y mide hasta que
la decisión aparece en la traza. No toca run/ ni el :8787. Requiere el banco levantado y aprovisionado.

  Parte A — sin contexto de la consola: FALLO_RAPIDO y MEMORIA_FALLOS (F3, F4, F5, F8).
  Parte B — con lo que sabe la consola: PRECHECK_APROVISIONADO (F2), ESCALADA_SOLO_APROVISIONADOS y
            ACCION_NO_EJECUTABLE (F6). Usa «Probar» de Conectividad con el opt-in de laboratorio.

Resultados en evaluacion/resultados/validacion-recortes-<fecha>/ (JSON por parte y registro de memoria).
"""
import argparse, json, os, signal, subprocess, sys, threading, time, urllib.request
from datetime import date

from lab.banco import casos, demo

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PUERTO = 8791
EQUIPO = "web-banking"
NODO_GESTION = "clab-banco-mdr-siem"
KNOWN = "/root/.ssh/known_hosts_triaje"
D1 = next(c for c in casos.CASOS if c["id"] == "D1")
TELNET = next(c for c in casos.CASOS if c["id"] == "TELNET")
INTERRUPTORES = ["TRIAJE_FALLO_RAPIDO", "TRIAJE_PRECHECK_APROVISIONADO", "TRIAJE_ESCALADA_SOLO_APROVISIONADOS",
                 "TRIAJE_MEMORIA_FALLOS", "TRIAJE_ACCION_NO_EJECUTABLE"]
# la contramedida de lab.banco.fallos borra reglas de 192.0.2.0/24; el atacante del banco usa 198.51.100.0/24
CONTRAMEDIDA = ("nohup sh -c 'while true; do for r in $(iptables -S INPUT | grep -o \"198\\.51\\.100\\.[0-9]*\"); do "
                "iptables -D INPUT -s $r -j DROP 2>/dev/null; done; sleep 0.1; done' >/dev/null 2>&1 & echo $! > /tmp/mdr-contramedida.pid",
                "kill $(cat /tmp/mdr-contramedida.pid) 2>/dev/null; rm -f /tmp/mdr-contramedida.pid")


def sh(cmd, timeout=60):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=RAIZ)


def dexec(nodo, cmd, timeout=60):
    return subprocess.run(["docker", "exec", nodo, "sh", "-c", cmd], capture_output=True, text=True, timeout=timeout)


def fallo(caso, deshacer=False, equipo=EQUIPO):
    if caso == "contramedida":
        return dexec(f"clab-banco-{equipo}", CONTRAMEDIDA[1 if deshacer else 0], 30)
    return sh(f"python3 -m lab.banco.fallos {'deshacer' if deshacer else 'provocar'} {caso} {equipo}")


def quitar_huella(ip):
    dexec(NODO_GESTION, f"cp -p {KNOWN} {KNOWN}.val && ssh-keygen -R {ip} -f {KNOWN} >/dev/null 2>&1")


def reponer_huellas():
    dexec(NODO_GESTION, f"test -f {KNOWN}.val && mv {KNOWN}.val {KNOWN}; rm -f {KNOWN}.old; true")


def vigilar_memoria(ruta, parar):
    with open(ruta, "a") as f:
        while not parar.is_set():
            mem = dict(l.split(":", 1) for l in open("/proc/meminfo").read().splitlines())
            f.write(f"{time.strftime('%H:%M:%S')} disponible_MB={int(mem['MemAvailable'].split()[0]) // 1024}\n")
            f.flush()
            parar.wait(10)


def arrancar(modo, dir_):
    env = dict(os.environ, PYTHONUNBUFFERED="1", TRIAJE_NODO_GESTION=NODO_GESTION,
               TRIAJE_SALUD_CONTENEDOR=f"{NODO_GESTION}:/var/log/banco/salud.jsonl",
               TRIAJE_CONECTIVIDAD_ABIERTA="1")          # opt-in de laboratorio: «Probar» sin mapa de operadores
    for v in INTERRUPTORES:      # explícito en los dos modos: sin variable, los validados van encendidos
        env[v] = "1" if modo == "encendidos" else "0"
    traza = os.path.join(dir_, f"trazas-{modo}.jsonl")
    log = open(os.path.join(dir_, f"daemon-{modo}.log"), "w")
    cmd = ("docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' | "
           f"python3 -m prototipo.servicio.stream - prototipo/perfiles/bancario.yml "
           f"lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --salida {traza} --web {PUERTO}")
    p = subprocess.Popen(cmd, shell=True, cwd=RAIZ, env=env, stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}/healthz", timeout=2)
            return p, traza
        except Exception:
            time.sleep(1)
    raise SystemExit("el daemon de validación no arrancó")


def parar(p):
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    time.sleep(2)


def probar(equipo):
    datos = json.dumps({"equipo": equipo, "operador": "validacion"}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{PUERTO}/api/conectividad/probar", data=datos,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def resumir(r):
    ej, esc = r.get("ejecucion") or {}, r.get("escalada") or {}
    causa = r.get("causa_fallo")
    return {"accion": r.get("accion_final"), "exito_activo": ej.get("exito"), "rc": ej.get("codigo_salida"),
            "omitido": ej.get("omitido"), "causa": causa.get("clase") if isinstance(causa, dict) else causa,
            "escalada": esc.get("resultado"), "contenido_en": esc.get("dispositivo_ejecutor"),
            "pasos": [f"{p.get('dispositivo')}: {p.get('estado') or (p.get('observacion') or '')[:50]}"
                      for p in esc.get("pasos") or []]}


def esperar(traza, ip, t0, accion=None, plazo=420):
    while time.time() - t0 < plazo:
        if os.path.exists(traza):
            for linea in open(traza):
                if ip not in linea:
                    continue
                r = json.loads(linea)
                if r.get("id_decision") and "ejecucion" in r and (accion is None or r.get("accion_final") == accion):
                    return round(time.time() - t0, 1), resumir(r)
        time.sleep(1)
    return None, {"error": "sin decisión en el plazo"}


def atacar(n, traza, caso=None, accion=None):
    caso = caso or D1
    ip = demo.ip_rotada(caso["origen"], n)
    # con la clave del host cambiada, OpenSSH desactiva la contraseña y la fuerza bruta no deja rastro
    dexec("clab-banco-internet", "ssh-keygen -R 10.10.0.10 >/dev/null 2>&1; true")
    t0 = time.time()
    if accion == "MATAR_CONEXION":
        demo.ataque_acceso_consumado(src_ip=ip)
    else:
        demo.lanzar(caso, src_ip=ip)
    return (ip, *esperar(traza, ip, t0, accion))


# (nombre, caso de fallo, veces, equipo del fallo, caso de ataque, acción esperada, preparar, deshacer)
PARTE_A = [
    ("Sin fallo", None, 1, EQUIPO, None, None),
    ("F5 — el equipo descarta el SSH del MDR (E1)", "e1", 1, EQUIPO, None, None),
    ("F5 — sshd parado (atm, telnet)", "sshd", 1, "atm", TELNET, None),
    ("F4 — clave del conector borrada", "sin-clave", 1, EQUIPO, None, None),
    ("F3 — clave del host regenerada", "clave-host", 1, EQUIPO, None, None),
    ("F8 — contramedida", "contramedida", 1, EQUIPO, None, None),
    ("F5 cuatro veces seguidas (memoria)", "e1", 4, EQUIPO, None, None),
]


def parte_a(traza, modo, dir_, n, solo):
    filas = []
    for nombre, caso, veces, equipo, ataque, accion in PARTE_A:
        if solo and (caso or "base") not in solo:
            continue
        if caso:
            fallo(caso, equipo=equipo)
            time.sleep(2)
        for k in range(veces):
            n += 1
            ip, t, res = atacar(n, traza, ataque, accion)
            filas.append({"modo": modo, "caso": nombre, "intento": k + 1, "ip": ip, "segundos": t, **res})
            print(json.dumps(filas[-1], ensure_ascii=False), flush=True)
        if caso:
            fallo(caso, deshacer=True, equipo=equipo)
            if caso == "e1" and veces > 1:
                time.sleep(75)
                texto = open(os.path.join(dir_, f"daemon-{modo}.log")).read()
                filas.append({"modo": modo, "caso": "memoria: se cierra sola tras deshacer (75 s)",
                              "recupera": "recupera el acceso" in texto, "abre": "no tiene acceso a" in texto})
                print(json.dumps(filas[-1], ensure_ascii=False), flush=True)
        time.sleep(5)
    return filas, n


def parte_b(traza, modo, n, solo=frozenset()):
    pr = probar(EQUIPO)
    filas = [{"modo": modo, "caso": f"Prueba de Conectividad de {EQUIPO}", "estado": pr.get("estado"),
              "faltan": (pr.get("reglas") or {}).get("faltan")}]
    print(json.dumps(filas[-1], ensure_ascii=False), flush=True)
    plan = [
        ("F2 — web-banking sin huella fijada (PRECHECK)", lambda: quitar_huella("10.10.0.10"), reponer_huellas, None),
        ("E1 + fw-core sin huella fijada (ESCALADA_SOLO)", lambda: (quitar_huella("10.0.0.1"), fallo("e1")),
         lambda: (fallo("e1", deshacer=True), reponer_huellas()), None),
        # La regla 5763 de Wazuh (fuerza bruta) calla 60 s tras dispararse, y sin ella la correlación
        # 40112 -> 100600 (intrusión) no salta: el acceso consumado necesita ese silencio antes.
        ("F6 — cortar conexión sin ss (ACCION_NO_EJECUTABLE)", lambda: time.sleep(70), lambda: None, "MATAR_CONEXION"),
    ]
    claves = {"F2": "precheck", "E1": "escalada", "F6": "no-ejecutable"}
    if solo:
        plan = [x for x in plan if claves[x[0].split()[0]] in solo]
    try:
        for nombre, preparar, deshacer, accion in plan:
            preparar()
            time.sleep(2)
            n += 1
            ip, t, res = atacar(n, traza, None, accion)
            filas.append({"modo": modo, "caso": nombre, "ip": ip, "segundos": t, **res})
            print(json.dumps(filas[-1], ensure_ascii=False), flush=True)
            deshacer()
            time.sleep(5)
    finally:
        reponer_huellas()
    return filas, n


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--parte", default="ab", choices=["a", "b", "ab"])
    a.add_argument("--solo", default="", help="casos: A (base,e1,sshd,sin-clave,clave-host,contramedida); "
                                              "B (precheck,escalada,no-ejecutable)")
    a.add_argument("--salida", default=os.path.join(RAIZ, "evaluacion", "resultados", f"validacion-recortes-{date.today()}"))
    o = a.parse_args(argv)
    os.makedirs(o.salida, exist_ok=True)
    solo = set(filter(None, o.solo.split(",")))
    parar_mem = threading.Event()
    threading.Thread(target=vigilar_memoria, args=(os.path.join(o.salida, "memoria.log"), parar_mem), daemon=True).start()
    n = 150 + int(time.time()) % 80          # IPs de origen nuevas en cada ejecución
    resultados = []
    try:
        for modo in ("apagados", "encendidos"):
            p, traza = arrancar(modo, o.salida)
            try:
                if "a" in o.parte:
                    filas, n = parte_a(traza, modo, o.salida, n, solo)
                    resultados += filas
                if "b" in o.parte:
                    filas, n = parte_b(traza, modo, n, solo)
                    resultados += filas
            finally:
                parar(p)
    finally:
        parar_mem.set()
        sufijo = o.parte + ("-" + "_".join(sorted(solo)) if solo else "")
        with open(os.path.join(o.salida, f"resultados-parte-{sufijo}.json"), "w") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
