"""API de la vista «Conectividad» del visor (GET/POST /api/conectividad…).

Junta el perfil (qué equipos hay y cuál es el canal de gestión, que no se toca), el inventario
operativo (equipos dados de alta desde la consola y el papel de cada uno), los ajustes del conector
(accion/conectividad), la clave del conector y el known_hosts. Reglas:

- La clave PRIVADA no sale nunca: solo la huella y la clave pública.
- Probar, leer la clave de un equipo, editar, dar de alta y rotar son FAIL-CLOSED, como el editor de
  Políticas: hace falta un operador identificado por el mapa de tokens (no repudio); sin mapa, solo con
  el opt-in de laboratorio TRIAJE_CONECTIVIDAD_ABIERTA=1. Ver la configuración basta con la sesión.
- Probar o leer la clave de un mismo equipo, como mucho una vez cada FRENO_S segundos.
- Un ajuste de equipo SOLO se guarda si la prueba de conexión con ese ajuste pasa.
- Una clave del host nueva SOLO se acepta si su huella es la que el analista vio y confirmó.
- Un equipo nuevo SOLO pasa a activo (y el motor lo ve) con su clave del host fijada y la prueba en verde.
- En modo laboratorio (contraseña) o sin configurar no se hace nada de esto: no aplicaría.
Cada prueba, lectura y cambio va al registro de auditoría (JSONL append-only, formato de Políticas).
"""
import json
import os
import threading
import time
from datetime import datetime, timezone

from prototipo.accion import catalogo as catalogom, conectividad as cx, conector, fallos
from prototipo.servicio import inventario_store as inv, politica_store

_MODOS_EDITABLES = ("clave", "directo")
FRENO_S = 10
_lock = threading.Lock()


def _junto(ruta, nombre):
    return os.path.join(os.path.dirname(os.path.abspath(ruta)), nombre) if ruta else None


def instalar(srv, ruta, ruta_auditoria):
    """Configura el servidor; `conectividad_*` son inyectables (los tests no tocan red ni docker).
    Carga el inventario operativo y lo fusiona en la base del perfil (antes de que se apliquen las
    Políticas encima): así el motor y el mapa ven los equipos dados de alta desde la consola."""
    srv.ruta_conectividad, srv.ruta_auditoria_conectividad = ruta, ruta_auditoria
    srv.conectividad_modo = conector.modo_actual
    srv.conectividad_correr = conector.correr_donde_las_claves
    srv.conectividad_ejecutor = conector.ejecutor_con
    srv.ruta_pruebas = _junto(ruta, "conectividad-pruebas.json")
    srv.conectividad_pruebas = cx.cargar_pruebas(srv.ruta_pruebas)    # ip -> última prueba (sobrevive al reinicio)
    srv.conectividad_ultimo = {}                                        # (qué, ip) -> instante, para el freno
    srv.conectividad_operativo = {}     # ip -> último fallo de una contención real (en memoria; fase 3)
    srv.ruta_inventario = _junto(ruta, "inventario-operativo.yml")
    srv.ruta_rotacion = cx.ruta_rotacion(ruta) if ruta else None
    srv._perfil_canonico = srv._perfil_base
    if srv.ruta_inventario:
        srv._perfil_base = inv.fusionar(srv._perfil_canonico, inv.cargar(srv.ruta_inventario))


def _reaplicar_perfil(srv):
    """Tras un cambio del inventario: base = canónico + inventario; vivo = base + Políticas."""
    from prototipo.motor import perfil as perfilm
    lock = getattr(srv, "_politica_lock", None) or threading.Lock()
    with lock:
        srv._perfil_base = inv.fusionar(srv._perfil_canonico, inv.cargar(srv.ruta_inventario))
        if getattr(srv, "ruta_overlay", None):
            srv.perfil = perfilm.fusionar_politicas(srv._perfil_base, politica_store.cargar_overlay(srv.ruta_overlay))
        else:
            srv.perfil = srv._perfil_base


def _inventario(srv):
    return inv.cargar(srv.ruta_inventario) if getattr(srv, "ruta_inventario", None) else {"equipos": {}}


def _equipos(srv):
    from prototipo.servicio.tablero import _red_segura
    gestion = (srv.perfil or {}).get("ip_gestion")
    r, _ = _red_segura(srv.perfil)
    inventario = _inventario(srv)["equipos"]
    out = []
    for n, v in r["nodos"].items():
        if v.get("ip") and v.get("tipo") != "externo":
            i = inventario.get(n) or {}
            out.append({"nombre": n, "ip": v.get("ip"), "zona": v.get("zona"), "tipo": v.get("tipo"), "funcion": v.get("funcion"),
                        "protegido": v.get("ip") == gestion, "alta": "activo" if i.get("nuevo") else None, **_reglas_vista(i)})
    for n, i in sorted(inventario.items()):
        if i.get("nuevo") and i.get("estado") != "activo":
            out.append({"nombre": n, "ip": i.get("ip"), "zona": i.get("zona"), "tipo": "host", "funcion": i.get("funcion"),
                        "protegido": False, "alta": "pendiente", "criticidad": i.get("criticidad"),
                        "depende_de": i.get("depende_de") or [], "interfaz": i.get("interfaz"), **_reglas_vista(i)})
    return out


