import os, json, unittest
from prototipo import ingesta, adaptador_wazuh

FX = os.path.join(os.path.dirname(__file__), "fixtures")

def j(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.loads(f.read().strip())

CAMPOS = {"id_alerta", "timestamp", "campaña", "fuente", "activo", "servicio",
          "familia", "origen_ip", "destino_ip", "mitre", "evento_crudo", "nivel_wazuh", "regla_id", "usuario"}


class TestNormalizarWazuh(unittest.TestCase):
    def test_alerta_wazuh_normaliza(self):
        reg = ingesta.normalizar(j("alerta_cruda_wazuh.json"), adaptador_wazuh.adaptador("c"))
        self.assertEqual(set(reg), CAMPOS)
        self.assertEqual(reg["activo"], "objetivo-vuln")
        self.assertEqual(reg["servicio"], "ssh")
        self.assertEqual(reg["familia"], "acceso_credenciales")
        self.assertIsInstance(reg["mitre"], list)
        self.assertEqual(reg["nivel_wazuh"], 5)
        self.assertIn("Failed password", reg["evento_crudo"])
        self.assertEqual(reg["campaña"], "c")

    def test_una_ipv4_mapeada_en_ipv6_se_normaliza(self):
        cruda = j("alerta_cruda_wazuh.json"); cruda["data"]["srcip"] = "::ffff:198.51.100.9"
        self.assertEqual(ingesta.normalizar(cruda, adaptador_wazuh.adaptador())["origen_ip"], "198.51.100.9")

    def test_resuelve_activo_sin_agente(self):
        # RF-16: el activo sale de predecoder.hostname / location, nunca del agent.id 000
        reg = ingesta.normalizar(j("alerta_cruda_wazuh.json"), adaptador_wazuh.adaptador())
        self.assertEqual(reg["activo"], "objetivo-vuln")
        self.assertNotEqual(reg["activo"], "000")


class TestTolerancia(unittest.TestCase):
    def test_campos_ausentes_no_rompe_ni_infiere(self):
        # RNF-07: tolera campos ausentes, no lanza, no inventa
        reg = ingesta.normalizar({}, adaptador_wazuh.adaptador())
        self.assertEqual(reg["mitre"], [])
        self.assertIsNone(reg["origen_ip"])
        self.assertIsNone(reg["regla_id"])
        self.assertIsNone(reg["id_alerta"])
        faltan = ingesta.campos_ausentes(reg)
        self.assertIn("origen_ip", faltan)
        self.assertIn("regla_id", faltan)
        self.assertIn("id_alerta", faltan)

    def test_campos_ausentes_vacio_cuando_completo(self):
        reg = ingesta.normalizar(j("alerta_cruda_wazuh.json"), adaptador_wazuh.adaptador())
        self.assertEqual(ingesta.campos_ausentes(reg), [])

    def test_evento_de_cuenta_nueva_es_abuso_de_cuenta_y_extrae_el_usuario(self):
        # useradd (T1136): la familia nueva, y el usuario objetivo (la cuenta a bloquear) sale del log.
        cruda = {"id": "u1", "timestamp": "t",
                 "rule": {"id": "5902", "groups": ["syslog", "adduser"], "level": 8, "mitre": {"id": ["T1136"]}},
                 "predecoder": {"hostname": "core-db", "program_name": "useradd"},
                 "data": {"dstuser": "backdoor"}}
        a = adaptador_wazuh.normalizar_alerta(cruda, "c")
        self.assertEqual(a["familia"], "abuso_de_cuenta")
        self.assertEqual(a["usuario"], "backdoor")

    def test_fim_syscheck_es_integridad(self):
        # FIM (T1565): un fichero crítico cambió -> familia integridad_fichero. Los grupos traen 'ossec'
        # además de 'syscheck': se comprueba que syscheck gana al cajón 'plataforma'. La IP del host a
        # aislar NO sale de la alerta (agent.ip es el manager en el laboratorio, M1): se resuelve del
        # inventario del perfil aguas abajo (orden.construir), como el nodo ejecutor de cualquier acción.
        cruda = {"id": "f1", "timestamp": "t",
                 "rule": {"id": "550", "groups": ["ossec", "syscheck"], "level": 7, "mitre": {"id": ["T1565"]}},
                 "agent": {"id": "001", "name": "core-db", "ip": "10.50.0.10"},
                 "data": {}, "full_log": "File '/etc/passwd' modified"}
        a = adaptador_wazuh.normalizar_alerta(cruda, "c")
        self.assertEqual(a["familia"], "integridad_fichero")
        self.assertNotIn("activo_ip", a)   # M1: el esquema normalizado ya no lleva la IP de agent.ip

    def test_intrusion_exitosa_es_acceso_consumado(self):
        # 8ª familia: login EXITOSO desde una IP que acababa de hacer fuerza bruta (regla compuesta
        # local, grupo 'intrusion'). Se comprueba ANTES del fallo de autenticación (que va a credenciales).
        cruda = {"id": "i1", "timestamp": "t",
                 "rule": {"id": "100600", "groups": ["syslog", "sshd", "intrusion"], "level": 10,
                          "mitre": {"id": ["T1078", "T1021"]}},
                 "agent": {"id": "000"}, "data": {"srcip": "198.51.100.10"},
                 "full_log": "Accepted password for cliente from 198.51.100.10"}
        a = adaptador_wazuh.normalizar_alerta(cruda, "c")
        self.assertEqual(a["familia"], "acceso_consumado")
        self.assertEqual(a["origen_ip"], "198.51.100.10")   # MATAR_CONEXION necesita la IP del atacante

    def test_login_exitoso_legitimo_no_es_acceso_consumado(self):
        # Invariante de orden: un login EXITOSO normal (authentication_success, SIN el contexto de
        # fuerza bruta -> sin grupo 'intrusion') NO cae en acceso_consumado (ni en credenciales): es 'otra'.
        cruda = {"id": "L1", "timestamp": "t",
                 "rule": {"id": "5715", "groups": ["syslog", "sshd", "authentication_success"], "level": 3},
                 "agent": {"id": "000"}, "data": {"srcip": "10.100.0.10"},
                 "full_log": "Accepted password for admin from 10.100.0.10"}
        self.assertEqual(adaptador_wazuh.familia_de(cruda["rule"]), "otra")

    def test_flood_es_denegacion_servicio(self):
        # 7ª familia (DoS/flood): una regla de frecuencia de Wazuh (grupo 'flood'/'dos') -> familia
        # denegacion_servicio. Se comprueba ANTES del cajón exploit/attack (un flood suele traer 'attack').
        cruda = {"id": "d1", "timestamp": "t",
                 "rule": {"id": "31530", "groups": ["web", "attack", "flood"], "level": 10, "mitre": {"id": ["T1499"]}},
                 "agent": {"id": "000"}, "data": {"srcip": "203.0.113.9"}, "full_log": "Multiple connections from same source"}
        a = adaptador_wazuh.normalizar_alerta(cruda, "c")
        self.assertEqual(a["familia"], "denegacion_servicio")

    def test_exfiltracion_c2_es_exfiltracion_y_extrae_el_destino(self):
        # 9ª familia: un match de la lista de amenazas (grupo 'c2'/'exfiltration') -> familia
        # exfiltracion. El DESTINO a bloquear (dstip) sale de la alerta: es fiable (es el destino de
        # la conexión, no agent.ip). Se comprueba ANTES del cajón exploit/attack.
        cruda = {"id": "e1", "timestamp": "t",
                 "rule": {"id": "100700", "groups": ["ids", "attack", "c2"], "level": 12, "mitre": {"id": ["T1071", "T1041"]}},
                 "predecoder": {"hostname": "web-banking"},
                 "data": {"srcip": "10.10.0.10", "dstip": "203.0.113.66"},
                 "full_log": "Outbound connection to known C2 203.0.113.66"}
        a = adaptador_wazuh.normalizar_alerta(cruda, "c")
        self.assertEqual(a["familia"], "exfiltracion")
        self.assertEqual(a["destino_ip"], "203.0.113.66")   # BLOQUEAR_DESTINO necesita el destino
        self.assertEqual(a["origen_ip"], "10.10.0.10")      # el host interno que baliza

    def test_destino_ip_ausente_es_none_y_no_estorba(self):
        # La inmensa mayoría de alertas no traen dstip: destino_ip queda None (aditivo, no estorba).
        a = adaptador_wazuh.normalizar_alerta(j("alerta_cruda_wazuh.json"), "c")
        self.assertIsNone(a["destino_ip"])

    def test_destino_ipv4_mapeada_en_ipv6_se_normaliza(self):
        cruda = {"id": "e2", "rule": {"id": "100700", "groups": ["c2"]},
                 "predecoder": {"hostname": "web"}, "data": {"srcip": "10.10.0.10", "dstip": "::ffff:203.0.113.66"}}
        self.assertEqual(adaptador_wazuh.normalizar_alerta(cruda, "c")["destino_ip"], "203.0.113.66")

    def test_malware_virustotal_es_malware(self):
        # 10ª familia: un veredicto de VirusTotal / rootcheck de trojano (grupo 'virustotal'/'malware')
        # -> familia malware. Se comprueba ANTES del cajón 'plataforma' (un hit de rootcheck trae
        # 'ossec'/'rootcheck' además): un malware confirmado NO debe tratarse como ruido de plataforma.
        cruda = {"id": "m1", "timestamp": "t",
                 "rule": {"id": "87105", "groups": ["virustotal", "malware"], "level": 12, "mitre": {"id": ["T1486"]}},
                 "predecoder": {"hostname": "core-db"},
                 "data": {}, "full_log": "VirusTotal: /tmp/x.bin positives 54/70"}
        a = adaptador_wazuh.normalizar_alerta(cruda, "c")
        self.assertEqual(a["familia"], "malware")

    def test_malware_con_grupo_attack_sigue_siendo_malware(self):
        # Revisión Opus (BAJO): un veredicto de malware que ADEMÁS trae 'attack' no debe degradarse a
        # explotacion_conocida (enrutada). La rama malware va ANTES de exploit/attack (más específico
        # primero), simétrica con exfil.
        cruda = {"id": "m2", "rule": {"id": "87105", "groups": ["attack", "virustotal", "malware"], "level": 12},
                 "predecoder": {"hostname": "core-db"}, "data": {}}
        self.assertEqual(adaptador_wazuh.familia_de(cruda["rule"]), "malware")

    def test_rootcheck_benigno_sigue_siendo_plataforma(self):
        # Regresión: un rootcheck/SCA SIN veredicto de malware (solo 'rootcheck'/'ossec') sigue siendo
        # 'plataforma' (ruido). La familia malware solo captura el veredicto explícito (virustotal/malware/trojan).
        cruda = {"id": "p1", "rule": {"id": "510", "groups": ["ossec", "rootcheck"], "level": 7},
                 "predecoder": {"hostname": "core-db"}, "data": {}}
        self.assertEqual(adaptador_wazuh.familia_de(cruda["rule"]), "plataforma")

    def test_abuso_de_sudo_bloquea_al_invocador_no_al_objetivo_root(self):
        # En un evento de sudo, dstuser es el OBJETIVO de la escalada (root) y srcuser QUIEN abusa. La
        # cuenta a bloquear es la que abusa, no root (bloquear root dejaría fuera al admin legítimo).
        cruda = {"id": "s1", "timestamp": "t",
                 "rule": {"id": "5402", "groups": ["syslog", "sudo"], "level": 10, "mitre": {"id": ["T1548"]}},
                 "predecoder": {"hostname": "web-banking", "program_name": "sudo"},
                 "data": {"srcuser": "www-data", "dstuser": "root"}}
        a = adaptador_wazuh.normalizar_alerta(cruda, "c")
        self.assertEqual(a["familia"], "abuso_de_cuenta")
        self.assertEqual(a["usuario"], "www-data")           # el invocador, NO root

    def test_un_fallo_de_autenticacion_sigue_siendo_acceso_credenciales(self):
        # Regresión: la familia nueva no debe robarle las alertas a acceso_credenciales (canónico).
        cruda = {"id": "a1", "rule": {"id": "5760", "groups": ["authentication_failed"], "level": 10},
                 "predecoder": {"hostname": "web-banking", "program_name": "sshd"}, "data": {"srcip": "1.2.3.4"}}
        a = adaptador_wazuh.normalizar_alerta(cruda, "c")
        self.assertEqual(a["familia"], "acceso_credenciales")

    def test_tipos_hostiles_se_coaccionan_a_texto_o_none(self):
        # Defensa anti-DoS: un atacante que controla campos de la alerta (srcip, hostname,
        # program_name, timestamp) podía colar un número/objeto/lista que luego reventaba aguas
        # abajo (rafaga._instante parsea el timestamp; Ventana/agrupar/postura usan claves hashables).
        # El adaptador los coacciona a str o None, así ninguno llega como tipo hostil al motor.
        cruda = {"id": "x", "timestamp": 99999,
                 "rule": {"id": "5760", "groups": ["authentication_failed"], "level": 10},
                 "predecoder": {"hostname": {"x": 1}, "program_name": {"y": 2}},
                 "data": {"srcip": {"a": 1}}}
        a = adaptador_wazuh.normalizar_alerta(cruda, "c")
        for k in ("timestamp", "activo", "servicio", "origen_ip"):
            self.assertTrue(a[k] is None or isinstance(a[k], str), f"{k}={a[k]!r}")

    def test_srcip_lista_no_rompe(self):
        a = adaptador_wazuh.normalizar_alerta({"data": {"srcip": [1, 2, 3]}}, "c")
        self.assertIsNone(a["origen_ip"])

    def test_regla_id_y_nivel_hostiles_no_rompen_la_agrupacion(self):
        # regla_id se usa como clave de Counter (agrupacion) y nivel_wazuh en comparaciones max/sorted:
        # un tipo hostil ahi tambien tumba el daemon FUERA de la barrera. Deben quedar hashable/comparable.
        from prototipo import agrupacion
        cr = lambda i, rid, lvl: {"id": i, "rule": {"id": rid, "groups": ["authentication_failed"], "level": lvl},
                                  "predecoder": {"hostname": "web", "program_name": "sshd"},
                                  "data": {"srcip": "1.2.3.4"}, "timestamp": "2026-01-01T00:00:00Z"}
        a1 = adaptador_wazuh.normalizar_alerta(cr("1", [1, 2], [9]), "c")
        a2 = adaptador_wazuh.normalizar_alerta(cr("2", "5760", 10), "c")
        self.assertTrue(a1["regla_id"] is None or isinstance(a1["regla_id"], str))
        self.assertTrue(a1["nivel_wazuh"] is None or isinstance(a1["nivel_wazuh"], int))
        agrupacion.agrupar([a1, a2])   # Counter(regla_id) + max/sorted(nivel_wazuh): no debe lanzar


class TestIngerirFichero(unittest.TestCase):
    def test_linea_corrupta_se_salta(self):
        regs = ingesta.ingerir_fichero(os.path.join(FX, "alertas_crudas.jsonl"),
                                       adaptador_wazuh.adaptador("lote"))
        self.assertEqual(len(regs), 1)          # solo la válida; vacía y corrupta se saltan
        self.assertEqual(regs[0]["activo"], "objetivo-vuln")


class TestAgnostico(unittest.TestCase):
    def test_adaptador_intercambiable(self):
        # RNF-06: el núcleo no sabe de Wazuh; un adaptador de otra fuente funciona igual
        def adaptador_falso(cruda):
            return {"id_alerta": cruda.get("uuid"), "activo": cruda.get("host"),
                    "fuente": "empresa-x"}
        reg = ingesta.normalizar({"uuid": "9", "host": "srv1"}, adaptador_falso)
        self.assertEqual(reg, {"id_alerta": "9", "activo": "srv1", "fuente": "empresa-x"})


if __name__ == "__main__":
    unittest.main()


class TestTelemetriaPropia(unittest.TestCase):
    def test_las_anclas_de_la_traza_no_son_alertas(self):
        # Sin esto: ancla -> alerta -> decision -> ancla -> ... (medido: 14 registros por un ataque).
        from prototipo import adaptador_wazuh
        cruda = {"id": "x", "rule": {"id": "100100", "level": 3, "groups": ["triaje"]},
                 "predecoder": {"hostname": "triaje", "program_name": "triaje-ancla"},
                 "full_log": "fichero=t.jsonl registros=3 hash=abc"}
        self.assertIsNone(ingesta.normalizar(cruda, adaptador_wazuh.adaptador("c")))

    def test_ingerir_fichero_salta_la_telemetria_propia(self):
        import json, os, tempfile
        from prototipo import adaptador_wazuh
        ruta = tempfile.mktemp(suffix=".json")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "1", "rule": {"id": "100100", "groups": ["triaje"]}}) + "\n")
            f.write(json.dumps({"id": "2", "rule": {"id": "5760", "groups": ["sshd", "authentication_failed"]},
                                "data": {"srcip": "1.2.3.4"}}) + "\n")
        try:
            regs = ingesta.ingerir_fichero(ruta, adaptador_wazuh.adaptador("c"))
        finally:
            os.unlink(ruta)
        self.assertEqual([r["id_alerta"] for r in regs], ["2"])

