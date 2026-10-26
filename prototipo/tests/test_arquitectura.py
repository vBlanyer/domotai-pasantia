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
# Las tres formas: `from prototipo.X import …`, `import prototipo.X[...]` y `from prototipo import X, Y`.
_CAPAS_RE = "|".join(CAPAS)
_IMPORT = re.compile(r"from prototipo\.(%s)\b|import prototipo\.(%s)\b" % (_CAPAS_RE, _CAPAS_RE))
_FROM_PAQ = re.compile(r"^\s*from prototipo import ([^#\n]+)", re.M)


def _destinos(texto, capa_propia):
    destinos = {m.group(1) or m.group(2) for m in _IMPORT.finditer(texto)}
    for m in _FROM_PAQ.finditer(texto):
        for nombre in m.group(1).split(","):
            base = nombre.split(" as ")[0].strip()
            if base in CAPAS:
                destinos.add(base)
    return destinos - {capa_propia}


def _grafo():
    aristas = set()
    for capa in CAPAS:
        for nombre in os.listdir(os.path.join(RAIZ, capa)):
            if not nombre.endswith(".py") or nombre == "__init__.py":
                continue
            with open(os.path.join(RAIZ, capa, nombre), encoding="utf-8") as f:
                texto = f.read()
            for destino in _destinos(texto, capa):
                aristas.add((f"{capa}/{nombre[:-3]}", destino))
    return aristas


class TestDetector(unittest.TestCase):
    def test_ve_las_tres_formas_de_import(self):
        # Revisión: el regex original exigía punto tras `import prototipo.motor` y no veía
        # `from prototipo import motor` — una dependencia nueva escrita así pasaba invisible.
        texto = ("from prototipo.servicio import traza\n"
                 "import prototipo.accion\n"
                 "from prototipo import explicacion, motor\n")
        self.assertEqual(_destinos(texto, "motor"), {"servicio", "accion", "explicacion"})

    def test_no_confunde_palabras_parecidas(self):
        texto = "from prototipo.motor import analisis\nfrom prototipo.tests import x\n# motor\n"
        self.assertEqual(_destinos(texto, "servicio"), {"motor"})


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
