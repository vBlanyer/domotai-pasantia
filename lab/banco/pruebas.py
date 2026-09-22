"""Prueba de regresion del laboratorio del banco: los cinco casos de la guia manual
(docs/pruebas/08-laboratorio-banco.md), ejecutados solos contra la red real.

    python3 -m lab.banco.pruebas              (los cinco casos, ~10 min)
    python3 -m lab.banco.pruebas --caso K1    (uno solo)

Para cada caso: comprueba el estado base (servicios sanos, cortafuegos sin reglas anadidas), prepara,
ataca desde un nodo del laboratorio, deja decidir al prototipo REAL (el mismo stream.ejecutar del
daemon, con el perfil bancario, el conector real desde mdr-siem y un lector que contesta al menu
como lo haria el analista), comprueba la decision en la traza, las reglas aplicadas y la salud que
mide el monitor, y deshace. El informe queda en lab/campañas/<fecha>-banco-regresion/.

K1 se comprueba tal como es HOY (fallo conocido: la prediccion de cascada esta vacia y caen cuatro
servicios). Si algun dia se corrige, este caso fallara y habra que actualizar lo esperado.

Entre ataques espera mas de 60 s: la regla 5763 de Wazuh tiene ignore="60" (verificaciones.md, V2).
"""
import argparse
import datetime
import json
import os
import select
import subprocess
import sys
import time

from lab.banco import casos, red

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = "clab-banco"
WAZUH = "clab-red-cliente-wazuh"
ALERTAS = "/var/ossec/logs/alerts/alerts.json"
PERFIL = os.path.join(RAIZ, "prototipo", "perfiles", "bancario.yml")
HALLAZGOS = os.path.join(RAIZ, "lab", "campañas", "2026-09-22-banco-hallazgos", "hallazgos.json")
NODOS_CON_REGLAS = ["web-banking", "api-movil", "swift-alliance", "middleware", "core-db", "hsm",
                    "atm", "taquilla", "fw-core", "fw-edge", "mdr-siem", "auditor"]
ESPERA_WAZUH = 65          # > ignore="60" de la regla 5763
PLAZO_DECISION = 150       # s desde que empieza el ataque hasta que debe haber decision
TODOS = set(red.SERVICIOS)


# ------------------------------------------------------------------ funciones puras --

def reglas_extra(salida_iptables_s):
    """Reglas anadidas sobre el estado base: sin politicas (-P) ni el aislamiento de eth0."""
    return [l.strip() for l in salida_iptables_s.splitlines()
            if l.strip() and not l.startswith("-P ") and "-i eth0" not in l]


def caidos(muestra):
    if muestra is None:
        return None
    return {n for n, e in muestra["estados"].items() if e != "ok"}


class Lector:
    """Contesta como el analista: el menu numerado de la validacion ('Elige [1-N]') y la aprobacion
    de la escalada ('[s/N]') por separado. Anota cada pregunta. Una pregunta sin respuesta prevista
    se contesta vacio, que el sistema lee como rechazo (lo seguro)."""
    def __init__(self, menu=None, escalada=None):
        self.menu, self.escalada, self.preguntas = menu, escalada, []

    def __call__(self, prompt=""):
        tipo = "escalada" if "[s/N]" in prompt else "menu"
        resp = (self.escalada if tipo == "escalada" else self.menu) or ""
        self.preguntas.append((tipo, resp))
        return resp


def fuente_filtrada(lineas, ip, parar):
    """Las lineas de alerts.json del atacante `ip` (y los ticks None), hasta que `parar()`."""
    patron = f'"srcip":"{ip}"'
    for linea in lineas:
        if parar():
            return
        if linea is None or patron in linea:
            yield linea


