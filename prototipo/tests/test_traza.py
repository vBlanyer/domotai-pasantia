import json, unittest
from prototipo import traza

class TestConstruir(unittest.TestCase):
    def test_registro_completo(self):
        r = traza.construir(
            id_decision="d1", timestamp="2026-08-31T00:00:00Z",
            alerta={"id_alerta":"a1","activo":"objetivo-vuln"},
            analisis_out={"clase":"vp_intento_acceso","prioridad":4,"confianza":1.0,"justificacion":"..."},
            accion_prop="BLOQUEAR_IP", impacto="localizado", perfil_nombre="empresarial",
            filtro_out={"resultado":"permite","accion_final":"BLOQUEAR_IP","requiere_humano":False},
            version_perfil="v0")
        for k in ("id_decision","timestamp","id_alerta","activo","clase","prioridad","confianza",
                  "justificacion","accion_propuesta","impacto","perfil_aplicado","resultado_filtro",
                  "accion_final","requiere_humano","version_baseline","version_perfil"):
            self.assertIn(k, r)
        self.assertEqual(r["id_alerta"], "a1")
        self.assertEqual(r["resultado_filtro"], "permite")
        self.assertEqual(r["version_baseline"], "baseline-0")
        self.assertEqual(r["version_perfil"], "v0")

    def test_registra_el_impacto_determinado(self):
        det = {"nivel": "localizado", "actor": {"tipo": "activo_interno", "nombre": "puesto"},
               "motivo": "bloquea a puesto (activo interno) · 0 servicios detenidos"}
        r = traza.construir("d1", "t", {"id_alerta": "a1"}, {"clase": "vp_intento_acceso"},
                            "BLOQUEAR_IP", "localizado", "empresarial",
                            {"resultado": "veta", "accion_final": "BLOQUEAR_IP", "requiere_humano": True,
                             "impacto": det}, "v0")
        self.assertEqual(r["impacto_determinado"], det)

    def test_sin_impacto_determinado_queda_none(self):
        r = traza.construir("d1", "t", {"id_alerta": "a1"}, {"clase": "no_soportada"}, None, "ninguno",
                            "empresarial", {"resultado": "sin_accion", "accion_final": None,
                                            "requiere_humano": False}, "v0")
        self.assertIsNone(r["impacto_determinado"])


class TestJustificacionEstructurada(unittest.TestCase):
    ALERTA = {"id_alerta": "a1", "regla_id": "5760", "origen_ip": "192.168.1.10",
              "activo": "objetivo-vuln", "servicio": "ssh", "mitre": ["T1110.001", "T1021.004"]}
    ANALISIS = {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0, "justificacion": "..."}

    def _construir(self, alerta=None, accion="BLOQUEAR_IP"):
        return traza.construir(
            id_decision="d1", timestamp="t", alerta=alerta or self.ALERTA,
            analisis_out=self.ANALISIS, accion_prop=accion, impacto="localizado",
            perfil_nombre="empresarial",
            filtro_out={"resultado": "permite", "accion_final": accion, "requiere_humano": False},
            version_perfil="v0")

    def test_tiene_los_4_componentes(self):
        est = self._construir()["justificacion_estructurada"]
        self.assertEqual(set(est), {"evidencia", "hipotesis", "tecnica_mitre", "accion_sugerida"})

    def test_copia_accion_y_mitre_y_evidencia(self):
        est = self._construir()["justificacion_estructurada"]
        self.assertEqual(est["accion_sugerida"], "BLOQUEAR_IP")
        self.assertEqual(est["tecnica_mitre"], ["T1110.001", "T1021.004"])
        self.assertEqual(est["evidencia"]["regla"], "5760")
        self.assertEqual(est["evidencia"]["origen_ip"], "192.168.1.10")
        self.assertEqual(est["hipotesis"]["clase"], "vp_intento_acceso")
        self.assertEqual(est["hipotesis"]["confianza"], 1.0)

    def test_tolera_campos_ausentes(self):
        est = self._construir(alerta={"id_alerta": "a2"}, accion=None)["justificacion_estructurada"]
        self.assertEqual(est["tecnica_mitre"], [])
        self.assertIsNone(est["evidencia"]["origen_ip"])
        self.assertIsNone(est["accion_sugerida"])


