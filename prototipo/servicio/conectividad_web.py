"""API de la vista «Conectividad» del visor (GET/POST /api/conectividad…).

Junta el perfil (qué equipos hay y cuál es el canal de gestión, que no se toca), los ajustes
operativos del conector (accion/conectividad), la clave del conector y el known_hosts. Reglas:

- La clave PRIVADA no sale nunca: solo la huella y la clave pública.
- Editar es FAIL-CLOSED, como el editor de Políticas: hace falta un operador identificado por el mapa
  de tokens (no repudio); sin mapa, solo con el opt-in de laboratorio TRIAJE_CONECTIVIDAD_ABIERTA=1.
- Un ajuste de equipo SOLO se guarda si la prueba de conexión con ese ajuste pasa.
- Una clave del host nueva SOLO se acepta si su huella es la que el analista vio y confirmó.
- En modo laboratorio (contraseña) o sin configurar no se edita nada: los ajustes no aplicarían.
Cada cambio va al registro de auditoría (JSONL append-only, mismo formato que el de Políticas).
"""
import json
import os
import threading

from prototipo.accion import conectividad as cx, conector
from prototipo.servicio import politica_store

_MODOS_EDITABLES = ("clave", "directo")
_lock = threading.Lock()


def instalar(srv, ruta, ruta_auditoria):
    """Configura el servidor; `conectividad_*` son inyectables (los tests no tocan red ni docker)."""
    srv.ruta_conectividad, srv.ruta_auditoria_conectividad = ruta, ruta_auditoria
    srv.conectividad_modo = conector.modo_actual
    srv.conectividad_correr = conector.correr_donde_las_claves
    srv.conectividad_ejecutor = conector.ejecutor_con
    srv.conectividad_pruebas = {}            # ip -> última prueba (en memoria; no es auditoría)


def _equipos(srv):
    from prototipo.servicio.tablero import _red_segura
    gestion = (srv.perfil or {}).get("ip_gestion")
    r, _ = _red_segura(srv.perfil)
    return [{"nombre": n, "ip": v.get("ip"), "zona": v.get("zona"), "tipo": v.get("tipo"), "funcion": v.get("funcion"),
             "protegido": v.get("ip") == gestion}
            for n, v in r["nodos"].items() if v.get("ip") and v.get("tipo") != "externo"]


def _puede_editar(srv, operador):
    hay_mapa = bool(getattr(srv, "operadores", None))
    return bool(operador) and (hay_mapa or os.environ.get("TRIAJE_CONECTIVIDAD_ABIERTA") == "1")


def _cambios(srv, n=20):
    ruta = srv.ruta_auditoria_conectividad
    if not ruta or not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as f:
        lineas = f.readlines()[-n:]
    out = []
    for l in reversed(lineas):
        try:
            out.append(json.loads(l))
        except ValueError:
            continue
    return out


def resumen(srv, operador):
    modo = srv.conectividad_modo()
    ajustes = cx.cargar(srv.ruta_conectividad) if srv.ruta_conectividad else {"usuario_defecto": None, "equipos": {}}
    clave, huellas = None, {}
    if modo in _MODOS_EDITABLES:
        correr = srv.conectividad_correr(modo)
        rc, pub = correr(["cat", conector.SSH_CLAVE + ".pub"])     # la PÚBLICA: la privada no se lee nunca
        huella, tipo = cx.huella_de(pub) if rc == 0 else (None, None)
        if huella:
            clave = {"huella": huella, "tipo": tipo, "publica": pub.strip()}
        rc3, kh = correr(["cat", conector.SSH_KNOWN_HOSTS])
        huellas = cx.huellas_fijadas(kh) if rc3 == 0 else {}
    defecto = ajustes.get("usuario_defecto")
    equipos = []
    for e in _equipos(srv):
        aj = ajustes["equipos"].get(e["ip"]) or {}
        equipos.append({**e, "puerto": aj.get("puerto") or 22, "usuario": aj.get("usuario") or defecto or conector.SSH_USUARIO,
                        "ajustado": bool(aj), "huella_fijada": huellas.get(e["ip"]),
                        "ultima_prueba": srv.conectividad_pruebas.get(e["ip"])})
    editable = _puede_editar(srv, operador) and modo in _MODOS_EDITABLES and bool(srv.ruta_conectividad)
    motivo = None if editable else (
        "el conector está en modo laboratorio o sin configurar: los ajustes no aplicarían" if modo not in _MODOS_EDITABLES
        else "solo lectura: editar exige un operador identificado por su token")
    return {"modo": modo, "nodo_gestion": conector.nodo_gestion() if modo == "clave" else None,
            "editable": editable, "motivo_no_editable": motivo,
            "usuario_defecto": defecto, "usuario_entorno": conector.SSH_USUARIO,
            "ruta_clave": conector.SSH_CLAVE, "known_hosts": conector.SSH_KNOWN_HOSTS,
            "clave": clave, "equipos": equipos, "cambios": _cambios(srv)}


