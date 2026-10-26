"""Contrato de imports entre capas (la reorg del 26/10 convertida en garantía).

La matriz permite importar HACIA DENTRO (motor es lo más interno) y nunca hacia fuera:
entrada/accion pueden usar motor; explicacion puede usar motor y accion; servicio y
herramientas pueden usar todo; a herramientas no lo importa nadie. Las excepciones
vigentes quedan CONGELADAS: una dependencia ascendente nueva rompe este test, y
retirar una excepción (p. ej. al mover el main batch de triaje a servicio, v2)
obliga a actualizar la lista — el contrato no se desactualiza en silencio."""
import os
import re
import unittest

RAIZ = os.path.join(os.path.dirname(__file__), "..")
CAPAS = ("entrada", "motor", "accion", "explicacion", "servicio", "herramientas")
PERMITIDAS = {
    "entrada": {"motor"},
    "motor": set(),                                  # el núcleo no mira hacia fuera
    "accion": {"motor"},
    "explicacion": {"motor", "accion"},
    "servicio": {"entrada", "motor", "accion", "explicacion"},
    "herramientas": {"entrada", "motor", "accion", "explicacion", "servicio"},
}
# Deuda consciente (candidatas a resolverse en v2); todo lo demás ascendente es un error.
EXCEPCIONES = {
    ("motor/triaje", "accion"),      # su main() batch carga el catálogo
    ("motor/triaje", "entrada"),     # su main() batch normaliza las alertas
    ("motor/triaje", "servicio"),    # su main() batch escribe la traza
    ("accion/revertir", "servicio"), # la reversión escribe su registro en la cadena (traza)
}
_IMPORT = re.compile(r"from prototipo\.(%s)[.\s]|import prototipo\.(%s)\." % ("|".join(CAPAS), "|".join(CAPAS)))


def _grafo():
    aristas = set()
    for capa in CAPAS:
        for nombre in os.listdir(os.path.join(RAIZ, capa)):
            if not nombre.endswith(".py") or nombre == "__init__.py":
                continue
            with open(os.path.join(RAIZ, capa, nombre), encoding="utf-8") as f:
                texto = f.read()
            for m in _IMPORT.finditer(texto):
                destino = m.group(1) or m.group(2)
                if destino != capa:
                    aristas.add((f"{capa}/{nombre[:-3]}", destino))
    return aristas


class TestContratoDeCapas(unittest.TestCase):
    def test_sin_dependencias_ascendentes_nuevas(self):
        violaciones = {(mod, destino) for mod, destino in _grafo()
                       if destino not in PERMITIDAS[mod.split("/")[0]]}
        nuevas = violaciones - EXCEPCIONES
        caducas = EXCEPCIONES - violaciones
        self.assertFalse(nuevas, f"dependencias ascendentes NUEVAS (mover el código de capa o "
                                 f"justificarlas aquí): {sorted(nuevas)}")
        self.assertFalse(caducas, f"excepciones que ya no existen (retíralas de la lista): "
                                  f"{sorted(caducas)}")


if __name__ == "__main__":
    unittest.main()
