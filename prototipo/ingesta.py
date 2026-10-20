"""Módulo de ingesta y normalización (RF-01): lee alertas de la fuente del cliente y las lleva al
esquema común del motor, tolerando campos ausentes. Es **agnóstico de fabricante** (RNF-06): el
conocimiento de la fuente vive en un *adaptador* inyectable (`cruda -> dict`); Wazuh es el implementado,
y el sistema de la empresa entraría como segunda fuente por el mismo módulo.
"""
import json, sys
from prototipo import adaptador_wazuh

# Registro de adaptadores por nombre de fuente. Una segunda fuente se añade aquí.
ADAPTADORES = {"wazuh": adaptador_wazuh.adaptador}

# Campos sin los cuales la alerta no es accionable; su ausencia se avisa, no se inventa (RNF-07).
CRITICOS = ("id_alerta", "activo", "origen_ip", "regla_id")

def normalizar(cruda, adaptador):
    """Aplica un adaptador (`cruda -> dict`) a una alerta cruda. El núcleo no conoce la fuente."""
    return adaptador(cruda)

def campos_ausentes(reg):
    """Nombres de los campos críticos ausentes (None o vacíos). No muta el registro ni infiere nada."""
    return [c for c in CRITICOS if not reg.get(c)]

def parsear_linea(linea):
    """Línea JSONL -> objeto, o None si está vacía o no parsea. La política de tolerancia vive aquí
    para TODAS las fronteras de entrada: además del JSON corrupto, un anidamiento hostil ('['*60000,
    bajo el tope de 1 MiB) lanza RecursionError y debe descartarse igual, no tumbar el proceso."""
    linea = (linea or "").strip()
    if not linea:
        return None
    try:
        return json.loads(linea)
    except (json.JSONDecodeError, RecursionError):
        return None

def ingerir_fichero(ruta, adaptador):
    """Lee un fichero JSONL de alertas crudas y devuelve la lista normalizada. Salta líneas vacías o
    corruptas sin romper el fichero (formato JSONL)."""
    regs = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            cruda = parsear_linea(linea)
            if cruda is None:
                continue
            reg = normalizar(cruda, adaptador)
            if reg is not None:            # el adaptador descarta la telemetria propia
                regs.append(reg)
    return regs

def main(argv):
    ruta, salida = argv[1:3]
    fuente = argv[3] if len(argv) > 3 else "wazuh"
    campaña = argv[4] if len(argv) > 4 else ""
    if fuente not in ADAPTADORES:
        print(f"fuente desconocida: {fuente}. Disponibles: {', '.join(ADAPTADORES)}")
        return 1
    adaptador = ADAPTADORES[fuente](campaña)
    regs = ingerir_fichero(ruta, adaptador)
    with open(salida, "w", encoding="utf-8") as f:
        for r in regs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    incompletas = sum(1 for r in regs if campos_ausentes(r))
    print(f"{len(regs)} alertas normalizadas -> {salida}"
          + (f" ({incompletas} con campos criticos ausentes)" if incompletas else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
