"""Demo de la ESCALADA DETERMINISTA (sin modelo): el equipo atacado está caído / fuera de alcance,
y el sistema escala la contención al cortafuegos aguas arriba. Es el requisito del tutor industrial:
que el MDR no se quede sin respuesta cuando no puede actuar sobre la máquina atacada.

A diferencia de `demo-agente-escalado.py` (que usa el agente ReAct + LLM), esto ejerce el lazo real
`lazo.procesar_lazo` con la escalada determinista por defecto: instantánea, auditable, sin modelo.

Usa la topología del laboratorio (perfil empresarial: objetivo-vuln -> gateway) y un ejecutor
SIMULADO: la víctima (objetivo-vuln, 192.168.1.30) rechaza la conexión; el firewall (gateway,
192.168.1.1) responde. La contención salta al firewall y la traza queda con `escalado: True`.

  (En el banco es idéntico con más saltos —web-banking -> FW-core -> FW-edge—; aquí se usa el lab
   porque la IP del activo se resuelve de un mapa del lab, orden.IP_DE_NODO.)

Uso:  python3 lab/scripts/demo-escalada-determinista.py            (interactivo: apruebas el firewall)
      python3 lab/scripts/demo-escalada-determinista.py --auto     (auto-aprueba, no interactivo)

Qué observar/evaluar:
  - ejecucion.exito = False          -> el host caído no se pudo contener
  - escalado        = True           -> se escaló la contención
  - dispositivo_ejecutor = gateway   -> se contuvo en el firewall, NO en la máquina inaccesible
  - la validación humana se pide en el firewall (impacto alcanza_servicio -> humano_siempre)
  - la traza guarda el comando de reversión (RF-18, reversibilidad)
"""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from prototipo import lazo, catalogo as catm, perfil as perfilm

AUTO = "--auto" in sys.argv


class HostCaido:
    """La víctima (objetivo-vuln, 192.168.1.30) está caída/inaccesible; el firewall (gateway,
    192.168.1.1) responde y modela el estado del bloqueo (verif-antes 'no está'; tras aplicar,
    'está')."""
    def __init__(self):
        self.aplicado, self.llamadas = set(), []
    def __call__(self, nodo_ip, cmd):
        self.llamadas.append(nodo_ip)
        if nodo_ip == "192.168.1.30":                     # host atacado, caído
            return (255, "connect to host 192.168.1.30 port 22: Connection refused")
        if "grep" in cmd:                                 # verificación en el firewall
            return (0, "DROP") if nodo_ip in self.aplicado else (1, "")
        self.aplicado.add(nodo_ip)                         # aplicar la regla en el firewall
        return (0, "")


def main():
    perfil = perfilm.cargar(os.path.join(REPO, "prototipo", "perfiles", "empresarial.yml"))
    catalogo = catm.cargar_catalogo(os.path.join(REPO, "prototipo", "catalogo.yml"))
    # Fuerza bruta SSH contra un servicio de gestión expuesto (según el auditor) -> VP.
    alerta = {"id_alerta": "esc-01", "regla_id": "5760", "origen_ip": "203.0.113.9",
              "activo": "objetivo-vuln", "servicio": "ssh", "familia": "acceso_credenciales",
              "mitre": ["T1110.001"], "timestamp": "2026-09-21T09:00:00Z"}
    hallazgos = {"nodos": {"objetivo-vuln": [{"servicio": "ssh", "estado": "open"}]}}
    ejecutor = HostCaido()
    leer = (lambda p: "s") if AUTO else input

    print("=" * 70)
    print(f"ALERTA  regla {alerta['regla_id']} · {alerta['origen_ip']} -> {alerta['activo']} "
          f"({alerta['servicio']}) · familia {alerta['familia']}")
    print("El auditor confirma ssh expuesto -> VP; se propone contener.")
    if not AUTO:
        print("\n(Se te pedirá aprobar el bloqueo EN EL FIREWALL. Escribe 's' para aprobar.)\n")
    print("=" * 70)

    r = lazo.procesar_lazo(alerta, hallazgos, perfil, "empresarial", catalogo, ejecutor,
                           "demo-esc", alerta["timestamp"], leer=leer)

    print("\n── TRAZA ──")
    print(f"clase            : {r['clase']}  (confianza {r['confianza']})")
    print(f"accion propuesta : {r['accion_propuesta']} -> final {r['accion_final']} "
          f"(filtro {r['resultado_filtro']})")
    print("\n1) INTENTO EN EL ACTIVO ATACADO (objetivo-vuln, 192.168.1.30):")
    print(f"     ejecucion.exito   = {r['ejecucion']['exito']}   <- host caído / sin acceso")
    print(f"     verificacion      = {r['verificacion']['verificado']}")
    esc = r.get("escalada")
    if not esc:
        print("\n(No hubo escalada: revisa que el perfil tenga topología.)")
        return
    print("\n2) ESCALADA DETERMINISTA AL CORTAFUEGOS:")
    print(f"     escalado             = {esc['escalado']}")
    print(f"     resultado            = {esc['resultado']}")
    print(f"     dispositivo_ejecutor = {esc['dispositivo_ejecutor']}")
    oe = esc.get("orden_efectiva") or {}
    print(f"     orden_efectiva       = {oe.get('accion_id')} sobre {oe.get('nodo_ip')}")
    print(f"     reversiones          = {esc['reversiones']}")
    print("\n3) NO SE DEPENDIÓ DEL HOST CAÍDO:")
    print(f"     IPs contactadas por el ejecutor: {sorted(set(ejecutor.llamadas))}")
    print(f"     la contención efectiva se aplicó en {oe.get('nodo_ip')} (el firewall), no en el host.")
    print("=" * 70)


if __name__ == "__main__":
    main()
