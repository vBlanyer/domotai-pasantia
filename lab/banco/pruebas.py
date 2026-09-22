"""Banco de pruebas del laboratorio del banco: casos de niveles decision/inyectada/perfil (sin
laboratorio, segundos) y vivo (los cinco de la guia manual docs/pruebas/08-laboratorio-banco.md,
ataques reales contra la red).

    python3 -m lab.banco.pruebas                 (decision+inyectada+perfil; los vivos OMITIDO)
    python3 -m lab.banco.pruebas --con-vivo       (todos los niveles, requiere el banco levantado, ~10 min)
    python3 -m lab.banco.pruebas --caso K1        (uno solo; si es vivo, fuerza --con-vivo)

Para cada caso vivo: comprueba el estado base (servicios sanos, cortafuegos sin reglas anadidas),
prepara, ataca desde un nodo del laboratorio, deja decidir al prototipo REAL (el mismo stream.ejecutar
del daemon, con el perfil bancario, el conector real desde mdr-siem y un lector que contesta al menu
como lo haria el analista), comprueba la decision en la traza, las reglas aplicadas y la salud que
mide el monitor, y deshace. Los de decision/inyectada/perfil llaman directamente al motor con el
perfil bancario, sin laboratorio. El informe queda en lab/campañas/<fecha>-banco-regresion/.

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


class LectorContador:
    """Envuelve un lector real (`input`, o el `_leer_interactivo` de stream que lee de /dev/tty) y
    anota cada pregunta igual que `Lector` (mismo formato `(tipo, respuesta)`), para que `evaluar`
    pueda comparar `preguntas` tambien en el camino interactivo de `--paso-a-paso` (el lector real no
    trae `.preguntas` por si solo: es una funcion corriente, no un objeto que las cuente)."""
    def __init__(self, leer):
        self.leer, self.preguntas = leer, []

    def __call__(self, prompt=""):
        tipo = "escalada" if "[s/N]" in prompt else "menu"
        resp = self.leer(prompt)
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


def veredicto_caso(esperado, fallos):
    """Traduce los fallos crudos al resultado del caso, contemplando `fallo_esperado`."""
    motivo = esperado.get("fallo_esperado")
    if motivo:
        if fallos:
            return "OK", [f"fallo conocido reproducido: {motivo}"]
        return "FALLO", [f"el fallo esperado ya no ocurre ({motivo}): el prototipo pudo haberse corregido"]
    return ("FALLO" if fallos else "OK"), fallos


def _requisito_ok(requisito):
    """Hoy solo se conoce 'modelo' (el servidor LLM del justificador/agente), que el banco no usa."""
    return False   # ningun requisito se da por satisfecho: los casos que lo declaran se omiten


def _json_seguro(obj):
    """default= de json.dumps: los `esperado` traen sets (p. ej. `caen`), que json no serializa de
    forma nativa (las tuplas, como `regla`, sí las serializa json.dumps por su cuenta, como listas)."""
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    return str(obj)


def guia_markdown(caso):
    """Guia manual de un caso, en markdown: preparar/atacar (o la alerta inyectada), lo esperado y
    como deshacer. Tolera casos sin `preparar`/`ataque`/`alerta`/`deshacer` (niveles decision/inyectada/
    perfil no los tienen)."""
    l = [f"# {caso['id']} · {caso['titulo']}", "", f"- nivel: {caso['nivel']}"]
    if caso.get("preparar"):
        l += ["", "## Preparar", "```bash"] + [f"docker exec clab-banco-{n} sh -c {cmd!r}" for n, cmd in caso["preparar"]] + ["```"]
    if caso.get("ataque"):
        origen, cmd = caso["ataque"]
        l += ["", f"## Atacar (desde {origen})", "```bash", f"docker exec clab-banco-{origen} sh -c {cmd!r}", "```"]
    if caso.get("alerta"):
        l += ["", "## Alerta (nivel decision)", "```json",
              json.dumps(caso["alerta"], ensure_ascii=False, default=_json_seguro), "```"]
    l += ["", "## Esperado", "```json",
          json.dumps(caso["esperado"], ensure_ascii=False, indent=1, default=_json_seguro), "```"]
    if caso.get("deshacer"):
        l += ["", "## Deshacer", "```bash"] + [f"docker exec clab-banco-{n} {cmd}" for n, cmd in caso["deshacer"]] + ["```"]
    return "\n".join(l) + "\n"


def generar_guias(destino):
    """Escribe una guia markdown por caso del catalogo en `destino`; devuelve cuantas escribio."""
    os.makedirs(destino, exist_ok=True)
    for caso in casos.CASOS:
        with open(os.path.join(destino, f"{caso['id']}.md"), "w", encoding="utf-8") as f:
            f.write(guia_markdown(caso))
    return len(casos.CASOS)


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


def decidir(caso, ruta_traza, ejecutor, perfil, hallazgos, catalogo, escribir, leer=None):
    """Lanza el ataque y deja decidir al prototipo; devuelve (primer registro de la traza o None, lector).

    `leer` permite sustituir el `Lector` guionizado (usado en las corridas automaticas) por un lector
    interactivo real (p. ej. `stream._leer_interactivo()`, usado por `--paso-a-paso`)."""
    from prototipo import stream
    lector = leer if leer is not None else Lector(menu=caso.get("menu"), escalada=caso.get("escalada"))
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


def _comparar_decision(esperado, traza):
    """Diferencias entre lo esperado y la traza de triaje.procesar (para nivel decision)."""
    from prototipo import validacion
    obs = {"clase": traza.get("clase"), "confianza": traza.get("confianza"),
           "accion_final": traza.get("accion_final"), "requiere_humano": traza.get("requiere_humano"),
           "filtro": validacion.filtro_legible(traza),
           "prediccion_cascada": (traza.get("impacto_determinado") or {}).get("activos_afectados_en_cascada")}
    return [f"{k}: esperado {esperado[k]!r}, obtenido {obs[k]!r}"
            for k in obs if k in esperado and obs[k] != esperado[k]]


def correr_decision(caso, perfil, hallazgos, catalogo):
    import time
    from prototipo import triaje, rafaga
    t0 = time.time()
    a = dict(caso["alerta"]); a.setdefault("timestamp", "2026-09-22T00:00:00Z"); a.setdefault("mitre", [])
    a.setdefault("id_alerta", caso["id"])
    if "rafaga_60s" in caso:
        a[rafaga.CAMPO] = caso["rafaga_60s"]
    traza = triaje.procesar(a, hallazgos, perfil, "bancario", catalogo, id_decision=caso["id"],
                            timestamp=a["timestamp"])
    fallos = _comparar_decision(caso["esperado"], traza)
    resultado, detalle = veredicto_caso(caso["esperado"], fallos)
    return {"id": caso["id"], "titulo": caso["titulo"], "resultado": resultado, "detalle": detalle,
            "segundos": round(time.time() - t0, 2)}


def correr_inyectada(caso, perfil, catalogo):
    """Filtra una acción inyectada directamente (sin ataque real): permite/degrada/veta, con quién
    ejecuta al final, si queda retenida y la predicción de cascada (nivel `inyectada`)."""
    import time
    from prototipo import perfil as perfilm
    t0 = time.time()
    filtro = perfilm.filtrar(perfil, caso["accion"], caso.get("params", {}), catalogo,
                             caso["activo"], caso.get("servicio"), caso.get("confianza", 1.0))
    esp = caso["esperado"]
    obs = {"filtro_resultado": filtro["resultado"], "accion_final": filtro["accion_final"],
           "requiere_humano": filtro["requiere_humano"],
           "prediccion_cascada": (filtro.get("impacto") or {}).get("activos_afectados_en_cascada")}
    fallos = [f"{k}: esperado {esp[k]!r}, obtenido {obs[k]!r}" for k in obs if k in esp and obs[k] != esp[k]]
    resultado, detalle = veredicto_caso(esp, fallos)
    return {"id": caso["id"], "titulo": caso["titulo"], "resultado": resultado, "detalle": detalle,
            "segundos": round(time.time() - t0, 2)}


def correr_perfil(caso, perfil, catalogo):
    """Variaciones de perfil/catálogo comprobadas sin laboratorio (nivel `perfil`): que una acción
    sin reversión definida se vete (RF-18) y que la cascada del inventario termine aunque haya
    dependencias (guardia de ciclos de `impacto.afectados_en_cascada`)."""
    import time
    from prototipo import perfil as perfilm, impacto
    t0 = time.time()
    esp, fallos = caso["esperado"], []
    if caso["comprobacion"] == "sin_reversion":
        filtro = perfilm.filtrar(perfil, caso["accion"], caso.get("params", {}), catalogo,
                                 caso["activo"], caso.get("servicio"), 1.0)
        if "filtro_resultado" in esp and filtro["resultado"] != esp["filtro_resultado"]:
            fallos.append(f"filtro_resultado: esperado {esp['filtro_resultado']!r}, obtenido {filtro['resultado']!r}")
    elif caso["comprobacion"] == "ciclo_depende_de":
        perfil_usado = caso.get("perfil_sintetico", perfil)
        try:
            impacto.afectados_en_cascada(caso["activo"], perfil_usado)   # no debe colgarse (guardia de ciclos)
            termino = True
        except RecursionError:
            termino = False
        if esp.get("termina") and not termino:
            fallos.append("afectados_en_cascada no terminó (posible ciclo sin guardia)")
    resultado, detalle = veredicto_caso(esp, fallos)
    return {"id": caso["id"], "titulo": caso["titulo"], "resultado": resultado, "detalle": detalle,
            "segundos": round(time.time() - t0, 2)}


def correr_caso(caso, dir_salida, ejecutor, perfil, hallazgos, catalogo, escribir=print):
    t0 = time.time()
    res = {"id": caso["id"], "titulo": caso["titulo"]}
    falta = caso.get("requiere")
    if falta and not _requisito_ok(falta):
        return {**res, "resultado": "OMITIDO", "detalle": [f"requiere {falta}"], "segundos": 0}
    if caso["nivel"] == "decision":
        return correr_decision(caso, perfil, hallazgos, catalogo)
    if caso["nivel"] == "inyectada":
        return correr_inyectada(caso, perfil, catalogo)
    if caso["nivel"] == "perfil":
        return correr_perfil(caso, perfil, catalogo)
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
    resultado, detalle = veredicto_caso(caso["esperado"], fallos)
    return {**res, "resultado": resultado, "detalle": detalle, "segundos": round(time.time() - t0)}


def _pausar(fase):
    print(f"\n== {fase} ==")
    input("   (Enter para continuar) ")


def paso_a_paso(caso, dir_salida, ejecutor, perfil, hallazgos, catalogo):
    """Corre un caso solo, deteniendose entre fases para que el analista confirme antes de seguir.
    Para los casos `vivo`, el menu real de la validacion (y la aprobacion de la escalada, si toca) lo
    contesta el analista de verdad por /dev/tty (`stream._leer_interactivo`), no un `Lector` guionizado.
    Los niveles sin laboratorio (decision/inyectada/perfil) no tienen fases de laboratorio que recorrer:
    se corren directamente."""
    res = {"id": caso["id"], "titulo": caso["titulo"]}
    if caso["nivel"] != "vivo":
        r = correr_caso(caso, dir_salida, ejecutor, perfil, hallazgos, catalogo)
        print(f"-> {r['resultado']}" + "".join(f"\n   - {d}" for d in r["detalle"]))
        return r
    from prototipo import stream
    _pausar("estado base")
    problemas = estado_base()
    if problemas:
        print(f"   BLOQUEADO: {problemas}")
        return {**res, "resultado": "BLOQUEADO", "detalle": problemas, "segundos": 0}
    fallos = []
    try:
        if caso.get("preparar"):
            _pausar("preparar")
            for nodo, cmd in caso["preparar"]:
                _exec(nodo, cmd)
        registro, preguntas = None, []
        if caso.get("ataque"):
            _pausar(f"atacar (desde {caso['ataque'][0]})")
            # Un solo `decidir()`: lanza el ataque Y espera la decision (no hay una pausa real entre
            # ambas cosas); esta segunda etiqueta solo marca que, a partir de aqui, el prototipo ya
            # esta corriendo y puede aparecer el menu real que el analista debe contestar.
            _pausar("esperando decision (conteste el menu real en esta misma terminal)")
            lector = LectorContador(stream._leer_interactivo())
            registro, lector = decidir(caso, os.path.join(dir_salida, f"traza-{caso['id']}.jsonl"),
                                       ejecutor, perfil, hallazgos, catalogo, print, leer=lector)
            preguntas = lector.preguntas
        _pausar("verificar")
        caen = caso["esperado"].get("caen", set())
        c = esperar_salud(caen, plazo=40 if caen else 10)
        reglas = leer_reglas()
        fallos = evaluar(caso["esperado"], registro, reglas, c, preguntas)
    finally:
        _pausar("deshacer")
        deshacer(caso)
    resultado, detalle = veredicto_caso(caso["esperado"], fallos)
    print(f"-> {resultado}" + "".join(f"\n   - {d}" for d in detalle))
    return {**res, "resultado": resultado, "detalle": detalle}


def informe(resultados, cuando):
    from collections import Counter
    por_res = Counter(r["resultado"] for r in resultados)
    orden = ["OK", "FALLO", "BLOQUEADO", "OMITIDO"]
    cab = " · ".join(f"{por_res.get(k, 0)} {k}" for k in orden if por_res.get(k))
    lineas = [f"# Banco de pruebas del laboratorio del banco — {cuando}", "",
              f"**{cab}** de {len(resultados)} casos. Catálogo: `docs/superpowers/specs/2026-09-21-laboratorio-banco-design.md` §4.", "",
              "| Caso | Nivel | Resultado | Tiempo | Qué se comprobó / qué falló |", "|---|---|---|---|---|"]
    for r in resultados:
        detalle = "; ".join(r["detalle"]) if r["detalle"] else r["titulo"]
        lineas.append(f"| {r['id']} | {r.get('nivel','')} | {r['resultado']} | {r['segundos']} s | {detalle} |")
    lineas += ["", "**Notas:** K1 y C4 declaran `fallo_esperado` (fallos conocidos del prototipo): cuentan "
               "OK mientras el fallo persista. Los casos que requieren el modelo LLM (E6) salen OMITIDO: el "
               "banco corre con la plantilla determinista."]
    return "\n".join(lineas) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Banco de pruebas del laboratorio del banco")
    ap.add_argument("--caso", choices=[c["id"] for c in casos.CASOS])
    ap.add_argument("--con-vivo", action="store_true",
                    help="corre tambien los casos de nivel vivo (requiere el laboratorio levantado)")
    ap.add_argument("--guias", action="store_true",
                    help="genera una guia markdown por caso en docs/pruebas/banco/ y termina")
    ap.add_argument("--paso-a-paso", action="store_true",
                    help="corre --caso solo, deteniendose entre fases (requiere --caso)")
    a = ap.parse_args(argv)
    if a.guias:
        n = generar_guias(os.path.join(RAIZ, "docs", "pruebas", "banco"))
        print(f"{n} guías -> docs/pruebas/banco/")
        return 0
    if a.paso_a_paso and a.caso is None:
        ap.error("--paso-a-paso requiere --caso")
    con_vivo = a.con_vivo
    if a.caso is not None:
        elegido = next(c for c in casos.CASOS if c["id"] == a.caso)
        if elegido["nivel"] == "vivo":
            con_vivo = True
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
    if a.paso_a_paso:
        r = paso_a_paso(elegido, dir_salida, ejecutor, perfil, hallazgos, catalogo)
        return 0 if r["resultado"] not in ("FALLO", "BLOQUEADO") else 1
    casos_a_correr = [c for c in casos.CASOS if a.caso in (None, c["id"])]
    resultados, ultimo_ataque = [], 0.0
    for caso in casos_a_correr:
        if caso["nivel"] == "vivo" and not con_vivo:
            resultados.append({"id": caso["id"], "titulo": caso["titulo"], "nivel": "vivo",
                               "resultado": "OMITIDO", "detalle": ["nivel vivo: usa --con-vivo con el banco levantado"],
                               "segundos": 0})
            continue
        if caso["nivel"] == "vivo" and caso.get("ataque"):
            espera = ESPERA_WAZUH - (time.time() - ultimo_ataque)
            if ultimo_ataque and espera > 0:
                print(f"   (esperando {int(espera)} s: la regla 5763 de Wazuh se silencia 60 s tras dispararse)")
                time.sleep(espera)
        print(f"== {caso['id']} [{caso['nivel']}]: {caso['titulo']}")
        r = correr_caso(caso, dir_salida, ejecutor, perfil, hallazgos, catalogo,
                        escribir=lambda s: print("   | " + s.replace("\n", "\n   | ")))
        r["nivel"] = caso["nivel"]
        if caso["nivel"] == "vivo" and caso.get("ataque"):
            ultimo_ataque = time.time()
        print(f"   -> {r['resultado']} ({r['segundos']} s)" + "".join(f"\n      - {d}" for d in r["detalle"]))
        resultados.append(r)
    with open(os.path.join(dir_salida, "resultados.json"), "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    texto = informe(resultados, cuando)
    with open(os.path.join(dir_salida, "informe.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print("\n" + texto + f"\n-> {dir_salida}")
    # OMITIDO no es un fallo (nivel vivo sin --con-vivo, o requisito ausente como el modelo LLM):
    # el proceso solo termina en error por FALLO (diferencia no esperada) o BLOQUEADO (lab no en estado base).
    return 0 if not any(r["resultado"] in ("FALLO", "BLOQUEADO") for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
