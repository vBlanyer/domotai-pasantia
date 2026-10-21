"""Ciclo de vida del caso: el analista anota, asigna y cambia el estado de una decisión.

Como la traza es append-only y encadenada por hash (RF-09), un cambio de caso NO muta el registro de
la decisión —eso rompería la cadena—, sino que añade un registro NUEVO `actualizacion_caso` que la
referencia (igual que el veredicto o la reversión). El estado "actual" de un caso se PLIEGA de esos
registros: el último estado/asignado y la lista de notas en orden. Módulo PURO (sin E/S)."""
import re

ESTADOS = ("nuevo", "en_revision", "resuelto")   # 'nuevo' es el estado implícito de toda decisión
_TOPE_NOTA = 500
_TOPE_CAMPO = 64


def _limpiar(t, tope=_TOPE_NOTA):
    """Colapsa espacios/saltos de línea y acota la longitud: los campos de caso pueden venir del
    navegador, así que se tratan como DATOS (no rompen la línea JSON de la traza ni crecen sin fin)."""
    return re.sub(r"\s+", " ", str(t if t is not None else "")).strip()[:tope]


def construir_actualizacion(id_decision, estado=None, asignado=None, nota=None, operador=None, ts=None):
    """Registro `actualizacion_caso` para añadir a la cadena. `estado` ∈ ESTADOS o None; `nota` y
    `asignado` se sanean. Lanza ValueError si el estado no es válido o si no hay NADA que actualizar
    (ni estado, ni nota, ni asignado): así una pulsación vacía no ensucia la traza."""
    if estado is not None and estado not in ESTADOS:
        raise ValueError(f"estado no válido: {estado!r} (debe ser uno de {ESTADOS})")
    nota_l = _limpiar(nota) if nota else None
    asig_l = _limpiar(asignado, _TOPE_CAMPO) if asignado else None
    if not (estado or nota_l or asig_l):
        raise ValueError("actualización de caso vacía: nada que anotar")
    return {"tipo": "actualizacion_caso",
            # Acotado: el id viene del cuerpo HTTP (hasta 64 KiB) y los reales (sN/dN) son cortos;
            # sin tope, registros huérfanos gigantes hinchaban la cadena (M5-relacionado).
            "id_decision": _limpiar(str(id_decision), _TOPE_CAMPO) if id_decision else None,
            "estado": estado, "asignado": asig_l, "nota": nota_l,
            "operador": _limpiar(operador, _TOPE_CAMPO) or None, "decidido_en": ts}


def estado_de_casos(registros):
    """Pliega los registros `actualizacion_caso` en el estado actual por `id_decision`:
    {id_decision: {estado, asignado, notas: [{texto, operador, decidido_en}], actualizado_en}}.
    Una decisión sin ninguna actualización NO aparece (su estado implícito es 'nuevo')."""
    casos = {}
    for r in registros:
        if r.get("tipo") != "actualizacion_caso":
            continue
        idd = r.get("id_decision")
        if not idd:
            continue
        c = casos.setdefault(idd, {"estado": "nuevo", "asignado": None, "notas": []})
        if r.get("estado"):
            c["estado"] = r["estado"]
        if r.get("asignado"):
            c["asignado"] = r["asignado"]
        if r.get("nota"):
            c["notas"].append({"texto": r["nota"], "operador": r.get("operador"),
                               "decidido_en": r.get("decidido_en")})
        c["actualizado_en"] = r.get("decidido_en")
    return casos
