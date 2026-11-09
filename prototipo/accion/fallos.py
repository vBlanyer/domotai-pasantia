"""Por qué falló una contención (PLAN-MANEJO-FALLOS-CONTENCION.md, sección 3).

Clasifica la salida REAL de ssh/sudo/el comando en una clase F1..F10 con evidencia inequívoca, en orden:
la primera que encaja gana y lo que no encaja es F10 (desconocido), que se trata exactamente como hasta
ahora. Regla que manda: ANTE LA DUDA, LO MÁS GRAVE. La clasificación solo AÑADE información; no decide
ejecutar, escalar ni dar nada por contenido.

«Regresión» = el equipo estaba verificado con la clave actual del conector y su clave del host actual
(última prueba vigente). La misma evidencia es configuración si el equipo nunca funcionó y una ANOMALÍA
si funcionaba y dejó de hacerlo (posible ataque: el atacante corta al SOC, quita la clave del conector
o cambia el sudoers). F3 (clave del host cambiada) y F8 (se ejecutó pero no está) nunca son
configuración.

Los patrones salen de salidas capturadas en el laboratorio (lab/banco/fallos.py capturar →
prototipo/tests/fixtures/fallos_conector.json), no de la documentación. El conector antepone LC_ALL=C
al comando remoto para que sudo no traduzca sus mensajes.
"""
import os
import re

# clase -> (descripción corta, qué hacer, posible ataque siempre)
CLASES = {
    "F1": ("orden rechazada antes de salir", "revisa la alerta: un parámetro no era válido", False),
    "F2": ("equipo sin aprovisionar", "dalo de alta o fija su clave del host en Conectividad", False),
    "F3": ("la clave del host cambió", "posible suplantación del equipo: compruébalo por otro canal antes de aceptar la clave", True),
    "F4": ("el equipo no acepta la clave del conector", "ejecuta su paquete de alta en Conectividad", False),
    "F5": ("equipo inalcanzable", "comprueba que el equipo y sshd están en marcha y que la red llega", False),
    "F6": ("sudo deniega la acción", "revisa el papel del equipo y su sudoers en Conectividad", False),
    "F7": ("la acción falló dentro del equipo", "revisa la salida del comando", False),
    "F8": ("se aplicó pero no está", "posible contramedida: alguien pudo deshacer la contención", True),
    "F9": ("el conector no tiene clave", "genera la clave del conector en Conectividad", False),
    "F10": ("causa no identificada", "revisa la salida en bruto", False),
}

_PATRONES = (
    ("F3", (r"REMOTE HOST IDENTIFICATION HAS CHANGED", r"Host key for \S+ has changed")),
    # «Host key verification failed» suelto: no es conocida o no cuadra; con huella fijada sube a F3
    ("F2", (r"No \S+ host key is known for", r"Host key verification failed")),
    ("F4", (r"Permission denied \(publickey",)),
    ("F5", (r"Connection refused", r"timed out", r"No route to host", r"Host is unreachable",
            r"Network is unreachable", r"Could not resolve hostname", r"Connection closed", r"Connection reset by",
            r"sin respuesta en \d+ s")),
    ("F6", (r"a password is required", r"is not allowed to execute", r"may not run sudo", r"usual lecture",
            r"no password was provided", r"incorrect password attempt", r"no tty present")),
)
_REGRESION = {"F4", "F5", "F6"}     # con el equipo verificado, dejan de ser configuración


def patron(salida):
    """La clase cuyo texto aparece en la salida de ssh/sudo, o None. Es la ÚNICA lista de patrones: la
    prueba de conexión de Conectividad (conectividad.diagnosticar) la usa también."""
    for clase, pats in _PATRONES:
        if any(re.search(p, salida or "", re.I) for p in pats):
            return clase
    return None


