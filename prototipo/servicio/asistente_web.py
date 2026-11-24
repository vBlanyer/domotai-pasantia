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


class IlegibleError(Exception):
    """Un fichero del asistente existe pero no se puede usar (permisos, o no tiene la forma esperada)."""


def _leer(ruta, forma=None):
    """El JSON de `ruta`; None si no existe. IlegibleError si existe y no se puede usar: antes se tragaba el
    error y la consola ignoraba en silencio, p. ej., el escaneo de «sudo mdr descubrir» (fichero de root)."""
    if not ruta or not os.path.isfile(ruta):
        return None
    nombre = os.path.basename(ruta)
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except PermissionError:
        raise IlegibleError(f"no se puede leer {nombre}: el servicio no tiene permiso (¿lo dejó root con "
                            f"«sudo mdr descubrir»?). Dale el fichero al usuario del servicio o vuelve a escanear")
    except (OSError, ValueError) as e:
        raise IlegibleError(f"{nombre} está dañado ({type(e).__name__}); vuelve a escanear")
    if forma is not None and not forma(datos):
        raise IlegibleError(f"{nombre} está dañado (no tiene la forma esperada); vuelve a escanear")
    return datos


def _desc_valido(d):
    return (isinstance(d, dict) and isinstance(d.get("fecha"), str) and isinstance(d.get("rangos"), list)
            and isinstance(d.get("equipos"), list)
            and all(isinstance(e, dict) and isinstance(e.get("ip"), str) and isinstance(e.get("puertos"), list)
                    for e in d["equipos"]))


_CLAVES_EQUIPO = {"incluido", "nombre", "zona", "papel", "criticidad", "no_tocar", "depende_de", "funcion", "gateway",
                  "interfaces", "servicios", "deducido", "sin_camino"}


def _borrador_valido(b):
    return (isinstance(b, dict) and isinstance(b.get("equipos"), dict) and isinstance(b.get("redes_internas"), list)
            and all(isinstance(e, dict) and _CLAVES_EQUIPO <= set(e) for e in b["equipos"].values()))


def _leer_desc(srv):
    return _leer(srv.ruta_asistente_desc, _desc_valido)


def _leer_borrador_crudo(srv):
    """El borrador guardado, o None si falta o está dañado (se rehace desde el descubrimiento)."""
    try:
        return _leer(srv.ruta_asistente_borrador, _borrador_valido)
    except IlegibleError:
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
        try:
            d = _leer_desc(srv)
        except IlegibleError:
            return
        if not d or d.get("origen") != "cli" or d.get("auditado"):
            return
        _guardar(srv.ruta_asistente_desc, {**d, "auditado": True})
    _auditar(srv, d.get("operador"), "escaneo_importado",
             {"rangos": d.get("rangos"), "externo": d.get("externo"), "fecha": d.get("fecha"), "autorizado": d.get("autorizado")})


def _borrador(srv):
    """El borrador vigente: el guardado si es del último descubrimiento; si no (escaneo hecho con
    «sudo mdr descubrir», o borrador de un escaneo anterior), el que propone ese descubrimiento."""
    d, b = _leer_desc(srv), _leer_borrador_crudo(srv)
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
    try:
        desc, borrador, aviso = _leer_desc(srv), _borrador(srv), None
    except IlegibleError as e:
        desc, borrador, aviso = None, None, str(e)
    return {**srv.asistente_estado, "descubrimiento": desc, "borrador": borrador, "aviso_lectura": aviso,
            "instalacion": getattr(srv, "rutas_instalacion", None),
            "nombres_siem": ar.nombres_del_siem(registros, base),
            "por_defecto": {"gestion": base.get("ip_gestion"), "rangos": list(base.get("redes_internas") or [])}}


def _escanear(srv, peticion, operador):
    error = None
    try:
        gestion = _base(srv).get("ip_gestion")
        r = desc.descubrir(peticion, srv.asistente_correr, gestion, operador, _ahora())
        # Lo que el técnico ya había escrito (también DURANTE el escaneo) se conserva para las mismas IPs. Los
        # dos ficheros se escriben juntos bajo el lock: un guardado del borrador no se cuela entre ellos.
        with srv._asistente_lock:
            try:
                previo = _borrador(srv)
            except IlegibleError:
                previo = None
            _guardar(srv.ruta_asistente_desc, r)
            _guardar(srv.ruta_asistente_borrador, ar.conservar_trabajo(previo, ar.borrador_inicial(r)))
        _auditar(srv, operador, "escaneo_fin", {"equipos": len(r["equipos"]), "traceroute": r["traceroute"]})
    except Exception as e:                        # el hilo nunca muere en silencio: el error se muestra
        error = str(e)[:500]
        try:
            _auditar(srv, operador, "escaneo_fin", {"error": error})
        except Exception:
            pass
    finally:
        with srv._asistente_lock:                 # pase lo que pase, el escaneo deja de estar «en marcha»
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
        try:
            _auditar(srv, operador, "escaneo", {k: peticion[k] for k in ("rangos", "externo", "ritmo", "puertos")})
        except Exception as e:
            # Sin rastro en la traza firmada no se escanea (fail-closed), y no se queda «en marcha» para siempre.
            with srv._asistente_lock:
                srv.asistente_estado = {"escaneando": False, "error": None}
            return 500, {"error": f"no se pudo anotar el escaneo en la traza ({type(e).__name__}); no se escanea"}
        threading.Thread(target=_escanear, args=(srv, peticion, operador), daemon=True).start()
        return 202, {"escaneando": True}
    if ruta == "/api/asistente/borrador":
        with srv._asistente_lock:
            try:
                borrador = _borrador(srv)
            except IlegibleError as e:
                return 409, {"error": str(e)}
            if borrador is None:
                return 404, {"error": "aún no hay escaneo"}
            try:
                nuevo, rechazados = ar.aplicar_cambios_parcial(borrador, cuerpo.get("cambios") or {})
            except ValueError as e:
                return 400, {"error": str(e)}
            _guardar(srv.ruta_asistente_borrador, nuevo)
        _auditar(srv, operador, "borrador", {"equipos": sorted((cuerpo.get("cambios") or {}).keys()),
                                             **({"rechazados": len(rechazados)} if rechazados else {})})
        # Lo que no valía vuelve campo a campo: la consola lo marca en la tabla sin perder lo demás.
        return 200, {"borrador": nuevo, "rechazados": rechazados}
    return 404, {"error": "no encontrado"}


def propuesta(srv, estado_red, registros=()):
    """GET /api/asistente/propuesta: los tres ficheros, la validación y el mapa. No escribe nada."""
    _adoptar_importado(srv)
    try:
        borrador, d = _borrador(srv), _leer_desc(srv)
    except IlegibleError as e:
        return 409, {"error": str(e)}
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
                 "validacion": ar.validar(borrador, getattr(srv, "catalogo", None) or {},
                                          vistos=ar.nombres_vistos(registros)),
                 "red": estado_red(perfil, [], [], None)}
