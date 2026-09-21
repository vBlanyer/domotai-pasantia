"""Construye el registro de decisión auditable (RF-09) y lo encadena por hash.

La cadena: cada registro lleva `hash_previo` (el `hash` del anterior; un valor fijo para el
primero) y `hash` = SHA-256 de `hash_previo` + el registro en JSON canonico (claves ordenadas,
sin espacios, sin los dos campos de la cadena). Alterar cualquier campo de cualquier registro,
borrar uno, insertar uno o cambiar el orden rompe la cadena desde ese punto, y `verificar`
dice en cual.

Lo que la cadena sola NO cubre: truncar el fichero por el final. Los registros que quedan
siguen encadenados entre si, asi que la cadena prueba la integridad de lo que hay, no que no
falte nada al final. Para eso esta el ANCLA: tras cada registro, la cadena envia el hash y el
numero de registros como un evento syslog al manager de Wazuh (TRIAJE_ANCLA=host:puerto), que
lo guarda con su regla local 100100 en alerts.json. Wazuh es otro sistema, ya es la fuente de
verdad del triaje, y el fichero que escribe no lo controla quien controla la traza. Verificar
con `--anclas <alerts.json>` compara la traza con el ancla mas reciente: si el ancla cuenta mas
registros de los que hay, la traza esta truncada; si el registro que el ancla senala tiene otro
hash, esta alterada o no es ese fichero.
"""
import hashlib
import json
import os
import re
import socket
import time

VERSION_BASELINE = "baseline-0"
GENESIS = "0" * 64
_CAMPOS_CADENA = ("hash", "hash_previo")
ANCLA_DESTINO = os.environ.get("TRIAJE_ANCLA")          # "host:puerto" del syslog del manager; sin ella no se ancla
_ANCLA_RE = re.compile(r"triaje-ancla: fichero=(\S+) linaje=([0-9a-f]{16}) registros=(\d+) hash=([0-9a-f]{64})")