def clasificar_fallo(ejecucion, verificacion=None, contexto=None):
    """{clase, descripcion, accion, posible_ataque, regresion, evidencia} de una contención que NO quedó
    contenida, o None si se ejecutó y se verificó. `ejecucion` es el registro de conector.ejecutar_orden;
    `contexto` lo que sabe la consola del equipo: {aprovisionado, verificado, regla_falta}."""
    ej = ejecucion or {}
    ctx = contexto or {}
    verificado = (verificacion or {}).get("verificado")
    if ej.get("exito") and verificado is not False:
        return None
    rc, salida = ej.get("codigo_salida"), ej.get("salida") or ""
    clase = None
    if ej.get("omitido") == "sin_aprovisionar":
        clase = "F2"            # no se intentó: la consola sabe que el equipo no tiene su clave del host fijada
    elif ej.get("omitido") == "sin_acceso":
        clase = ej.get("clase_memoria") if ej.get("clase_memoria") in ("F4", "F5") else "F5"   # memoria de fallos
    elif rc == -1 and "rechazado" in salida:
        clase = "F1"
    elif rc == 126 and "sin configurar" in salida:
        clase = "F9"
    else:
        clase = patron(salida)
        if clase == "F2" and ctx.get("aprovisionado"):
            clase = "F3"        # dice «no conocida» pero la consola SÍ tiene su huella: algo no cuadra con la clave
        if clase is None:
            if ej.get("exito") or rc == 0:
                clase = "F8"    # entró, ejecutó sin error y la verificación no la encuentra
            elif rc in (255, 124):
                clase = "F10"   # fallo de transporte sin texto reconocible: como hasta ahora
            elif isinstance(rc, int) and rc > 0:
                clase = "F7"
            else:
                clase = "F10"
    regresion = bool(ctx.get("verificado")) and clase in _REGRESION
    descripcion, accion, ataque = CLASES[clase]
    if clase == "F6" and ctx.get("regla_falta"):
        descripcion, accion = "acción no ejecutable en este equipo", f"falta en su sudoers: {ctx['regla_falta']} (binario no instalado o fuera de su papel)"
    elif regresion:
        descripcion = {"F4": "el equipo dejó de aceptar la clave del conector",
                       "F5": "el MDR perdió el acceso a un equipo que funcionaba",
                       "F6": "sudo deniega algo que el equipo permitía (el sudoers cambió)"}[clase]
        accion = "posible ataque: compruébalo antes de reaprovisionar"
    # la línea que decidió la clase (F2 y F3 terminan igual: «Host key verification failed.»); si no
    # la hay, la última con texto
    pats = dict(_PATRONES).get("F2" if clase == "F3" and patron(salida) == "F2" else clase, ())
    lineas = [l.strip() for l in salida.splitlines() if l.strip()]
    evidencia = next((l for l in lineas if any(re.search(p, l, re.I) for p in pats)), lineas[-1] if lineas else "")
    return {"clase": clase, "descripcion": descripcion, "accion": accion,
            "posible_ataque": ataque or regresion, "regresion": regresion, "evidencia": evidencia[:300]}


def interruptor(nombre):
    """Los recortes de la fase 4 van con su variable, apagados por defecto hasta validarlos."""
    return os.environ.get(nombre) == "1"


def no_entro(rc, salida):
    """La conexión no llegó a entrar en el equipo (F2..F5) o el conector no tiene clave (F9): ahí no pudo
    cambiar nada, así que repetir contra el mismo equipo solo cuesta tiempo. F6 (sudo deniega) SÍ entró
    y sigue la secuencia completa, igual que F7 y F8."""
    if rc == 0:
        return False
    if rc == 126 and "sin configurar" in (salida or ""):
        return True
    return patron(salida) in ("F2", "F3", "F4", "F5")


def se_ejecuto(causa):
    """Si la orden llegó a ejecutarse en el equipo (F7: falló dentro; F8: se aplicó y no está). En el
    resto ni se entró o sudo no la dejó correr: decir «NO verificada» ahí confunde."""
    return bool(causa) and causa.get("clase") in ("F7", "F8")


def texto(causa, equipo=None):
    """Una línea para la consola: lo que puede ser un ataque lo dice primero, luego dónde, qué pasó y qué
    hacer. F3 y F8 llevan su propia descripción: nunca un texto de configuración."""
    if not causa:
        return ""
    pre = "POSIBLE ATAQUE · " if causa.get("posible_ataque") else ""
    donde = f"{equipo}: " if equipo else ""
    return f"{pre}{donde}{causa.get('descripcion')} — {causa.get('accion')}"


# ---------------------------------------------------------------- contexto de la consola --
# La consola (servicio/conectividad_web) sabe si un equipo está aprovisionado y verificado. El lazo y la
# escalada la consultan a través de este registro, para no depender de la capa de servicio. Sin
# proveedor (pruebas, lote) el contexto es vacío y la clasificación es la más conservadora.
_proveedor = None


def configurar_contexto(fn):
    global _proveedor
    _proveedor = fn


def contexto(ip, accion_id=None):
    if _proveedor is None:
        return {}
    try:
        return _proveedor(ip, accion_id) or {}
    except Exception:
        return {}       # un fallo al consultar la consola nunca rompe una contención


# Y al revés (fase 3): cada contención real le cuenta a la consola cómo fue en cada equipo, para que
# Conectividad no siga enseñando «verificada» un equipo en el que las contenciones fallan. `causa` None =
# contenida y verificada ahí. Solo informa: un fallo del observador nunca rompe una contención.
_observador = None


def configurar_observador(fn):
    global _observador
    _observador = fn


def observar(ip, causa):
    if not ip:
        return
    if interruptor("TRIAJE_MEMORIA_FALLOS"):
        try:
            from prototipo.accion import memoria_fallos
            memoria_fallos.registrar(ip, causa)
        except Exception:
            pass
    if _observador is None:
        return
    try:
        _observador(ip, causa)
    except Exception:
        pass


def sin_acceso(ip):
    """Con TRIAJE_MEMORIA_FALLOS, {clase, desde, …} si la memoria dice que el MDR no tiene acceso a `ip`
    (3 fallos F4/F5 seguidos): no se intenta ahí. Si no, None y se intenta como siempre."""
    if not ip or not interruptor("TRIAJE_MEMORIA_FALLOS"):
        return None
    from prototipo.accion import memoria_fallos
    return memoria_fallos.abierta(ip)