def _reglas_vista(i):
    return {"papel": i.get("papel"), "acciones": i.get("acciones"), "servicios": i.get("servicios") or [],
            "cuentas": i.get("cuentas") or [], "cuentas_cualquiera": i.get("cuentas_cualquiera") is True}


def _destino_claves(modo):
    """Dónde viven (o vivirán) la clave y el known_hosts del conector: el modo con clave en uso o, si el
    daemon arrancó sin clave («sin_configurar»), el que pide TRIAJE_SSH_MODO (directo = este host) o el
    nodo de gestión. En modo laboratorio (contraseña) no hay clave que gestionar."""
    if modo in _MODOS_EDITABLES:
        return modo
    if modo == "sin_configurar":
        return "directo" if os.environ.get("TRIAJE_SSH_MODO") == "directo" else "clave"
    return None


def _clave_conector(srv, modo):
    """{huella, tipo, publica} de la clave PÚBLICA del conector, o None si aún no existe."""
    destino = _destino_claves(modo)
    if not destino:
        return None
    rc, pub = srv.conectividad_correr(destino)(["cat", conector.SSH_CLAVE + ".pub"])
    huella, tipo = cx.huella_de(pub) if rc == 0 else (None, None)
    return {"huella": huella, "tipo": tipo, "publica": pub.strip()} if huella else None


DESACTIVADA = ("la vista Conectividad está desactivada por la administración (TRIAJE_CONECTIVIDAD_DESACTIVADA): "
               "no prueba, no lee claves ni cambia nada")


def _desactivada():
    """La administración puede apagar la vista sin tocar código: solo lectura de la configuración
    guardada, sin abrir conexiones ni leer claves del host."""
    return os.environ.get("TRIAJE_CONECTIVIDAD_DESACTIVADA") == "1"


def _puede_editar(srv, operador):
    hay_mapa = bool(getattr(srv, "operadores", None))
    return bool(operador) and (hay_mapa or os.environ.get("TRIAJE_CONECTIVIDAD_ABIERTA") == "1")


def _motivo_no_editable(modo):
    """Por qué no se puede probar ni cambiar nada en Conectividad con este modo del conector."""
    if modo == "password":
        return "el conector está en modo contraseña (pruebas): probar y cambiar no aplicarían"
    return "el conector aún no tiene clave: genérala primero con «Generar la clave del conector»"


def _permisos(srv, operador, modo):
    if _desactivada():
        return False, DESACTIVADA
    if modo not in _MODOS_EDITABLES:
        return False, _motivo_no_editable(modo)
    if not srv.ruta_conectividad:
        return False, "el daemon no tiene fichero de ajustes del conector"
    if not _puede_editar(srv, operador):
        return False, "probar y cambiar exigen un operador identificado por su token"
    return True, None


def _cambios(srv, n=40):
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


def _catalogo(srv):
    return getattr(srv, "catalogo", None) or {}


def _esperadas(srv, e):
    """Reglas del sudoers que el equipo debería tener según su papel (sin papel: el catálogo entero)."""
    cat = _catalogo(srv)
    if not cat:
        return None
    if e.get("papel"):
        return catalogom.reglas_de_equipo(cat, e.get("acciones") or [], e.get("servicios"), e.get("cuentas"),
                                          e.get("cuentas_cualquiera") is True)
    return catalogom.reglas_de_equipo(cat, None)


def _permitido(esperadas):
    """Un comando del catálogo SIN comodines para la prueba (iptables -L -n si el equipo lo admite)."""
    if not esperadas:
        return None
    if ("iptables", "-L -n") in esperadas:
        return "iptables -L -n"
    sin = next(((b, a) for b, a in esperadas if "*" not in a), None)
    return f"{sin[0]} {sin[1]}".strip() if sin else None


def _rotacion_vista(srv):
    r = cx.cargar_rotacion(srv.ruta_rotacion) if getattr(srv, "ruta_rotacion", None) else None
    if not r:
        return None
    return {"iniciada_por": r.get("iniciada_por"), "en": r.get("en"), "huella_nueva": cx.huella_de(r.get("publica_nueva"))[0],
            "equipos": r.get("equipos") or {}}


def _vigente(prueba, clave, fijada):
    """Una prueba solo vale con la MISMA clave del conector y la MISMA clave del host con las que se hizo:
    tras recrear el laboratorio, rotar la clave o aceptar otra del host, la vieja ya no dice nada."""
    return bool(prueba) and prueba.get("clave_conector") == (clave or {}).get("huella") and prueba.get("huella_host") == fijada


_CAMPOS_OPERATIVO = ("clase", "descripcion", "accion", "posible_ataque", "regresion")


