"""Tarea 2 del plan de politica.yml: el servicio la lee al arrancar, la fusiona con el perfil y deja
constancia en la traza firmada (registro `politica_cargada`). Sin TRIAJE_POLITICA, todo como hoy."""
import hashlib, io, json, os, tempfile, unittest, yaml

from prototipo.accion import catalogo
from prototipo.servicio import lazo, stream, tablero, traza

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
PERFIL = {"activos": {"web01": {"ip": "192.0.2.10"}}, "ip_gestion": "10.99.0.10"}
POLITICA = {"politica": {"version": 3, "aprobada_por": "Dirección de Seguridad", "fecha": "2026-11-10"},
            "confianza": {"administradores": ["10.99.0.10"]},
            "respuesta_automatica": {"por_defecto": "con_analista"}}


def _escribir(texto):
    f = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8")
    f.write(texto); f.close()
    return f.name


class TestCargarPolitica(unittest.TestCase):
    def test_sin_fichero_el_perfil_no_cambia(self):
        perfil, info = stream.cargar_politica(PERFIL, CAT, None)
        self.assertIs(perfil, PERFIL)
        self.assertIsNone(info)

    def test_con_fichero_valido_fusiona_y_devuelve_la_cabecera_y_la_huella(self):
        texto = yaml.safe_dump(POLITICA, allow_unicode=True)
        ruta = _escribir(texto)
        perfil, info = stream.cargar_politica(PERFIL, CAT, ruta)
        self.assertEqual(perfil["origenes_legitimos"], ["10.99.0.10"])
        self.assertEqual(perfil["continuidad"]["impacto_localizado"], "humano_siempre")
        self.assertEqual((info["version"], info["aprobada_por"], info["fecha"]), (3, "Dirección de Seguridad", "2026-11-10"))
        self.assertEqual(info["hash"], hashlib.sha256(texto.encode("utf-8")).hexdigest())
        self.assertEqual(info["politica"], POLITICA)

    def test_fichero_invalido_no_arranca_y_dice_por_que(self):
        ruta = _escribir(yaml.safe_dump({"respuesta_automatica": {"por_defecto": "siempre"}}))
        with self.assertRaises(SystemExit) as e:
            stream.cargar_politica(PERFIL, CAT, ruta)
        self.assertIn("por_defecto", str(e.exception))

    def test_fichero_ausente_no_arranca(self):
        with self.assertRaises(SystemExit) as e:
            stream.cargar_politica(PERFIL, CAT, "/no/existe/politica.yml")
        self.assertIn("/no/existe/politica.yml", str(e.exception))

    def test_regla_repetida_en_el_perfil_no_arranca(self):
        ruta = _escribir(yaml.safe_dump(POLITICA))
        with self.assertRaises(SystemExit) as e:
            stream.cargar_politica({**PERFIL, "origenes_legitimos": ["10.99.0.10"]}, CAT, ruta)
        self.assertIn("origenes_legitimos", str(e.exception))


class TestRegistroEnLaTraza(unittest.TestCase):
    def test_el_arranque_anota_la_politica_en_la_cadena(self):
        info = {"ruta": "/etc/mdr/politica.yml", "version": 3, "aprobada_por": "Seguridad", "fecha": "2026-11-10",
                "hash": "ab" * 32, "politica": POLITICA}
        buf = io.StringIO()
        with open(os.path.join(FX, "hallazgos.json"), encoding="utf-8") as f:
            hallazgos = json.load(f)
        with open(os.path.join(FX, "perfil.yml"), encoding="utf-8") as f:
            perfil = yaml.safe_load(f)
        stream.ejecutar([None], hallazgos=hallazgos, perfil=perfil, perfil_nombre="prueba", catalogo=CAT,
                        ejecutor=lazo._EjecutorAuto(), salida_traza=buf, escribir=lambda *a, **k: None,
                        leer=lambda *_: "2", al_arrancar=[stream.registro_politica(info, "2026-11-11T10:00:00+00:00")])
        regs = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
        self.assertEqual(len(regs), 1)
        r = regs[0]
        self.assertEqual(r["tipo"], "politica_cargada")
        self.assertEqual((r["version"], r["aprobada_por"], r["huella"]), (3, "Seguridad", "ab" * 32))
        self.assertNotIn("politica", r)                     # la huella basta; el fichero no viaja a la traza
        self.assertTrue(traza.verificar(regs)["valida"])

    def test_no_cuenta_como_decision(self):
        self.assertIn("politica_cargada", tablero._NO_DECISIONES)


if __name__ == "__main__":
    unittest.main()


class TestCargaRobusta(unittest.TestCase):
    def test_una_forma_incorrecta_no_arranca_con_mensaje_y_sin_traceback(self):
        for texto in ("confianza: [10.99.0.10]\n", "politica: [1]\n", "- a\n- b\n", "politica: {version: '1.2'}\n"):
            with self.subTest(texto=texto), self.assertRaises(SystemExit) as e:
                stream.cargar_politica(PERFIL, CAT, _escribir(texto))
            self.assertIn("politica", str(e.exception).lower())

    def test_la_cabecera_se_normaliza_a_texto(self):
        ruta = _escribir("politica: {version: 2, aprobada_por: Seguridad, fecha: 2026-11-11}\n")
        _, info = stream.cargar_politica(PERFIL, CAT, ruta)
        self.assertEqual((info["version"], info["fecha"]), (2, "2026-11-11"))
        json.dumps(stream.registro_politica(info, "t"))         # la traza la puede escribir