def evaluar(esperado, registro, reglas, caidos_obs, preguntas):
    """Diferencias entre lo esperado y lo observado ([] = el caso pasa)."""
    fallos = []
    if registro is not None or any(k in esperado for k in ("requiere_humano", "accion_final", "veredicto",
                                                            "escalado", "dispositivo_ejecutor",
                                                            "prediccion_cascada")):
        if registro is None:
            return ["el prototipo no produjo ninguna decision (sin alerta de Wazuh o sin incidente)"]
        esc = registro.get("escalada") or {}
        obs = {"requiere_humano": registro.get("requiere_humano"),
               "accion_final": registro.get("accion_final"),
               "veredicto": registro.get("veredicto_humano"),
               "escalado": esc.get("escalado"),
               "dispositivo_ejecutor": esc.get("dispositivo_ejecutor"),
               "prediccion_cascada": (registro.get("impacto_determinado") or {}).get("activos_afectados_en_cascada")}
        for k in obs:
            if k in esperado and obs[k] != esperado[k]:
                fallos.append(f"{k}: esperado {esperado[k]!r}, obtenido {obs[k]!r}")
    if "preguntas" in esperado and len(preguntas) != esperado["preguntas"]:
        fallos.append(f"preguntas al analista: esperadas {esperado['preguntas']}, hechas {len(preguntas)} {preguntas}")
    if "regla" in esperado:
        nodo, frag = esperado["regla"]
        if frag not in (reglas.get(nodo) or []):
            fallos.append(f"regla ausente en {nodo}: {frag!r} (hay: {reglas.get(nodo)})")
    if esperado.get("sin_reglas"):
        sobran = {n: r for n, r in reglas.items() if r}
        if sobran:
            fallos.append(f"se aplicaron reglas que no debian: {sobran}")
    if "caen" in esperado:
        if caidos_obs is None:
            fallos.append("sin datos del monitor de salud")
        elif caidos_obs != esperado["caen"]:
            fallos.append(f"servicios caidos: esperados {sorted(esperado['caen'])}, observados {sorted(caidos_obs)}")
    return fallos


# ------------------------------------------------------------------ E/S con el laboratorio --