def registrar_operativo(srv, ip, causa):
    """El resultado de una contención real en un equipo: un fallo deja un aviso encima de su prueba;
    una contención verificada lo quita. Nunca pone nada en «verificada»: solo resta confianza. La
    evidencia en bruto no se guarda aquí (está en la traza de la decisión)."""
    with _lock:
        if causa is None:
            srv.conectividad_operativo.pop(ip, None)
        else:
            from prototipo.accion.conector import ahora_iso
            srv.conectividad_operativo[ip] = {**{k: causa.get(k) for k in _CAMPOS_OPERATIVO}, "en": ahora_iso()}


def sondear_acceso(srv, ip):
    """Sondeo inocuo de la memoria de fallos (fase 5): entra por SSH SIN sudo y ejecuta `true`, con el
    usuario y el puerto del equipo. Sin sudo no deja fallos de sudo en el registro del equipo (que el SIEM
    vería). None si el conector no está en un modo con clave (entonces se usa el ejecutor del lazo)."""
    modo = srv.conectividad_modo()
    if modo not in _MODOS_EDITABLES:
        return None
    ajustes = cx.cargar(srv.ruta_conectividad) if srv.ruta_conectividad else {"usuario_defecto": None, "equipos": {}}
    aj = ajustes["equipos"].get(ip) or {}
    usuario = aj.get("usuario") or ajustes.get("usuario_defecto") or conector.SSH_USUARIO
    return srv.conectividad_ejecutor(modo, usuario=usuario, puerto=aj.get("puerto") or 22, sudo=False)(ip, "true")


def contexto_equipo(srv, ip, accion_id=None):
    """Lo que la consola sabe de un equipo para clasificar un fallo de contención (accion/fallos):
    si tiene su clave del host fijada, si estaba verificado con las claves actuales (regresión) y, si su
    última prueba vigente lo dice, qué regla de la acción falta en su sudoers. Solo lectura."""
    modo = srv.conectividad_modo()
    destino = _destino_claves(modo)
    if not destino or not ip:
        return {}
    rc, kh = srv.conectividad_correr(destino)(["cat", conector.SSH_KNOWN_HOSTS])
    huellas = cx.huellas_fijadas(kh) if rc == 0 else {}
    prueba = srv.conectividad_pruebas.get(ip)
    vigente = _vigente(prueba, _clave_conector(srv, modo), huellas.get(ip))
    ctx = {"aprovisionado": ip in huellas, "verificado": bool(vigente and prueba.get("estado") == "verificada"),
           "prueba_en": prueba.get("en") if vigente else None}
    cat = _catalogo(srv)
    if vigente and accion_id in cat:
        faltan = set((prueba.get("reglas") or {}).get("faltan") or [])
        texto = lambda r: f"{r[0]} {r[1]}".strip()
        falta = next((texto(cx._norm(b, a)) for b, a in catalogom.reglas({accion_id: cat[accion_id]})
                      if texto(cx._norm(b, a)) in faltan), None)
        if falta:
            ctx["regla_falta"] = falta
    return ctx


def resumen(srv, operador):
    modo = srv.conectividad_modo()
    ajustes = cx.cargar(srv.ruta_conectividad) if srv.ruta_conectividad else {"usuario_defecto": None, "equipos": {}}
    clave, huellas = _clave_conector(srv, modo), {}        # la PÚBLICA: la privada no se lee nunca
    destino = None if _desactivada() else _destino_claves(modo)
    if _desactivada():
        clave = None
    alcanzable = False
    if destino:
        correr = srv.conectividad_correr(destino)
        rc3, kh = correr(["cat", conector.SSH_KNOWN_HOSTS])
        huellas = cx.huellas_fijadas(kh) if rc3 == 0 else {}
        alcanzable = modo in _MODOS_EDITABLES or correr(["true"])[0] == 0
        _limpiar_rotacion_huerfana(srv, correr, operador)
    defecto = ajustes.get("usuario_defecto")
    equipos = []
    for e in _equipos(srv):
        aj = ajustes["equipos"].get(e["ip"]) or {}
        equipos.append({**e, "puerto": aj.get("puerto") or 22, "usuario": aj.get("usuario") or defecto or conector.SSH_USUARIO,
                        "ajustado": bool(aj), "huella_fijada": huellas.get(e["ip"]),
                        "ultima_prueba": (lambda p: p if _vigente(p, clave, huellas.get(e["ip"])) else None)(
                            srv.conectividad_pruebas.get(e["ip"])),
                        "operativo": srv.conectividad_operativo.get(e["ip"]),
                        "sin_acceso": fallos.sin_acceso(e["ip"])})
    puede, motivo = _permisos(srv, operador, modo)
    falta_clave = clave is None and alcanzable
    if falta_clave:
        puede, motivo = False, "falta la clave del conector: genérala para empezar"
    cat = _catalogo(srv)
    perfil = srv.perfil or {}
    return {"modo": modo, "nodo_gestion": conector.nodo_gestion() if modo == "clave" else None,
            "editable": puede, "motivo_no_editable": motivo,
            "permisos": {"probar": puede, "editar": puede, "motivo": motivo,
                         "generar_clave": falta_clave and _puede_editar(srv, operador) and bool(srv.ruta_conectividad)},
            "falta_clave": falta_clave,
            "usuario_defecto": defecto, "usuario_entorno": conector.SSH_USUARIO,
            "ruta_clave": conector.SSH_CLAVE, "known_hosts": conector.SSH_KNOWN_HOSTS,
            "clave": clave, "equipos": equipos, "cambios": _cambios(srv),
            "papeles": [{"id": k, **v} for k, v in catalogom.PAPELES.items()],
            "acciones": [{"id": k, "comando": (v.get("comando") or "").split(";")[0].strip(), "nunca_automatica": bool(v.get("nunca_automatica")),
                          "lista": (catalogom.ACCION_CON_LISTA.get(k) or (None, None))[1]} for k, v in cat.items()],
            "zonas": inv.zonas(perfil), "activos": sorted((perfil.get("activos") or {}).keys()),
            "criticidades": list(inv.CRITICIDADES), "rotacion": _rotacion_vista(srv)}