def _equipo(srv, nombre):
    return next((e for e in _equipos(srv) if e["nombre"] == nombre), None) if isinstance(nombre, str) else None


def _auditar(srv, operador, dimension, clave, antes, despues):
    if srv.ruta_auditoria_conectividad:
        politica_store.registrar_auditoria(srv.ruta_auditoria_conectividad, operador, dimension, clave, antes, despues)


def _candidatos(srv, e, cuerpo):
    """(usuario, puerto) a probar: lo que viene en el cuerpo (None = quitar el ajuste) o lo guardado."""
    ajustes = cx.cargar(srv.ruta_conectividad) if srv.ruta_conectividad else {"usuario_defecto": None, "equipos": {}}
    aj = ajustes["equipos"].get(e["ip"]) or {}
    puerto = cx.validar_puerto(cuerpo["puerto"]) if "puerto" in cuerpo else aj.get("puerto")
    usuario = cx.validar_usuario(cuerpo["usuario"]) if "usuario" in cuerpo else aj.get("usuario")
    return ajustes, usuario, puerto


def _probar(srv, modo, e, usuario, puerto):
    from prototipo.accion.conector import ahora_iso
    ajustes = cx.cargar(srv.ruta_conectividad) if srv.ruta_conectividad else {}
    efectivo = usuario or ajustes.get("usuario_defecto") or conector.SSH_USUARIO
    r = cx.probar(srv.conectividad_ejecutor(modo, usuario=efectivo, puerto=puerto or 22), e["ip"])
    r = {**r, "en": ahora_iso(), "puerto": puerto or 22, "usuario": efectivo}
    srv.conectividad_pruebas[e["ip"]] = r
    return r