def _canonico(registro):
    limpio = {k: v for k, v in registro.items() if k not in _CAMPOS_CADENA}
    return json.dumps(limpio, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _hash(hash_previo, registro):
    return hashlib.sha256((hash_previo + _canonico(registro)).encode("utf-8")).hexdigest()

def encadenar(registro, hash_previo):
    """Copia del registro con `hash_previo` y su `hash`."""
    return {**registro, "hash_previo": hash_previo, "hash": _hash(hash_previo, registro)}

def verificar(registros):
    """Recorre la cadena. Devuelve {valida, n, primer_fallo, motivo}; `primer_fallo` es el indice
    (desde 0) del primer registro que no cuadra, o None."""
    esperado = GENESIS
    for i, reg in enumerate(registros):
        if "hash" not in reg or "hash_previo" not in reg:
            return {"valida": False, "n": i, "primer_fallo": i, "motivo": "registro sin cadena"}
        if reg["hash_previo"] != esperado:
            return {"valida": False, "n": i, "primer_fallo": i,
                    "motivo": "hash_previo no coincide con el registro anterior (borrado, insercion o reorden)"}
        if reg["hash"] != _hash(reg["hash_previo"], reg):
            return {"valida": False, "n": i, "primer_fallo": i,
                    "motivo": "el hash no corresponde al contenido (registro alterado)"}
        esperado = reg["hash"]
    return {"valida": True, "n": len(registros) if isinstance(registros, list) else None,
            "primer_fallo": None, "motivo": ""}

def leer_registros(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def ultimo_hash(ruta):
    """Hash del ultimo registro de un fichero de traza, o GENESIS si no existe o esta vacio. Sirve
    para retomar la cadena al reabrir el fichero y para anclar su estado fuera de el."""
    try:
        regs = leer_registros(ruta)
    except FileNotFoundError:
        return GENESIS
    return regs[-1].get("hash", GENESIS) if regs else GENESIS

def linaje_de(registros):
    """Identidad de un fichero de traza: los 16 primeros caracteres del hash de su primer registro.
    Un fichero borrado y rehecho con el mismo nombre tiene otro linaje; uno truncado, el mismo."""
    return registros[0]["hash"][:16] if registros and registros[0].get("hash") else None

def formatear_ancla(nombre, linaje, n, hash_):
    """Linea syslog (prioridad 38 = auth.info, como el resto del laboratorio) con el ancla."""
    return (f"<38>{time.strftime('%b %d %H:%M:%S')} triaje triaje-ancla: fichero={nombre} linaje={linaje} "
            f"registros={n} hash={hash_}")

def _enviar_udp(linea, destino):
    host, puerto = destino.rsplit(":", 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(linea.encode("utf-8"), (host, int(puerto)))

def anclar(nombre, linaje, n, hash_, destino=None, _enviar=_enviar_udp):
    """Envia el ancla al manager. Nunca lanza: anclar es lo mejor posible, y que falle el ancla no
    debe parar la traza (que es lo que esta protegiendo). Devuelve si se envio."""
    destino = destino or ANCLA_DESTINO
    if not destino:
        return False
    try:
        _enviar(formatear_ancla(nombre, linaje, n, hash_), destino)
        return True
    except (OSError, ValueError):
        return False

def leer_anclas(ruta_alerts, nombre):
    """[(registros, hash, linaje)] de las anclas de `nombre` en un alerts.json de Wazuh."""
    anclas = []
    with open(ruta_alerts, encoding="utf-8", errors="replace") as f:
        for l in f:
            if "triaje-ancla" not in l:
                continue
            m = _ANCLA_RE.search(l)
            if m and m.group(1) == nombre:
                anclas.append((int(m.group(3)), m.group(4), m.group(2)))
    return anclas

def verificar_contra_anclas(registros, anclas):
    """Compara la traza con las anclas que Wazuh guarda para su nombre de fichero.

    Tres fallos distintos, y conviene nombrarlos: TRUNCADA (las anclas de este mismo linaje
    cuentan mas registros de los que hay), REHECHA (hay anclas para ese nombre y ninguna
    coincide con ningun registro: el fichero se borro y se volvio a crear, que es perder lo
    anclado) y ALTERADA (el registro que el ancla senala tiene otro hash)."""
    if not anclas:
        return {"valida": True, "motivo": "sin anclas para este fichero", "ancla": None}
    linaje = linaje_de(registros)
    mias = [(n, h) for n, h, lin in anclas if lin == linaje]
    if not mias:
        n, h, _ = max(anclas)
        return {"valida": False, "ancla": (n, h),
                "motivo": f"REHECHA: Wazuh tiene {len(anclas)} anclas para este nombre (hasta {n} registros) y "
                          f"ninguna es de este linaje; el fichero se borro y se volvio a crear"}
    n, h = max(mias)
    if n > len(registros):
        return {"valida": False, "ancla": (n, h),
                "motivo": f"TRUNCADA: el ancla mas reciente de este linaje cuenta {n} registros y la traza "
                          f"tiene {len(registros)}"}
    if registros[n - 1].get("hash") != h:
        return {"valida": False, "ancla": (n, h),
                "motivo": f"ALTERADA: el registro {n - 1} no tiene el hash que el ancla senala"}
    return {"valida": True, "ancla": (n, h),
            "motivo": f"el ancla coincide: {n} registros" + (f" (la traza tiene {len(registros) - n} mas, aun sin anclar)"
                                                            if len(registros) > n else "")}

class Cadena:
    """Escribe registros encadenados, una linea JSON por registro, sobre un objeto fichero, y
    ancla cada uno en el manager si hay destino (`ancla`). `n` y `nombre` retoman un fichero."""
    def __init__(self, fichero, hash_previo=GENESIS, n=0, nombre="", ancla=None, linaje=None):
        self.fichero, self.ultimo, self.n, self.nombre = fichero, hash_previo, n, nombre
        self.ancla = ancla if ancla is not None else ANCLA_DESTINO
        self.linaje, self.anclados = linaje, 0
    def escribir(self, registro):
        reg = encadenar(registro, self.ultimo)
        self.fichero.write(json.dumps(reg, ensure_ascii=False) + "\n")
        self.fichero.flush()
        self.ultimo, self.n = reg["hash"], self.n + 1
        if self.linaje is None:
            self.linaje = reg["hash"][:16]        # fichero nuevo: el primer registro fija el linaje
        if self.ancla and anclar(self.nombre, self.linaje, self.n, self.ultimo, self.ancla):
            self.anclados += 1
        return reg

def _main(argv):
    if len(argv) >= 2 and argv[0] == "--verificar":
        try:
            regs = leer_registros(argv[1])
        except FileNotFoundError:
            print(f"no existe {argv[1]}"); return 2
        # Un fichero puede empezar con registros anteriores a la cadena (escritos antes de
        # que existiera). Se informan como tales y se verifica desde el primer encadenado: no
        # son una rotura, son historia sin proteccion, y conviene que se vea la frontera.
        k = next((i for i, reg in enumerate(regs) if "hash" in reg), len(regs))
        if k:
            print(f"{k} registros anteriores a la cadena (sin proteccion); se verifica desde el {k}")
        v = verificar(regs[k:])
        if not v["valida"]:
            print(f"CADENA ROTA en el registro {k + v['primer_fallo']} (de {len(regs)}): {v['motivo']}")
            return 1
        print(f"cadena valida: {v['n']} registros · ultimo hash {regs[-1]['hash'][:16]}..." if regs[k:]
              else "sin registros encadenados: cadena trivialmente valida")
        if "--anclas" in argv:
            anclas = leer_anclas(argv[argv.index("--anclas") + 1], os.path.basename(argv[1]))
            a = verificar_contra_anclas(regs[k:], anclas)
            print(("anclas: " if a["valida"] else "ANCLAS: ") + a["motivo"])
            return 0 if a["valida"] else 1
        return 0
    print("uso: python3 -m prototipo.traza --verificar <traza.jsonl> [--anclas <alerts.json de Wazuh>]")
    return 2

if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))

def justificacion_estructurada(alerta, analisis_out, accion_prop):
    """Justificación estructurada (RF-05): los 4 componentes de la decisión como objeto.
    Puro y tolerante — usa `.get()`, no infiere lo ausente (RNF-07)."""
    return {
        "evidencia": {
            "regla": alerta.get("regla_id"),
            "origen_ip": alerta.get("origen_ip"),
            "activo": alerta.get("activo"),
            "servicio": alerta.get("servicio"),
        },
        "hipotesis": {
            "clase": analisis_out.get("clase"),
            "confianza": analisis_out.get("confianza"),
        },
        "tecnica_mitre": alerta.get("mitre", []) or [],
        "accion_sugerida": accion_prop,
    }

def construir(id_decision, timestamp, alerta, analisis_out, accion_prop, impacto, perfil_nombre, filtro_out, version_perfil):
    return {
        "id_decision": id_decision,
        "timestamp": timestamp,
        "id_alerta": alerta.get("id_alerta"),
        "activo": alerta.get("activo"),
        "clase": analisis_out.get("clase"),
        "prioridad": analisis_out.get("prioridad"),
        "confianza": analisis_out.get("confianza"),
        "justificacion": analisis_out.get("justificacion"),
        "justificacion_estructurada": justificacion_estructurada(alerta, analisis_out, accion_prop),
        "version_justificador": analisis_out.get("version_justificador", "plantilla-0"),  # RF-09/RNF-03
        "pasajes_usados": analisis_out.get("pasajes_usados", []),
        "consulta_rag": analisis_out.get("consulta_rag", ""),                    # Opcion C (RNF-03)
        "recuperacion_agentica": analisis_out.get("recuperacion_agentica", False),
        "ruta": analisis_out.get("ruta"),                    # rol/destino de encaminamiento (triar_y_enrutar)
        "accion_propuesta": accion_prop,
        "impacto": impacto,
        "perfil_aplicado": perfil_nombre,
        "resultado_filtro": filtro_out.get("resultado"),
        "accion_final": filtro_out.get("accion_final"),
        "requiere_humano": filtro_out.get("requiere_humano"),
        "impacto_determinado": filtro_out.get("impacto"),   # a quién bloquea y qué detiene (RF-17)
        "version_baseline": VERSION_BASELINE,
        "version_perfil": version_perfil,
    }
