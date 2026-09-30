"""Doble de un nodo con iptables que responde como el de verdad: las reglas se guardan por cadena,
`iptables -L [CADENA] -n` devuelve la tabla con el formato real y el resto de la tubería de la
verificación (`| grep …`) se ejecuta con el grep del sistema. Sirve para probar lo que los dobles
simples no ven: que un patrón de verificación case de más (192.168.1.1 dentro de 192.168.1.10)."""
import re, subprocess

_REGLA = re.compile(r"^iptables -([AD]) (INPUT|FORWARD) -s (\S+) -j DROP$")


class NodoIptables:
    def __init__(self, drop_input=(), drop_forward=(), accept_input=()):
        self.reglas = {"INPUT": [("DROP", ip) for ip in drop_input] + [("ACCEPT", ip) for ip in accept_input],
                       "FORWARD": [("DROP", ip) for ip in drop_forward]}
        self.llamadas = []

    def tabla(self, cadena=None):
        lineas = []
        for nombre in ([cadena] if cadena else ["INPUT", "FORWARD", "OUTPUT"]):
            lineas.append(f"Chain {nombre} (policy ACCEPT)")
            lineas.append("target     prot opt source               destination")
            for objetivo, ip in self.reglas.get(nombre, []):
                lineas.append(f"{objetivo:<10} all  --  {ip:<20} 0.0.0.0/0")
            lineas.append("")
        return "\n".join(lineas) + "\n"

    def __call__(self, nodo_ip, cmd):
        self.llamadas.append(cmd)
        m = _REGLA.match(cmd)
        if m:
            op, cadena, ip = m.groups()
            if op == "A":
                self.reglas[cadena].append(("DROP", ip))
                return (0, "")
            if ("DROP", ip) in self.reglas[cadena]:
                self.reglas[cadena].remove(("DROP", ip))
                return (0, "")
            return (1, "iptables: Bad rule (does a matching rule exist in that chain?).")
        listado = re.match(r"^iptables -L(?: (INPUT|FORWARD))? -n(.*)$", cmd)
        if listado:
            cadena, resto = listado.groups()
            salida = self.tabla(cadena)
            resto = resto.strip()
            if not resto:
                return (0, salida)
            assert resto.startswith("|"), cmd
            p = subprocess.run(["sh", "-c", resto[1:]], input=salida, capture_output=True, text=True)
            return (p.returncode, p.stdout)
        return (0, "")
