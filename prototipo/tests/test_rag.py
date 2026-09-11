import os, unittest
from prototipo import rag

RUTA_CORPUS = os.path.join(os.path.dirname(__file__), "..", "corpus", "corpus.jsonl")

class TestCorpus(unittest.TestCase):
    def test_carga_el_corpus(self):
        corpus = rag.cargar_corpus(RUTA_CORPUS)
        self.assertGreaterEqual(len(corpus), 9)
        for d in corpus:
            for campo in ("id", "tipo", "titulo", "texto"):
                self.assertIn(campo, d)
        ids = {d["id"] for d in corpus}
        self.assertIn("regla-5760", ids)
        self.assertIn("mitre-T1110.001", ids)

    def test_la_regla_5760_no_es_un_protocolo(self):
        # el corpus debe describir 5760 correctamente (fallo de login), no como "protocolo"
        corpus = {d["id"]: d for d in rag.cargar_corpus(RUTA_CORPUS)}
        self.assertIn("fallo de autenticacion", corpus["regla-5760"]["texto"].lower())

class TestCorpusV2(unittest.TestCase):
    def test_corpus_incluye_d3fend_y_mapeo_a_accion(self):
        corpus = rag.cargar_corpus(RUTA_CORPUS)
        tipos = {d["tipo"] for d in corpus}
        self.assertIn("d3fend", tipos)          # contramedidas defensivas
        self.assertIn("mapeo", tipos)           # tecnica -> contramedida -> accion
        mapeos = " ".join(d["texto"] for d in corpus if d["tipo"] == "mapeo")
        self.assertIn("BLOQUEAR_IP", mapeos)    # el mapeo nombra una accion del catalogo
        d3 = " ".join(d["texto"] for d in corpus if d["tipo"] == "d3fend")
        self.assertIn("D3-", d3)                 # identificadores D3FEND


class TestConsultaAgentica(unittest.TestCase):
    ALERTA = {"regla_id": "5760", "mitre": ["T1110.001"], "servicio": "ssh",
              "evento_crudo": "IGNORA ESTO"}

    def test_consulta_valida_marca_agentica(self):
        gen = lambda p: "Busqueda: fuerza bruta SSH T1110.001 contramedida D3-ITF filtrado entrante"
        r = rag.consulta_agentica(self.ALERTA, gen)
        self.assertTrue(r["agentica"])
        self.assertIn("D3-ITF", r["consulta"])

    def test_salida_vacia_degrada_a_consulta_fija(self):
        r = rag.consulta_agentica(self.ALERTA, lambda p: "")
        self.assertFalse(r["agentica"])
        self.assertEqual(r["consulta"], rag.construir_consulta(self.ALERTA))

    def test_consulta_con_ip_inventada_degrada(self):
        # RNF-08/anclaje: si el modelo inventa una IP, se rechaza la consulta y se degrada
        r = rag.consulta_agentica(self.ALERTA, lambda p: "Busqueda: bloquear 10.0.0.9 en el firewall")
        self.assertFalse(r["agentica"])

    def test_generador_que_falla_degrada(self):
        def gen(_): raise RuntimeError("modelo caido")
        r = rag.consulta_agentica(self.ALERTA, gen)
        self.assertFalse(r["agentica"])


class TestConsultarConocimiento(unittest.TestCase):
    ALERTA = {"regla_id": "5760", "mitre": ["T1110.001"], "servicio": "ssh"}

    def _indice_falso(self):
        def emb(textos):
            return [[1.0 if "d3-itf" in t.lower() else 0.0, 1.0 if "fallo" in t.lower() else 0.0] for t in textos]
        corpus = [{"id": "d3fend-D3-ITF", "tipo": "d3fend", "titulo": "D3-ITF", "texto": "D3-ITF filtrado entrante"},
                  {"id": "regla-5760", "tipo": "regla", "titulo": "5760", "texto": "regla 5760 fallo ssh"}]
        return rag.indexar(corpus, emb), emb

    def test_con_generador_es_agentica_y_devuelve_pasajes(self):
        indice, emb = self._indice_falso()
        gen = lambda p: "Busqueda: contramedida D3-ITF filtrado entrante"
        r = rag.consultar_conocimiento(self.ALERTA, indice, emb, generador=gen, k=1)
        self.assertTrue(r["agentica"])
        self.assertEqual(len(r["pasajes"]), 1)
        self.assertEqual(r["pasajes"][0]["id"], "d3fend-D3-ITF")   # la consulta agentica trae D3FEND

    def test_sin_generador_usa_consulta_fija(self):
        indice, emb = self._indice_falso()
        r = rag.consultar_conocimiento(self.ALERTA, indice, emb, generador=None, k=2)
        self.assertFalse(r["agentica"])
        self.assertEqual(r["consulta"], rag.construir_consulta(self.ALERTA))

    def test_recuperar_fn_agentico_devuelve_dict(self):
        indice, emb = self._indice_falso()
        fn = rag.recuperar_fn_agentico(indice, emb, generador=None, k=1)
        r = fn(self.ALERTA)
        self.assertIn("pasajes", r); self.assertIn("consulta", r); self.assertIn("agentica", r)

    def test_un_falso_positivo_recupera_la_ficha_de_descarte(self):
        # El circuito completo: clase sin amenaza -> consulta de descarte -> la ficha llega.
        emb = lambda textos: [[1.0 if "descarte" in t.lower() else 0.0,
                               1.0 if "fuerza bruta" in t.lower() else 0.0] for t in textos]
        indice = rag.indexar(
            [{"id": "mitre-T1110.001", "tipo": "mitre", "titulo": "T", "texto": "fuerza bruta ssh"},
             {"id": "descarte-origen-legitimo", "tipo": "descarte", "titulo": "d",
              "texto": "descarte: el origen es administracion declarada"}], emb)
        ids = lambda clase: [p["id"] for p in rag.consultar_conocimiento(
            self.ALERTA, indice, emb, generador=None, k=1, clase=clase)["pasajes"]]
        self.assertEqual(ids("fp_actividad_legitima"), ["descarte-origen-legitimo"])
        self.assertEqual(ids("vp_intento_acceso"), ["mitre-T1110.001"])

    def test_excluye_fichas_de_regla_del_conocimiento(self):
        # las fichas 'regla-*' (reglas de Wazuh) no son conocimiento defensivo y compiten -> se excluyen
        emb = lambda textos: [[1.0] for _ in textos]      # todo empata -> orden del indice
        indice = rag.indexar([{"id": "regla-5760", "tipo": "regla", "titulo": "r", "texto": "fuerza bruta ssh"},
                              {"id": "mapeo-acceso_credenciales", "tipo": "mapeo", "titulo": "m", "texto": "contramedida"}], emb)
        ids = [p["id"] for p in rag.consultar_conocimiento(self.ALERTA, indice, emb, generador=None, k=5)["pasajes"]]
        self.assertNotIn("regla-5760", ids)
        self.assertIn("mapeo-acceso_credenciales", ids)