def _equipo(srv, nombre):
    return next((e for e in _equipos(srv) if e["nombre"] == nombre), None) if isinstance(nombre, str) else None


def _auditar(srv, operador, dimension, clave, antes, despues):
    """Cada prueba, alta o cambio queda en el registro de Conectividad y, si el daemon lo da, también
    en la traza encadenada y firmada (no se puede borrar sin que se note)."""
    if srv.ruta_auditoria_conectividad:
        politica_store.registrar_auditoria(srv.ruta_auditoria_conectividad, operador, dimension, clave, antes, despues)
    estado = getattr(srv, "estado", None)
    if estado is not None:
        estado.auditar_en_traza({"id_decision": f"conectividad~{_ahora()}", "tipo": "auditoria_conectividad",
                                 "timestamp": _ahora(), "operador": operador, "dimension": dimension,
                                 "clave": clave, "antes": antes, "despues": despues})


def _candidatos(srv, e, cuerpo):
    """(usuario, puerto) a probar: lo que viene en el cuerpo (None = quitar el ajuste) o lo guardado."""
    ajustes = cx.cargar(srv.ruta_conectividad) if srv.ruta_conectividad else {"usuario_defecto": None, "equipos": {}}
    aj = ajustes["equipos"].get(e["ip"]) or {}
    puerto = cx.validar_puerto(cuerpo["puerto"]) if "puerto" in cuerpo else aj.get("puerto")
    usuario = cx.validar_usuario(cuerpo["usuario"]) if "usuario" in cuerpo else aj.get("usuario")
    return ajustes, usuario, puerto


def _efectivo(srv, usuario):
    ajustes = cx.cargar(srv.ruta_conectividad) if srv.ruta_conectividad else {}
    return usuario or ajustes.get("usuario_defecto") or conector.SSH_USUARIO


def _probar(srv, modo, e, usuario, puerto, operador=None):
    from prototipo.accion.conector import ahora_iso
    efectivo = _efectivo(srv, usuario)
    esperadas = _esperadas(srv, e)
    listar = srv.conectividad_ejecutor(modo, usuario=efectivo, puerto=puerto or 22, sudo=False) if esperadas else None
    r = cx.probar(srv.conectividad_ejecutor(modo, usuario=efectivo, puerto=puerto or 22), e["ip"],
                  permitido=_permitido(esperadas), listar=listar, esperadas=esperadas)
    # con qué claves se hizo: si cambian (laboratorio recreado, rotación, otra clave del host), deja de valer
    rc, kh = srv.conectividad_correr(modo)(["cat", conector.SSH_KNOWN_HOSTS])
    r = {**r, "en": ahora_iso(), "puerto": puerto or 22, "usuario": efectivo, "por": operador,
         "clave_conector": ((_clave_conector(srv, modo) or {}).get("huella")),
         "huella_host": (cx.huellas_fijadas(kh) if rc == 0 else {}).get(e["ip"])}
    with _lock:
        srv.conectividad_pruebas[e["ip"]] = r
        if r.get("estado") == "verificada":
            srv.conectividad_operativo.pop(e["ip"], None)    # una prueba correcta quita el aviso
        try:
            cx.guardar_pruebas(srv.ruta_pruebas, srv.conectividad_pruebas)
        except OSError:
            pass                    # la prueba vale aunque no se pueda guardar en disco
    return r


