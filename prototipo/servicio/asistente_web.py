"""API de la vista «Asistente de red» (GET/POST /api/asistente…).

- Escanear y cambiar el borrador son FAIL-CLOSED, como Conectividad y Políticas: hace falta un operador
  identificado por el mapa de tokens; sin mapa, solo con el opt-in de laboratorio TRIAJE_ASISTENTE_ABIERTO=1.
- Escanear exige `autorizado: true` (la autorización por escrito del cliente). Un escaneo a la vez, en
  segundo plano; si falla, se conserva el descubrimiento anterior.
- El escaneo (inicio y fin) y cada cambio del borrador van a la traza firmada (`auditoria_asistente`).
- La propuesta NUNCA escribe nada: el perfil, la postura y la política se ofrecen para descargar y los
  instala el técnico.
Ficheros junto a la traza: asistente-descubrimiento.json y asistente-borrador.json (0600).
Plan: documentacion/05-fase5-implementacion-del-prototipo/plan-asistente-de-red.md (tarea 5).
"""
import json
import os
import tempfile
import threading
from datetime import datetime, timezone

import yaml

from prototipo.servicio import asistente_red as ar
from prototipo.servicio import descubrimiento as desc


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def instalar(srv, ruta_traza):
    d = os.path.dirname(os.path.abspath(ruta_traza)) if ruta_traza else None
    srv.ruta_asistente_desc = os.path.join(d, "asistente-descubrimiento.json") if d else None
    srv.ruta_asistente_borrador = os.path.join(d, "asistente-borrador.json") if d else None
    srv.asistente_correr = desc.ejecutor_nmap()
    srv.asistente_estado = {"escaneando": False, "error": None}
    srv._asistente_lock = threading.Lock()


