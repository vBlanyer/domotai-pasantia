"""Órdenes de mdr para la política de la empresa (politica.yml).

    mdr validar-politica [politica.yml]     revisa el fichero contra el perfil; código 1 si no es válida
    mdr explicar-politica [politica.yml]    la política efectiva, en frases (lo que firma Seguridad)
    mdr migrar-politica                     saca del perfil las reglas de política a un politica.yml nuevo

Por defecto usan TRIAJE_POLITICA y TRIAJE_PERFIL. Plan:
documentacion/05-fase5-implementacion-del-prototipo/plan-politica-empresa.md (tarea 3).
"""
import argparse, os, shutil, sys, tempfile
from datetime import date

import yaml

from prototipo.accion import catalogo as catm
from prototipo.motor import perfil as perfilm
from prototipo.motor import politica_empresa as pe

_CATALOGO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "catalogo.yml")


def _yaml(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _overlay(env):
    """Cambios hechos en la consola (politica-operativa.yml, junto a la traza)."""
    salida = env.get("TRIAJE_SALIDA")
    ruta = os.path.join(os.path.dirname(salida), "politica-operativa.yml") if salida else None
    if not ruta or not os.path.isfile(ruta):
        return {}
    try:
        return _yaml(ruta)
    except (OSError, yaml.YAMLError):
        return {}


def _n_cambios(overlay):
    return sum(len((overlay or {}).get(d) or {}) for d in ("automatizacion_por_familia", "politicas_por_zona",
                                                           "overrides_por_activo"))


def linea_estado(env, perfil):
    """La línea «política» de `mdr estado`."""
    ruta = env.get("TRIAJE_POLITICA")
    if not ruta:
        return {"tema": "política", "nivel": "ok", "texto": "sin politica.yml: las reglas están en el perfil",
                "remedio": ""}
    if not os.path.isfile(ruta):
        return {"tema": "política", "nivel": "fallo", "texto": f"no existe {ruta}: el servicio no arrancará",
                "remedio": "sudo mdr migrar-politica  (o quita TRIAJE_POLITICA)"}
    try:
        pol = _yaml(ruta)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        return {"tema": "política", "nivel": "fallo", "texto": f"no se puede leer: {type(e).__name__}",
                "remedio": "sudo mdr validar-politica"}
    avisos = pe.validar_politica(pol, perfil or {}, catm.cargar_catalogo(_CATALOGO)) if perfil is not None else []
    if avisos:
        return {"tema": "política", "nivel": "fallo", "texto": f"no es válida ({len(avisos)} aviso(s)): el servicio no arrancará",
                "remedio": "sudo mdr validar-politica"}
    cab = pe.cabecera(pol)
    texto = f"versión {cab.get('version', '?')} · aprobada por {cab.get('aprobada_por') or '(sin indicar)'}"
    try:
        base = pe.fusionar_perfil_y_politica(perfil or {}, pol)
    except ValueError as e:                    # solo sin perfil legible: la validación no pudo cruzarlos
        return {"tema": "política", "nivel": "fallo", "texto": str(e), "remedio": "sudo mdr validar-politica"}
    n = _n_cambios(perfilm.overlay_efectivo(base, _overlay(env)))
    if n:
        return {"tema": "política", "nivel": "aviso",
                "texto": f"{texto} · {n} cambio{'s' if n != 1 else ''} de consola sin pasar al fichero",
                "remedio": "en la consola, Políticas → «Exportar propuesta», y que Seguridad la apruebe"}
    return {"tema": "política", "nivel": "ok", "texto": texto, "remedio": ""}


def _validar(a, env):
    ruta = a.politica or env.get("TRIAJE_POLITICA")
    if not ruta:
        print("indica el fichero (o fija TRIAJE_POLITICA)")
        return 1
    pol, perfil = _yaml(ruta), _yaml(a.perfil)
    avisos = pe.validar_politica(pol, perfil, catm.cargar_catalogo(_CATALOGO))
    if avisos:
        print(f"{ruta}: la política no es válida:")
        print("\n".join(f"  - {x}" for x in avisos))
        return 1
    cab = pe.cabecera(pol)
    print(f"{ruta}: política válida (versión {cab.get('version', '?')}, aprobada por {cab.get('aprobada_por') or '(sin indicar)'})")
    return 0


def _explicar(a, env):
    ruta = a.politica or env.get("TRIAJE_POLITICA")
    perfil = _yaml(a.perfil)
    cat = catm.cargar_catalogo(_CATALOGO)
    if ruta:
        pol = _yaml(ruta)
        avisos = pe.validar_politica(pol, perfil, cat)
        if avisos:
            print("la política no es válida; corrígela antes (mdr validar-politica)")
            return 1
        perfil = pe.fusionar_perfil_y_politica(perfil, pol)
        cab = pe.cabecera(pol)
        print(f"Política versión {cab.get('version', '?')}, aprobada por {cab.get('aprobada_por') or '(sin indicar)'}.")
    else:
        print("Sin politica.yml: las reglas vienen del perfil.")
    overlay = perfilm.overlay_efectivo(perfil, _overlay(env))
    if _n_cambios(overlay):
        perfil = perfilm.fusionar_politicas(perfil, overlay)
        print(f"Incluye {_n_cambios(overlay)} cambio(s) hecho(s) en la consola (solo endurecen).")
    print()
    for frase in pe.explicar(perfil, cat):
        print(f"- {frase}")
    return 0


def _escribir_atomico(ruta, datos):
    """Temporal en el mismo directorio + os.replace: un corte a medias no deja el fichero roto."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(ruta)), prefix=".mdr-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(datos, f, allow_unicode=True, sort_keys=False)
        if os.path.exists(ruta):
            shutil.copymode(ruta, tmp)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _migrar(a, env):
    if os.path.exists(a.salida):
        print(f"{a.salida} ya existe: no se pisa. Bórralo o indica otra salida.")
        return 1
    copia = a.perfil + ".antes-de-migrar"
    if os.path.exists(copia):
        print(f"{copia} ya existe (¿una migración anterior?): no se pisa. Muévelo antes de repetir.")
        return 1
    perfil = _yaml(a.perfil)
    pol, resto = pe.extraer_politica(perfil)
    if not pol:
        print("el perfil no tiene reglas de política que migrar")
        return 1
    pol = {"politica": {"version": 1, "aprobada_por": "[pendiente de aprobación]", "fecha": date.today().isoformat()}, **pol}
    # Antes de tocar nada: la política resultante debe ser válida y, junto al perfil recortado, decir
    # exactamente lo mismo que el perfil de partida.
    avisos = pe.validar_politica(pol, resto, catm.cargar_catalogo(_CATALOGO))
    if not avisos and pe.fusionar_perfil_y_politica(resto, pol) != perfil:
        avisos = ["el perfil recortado y la política no equivalen al perfil de partida"]
    if avisos:
        print("No se migra: la política resultante no sería válida (corrige el perfil y repite):")
        print("\n".join(f"  - {x}" for x in avisos))
        return 1
    shutil.copy2(a.perfil, copia)
    _escribir_atomico(a.salida, pol)
    _escribir_atomico(a.perfil, resto)
    print(f"política -> {a.salida}\nperfil sin las reglas de política -> {a.perfil} (copia: {copia})")
    print("Los comentarios del perfil no se conservan (están en la copia).")
    if env.get("TRIAJE_POLITICA") != a.salida:
        print(f"IMPORTANTE: fija TRIAJE_POLITICA={a.salida} en /etc/mdr/triaje.env y reinicia el servicio. "
              "Hasta entonces, si el servicio se reinicia, arranca SIN estas reglas (todo espera a un analista "
              "y no se reconocen los orígenes legítimos).")
    else:
        print("Reinicia el servicio para aplicarla.")
    return 0


def main(argv=None, env=None):
    env = os.environ if env is None else env
    ap = argparse.ArgumentParser(prog="mdr", description="política de la empresa (politica.yml)")
    sub = ap.add_subparsers(dest="orden", required=True)
    for nombre in ("validar", "explicar"):
        p = sub.add_parser(nombre)
        p.add_argument("politica", nargs="?")
        p.add_argument("--perfil", default=env.get("TRIAJE_PERFIL"))
    p = sub.add_parser("migrar")
    p.add_argument("--perfil", default=env.get("TRIAJE_PERFIL"))
    p.add_argument("--salida", default=env.get("TRIAJE_POLITICA") or "/etc/mdr/politica.yml")
    a = ap.parse_args(argv)
    if not a.perfil and getattr(a, "politica", None):
        # lo habitual: perfil.yml junto a la política (run/banco-nuevo/, /etc/mdr/)
        junto = os.path.join(os.path.dirname(os.path.abspath(a.politica)), "perfil.yml")
        if os.path.isfile(junto):
            a.perfil = junto
            print(f"perfil: {junto} (el que está junto a la política)")
    if not a.perfil:
        print("indica el perfil (--perfil o TRIAJE_PERFIL)")
        return 1
    try:
        return {"validar": _validar, "explicar": _explicar, "migrar": _migrar}[a.orden](a, env)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        print(f"no se puede leer: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