def _frenar(srv, que, ip):
    """Segundos que faltan para poder repetir `que` sobre `ip` (0 = adelante, y se anota)."""
    ahora = time.monotonic()
    with _lock:
        antes = srv.conectividad_ultimo.get((que, ip))
        if antes is not None and ahora - antes < FRENO_S:
            return max(1, int(FRENO_S - (ahora - antes) + 0.999))
        srv.conectividad_ultimo[(que, ip)] = ahora
    return 0


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def post(srv, ruta, cuerpo, operador):
    """(estado_http, cuerpo) para los POST de conectividad."""
    if _desactivada():
        return 403, {"error": DESACTIVADA}
    if not isinstance(cuerpo, dict):
        return 400, {"error": "cuerpo invalido"}
    modo = srv.conectividad_modo()
    if ruta == "/api/conectividad/clave-conector":
        return _post_clave_conector(srv, modo, cuerpo, operador)
    puede, motivo = _permisos(srv, operador, modo)
    if not puede:
        # FAIL-CLOSED: sin operador identificado ni opt-in no se abre ninguna conexión ni se cambia nada
        codigo = 403 if motivo and "operador" in motivo else 409
        return codigo, {"error": motivo}
    if ruta == "/api/conectividad/probar":
        e = _equipo(srv, cuerpo.get("equipo"))
        if not e or e["protegido"]:
            return 400, {"error": "equipo desconocido o protegido"}
        try:
            _, usuario, puerto = _candidatos(srv, e, cuerpo)
        except ValueError as ex:
            return 400, {"error": str(ex)}
        espera = _frenar(srv, "probar", e["ip"])
        if espera:
            return 429, {"error": f"espera {espera} s para volver a probar {e['nombre']}", "reintentar_en": espera}
        r = _probar(srv, modo, e, usuario, puerto, operador)
        _auditar(srv, operador, "prueba", e["nombre"], None, {"estado": r["estado"], "reglas": (r.get("reglas") or {}).get("estado")})
        return 200, r
    if ruta == "/api/conectividad/leer-clave-host":
        e = _equipo(srv, cuerpo.get("equipo"))
        if not e or e["protegido"]:
            return 400, {"error": "equipo desconocido o protegido"}
        espera = _frenar(srv, "leer", e["ip"])
        if espera:
            return 429, {"error": f"espera {espera} s para volver a leer {e['nombre']}", "reintentar_en": espera}
        correr = srv.conectividad_correr(modo)
        ajustes = cx.cargar(srv.ruta_conectividad)
        puerto = (ajustes["equipos"].get(e["ip"]) or {}).get("puerto") or 22
        rc, kh = correr(["cat", conector.SSH_KNOWN_HOSTS])
        claves = (cx.claves_de_known_hosts(kh) if rc == 0 else {}).get(e["ip"]) or []
        presentada = cx.huella_presentada(e["ip"], puerto, correr)
        _auditar(srv, operador, "lectura_clave_host", e["nombre"], None, presentada)
        return 200, {"equipo": e["nombre"], "fijada": cx.huellas_fijadas(kh).get(e["ip"]) if rc == 0 else None,
                     "presentada": presentada, "coincide": bool(presentada and presentada in {h for _, h in claves})}
    if ruta == "/api/conectividad/inventario":
        return _post_inventario(srv, cuerpo, operador)
    if ruta == "/api/conectividad/inventario/quitar":
        return _post_quitar(srv, cuerpo, operador)
    if ruta == "/api/conectividad/alta":
        return _post_alta(srv, modo, cuerpo, operador)
    if ruta == "/api/conectividad/rotacion":
        return _post_rotacion(srv, modo, cuerpo, operador)
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
            if antes and antes != huella and cuerpo.get("reemplazar") is not True:
                # Sustituir una clave ya fijada es el caso de una posible suplantación: no basta con la
                # huella, hay que pedirlo explícitamente (la consola lo hace tras su diálogo).
                return 409, {"error": f"{e['nombre']} ya tiene otra clave fijada ({antes}); sustituirla exige "
                                      "confirmarlo explícitamente (reemplazar)"}
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
    prueba = _probar(srv, modo, e, usuario, puerto, operador)
    if not prueba["ok"]:
        return 409, {"guardado": False, "prueba": prueba}
    with _lock:
        ajustes = cx.cargar(srv.ruta_conectividad)
        antes = ajustes["equipos"].get(e["ip"])
        nuevos = cx.con_cambio(ajustes, e["ip"], e["nombre"], puerto, usuario)
        cx.guardar(srv.ruta_conectividad, nuevos)
        _auditar(srv, operador, "equipo", e["nombre"], antes, nuevos["equipos"].get(e["ip"]))
    return 200, {"guardado": True, "prueba": prueba}


# --------------------------------------------------------- clave del conector, desde cero --
def _post_clave_conector(srv, modo, cuerpo, operador):
    """Genera el par de claves del conector cuando NO hay ninguno (un despliegue nuevo, sin el script de
    aprovisionamiento). Si ya hay clave, se cambia con la rotación (que no deja a ningún equipo fuera).
    La privada se crea y se queda donde vive el conector; aquí solo vuelve la pública."""
    if not _puede_editar(srv, operador):
        return 403, {"error": "generar la clave exige un operador identificado por su token"}
    destino = _destino_claves(modo)
    if not destino or not srv.ruta_conectividad:
        return 409, {"error": "el conector está en modo laboratorio (contraseña): no usa clave"}
    if _clave_conector(srv, modo):
        return 409, {"error": "el conector ya tiene clave: para cambiarla, usa la rotación"}
    tipo = cuerpo.get("tipo") or "ed25519"
    if tipo not in ("ed25519", "rsa"):
        return 400, {"error": "tipo: ed25519 o rsa"}
    correr = srv.conectividad_correr(destino)
    import posixpath
    directorio = posixpath.dirname(conector.SSH_CLAVE)
    correr(["mkdir", "-p", directorio])
    correr(["chmod", "700", directorio])
    correr(["rm", "-f", conector.SSH_CLAVE, conector.SSH_CLAVE + ".pub"])     # restos sin pareja (la pública falta)
    args = ["-t", "ed25519"] if tipo == "ed25519" else ["-t", "rsa", "-b", "3072"]
    rc, salida = correr(["ssh-keygen", "-q", *args, "-N", "", "-C", "mdr-conector", "-f", conector.SSH_CLAVE])
    nueva = _clave_conector(srv, modo if modo in _MODOS_EDITABLES else destino)
    if rc != 0 or not nueva:
        return 500, {"error": "no se pudo generar la clave donde vive el conector (¿falta ssh-keygen en el nodo de gestión?)"}
    _auditar(srv, operador, "clave_conector", "generar", None, nueva["huella"])
    return 200, {"clave": nueva}


