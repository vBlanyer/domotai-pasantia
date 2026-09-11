"""Construye el registro de decisión auditable (RF-09) y lo encadena por hash.

La cadena: cada registro lleva `hash_previo` (el `hash` del anterior; un valor fijo para el
primero) y `hash` = SHA-256 de `hash_previo` + el registro en JSON canonico (claves ordenadas,
sin espacios, sin los dos campos de la cadena). Alterar cualquier campo de cualquier registro,
borrar uno, insertar uno o cambiar el orden rompe la cadena desde ese punto, y `verificar`
dice en cual.

Lo que la cadena NO cubre, y conviene decirlo: truncar el fichero por el final. Los registros
que quedan siguen encadenados entre si, asi que la cadena prueba la integridad de lo que hay,
no que no falte nada al final. Cubrir eso exige anclar el ultimo hash fuera del fichero (otro
sistema, un registro firmado, un tercero); la funcion `ultimo_hash` existe para poder hacerlo.
"""
import hashlib
import json

VERSION_BASELINE = "baseline-0"
GENESIS = "0" * 64
_CAMPOS_CADENA = ("hash", "hash_previo")

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

class Cadena:
    """Escribe registros encadenados, una linea JSON por registro, sobre un objeto fichero."""
    def __init__(self, fichero, hash_previo=GENESIS):
        self.fichero, self.ultimo = fichero, hash_previo
    def escribir(self, registro):
        reg = encadenar(registro, self.ultimo)
        self.fichero.write(json.dumps(reg, ensure_ascii=False) + "\n")
        self.fichero.flush()
        self.ultimo = reg["hash"]
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
        if v["valida"]:
            print(f"cadena valida: {v['n']} registros · ultimo hash {regs[-1]['hash'][:16]}..." if regs[k:]
                  else "sin registros encadenados: cadena trivialmente valida")
            return 0
        print(f"CADENA ROTA en el registro {k + v['primer_fallo']} (de {len(regs)}): {v['motivo']}")
        return 1
    print("uso: python3 -m prototipo.traza --verificar <traza.jsonl>")
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
        "accion_propuesta": accion_prop,
        "impacto": impacto,
        "perfil_aplicado": perfil_nombre,
        "resultado_filtro": filtro_out.get("resultado"),
        "accion_final": filtro_out.get("accion_final"),
        "requiere_humano": filtro_out.get("requiere_humano"),
        "version_baseline": VERSION_BASELINE,
        "version_perfil": version_perfil,
    }