def _exec(nodo, cmd, contenedor=None):
    r = subprocess.run(["docker", "exec", contenedor or f"{P}-{nodo}", "sh", "-c", cmd],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def leer_salud():
    rc, out = _exec("mdr-siem", "tail -n1 /var/log/banco/salud.jsonl")
    try:
        return json.loads(out.strip().splitlines()[-1]) if rc == 0 and out.strip() else None
    except (json.JSONDecodeError, IndexError):
        return None


def leer_reglas(nodos=NODOS_CON_REGLAS):
    return {n: reglas_extra(_exec(n, "iptables -S")[1]) for n in nodos}


def esperar_salud(caen, plazo=40):
    """Consulta el monitor hasta que los caidos coinciden con `caen` o vence el plazo; devuelve lo ultimo visto."""
    fin, visto = time.time() + plazo, None
    while time.time() < fin:
        visto = caidos(leer_salud())
        if visto == caen:
            return visto
        time.sleep(2)
    return visto


def estado_base():
    """[] si el laboratorio esta limpio; si no, lo que sobra o falla."""
    problemas = []
    c = esperar_salud(set(), plazo=20)
    if c is None:
        problemas.append("sin datos del monitor de salud (¿banco levantado?)")
    elif c:
        problemas.append(f"servicios caidos antes de empezar: {sorted(c)}")
    sobran = {n: r for n, r in leer_reglas().items() if r}
    if sobran:
        problemas.append(f"reglas anadidas antes de empezar: {sobran}")
    return problemas


def _lineas_wazuh(proc):
    """Lineas nuevas de alerts.json; None cada 0,5 s sin datos (para vencer la ventana de agrupacion)."""
    while True:
        listo, _, _ = select.select([proc.stdout], [], [], 0.5)
        if not listo:
            yield None
            continue
        linea = proc.stdout.readline()
        if not linea:
            return
        yield linea


def decidir(caso, ruta_traza, ejecutor, perfil, hallazgos, catalogo, escribir):
    """Lanza el ataque y deja decidir al prototipo; devuelve (primer registro de la traza o None, lector)."""
    from prototipo import stream
    lector = Lector(menu=caso.get("menu"), escalada=caso.get("escalada"))
    tail = subprocess.Popen(["docker", "exec", WAZUH, "tail", "-n0", "-F", ALERTAS],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        time.sleep(1)
        origen, cmd = caso["ataque"]
        _exec(origen, cmd)
        fin = time.time() + PLAZO_DECISION
        def parar():
            return time.time() > fin or (os.path.exists(ruta_traza) and os.path.getsize(ruta_traza) > 0)
        with open(ruta_traza, "a", encoding="utf-8") as f:
            stream.ejecutar(fuente_filtrada(_lineas_wazuh(tail), caso["origen"], parar), hallazgos, perfil,
                            "bancario", catalogo, ejecutor, ventana_agrupacion=15, salida_traza=f,
                            escribir=escribir, leer=lector)
    finally:
        tail.terminate()
        tail.wait(timeout=5)
    with open(ruta_traza, encoding="utf-8") as f:
        primera = f.readline()
    return (json.loads(primera) if primera.strip() else None), lector


def deshacer(caso):
    for nodo, cmd in caso["deshacer"]:
        if cmd == "REARRANCAR":
            subprocess.run(["docker", "exec", "-d", f"{P}-{nodo}", "sh", "-c", red.comando_servicio(nodo)])
        else:
            _exec(nodo, cmd)


def correr_caso(caso, dir_salida, ejecutor, perfil, hallazgos, catalogo, escribir=print):
    t0 = time.time()
    res = {"id": caso["id"], "titulo": caso["titulo"]}
    problemas = estado_base()
    if problemas:
        return {**res, "resultado": "BLOQUEADO", "detalle": problemas, "segundos": round(time.time() - t0)}
    try:
        for nodo, cmd in caso.get("preparar", []):
            _exec(nodo, cmd)
        registro, preguntas = None, []
        if "ataque" in caso:
            registro, lector = decidir(caso, os.path.join(dir_salida, f"traza-{caso['id']}.jsonl"),
                                       ejecutor, perfil, hallazgos, catalogo, escribir)
            preguntas = lector.preguntas
        caen = caso["esperado"].get("caen", set())
        c = esperar_salud(caen, plazo=40 if caen else 10)
        reglas = leer_reglas()
        fallos = evaluar(caso["esperado"], registro, reglas, c, preguntas)
    finally:
        deshacer(caso)
    restaurado = estado_base()
    if restaurado:
        fallos = fallos + [f"no se pudo restaurar el estado base: {restaurado}"]
    return {**res, "resultado": "FALLO" if fallos else "OK", "detalle": fallos,
            "segundos": round(time.time() - t0)}


def informe(resultados, cuando):
    ok = sum(1 for r in resultados if r["resultado"] == "OK")
    lineas = [f"# Regresión del laboratorio del banco — {cuando}", "",
              f"**{ok} de {len(resultados)} casos OK.** Guía de los casos: `docs/pruebas/08-laboratorio-banco.md`.", "",
              "| Caso | Resultado | Tiempo | Qué se comprobó / qué falló |", "|---|---|---|---|"]
    for r in resultados:
        detalle = "; ".join(r["detalle"]) if r["detalle"] else r["titulo"]
        lineas.append(f"| {r['id']} | {r['resultado']} | {r['segundos']} s | {detalle} |")
    lineas += ["", "K1 comprueba el comportamiento de HOY, que es un fallo conocido del prototipo: la "
               "predicción de cascada está vacía y caen cuatro servicios. Si se corrige, K1 fallará aquí "
               "y habrá que actualizar lo esperado en `lab/banco/casos.py`."]
    return "\n".join(lineas) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Regresion del laboratorio del banco (5 casos de la guia manual)")
    ap.add_argument("--caso", choices=[c["id"] for c in casos.CASOS])
    a = ap.parse_args(argv)
    os.environ["TRIAJE_NODO_GESTION"] = f"{P}-mdr-siem"
    from prototipo import conector, perfil as perfilm, catalogo as catm
    perfil = perfilm.cargar(PERFIL)
    catalogo = catm.cargar_catalogo(os.path.join(RAIZ, "prototipo", "catalogo.yml"))
    with open(HALLAZGOS, encoding="utf-8") as f:
        hallazgos = json.load(f)
    ejecutor = conector.ejecutor_por_defecto()
    cuando = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    dir_salida = os.path.join(RAIZ, "lab", "campañas", f"{datetime.date.today().isoformat()}-banco-regresion")
    os.makedirs(dir_salida, exist_ok=True)
    for f in os.listdir(dir_salida):
        if f.startswith("traza-"):
            os.remove(os.path.join(dir_salida, f))
    casos_a_correr = [c for c in casos.CASOS if a.caso in (None, c["id"])]
    resultados, ultimo_ataque = [], 0.0
    for caso in casos_a_correr:
        if "ataque" in caso:
            espera = ESPERA_WAZUH - (time.time() - ultimo_ataque)
            if ultimo_ataque and espera > 0:
                print(f"   (esperando {int(espera)} s: la regla 5763 de Wazuh se silencia 60 s tras dispararse)")
                time.sleep(espera)
        print(f"== {caso['id']}: {caso['titulo']}")
        r = correr_caso(caso, dir_salida, ejecutor, perfil, hallazgos, catalogo,
                        escribir=lambda s: print("   | " + s.replace("\n", "\n   | ")))
        if "ataque" in caso:
            ultimo_ataque = time.time()
        print(f"   -> {r['resultado']} ({r['segundos']} s)" + "".join(f"\n      - {d}" for d in r["detalle"]))
        resultados.append(r)
    with open(os.path.join(dir_salida, "resultados.json"), "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    texto = informe(resultados, cuando)
    with open(os.path.join(dir_salida, "informe.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print("\n" + texto + f"\n-> {dir_salida}")
    return 0 if all(r["resultado"] == "OK" for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