def _limpiar_rotacion_huerfana(srv, correr, operador):
    """Una rotación en curso cuyo par nuevo ya no existe (laboratorio recreado) se descarta."""
    if not getattr(srv, "ruta_rotacion", None) or not cx.cargar_rotacion(srv.ruta_rotacion):
        return
    if correr(["test", "-f", conector.SSH_CLAVE + ".nueva"])[0] != 0:
        cx.guardar_rotacion(srv.ruta_rotacion, None)
        _auditar(srv, operador, "rotacion", "abandonada", None, "el par nuevo ya no existe")


# ---------------------------------------------------------------- inventario y alta --
def _olvidar_prueba(srv, ip):
    """La última prueba de un equipo deja de valer si cambia su papel (comparaba con otras reglas)."""
    if ip and srv.conectividad_pruebas.pop(ip, None) is not None:
        try:
            cx.guardar_pruebas(srv.ruta_pruebas, srv.conectividad_pruebas)
        except OSError:
            pass


def _post_inventario(srv, cuerpo, operador):
    """Alta de un equipo nuevo (queda PENDIENTE) o cambio del papel y las reglas de uno existente."""
    nombre = cuerpo.get("nombre")
    cat = _catalogo(srv)
    try:
        reglas = inv.validar_reglas(cat, cuerpo)
    except ValueError as ex:
        return 400, {"error": str(ex)}
    with _lock:
        inventario = _inventario(srv)
        previo = inventario["equipos"].get(nombre)
        existente = _equipo(srv, nombre)
        if existente and existente["protegido"]:
            return 400, {"error": "equipo protegido (canal de gestión del MDR): no se configura desde aquí"}
        if existente and not (previo or {}).get("nuevo"):
            nuevo = {**reglas, "nuevo": False}                         # equipo del perfil: solo su papel
        elif previo and previo.get("nuevo") and previo.get("estado") == "activo":
            nuevo = {**previo, **reglas}                               # ya dado de alta: solo su papel
        else:
            otros = {"equipos": {k: v for k, v in inventario["equipos"].items() if k != nombre}}
            try:
                datos = inv.validar_alta(srv._perfil_canonico, otros, cuerpo)
            except ValueError as ex:
                return 400, {"error": str(ex)}
            nuevo = {**datos, **reglas, "nuevo": True, "estado": "pendiente"}
        nuevo = {**nuevo, "actualizado_por": operador, "actualizado_en": _ahora()}
        inventario["equipos"][nombre] = nuevo
        inv.guardar(srv.ruta_inventario, inventario)
        _auditar(srv, operador, "inventario", nombre, previo, nuevo)
        _olvidar_prueba(srv, (existente or {}).get("ip") or nuevo.get("ip"))
    _reaplicar_perfil(srv)
    return 200, {"equipo": nombre, "alta": "pendiente" if nuevo.get("nuevo") and nuevo.get("estado") != "activo" else None}


def _post_quitar(srv, cuerpo, operador):
    """Quita un alta pendiente, o el papel de un equipo (vuelve al catálogo completo)."""
    nombre = cuerpo.get("nombre")
    with _lock:
        inventario = _inventario(srv)
        previo = inventario["equipos"].get(nombre)
        if not previo:
            return 400, {"error": "ese equipo no tiene nada en el inventario operativo"}
        if previo.get("nuevo") and previo.get("estado") == "activo":
            return 409, {"error": "un equipo ya dado de alta no se borra desde aquí: quita su papel, o bórralo de "
                                  f"{os.path.basename(srv.ruta_inventario or 'inventario-operativo.yml')} y reinicia el daemon"}
        del inventario["equipos"][nombre]
        inv.guardar(srv.ruta_inventario, inventario)
        _auditar(srv, operador, "inventario", nombre, previo, None)
        _olvidar_prueba(srv, ((_equipo(srv, nombre) or {}).get("ip")) or previo.get("ip"))
    _reaplicar_perfil(srv)
    return 200, {"equipo": nombre, "quitado": True}