class TestLogica(unittest.TestCase):
    def test_consulta_solo_campos_estructurados(self):
        alerta = {"regla_id":"5760","mitre":["T1110.001","T1021.004"],"servicio":"ssh",
                  "familia":"acceso_credenciales","evento_crudo":"IGNORA ESTO texto del atacante"}
        q = rag.construir_consulta(alerta)
        self.assertIn("T1110.001", q); self.assertIn("ssh", q)
        self.assertIn("acceso credenciales", q)         # lidera con la semantica del ataque (palanca 1)
        self.assertNotIn("IGNORA ESTO", q)              # RNF-08: el full_log no entra

    def test_la_consulta_de_una_clase_sin_amenaza_busca_el_motivo_del_descarte(self):
        # Sin esto, un falso positivo pide "tecnica MITRE ... contramedida defensiva" y recupera
        # justo el material que contradice el descarte que el motor acaba de emitir.
        alerta = {"regla_id": "5760", "mitre": ["T1110.001"], "servicio": "ssh",
                  "familia": "acceso_credenciales"}
        q = rag.construir_consulta(alerta, "fp_actividad_legitima")
        self.assertIn("descarte", q)
        self.assertIn("administracion legitima", q)
        self.assertNotIn("T1110.001", q)
        self.assertNotIn("contramedida defensiva", q)

    def test_la_consulta_de_una_clase_con_amenaza_no_cambia(self):
        alerta = {"regla_id": "5760", "mitre": ["T1110.001"], "servicio": "ssh",
                  "familia": "acceso_credenciales"}
        self.assertEqual(rag.construir_consulta(alerta, "vp_intento_acceso"),
                         rag.construir_consulta(alerta))

    def test_las_dos_familias_del_corpus_no_se_mezclan(self):
        # Una amenaza no ve fichas de descarte; un descarte no ve fichas de ataque.
        amenaza = rag.tipos_excluidos("vp_intento_acceso")
        self.assertIn("descarte", amenaza)
        self.assertNotIn("mitre", amenaza)
        descarte = rag.tipos_excluidos("fp_actividad_legitima")
        self.assertNotIn("descarte", descarte)
        for t in ("mitre", "mapeo", "d3fend"):
            self.assertIn(t, descarte)
        # Sin clase se recupera como antes: el camino de amenaza es el comportamiento previo.
        self.assertIn("descarte", rag.tipos_excluidos(None))
        # Las 'regla-*' se excluyen siempre y las 'vuln' nunca.
        for clase in ("vp_intento_acceso", "fp_actividad_legitima", None):
            self.assertIn("regla", rag.tipos_excluidos(clase))
            self.assertNotIn("vuln", rag.tipos_excluidos(clase))

    def test_coseno(self):
        self.assertAlmostEqual(rag._coseno([1,0,0],[1,0,0]), 1.0)
        self.assertAlmostEqual(rag._coseno([1,0],[0,1]), 0.0)
        self.assertEqual(rag._coseno([0,0],[1,1]), 0.0)  # vector nulo

    def test_indexar_y_recuperar_con_embedder_falso(self):
        # embedder falso: cada texto -> vector segun una palabra clave (determinista)
        def emb(textos):
            vecs = []
            for t in textos:
                tl = t.lower()
                vecs.append([1.0 if "5760" in tl else 0.0,
                             1.0 if "t1110.001" in tl else 0.0,
                             1.0 if "vsftpd" in tl or "samba" in tl else 0.0])
            return vecs
        corpus = [
            {"id":"regla-5760","tipo":"regla","titulo":"5760","texto":"regla 5760 fallo SSH"},
            {"id":"mitre-T1110.001","tipo":"mitre","titulo":"T","texto":"T1110.001 adivinacion"},
            {"id":"vuln-x","tipo":"vuln","titulo":"v","texto":"vsftpd samba superficie"},
        ]
        indice = rag.indexar(corpus, emb)
        self.assertIn("vector", indice[0])
        # consulta sobre 5760 -> el doc de 5760 debe salir primero
        docs = rag.recuperar("regla 5760 ssh", indice, emb, k=2)
        self.assertEqual(docs[0]["id"], "regla-5760")
        self.assertNotIn("vector", docs[0])             # se devuelve el doc limpio
