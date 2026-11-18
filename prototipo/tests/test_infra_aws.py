"""infra/aws: lo común a las dos variantes y el descubrimiento de sus pruebas. Cada variante (mdr/,
laboratorio/) es autosuficiente y trae sus pruebas en infra/aws/<variante>/pruebas/; aquí se cargan las
que existan, así que borrar una variante no rompe la suite (plan-aws-dos-carpetas.md)."""
import glob
import os
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INFRA = os.path.join(RAIZ, "infra", "aws")


def carpetas_de_pruebas(infra=INFRA):
    """Las carpetas infra/aws/<variante>/pruebas que existen."""
    return sorted(d for d in glob.glob(os.path.join(infra, "*", "pruebas")) if os.path.isdir(d))


def load_tests(loader, pruebas, patron):
    for d in carpetas_de_pruebas():
        pruebas.addTests(loader.discover(d, pattern="test_*.py", top_level_dir=d))
    return pruebas


class TestComun(unittest.TestCase):
    def test_descubre_las_pruebas_de_cada_variante(self):
        nombres = [os.path.basename(os.path.dirname(d)) for d in carpetas_de_pruebas()]
        self.assertIn("mdr", nombres)
        cargadas = unittest.TestSuite()
        load_tests(unittest.defaultTestLoader, cargadas, None)
        ids = [t.id() for s in cargadas for g in s for t in g]
        self.assertTrue(any(i.startswith("test_mdr.") for i in ids), ids[:5])


PROBAR = os.path.join(INFRA, "emulador", "probar.sh")


def copia_sin(variante, destino):
    """Copia de infra/aws en destino/infra/aws sin la carpeta `variante` (ni estados ni cachés)."""
    import shutil
    dst = os.path.join(destino, "infra", "aws")
    shutil.copytree(INFRA, dst, ignore=shutil.ignore_patterns(".terraform", "terraform.tfstate*", "__pycache__"))
    shutil.rmtree(os.path.join(dst, variante))
    return dst


class TestEmulador(unittest.TestCase):
    def _probar(self, *args, raiz=None):
        import subprocess
        script = PROBAR if raiz is None else os.path.join(raiz, "emulador", "probar.sh")
        return subprocess.run(["sh", script, *args], capture_output=True, text=True, timeout=60)

    def test_listar_variantes(self):
        r = self._probar("--listar")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mdr: A B C D", r.stdout)
        self.assertIn("laboratorio: E F", r.stdout)

    def test_letra_de_variante_inexistente(self):
        # Review Focus 4: sin laboratorio/, «probar.sh E» dice que no existe, sin arrancar el emulador.
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            copia = copia_sin("laboratorio", d)
            r = self._probar("--listar", raiz=copia)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("mdr: A B C D", r.stdout)
            self.assertNotIn("laboratorio", r.stdout)
            r = self._probar("E", raiz=copia)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("escenario desconocido", r.stdout + r.stderr)
            self.assertNotIn("emulador no responde", r.stdout + r.stderr)



def enlaces_rotos(raiz=INFRA, solo_dentro=False):
    """Enlaces relativos que no existen en el índice (README.md, INSTALAR.md) y en el README de cada carpeta.
    Con solo_dentro, se ignoran los que salen de infra/aws (para una copia suelta de la carpeta)."""
    import re
    docs = [os.path.join(raiz, "README.md"), os.path.join(raiz, "INSTALAR.md")] + glob.glob(os.path.join(raiz, "*", "README.md"))
    rotos = []
    for doc in docs:
        if not os.path.exists(doc):
            continue
        with open(doc, encoding="utf-8") as f:
            for destino in re.findall(r"\]\(([^)#\s]+)", f.read()):
                if "://" in destino:
                    continue
                ruta = os.path.normpath(os.path.join(os.path.dirname(doc), destino))
                if solo_dentro and not ruta.startswith(os.path.normpath(raiz) + os.sep):
                    continue          # fuera de infra/aws (documentación): no depende de las variantes
                if not os.path.exists(ruta):
                    rotos.append(f"{os.path.relpath(doc, raiz)} -> {destino}")
    return rotos


def variantes(raiz=INFRA):
    return sorted(os.path.basename(os.path.dirname(os.path.dirname(f)))
                  for f in glob.glob(os.path.join(raiz, "*", "emulador", "escenarios.sh")))