def _leer(ruta):
    if not ruta or not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _guardar(ruta, datos):
    """Escritura atómica en 0600: temporal en el mismo directorio + os.replace."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ruta), prefix=".asistente-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        os.chmod(tmp, 0o600)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _adoptar_importado(srv):
    """Un descubrimiento hecho con «sudo mdr descubrir» entra en la traza firmada la primera vez que la
    consola lo usa (quién, qué rangos), y queda en 0600 como los de la consola."""
    with srv._asistente_lock:
        d = _leer(srv.ruta_asistente_desc)
        if not d or d.get("origen") != "cli" or d.get("auditado"):
            return
        _guardar(srv.ruta_asistente_desc, {**d, "auditado": True})
    _auditar(srv, d.get("operador"), "escaneo_importado",
             {"rangos": d.get("rangos"), "externo": d.get("externo"), "fecha": d.get("fecha"), "autorizado": d.get("autorizado")})


def _borrador(srv):
    """El borrador vigente: el guardado si es del último descubrimiento; si no (escaneo hecho con
    «sudo mdr descubrir», o borrador de un escaneo anterior), el que propone ese descubrimiento."""
    d, b = _leer(srv.ruta_asistente_desc), _leer(srv.ruta_asistente_borrador)
    if d and (b is None or b.get("basado_en") != d.get("fecha")):
        return ar.borrador_inicial(d)
    return b


def _puede(srv, operador):
    return bool(operador) and (bool(getattr(srv, "operadores", None)) or os.environ.get("TRIAJE_ASISTENTE_ABIERTO") == "1")


def _auditar(srv, operador, accion, detalle):
    estado = getattr(srv, "estado", None)
    if estado is not None:
        ts = _ahora()
        estado.auditar_en_traza({"id_decision": f"asistente~{ts}~{accion}", "tipo": "auditoria_asistente",
                                 "timestamp": ts, "operador": operador, "accion": accion, "detalle": detalle})


def _base(srv):
    return getattr(srv, "_perfil_base", None) or {}


def resumen(srv, registros):
    """GET /api/asistente."""
    _adoptar_importado(srv)
    base = _base(srv)
    return {**srv.asistente_estado, "descubrimiento": _leer(srv.ruta_asistente_desc),
            "borrador": _borrador(srv), "nombres_siem": ar.nombres_del_siem(registros, base),
            "por_defecto": {"gestion": base.get("ip_gestion"), "rangos": list(base.get("redes_internas") or [])}}


def _escanear(srv, peticion, operador):
    try:
        gestion = _base(srv).get("ip_gestion")
        r = desc.descubrir(peticion, srv.asistente_correr, gestion, operador, _ahora())
        _guardar(srv.ruta_asistente_desc, r)
        _guardar(srv.ruta_asistente_borrador, ar.borrador_inicial(r))
        error = None
        _auditar(srv, operador, "escaneo_fin", {"equipos": len(r["equipos"]), "traceroute": r["traceroute"]})
    except Exception as e:                        # el hilo nunca muere en silencio: el error se muestra
        error = str(e)[:500]
        _auditar(srv, operador, "escaneo_fin", {"error": error})
    with srv._asistente_lock:
        srv.asistente_estado = {"escaneando": False, "error": error}


def post(srv, ruta, cuerpo, operador):
    """POST /api/asistente/escanear | /api/asistente/borrador → (código, respuesta)."""
    if not srv.ruta_asistente_desc:
        return 503, {"error": "el asistente necesita una traza en fichero"}
    if not _puede(srv, operador):
        return 403, {"error": "el asistente de red exige un operador identificado por su token"}
    if not isinstance(cuerpo, dict):
        return 400, {"error": "cuerpo inválido"}
    if ruta == "/api/asistente/escanear":
        if cuerpo.get("autorizado") is not True:
            return 400, {"error": "marca que tienes la autorización por escrito del cliente para escanear"}
        try:
            peticion = desc.validar_peticion(cuerpo)
        except ValueError as e:
            return 400, {"error": str(e)}
        if not _base(srv).get("ip_gestion"):
            return 409, {"error": "el perfil no declara la IP de gestión del MDR"}
        with srv._asistente_lock:
            if srv.asistente_estado["escaneando"]:
                return 409, {"error": "ya hay un escaneo en marcha"}
            srv.asistente_estado = {"escaneando": True, "error": None}
        _auditar(srv, operador, "escaneo", {k: peticion[k] for k in ("rangos", "externo", "ritmo", "puertos")})
        threading.Thread(target=_escanear, args=(srv, peticion, operador), daemon=True).start()
        return 202, {"escaneando": True}
    if ruta == "/api/asistente/borrador":
        with srv._asistente_lock:
            borrador = _borrador(srv)
            if borrador is None:
                return 404, {"error": "aún no hay escaneo"}
            try:
                nuevo = ar.aplicar_cambios(borrador, cuerpo.get("cambios") or {})
            except ValueError as e:
                return 400, {"error": str(e)}
            _guardar(srv.ruta_asistente_borrador, nuevo)
        _auditar(srv, operador, "borrador", {"equipos": sorted((cuerpo.get("cambios") or {}).keys())})
        return 200, nuevo
    return 404, {"error": "no encontrado"}


def propuesta(srv, estado_red):
    """GET /api/asistente/propuesta: los tres ficheros, la validación y el mapa. No escribe nada."""
    _adoptar_importado(srv)
    borrador, d = _borrador(srv), _leer(srv.ruta_asistente_desc)
    if borrador is None or d is None:
        return 404, {"error": "aún no hay escaneo"}
    try:
        perfil = ar.perfil_desde_borrador(borrador)
    except ValueError as e:
        return 409, {"error": f"el descubrimiento no sirve para proponer un perfil: {e}"}
    hoy = _ahora()[:10]
    return 200, {"perfil_yaml": "# Propuesto por el asistente de red. Revísalo con: mdr validar-perfil perfil.yml\n"
                                + yaml.safe_dump(perfil, allow_unicode=True, sort_keys=False),
                 "postura_json": json.dumps(ar.postura_desde(d, borrador), ensure_ascii=False, indent=2),
                 "politica_yaml": yaml.safe_dump(ar.politica_desde(borrador, hoy), allow_unicode=True, sort_keys=False),
                 "validacion": ar.validar(borrador, getattr(srv, "catalogo", None) or {}),
                 "red": estado_red(perfil, [], [], None)}