def _post_alta(srv, modo, cuerpo, operador):
    """Pendiente -> activo: exige su clave del host fijada (la huella que se confirma aquí) y la prueba
    completa en verde. Solo entonces el motor puede contener en el equipo."""
    nombre = cuerpo.get("equipo")
    e = _equipo(srv, nombre)
    if not e or e.get("alta") != "pendiente":
        return 400, {"error": "no hay un alta pendiente de ese equipo"}
    correr = srv.conectividad_correr(modo)
    rc, kh = correr(["cat", conector.SSH_KNOWN_HOSTS])
    fijada = (cx.huellas_fijadas(kh) if rc == 0 else {}).get(e["ip"])
    if not fijada or fijada != cuerpo.get("huella"):
        return 409, {"error": "fija antes la clave del host del equipo con la huella que imprimió el paquete"}
    _, usuario, puerto = _candidatos(srv, e, {})
    prueba = _probar(srv, modo, e, usuario, puerto, operador)
    _auditar(srv, operador, "prueba", e["nombre"], None, {"estado": prueba["estado"], "reglas": (prueba.get("reglas") or {}).get("estado")})
    if not prueba["ok"]:
        return 409, {"error": "la prueba no pasa: el alta no se completa", "prueba": prueba}
    with _lock:
        inventario = _inventario(srv)
        previo = inventario["equipos"][nombre]
        inventario["equipos"][nombre] = {**previo, "estado": "activo", "alta_por": operador, "alta_en": _ahora()}
        inv.guardar(srv.ruta_inventario, inventario)
        _auditar(srv, operador, "alta", nombre, "pendiente", "activo")
    _reaplicar_perfil(srv)
    return 200, {"equipo": nombre, "alta": "activo", "prueba": prueba}


def paquete(srv, equipo, formato, operador):
    """GET /api/conectividad/paquete: el paquete de alta (o de corrección) de un equipo."""
    if _desactivada():
        return 403, {"error": DESACTIVADA}
    modo = srv.conectividad_modo()
    if modo not in _MODOS_EDITABLES:
        return 409, {"error": _motivo_no_editable(modo)}
    e = _equipo(srv, equipo)
    if not e or e["protegido"]:
        return 400, {"error": "equipo desconocido o protegido"}
    rc, pub = srv.conectividad_correr(modo)(["cat", conector.SSH_CLAVE + ".pub"])
    ajustes = cx.cargar(srv.ruta_conectividad) if srv.ruta_conectividad else {"usuario_defecto": None, "equipos": {}}
    usuario = (ajustes["equipos"].get(e["ip"]) or {}).get("usuario") or ajustes.get("usuario_defecto") or conector.SSH_USUARIO
    cat = _catalogo(srv)
    reglas = catalogom.reglas_de_equipo(cat, e.get("acciones") if e.get("papel") else None, e.get("servicios"), e.get("cuentas"),
                                        e.get("cuentas_cualquiera") is True)
    generado = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC") + (f" por {operador}" if operador else "")
    try:
        nombre, contenido = cx.paquete(formato, e, usuario, pub if rc == 0 else "", reglas, generado)
    except ValueError as ex:
        return 400, {"error": str(ex)}
    return 200, {"nombre": nombre, "contenido": contenido, "formato": formato}


# --------------------------------------------------------------------------- rotación --
def _contenibles(srv):
    return [e for e in resumen_equipos_con_huella(srv) if not e["protegido"] and e.get("alta") != "pendiente" and e.get("huella_fijada")]


def resumen_equipos_con_huella(srv):
    modo = srv.conectividad_modo()
    rc, kh = srv.conectividad_correr(modo)(["cat", conector.SSH_KNOWN_HOSTS])
    huellas = cx.huellas_fijadas(kh) if rc == 0 else {}
    return [{**e, "huella_fijada": huellas.get(e["ip"])} for e in _equipos(srv)]