def post(srv, ruta, cuerpo, operador):
    """(estado_http, cuerpo) para los POST de conectividad."""
    if not isinstance(cuerpo, dict):
        return 400, {"error": "cuerpo invalido"}
    modo = srv.conectividad_modo()
    if ruta == "/api/conectividad/probar":          # solo lectura sobre el equipo: no exige operador
        e = _equipo(srv, cuerpo.get("equipo"))
        if not e:
            return 400, {"error": "equipo desconocido"}
        if modo not in _MODOS_EDITABLES:
            return 409, {"error": "el conector está en modo laboratorio o sin configurar"}
        try:
            _, usuario, puerto = _candidatos(srv, e, cuerpo)
        except ValueError as ex:
            return 400, {"error": str(ex)}
        return 200, _probar(srv, modo, e, usuario, puerto)
    if ruta == "/api/conectividad/leer-clave-host":
        e = _equipo(srv, cuerpo.get("equipo"))
        if not e:
            return 400, {"error": "equipo desconocido"}
        if modo not in _MODOS_EDITABLES:
            return 409, {"error": "el conector está en modo laboratorio o sin configurar"}
        correr = srv.conectividad_correr(modo)
        ajustes = cx.cargar(srv.ruta_conectividad) if srv.ruta_conectividad else {"equipos": {}}
        puerto = (ajustes["equipos"].get(e["ip"]) or {}).get("puerto") or 22
        rc, kh = correr(["cat", conector.SSH_KNOWN_HOSTS])
        claves = (cx.claves_de_known_hosts(kh) if rc == 0 else {}).get(e["ip"]) or []
        presentada = cx.huella_presentada(e["ip"], puerto, correr)
        return 200, {"equipo": e["nombre"], "fijada": cx.huellas_fijadas(kh).get(e["ip"]) if rc == 0 else None,
                     "presentada": presentada, "coincide": bool(presentada and presentada in {h for _, h in claves})}

    # --- a partir de aquí, cambios: operador identificado y modo con clave
    if not _puede_editar(srv, operador):
        return 403, {"error": "operador no identificado"}
    if modo not in _MODOS_EDITABLES or not srv.ruta_conectividad:
        return 409, {"error": "el conector está en modo laboratorio o sin configurar: los ajustes no aplicarían"}
    if ruta == "/api/conectividad/clave-host":
        e = _equipo(srv, cuerpo.get("equipo"))
        if not e or e["protegido"]:
            return 400, {"error": "equipo desconocido o protegido"}
        huella = cuerpo.get("huella")
        if not isinstance(huella, str) or not huella.startswith("SHA256:"):
            return 400, {"error": "huella invalida"}
        correr = srv.conectividad_correr(modo)
        ajustes = cx.cargar(srv.ruta_conectividad)
        puerto = (ajustes["equipos"].get(e["ip"]) or {}).get("puerto") or 22
        with _lock:
            rc, kh = correr(["cat", conector.SSH_KNOWN_HOSTS])
            antes = (cx.huellas_fijadas(kh) if rc == 0 else {}).get(e["ip"])
            try:
                nueva = cx.aceptar_clave_host(e["ip"], puerto, huella, conector.SSH_KNOWN_HOSTS, correr)
            except cx.HuellaDistinta as ex:
                return 409, {"error": str(ex)}
            _auditar(srv, operador, "clave_host", e["nombre"], antes, nueva)
        srv.conectividad_pruebas.pop(e["ip"], None)
        return 200, {"equipo": e["nombre"], "huella": nueva}

    # POST /api/conectividad: usuario por defecto, o puerto/usuario de un equipo (probado antes)
    if "usuario_defecto" in cuerpo and "equipo" not in cuerpo:
        try:
            nuevo = cx.validar_usuario(cuerpo["usuario_defecto"])
        except ValueError as ex:
            return 400, {"error": str(ex)}
        with _lock:
            ajustes = cx.cargar(srv.ruta_conectividad)
            antes = ajustes.get("usuario_defecto")
            cx.guardar(srv.ruta_conectividad, {**ajustes, "usuario_defecto": nuevo})
            _auditar(srv, operador, "usuario_defecto", "*", antes, nuevo)
        return 200, {"guardado": True, "usuario_defecto": nuevo}
    e = _equipo(srv, cuerpo.get("equipo"))
    if not e:
        return 400, {"error": "equipo desconocido"}
    if e["protegido"]:
        return 400, {"error": "equipo protegido (canal de gestión del MDR): no se configura desde aquí"}
    try:
        ajustes, usuario, puerto = _candidatos(srv, e, cuerpo)
    except ValueError as ex:
        return 400, {"error": str(ex)}
    prueba = _probar(srv, modo, e, usuario, puerto)
    if not prueba["ok"]:
        return 409, {"guardado": False, "prueba": prueba}
    with _lock:
        ajustes = cx.cargar(srv.ruta_conectividad)
        antes = ajustes["equipos"].get(e["ip"])
        nuevos = cx.con_cambio(ajustes, e["ip"], e["nombre"], puerto, usuario)
        cx.guardar(srv.ruta_conectividad, nuevos)
        _auditar(srv, operador, "equipo", e["nombre"], antes, nuevos["equipos"].get(e["ip"]))
    return 200, {"guardado": True, "prueba": prueba}
