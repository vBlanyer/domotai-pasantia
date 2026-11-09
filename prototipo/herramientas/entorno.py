"""Lee y escribe /etc/mdr/triaje.env, el EnvironmentFile del servicio, sin romperlo.

systemd no entiende el fichero como un shell: no quita un comentario al final de la línea y solo
quita las comillas que envuelven el valor entero. Por eso aquí cada variable va en su línea, los
comentarios en la suya, y un valor con caracteres especiales (el JSON de los operadores) va entre
comillas simples. Al escribir se conserva todo lo demás: comentarios, orden y variables ajenas.
"""
import json
import os
import re
import tempfile

_LINEA = re.compile(r"^(#?)\s*([A-Z][A-Z0-9_]*)=(.*)$")
_SIMPLE = re.compile(r"^[A-Za-z0-9_./:,@+=-]*$")


def _sin_comillas(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


def leer(ruta):
    """{VARIABLE: valor} de las líneas activas (las comentadas no cuentan)."""
    valores = {}
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                m = _LINEA.match(linea.rstrip("\n"))
                if m and not m.group(1):
                    valores[m.group(2)] = _sin_comillas(m.group(3))
    except FileNotFoundError:
        pass
    return valores


def _formato(clave, valor):
    if any(c in valor for c in "\n'#"):
        raise ValueError(f"{clave}: el valor no puede llevar saltos de línea, comillas simples ni «#»")
    return f"{clave}={valor}" if _SIMPLE.match(valor) else f"{clave}='{valor}'"


def escribir(ruta, cambios):
    """Aplica `cambios` ({VARIABLE: valor | None}) a `ruta`: cambia la línea activa, o descomenta la
    de la plantilla, o la añade al final; None la deja comentada. Escribe de una vez, en 0600."""
    pendientes = {k: (None if v is None else _formato(k, str(v))) for k, v in cambios.items()}
    try:
        with open(ruta, encoding="utf-8") as f:
            lineas = f.read().splitlines()
    except FileNotFoundError:
        lineas = []
    activas = {m.group(2) for m in map(_LINEA.match, lineas) if m and not m.group(1)}
    salida = []
    for linea in lineas:
        m = _LINEA.match(linea)
        if m and m.group(2) in pendientes:
            clave, comentada = m.group(2), bool(m.group(1))
            if comentada and clave in activas:          # la de la plantilla, con otra activa: se queda
                salida.append(linea)
                continue
            nueva = pendientes.pop(clave)
            salida.append(nueva if nueva is not None else (linea if comentada else f"#{clave}="))
            continue
        salida.append(linea)
    salida += [v for v in pendientes.values() if v is not None]
    d = os.path.dirname(os.path.abspath(ruta))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".triaje-env-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(salida) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def operadores(valores):
    """{token: nombre} de TRIAJE_CONSOLA_OPERADORES. ValueError si el JSON está roto."""
    texto = valores.get("TRIAJE_CONSOLA_OPERADORES")
    if not texto:
        return {}
    ops = json.loads(texto)
    if not isinstance(ops, dict):
        raise ValueError("TRIAJE_CONSOLA_OPERADORES no es un objeto JSON {token: nombre}")
    return ops
