"""Tras rehacer el laboratorio del banco (servicio-mdr.sh, en cada encendido), las contenciones que la
traza daba por activas ya no existen: los equipos se recrearon desde cero. Se anotan como revertidas en
la misma cadena, para que el MDR vuelva a decidir los ataques repetidos y la consola no muestre
contenciones fantasma.

    python3 -m lab.banco.rehecho <traza.jsonl>
"""
import os
import sys

from prototipo.accion import catalogo as catm, revertir

MOTIVO = "laboratorio rehecho: los equipos se recrearon desde cero al arrancar"


def main(argv):
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cat = catm.cargar_catalogo(os.path.join(raiz, "prototipo", "catalogo.yml"))
    n = revertir.anotar_desaparecidas(argv[0], cat, MOTIVO)
    print(f"laboratorio rehecho: {n} contención(es) de la traza anotadas como revertidas")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
