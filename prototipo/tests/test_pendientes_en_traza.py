"""#1 de la revisión del 15/11: una aprobación pendiente deja rastro en la traza al encolarse, y al
arrancar se avisa de las que se perdieron con el reinicio."""
import io
import json
import unittest

from prototipo.servicio import lazo, stream, tablero, traza
from prototipo.tests import test_stream as ts

CAT, j, y = ts.CAT, ts.j, ts.y


def _regs(buf):
    return [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]


class TestPendientesEnTraza(unittest.TestCase):
    def test_al_encolar_queda_en_la_traza(self):
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        ts.TestColaNoBloqueante._ejecutar(ts.TestColaNoBloqueante(), estado, buf)
        [p] = _regs(buf)
        cola = estado.decisiones_pendientes()
        self.assertEqual((p["tipo"], p["id_cola"], p["activo"]), ("pendiente", cola[0]["id"], "fantasma"))
        self.assertTrue(p["id_decision"])
        self.assertTrue(traza.verificar([p])["valida"])
        estado.resolver_decision(cola[0]["id"], "1")
        regs = _regs(buf)
        self.assertEqual([r.get("tipo") for r in regs], ["pendiente", "decision"])
        self.assertEqual(regs[1]["id_decision"], p["id_decision"])
        self.assertEqual(stream.pendientes_sin_resolver(regs), [])

    def test_la_repeticion_que_se_suma_a_la_tarjeta_no_traza_otro_pendiente(self):
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        linea = ts.TestColaNoBloqueante._linea_humana(ts.TestColaNoBloqueante())
        stream.ejecutar([linea, None, linea, None], hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"),
                        perfil_nombre="prueba", catalogo=CAT, ejecutor=lazo._EjecutorAuto(), justificar_fn=None,
                        ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None, estado_web=estado,
                        suprimir=False)
        self.assertEqual(len(estado.decisiones_pendientes()), 1)
        self.assertEqual([r["tipo"] for r in _regs(buf)].count("pendiente"), 1)

    def test_pendientes_perdidas_al_arrancar(self):
        regs = [{"tipo": "pendiente", "id_decision": "s1", "activo": "web"},
                {"tipo": "pendiente", "id_decision": "s2", "activo": "db"},
                {"tipo": "pendiente", "id_decision": "s3", "activo": "app"},
                {"tipo": "pendiente", "id_decision": "s4", "activo": "nas"},
                {"tipo": "pendiente", "id_decision": "s5", "activo": "fw"},
                {"id_decision": "s1", "clase": "vp_intento_acceso"},                 # resuelta
                {"tipo": "error", "id_decision": "s3~tope"},                        # desalojada por el tope
                {"tipo": "pendiente_perdida", "id_decision": "s5"}]                 # ya avisada antes
        perdidas = stream.pendientes_sin_resolver(regs)
        self.assertEqual([p["id_decision"] for p in perdidas], ["s2", "s4"])
        r = stream.registro_pendiente_perdida(perdidas[0], "2026-11-16T10:00:00+00:00")
        self.assertEqual((r["tipo"], r["id_decision"], r["activo"]), ("pendiente_perdida", "s2", "db"))
        self.assertIn("reinici", r["motivo"])
        self.assertIn("2 aprobación(es) pendiente(s)", stream.linea_pendientes_perdidas(perdidas))

    def test_no_cuentan_como_decision(self):
        self.assertIn("pendiente", tablero._NO_DECISIONES)
        self.assertIn("pendiente_perdida", tablero._NO_DECISIONES)
        regs = [{"tipo": "pendiente", "id_decision": "s1", "clase": "vp_intento_acceso", "origen_ip": "1.2.3.4"}]
        self.assertEqual(tablero.metricas(regs)["total"], 0)


if __name__ == "__main__":
    unittest.main()