def _post_rotacion(srv, modo, cuerpo, operador):
    accion = cuerpo.get("accion")
    correr = srv.conectividad_correr(modo)
    actual, nueva = conector.SSH_CLAVE, conector.SSH_CLAVE + ".nueva"
    estado = cx.cargar_rotacion(srv.ruta_rotacion)
    if accion == "iniciar":
        if estado:
            return 409, {"error": "ya hay una rotación en curso"}
        rc, pub = correr(["cat", actual + ".pub"])
        pub_actual = cx.clave_publica_valida((pub or "").strip().splitlines()[-1] if rc == 0 and pub else "")
        if not pub_actual:
            return 409, {"error": "no se pudo leer la clave pública actual del conector"}
        correr(["rm", "-f", nueva, nueva + ".pub"])
        tipo = ["-t", "ed25519"] if pub_actual.startswith("ssh-ed25519") else ["-t", "rsa", "-b", "3072"]
        rc, out = correr(["ssh-keygen", "-q", *tipo, "-N", "", "-C", "mdr-conector", "-f", nueva])
        rc2, pub2 = correr(["cat", nueva + ".pub"])
        pub_nueva = cx.clave_publica_valida((pub2 or "").strip()) if rc == 0 and rc2 == 0 else None
        if not pub_nueva:
            correr(["rm", "-f", nueva, nueva + ".pub"])
            return 500, {"error": "no se pudo generar el par nuevo en el nodo del conector (¿falta ssh-keygen?)"}
        estado = {"estado": "en_curso", "iniciada_por": operador, "en": _ahora(), "publica_actual": pub_actual,
                  "publica_nueva": pub_nueva, "equipos": {e["nombre"]: {} for e in _contenibles(srv)}}
        cx.guardar_rotacion(srv.ruta_rotacion, estado)
        _auditar(srv, operador, "rotacion", "iniciar", cx.huella_de(pub_actual)[0], cx.huella_de(pub_nueva)[0])
        return 200, {"rotacion": _rotacion_vista(srv)}
    if not estado:
        return 409, {"error": "no hay ninguna rotación en curso"}
    equipos = {e["nombre"]: e for e in _contenibles(srv)}
    filas = estado.setdefault("equipos", {})
    viejo, nuevo = cx.cuerpo_clave(estado["publica_actual"]), cx.cuerpo_clave(estado["publica_nueva"])
    if accion == "preparar":
        for n, e in equipos.items():
            f = filas.setdefault(n, {})
            if f.get("retirada"):
                continue
            _, usuario, puerto = _candidatos(srv, e, {})
            u = _efectivo(srv, usuario)
            if not f.get("anadida"):
                rc, out = srv.conectividad_ejecutor(modo, usuario=u, puerto=puerto or 22, sudo=False, claves=[actual])(
                    e["ip"], cx.cmd_anadir_clave(estado["publica_nueva"]))
                f.update({"anadida": rc == 0, "error": None if rc == 0 else "no se pudo añadir la clave nueva"})
            if f.get("anadida"):
                rc, _ = srv.conectividad_ejecutor(modo, usuario=u, puerto=puerto or 22, claves=[nueva])(
                    e["ip"], _permitido(_esperadas(srv, e)) or cx.COMANDO_PERMITIDO)
                f.update({"probada": rc == 0, "error": None if rc == 0 else "la clave nueva no entra"})
        cx.guardar_rotacion(srv.ruta_rotacion, estado)
        _auditar(srv, operador, "rotacion", "preparar", None, {n: f for n, f in filas.items()})
        return 200, {"rotacion": _rotacion_vista(srv)}
    if accion == "retirar":
        for n, e in equipos.items():
            f = filas.setdefault(n, {})
            if f.get("probada") and not f.get("retirada"):
                _, usuario, puerto = _candidatos(srv, e, {})
                rc, _ = srv.conectividad_ejecutor(modo, usuario=_efectivo(srv, usuario), puerto=puerto or 22, sudo=False,
                                                  claves=[nueva])(e["ip"], cx.cmd_quitar_clave(viejo, nuevo))
                f.update({"retirada": rc == 0, "error": None if rc == 0 else "no se pudo retirar la clave vieja"})
        cx.guardar_rotacion(srv.ruta_rotacion, estado)
        _auditar(srv, operador, "rotacion", "retirar", None, {n: f for n, f in filas.items()})
        return 200, {"rotacion": _rotacion_vista(srv)}
    if accion == "finalizar":
        faltan = [n for n in equipos if not (filas.get(n) or {}).get("retirada")]
        if faltan:
            return 409, {"error": "la clave vieja sigue en algunos equipos: si se finaliza, el conector dejaría de entrar en ellos",
                         "faltan": faltan}
        for a, b in ((actual, actual + ".anterior"), (actual + ".pub", actual + ".anterior.pub"),
                     (nueva, actual), (nueva + ".pub", actual + ".pub")):
            rc, out = correr(["mv", "-f", a, b])
            if rc != 0:
                return 500, {"error": f"no se pudo mover {a}: revisa el nodo del conector"}
        cx.guardar_rotacion(srv.ruta_rotacion, None)
        _auditar(srv, operador, "rotacion", "finalizar", cx.huella_de(estado["publica_actual"])[0], cx.huella_de(estado["publica_nueva"])[0])
        return 200, {"rotacion": None}
    if accion == "cancelar":
        retiradas = [n for n, f in filas.items() if f.get("retirada")]
        if retiradas:
            return 409, {"error": "en algunos equipos ya solo queda la clave nueva: termina la rotación", "retiradas": retiradas}
        for n, e in equipos.items():
            if (filas.get(n) or {}).get("anadida"):
                _, usuario, puerto = _candidatos(srv, e, {})
                srv.conectividad_ejecutor(modo, usuario=_efectivo(srv, usuario), puerto=puerto or 22, sudo=False, claves=[actual])(
                    e["ip"], cx.cmd_quitar_clave(nuevo, viejo))
        correr(["rm", "-f", nueva, nueva + ".pub"])
        cx.guardar_rotacion(srv.ruta_rotacion, None)
        _auditar(srv, operador, "rotacion", "cancelar", None, None)
        return 200, {"rotacion": None}
    return 400, {"error": "accion desconocida"}