class TestVersionJustificadorTraza(unittest.TestCase):
    def _c(self, analisis_out):
        return traza.construir(id_decision="d", timestamp="t", alerta={"id_alerta": "a"},
                               analisis_out=analisis_out, accion_prop="BLOQUEAR_IP", impacto="localizado",
                               perfil_nombre="p", filtro_out={"resultado": "permite", "accion_final": "BLOQUEAR_IP",
                               "requiere_humano": False}, version_perfil="v0")

    def test_registra_version_justificador_y_pasajes(self):
        r = self._c({"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0, "justificacion": "x",
                     "version_justificador": "llm-1b-0:llama-3.2-1b-q4.gguf", "pasajes_usados": ["regla-5760"]})
        self.assertEqual(r["version_justificador"], "llm-1b-0:llama-3.2-1b-q4.gguf")
        self.assertEqual(r["pasajes_usados"], ["regla-5760"])

    def test_default_plantilla_sin_metadata(self):
        r = self._c({"clase": "no_soportada", "prioridad": 1, "confianza": 1.0, "justificacion": "x"})
        self.assertEqual(r["version_justificador"], "plantilla-0")
        self.assertEqual(r["pasajes_usados"], [])

    def test_registra_consulta_rag_y_recuperacion_agentica(self):
        r = self._c({"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0, "justificacion": "x",
                     "consulta_rag": "contramedida D3-ITF filtrado", "recuperacion_agentica": True})
        self.assertEqual(r["consulta_rag"], "contramedida D3-ITF filtrado")
        self.assertTrue(r["recuperacion_agentica"])

    def test_default_sin_recuperacion_agentica(self):
        r = self._c({"clase": "no_soportada", "prioridad": 1, "confianza": 1.0, "justificacion": "x"})
        self.assertEqual(r["consulta_rag"], "")
        self.assertFalse(r["recuperacion_agentica"])


class TestCadena(unittest.TestCase):
    def _regs(self, n=4):
        import io as _io
        buf = _io.StringIO()
        cadena = traza.Cadena(buf)
        for i in range(n):
            cadena.escribir({"id_decision": f"d{i}", "clase": "vp_intento_acceso", "accion_final": "BLOQUEAR_IP"})
        return [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]

    def test_cadena_valida_y_primer_registro_desde_genesis(self):
        regs = self._regs()
        self.assertEqual(regs[0]["hash_previo"], traza.GENESIS)
        self.assertEqual(regs[1]["hash_previo"], regs[0]["hash"])
        self.assertTrue(traza.verificar(regs)["valida"])

    def test_alterar_un_campo_rompe_la_cadena_en_ese_registro(self):
        regs = self._regs()
        regs[2]["accion_final"] = "AISLAR_NODO"          # alguien "corrige" una decision ya tomada
        v = traza.verificar(regs)
        self.assertFalse(v["valida"]); self.assertEqual(v["primer_fallo"], 2)
        self.assertIn("alterado", v["motivo"])

    def test_borrar_un_registro_interior_rompe_la_cadena_en_el_siguiente(self):
        regs = self._regs()
        del regs[1]
        v = traza.verificar(regs)
        self.assertFalse(v["valida"]); self.assertEqual(v["primer_fallo"], 1)

    def test_reordenar_o_insertar_rompe_la_cadena(self):
        regs = self._regs()
        regs[1], regs[2] = regs[2], regs[1]
        self.assertFalse(traza.verificar(regs)["valida"])
        regs = self._regs()
        regs.insert(2, traza.encadenar({"id_decision": "colada"}, regs[1]["hash"]))
        self.assertFalse(traza.verificar(regs)["valida"])   # el d2 original ya no cuadra

    def test_truncar_por_el_final_NO_se_detecta_y_esta_documentado(self):
        # Limite explicito de la cadena: lo que queda sigue encadenado. Cubrirlo exige anclar
        # el ultimo hash fuera del fichero (ultimo_hash existe para eso).
        regs = self._regs()[:2]
        self.assertTrue(traza.verificar(regs)["valida"])

    def test_un_registro_sin_cadena_falla(self):
        v = traza.verificar([{"id_decision": "x"}])
        self.assertFalse(v["valida"]); self.assertEqual(v["primer_fallo"], 0)

    def test_retomar_un_fichero_continua_la_misma_cadena(self):
        import os, tempfile
        ruta = tempfile.mktemp(suffix=".jsonl")
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                traza.Cadena(f).escribir({"id_decision": "s1"})
            h = traza.ultimo_hash(ruta)
            with open(ruta, "a", encoding="utf-8") as f:      # segunda sesion del daemon
                traza.Cadena(f, h).escribir({"id_decision": "s2"})
            regs = traza.leer_registros(ruta)
            self.assertEqual(len(regs), 2)
            self.assertTrue(traza.verificar(regs)["valida"])
            self.assertEqual(regs[1]["hash_previo"], regs[0]["hash"])
        finally:
            os.unlink(ruta)

    def test_ultimo_hash_de_fichero_inexistente_es_genesis(self):
        self.assertEqual(traza.ultimo_hash("/no/existe.jsonl"), traza.GENESIS)

    def test_el_hash_no_depende_del_orden_de_las_claves(self):
        a = traza.encadenar({"x": 1, "y": 2}, traza.GENESIS)
        b = traza.encadenar({"y": 2, "x": 1}, traza.GENESIS)
        self.assertEqual(a["hash"], b["hash"])