class TestIndiceYAutosuficiencia(unittest.TestCase):
    def test_indice_enlaza_cada_variante_y_nada_roto(self):
        with open(os.path.join(INFRA, "README.md"), encoding="utf-8") as f:
            indice = f.read()
        self.assertEqual(variantes(), ["laboratorio", "mdr"])
        for v in variantes():
            self.assertIn(f"]({v}/", indice, v)
        self.assertIn("](INSTALAR.md)", indice)
        self.assertEqual(enlaces_rotos(), [])

    def test_borrar_una_variante(self):
        import subprocess
        import tempfile
        for borrada, queda in (("laboratorio", "mdr"), ("mdr", "laboratorio")):
            with self.subTest(borrada=borrada), tempfile.TemporaryDirectory() as d:
                copia = copia_sin(borrada, d)
                rotos = enlaces_rotos(copia, solo_dentro=True)
                self.assertTrue(rotos)
                self.assertTrue(all(borrada in r for r in rotos), rotos)   # solo lo que apuntaba a la borrada
                pruebas = os.path.join(copia, queda, "pruebas")
                r = subprocess.run(["python3", "-m", "unittest", "discover", "-s", pruebas, "-t", pruebas],
                                   capture_output=True, text=True, timeout=120)
                self.assertEqual(r.returncode, 0, r.stderr[-1500:])
                for carpeta in (os.path.join(copia, queda), os.path.join(copia, "modulos")):
                    for raiz_, dirs, ficheros in os.walk(carpeta):
                        dirs[:] = [x for x in dirs if x not in ("pruebas", ".terraform")]
                        for nombre in ficheros:
                            with open(os.path.join(raiz_, nombre), encoding="utf-8", errors="ignore") as f:
                                self.assertNotIn(f"../{borrada}", f.read(), os.path.join(raiz_, nombre))

    def test_como_probarla(self):
        for v in variantes():
            with open(os.path.join(INFRA, v, "README.md"), encoding="utf-8") as f:
                r = f.read()
            self.assertIn("## Cómo probarla", r, v)
            s = r[r.index("## Cómo probarla"):]
            self.assertIn(f"probar.sh {v}", s, v)
            self.assertIn("tofu validate", s, v)

    def test_copiar_una_carpeta(self):
        # Review Focus 2: quien se lleve solo una carpeta necesita también el módulo común.
        for v in variantes():
            with open(os.path.join(INFRA, v, "README.md"), encoding="utf-8") as f:
                self.assertIn("modulos/base", f.read(), v)

    def test_estado_separado(self):
        # Review Focus 3: las dos variantes en el mismo bucket no se pisan el estado.
        import re
        claves = []
        for v in variantes():
            with open(os.path.join(INFRA, v, "backend.tf.ejemplo"), encoding="utf-8") as f:
                claves.append(re.search(r'key\s*=\s*"([^"]+)"', f.read()).group(1))
        self.assertEqual(len(set(claves)), len(claves), claves)


class TestCiEInstalar(unittest.TestCase):
    def test_ci_valida_cada_variante(self):
        # infra/aws ya no tiene .tf: validar ahí daba verde en vacío
        with open(os.path.join(RAIZ, ".github", "workflows", "ci.yml"), encoding="utf-8") as f:
            ci = f.read()
        iac = ci[ci.index("  iac:"):]
        for v in variantes():
            self.assertIn(f"infra/aws/{v}", iac, v)

    def test_instalar_sin_region_fija(self):
        # si se cambia la región, las órdenes y el destroy deben ir a la misma
        with open(os.path.join(INFRA, "INSTALAR.md"), encoding="utf-8") as f:
            g = f.read()
        self.assertNotIn("--region eu-west-1", g)
        self.assertIn('--region "$REGION"', g)
        self.assertIn('tofu destroy -var region="$REGION" -var egreso_bootstrap=true', g)


class TestMcpContraElEmulador(unittest.TestCase):
    """El servidor MCP de API de AWS contra el emulador (MDR_MCP=1 en probar.sh): nunca contra AWS real,
    solo lectura y sin telemetría."""
    CLIENTE = os.path.join(INFRA, "emulador", "mcp_cliente.py")

    def test_cliente_apunta_al_emulador_en_solo_lectura(self):
        with open(self.CLIENTE, encoding="utf-8") as f:
            c = f.read()
        for txt in ('"AWS_ENDPOINT_URL": "https://127.0.0.1:9297"', '"READ_OPERATIONS_ONLY": "true"',
                    '"AWS_API_MCP_TELEMETRY": "false"', '"AWS_CONFIG_FILE": "/dev/null"', "emulator_credentials",
                    "awslabs.aws-api-mcp-server"):
            self.assertIn(txt, c)
        # el entorno del servidor se construye entero: no hereda credenciales reales
        self.assertNotIn("os.environ.copy()", c)
        self.assertNotIn("**os.environ", c)

    def test_probar_lo_lanza_con_mdr_mcp(self):
        with open(PROBAR, encoding="utf-8") as f:
            p = f.read()
        self.assertIn("MDR_MCP", p)
        self.assertIn("mcp_cliente.py", p)
        self.assertLess(p.index("mcp_cliente.py"), p.index("tofu destroy -input=false"))   # antes de destruir

    def test_instrucciones(self):
        with open(os.path.join(INFRA, "README.md"), encoding="utf-8") as f:
            r = f.read()
        self.assertIn("MDR_MCP=1 sh infra/aws/emulador/probar.sh", r)
        self.assertIn("READ_OPERATIONS_ONLY", r)

    def test_instrucciones_de_la_cli_contra_el_emulador(self):
        with open(os.path.join(INFRA, "README.md"), encoding="utf-8") as f:
            r = f.read()
        s = r[r.index("## Consultar el emulador a mano"):]
        for txt in ('export PATH="$HOME/.local/bin:$PATH"', "aws-emulator --telemetry off",
                    "AWS_ENDPOINT_URL=https://127.0.0.1:9297", "AWS_DEFAULT_REGION=us-east-1",
                    "alias aws='uvx --quiet --from awscli aws'"):
            self.assertIn(txt, s)


if __name__ == "__main__":
    unittest.main()