class TestAncla(unittest.TestCase):
    def test_la_cadena_ancla_cada_registro_con_su_numero_y_su_hash(self):
        import io as _io
        enviados = []
        original = traza._enviar_udp
        traza._enviar_udp = lambda linea, destino: enviados.append((linea, destino))
        try:
            # anclar() toma _enviar por defecto en la firma: se inyecta a traves de anclar directamente
            buf = _io.StringIO()
            cadena = traza.Cadena(buf, nombre="t.jsonl", ancla="127.0.0.1:514")
            # sustituimos anclar para capturar sin red
            capturas = []
            traza_anclar = traza.anclar
            traza.anclar = lambda nombre, lin, n, h, destino=None, _enviar=None: capturas.append((nombre, lin, n, h, destino)) or True
            try:
                r1 = cadena.escribir({"id_decision": "a"}); r2 = cadena.escribir({"id_decision": "b"})
            finally:
                traza.anclar = traza_anclar
        finally:
            traza._enviar_udp = original
        lin = r1["hash"][:16]                                   # el linaje es el primer registro
        self.assertEqual(capturas, [("t.jsonl", lin, 1, r1["hash"], "127.0.0.1:514"),
                                    ("t.jsonl", lin, 2, r2["hash"], "127.0.0.1:514")])
        self.assertEqual(cadena.anclados, 2)

    def test_sin_destino_no_se_ancla_y_no_falla(self):
        import io as _io
        cadena = traza.Cadena(_io.StringIO(), nombre="t.jsonl", ancla="")
        cadena.escribir({"id_decision": "a"})
        self.assertEqual(cadena.anclados, 0)

    def test_anclar_nunca_lanza(self):
        def _cae(linea, destino):
            raise OSError("red caida")
        self.assertFalse(traza.anclar("t.jsonl", "0" * 16, 1, "0" * 64, "127.0.0.1:514", _enviar=_cae))

    def test_formato_del_ancla_es_syslog_con_los_tres_campos(self):
        linea = traza.formatear_ancla("t.jsonl", "c" * 16, 7, "ab" * 32)
        self.assertTrue(linea.startswith("<38>"))
        m = traza._ANCLA_RE.search(linea)
        self.assertEqual((m.group(1), m.group(2), int(m.group(3)), m.group(4)), ("t.jsonl", "c" * 16, 7, "ab" * 32))

    def _regs(self, n=4):
        import io as _io
        buf = _io.StringIO(); c = traza.Cadena(buf, ancla="")
        for i in range(n):
            c.escribir({"id_decision": f"d{i}"})
        return [json.loads(l) for l in buf.getvalue().splitlines()]

    def test_verificar_contra_anclas_detecta_el_truncado_final(self):
        regs = self._regs(4)
        lin = traza.linaje_de(regs)
        anclas = [(i + 1, regs[i]["hash"], lin) for i in range(4)]
        self.assertTrue(traza.verificar_contra_anclas(regs, anclas)["valida"])
        v = traza.verificar_contra_anclas(regs[:2], anclas)          # alguien borro los dos ultimos
        self.assertFalse(v["valida"]); self.assertIn("TRUNCADA", v["motivo"])

    def test_verificar_contra_anclas_detecta_un_hash_distinto(self):
        regs = self._regs(3)
        lin = traza.linaje_de(regs)
        v = traza.verificar_contra_anclas(regs, [(3, "f" * 64, lin)])   # mismo linaje, otro hash
        self.assertFalse(v["valida"]); self.assertIn("ALTERADA", v["motivo"])

    def test_una_traza_rehecha_se_distingue_de_una_truncada(self):
        # Se midio: borrar y recrear el fichero con el mismo nombre deja en Wazuh anclas que no
        # coinciden con nada. No es un truncado, pero tampoco es aceptable, y se dice cual es.
        regs = self._regs(3)
        v = traza.verificar_contra_anclas(regs, [(5, "e" * 64, "0" * 16), (2, "d" * 64, "0" * 16)])
        self.assertFalse(v["valida"]); self.assertIn("REHECHA", v["motivo"])

    def test_sin_anclas_no_se_puede_afirmar_nada_y_se_dice(self):
        v = traza.verificar_contra_anclas(self._regs(2), [])
        self.assertTrue(v["valida"]); self.assertIn("sin anclas", v["motivo"])

    def test_leer_anclas_filtra_por_fichero(self):
        import os, tempfile
        ruta = tempfile.mktemp(suffix=".json")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(json.dumps({"rule": {"id": "100100"}, "full_log": traza.formatear_ancla("a.jsonl", "a" * 16, 1, "1" * 64)}) + "\n")
            f.write(json.dumps({"rule": {"id": "100100"}, "full_log": traza.formatear_ancla("b.jsonl", "b" * 16, 5, "2" * 64)}) + "\n")
            f.write(json.dumps({"rule": {"id": "5760"}, "full_log": "Failed password"}) + "\n")
        try:
            self.assertEqual(traza.leer_anclas(ruta, "b.jsonl"), [(5, "2" * 64, "b" * 16)])
        finally:
            os.unlink(ruta)

