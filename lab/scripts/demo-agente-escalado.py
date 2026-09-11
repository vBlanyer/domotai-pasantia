"""Demo del agente de mitigación (ReAct + Tool Calling acotado): escalado host->firewall.
Por defecto usa ejecutores SIMULADOS (host caído / firewall ok), que reproducen el escenario sin
necesitar SSH en el firewall del lab. Con --lab usa el conector SSH real (requiere el firewall
'borde' provisionado con sshd + credenciales, no incluido por defecto).

Uso:  python3 lab/scripts/demo-agente-escalado.py [--lab] [--autonomo] [--con-llm]
"""
import json, os, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from prototipo import agente_mitigacion as ag, catalogo as catm, perfil as perfilm, conector, rag


class EjecutorSimulado:
    """host víctima (.30) caído; firewall (.1) responde y modela el estado del bloqueo."""
    def __init__(self): self.aplicado = set()
    def __call__(self, nodo_ip, cmd):
        if nodo_ip == "192.168.1.30":
            return (255, "connect to host 192.168.1.30 port 22: Connection refused")
        if "grep" in cmd:
            return (0, "DROP") if nodo_ip in self.aplicado else (1, "")
        self.aplicado.add(nodo_ip)
        return (0, "(simulado)")


def generador_guion(_prompt, _estado={"i": 0}):
    pasos = [
        'Thought: consulto el conocimiento defensivo de la tecnica.\nAction: {"tool":"consultar_conocimiento","args":{}}',
        'Thought: intento el bloqueo local en el host victima.\nAction: {"tool":"ejecutar_comando","args":{"dispositivo":"objetivo-vuln","accion":"bloquear_ip"}}',
        'Thought: el host no responde; escalo al firewall perimetral.\nAction: {"tool":"ejecutar_comando","args":{"dispositivo":"gateway","accion":"bloquear_ip"}}',
        'Thought: verifico el corte en el firewall.\nAction: {"tool":"verificar_mitigacion","args":{"dispositivo":"gateway"}}',
        'Final: {"resultado":"mitigado","dispositivo_ejecutor":"gateway"}']
    i = _estado["i"]; _estado["i"] = min(i + 1, len(pasos) - 1); return pasos[i]


def main():
    lab, autonomo, con_llm = "--lab" in sys.argv, "--autonomo" in sys.argv, "--con-llm" in sys.argv
    perfil = perfilm.cargar(os.path.join(REPO, "prototipo/perfiles/empresarial.yml"))
    catalogo = catm.cargar_catalogo(os.path.join(REPO, "prototipo/catalogo.yml"))
    ejecutor = conector.ejecutor_por_defecto() if lab else EjecutorSimulado()
    try:
        indice = rag.cargar_indice()
    except Exception:
        indice = None
    if con_llm:
        # Misma invocacion que stream.construir_mitigar_fn: generador por defecto (servidor si
        # esta arrancado) con el esquema derivado del catalogo y la topologia, para que el
        # modelo no pueda nombrar nada fuera del catalogo (RF-15).
        from prototipo import justificador_llm
        esquema = ag.esquema_accion(catalogo, ag.resolver_topologia(perfil))
        base = justificador_llm.generador_por_defecto()
        generador = ((lambda p: base(p, esquema=esquema))
                     if base is justificador_llm.generador_servidor else base)
    else:
        generador = generador_guion
    alerta = {"id_alerta": "demo1", "origen_ip": "192.168.1.10", "activo": "objetivo-vuln",
              "servicio": "ssh", "regla_id": "5760", "mitre": ["T1110.001"]}
    print("== DEMO Agente de Mitigación — escalado host -> firewall (Tool Calling acotado) ==")
    plan = ag.bucle_react(alerta, "vp_intento_acceso", perfil, catalogo, ejecutor, generador,
                          autonomo=autonomo, timestamp="demo", indice=indice, embedder=rag.embedder_por_defecto())
    for p in plan["pasos"]:
        if p.get("thought"): print("  Thought:", p["thought"])
        if p.get("observacion"): print("  Observation:", p["observacion"])
    print(f"\n  Resultado: {plan['resultado']} · dispositivo ejecutor: {plan['dispositivo_ejecutor']} · "
          f"escalado: {plan['escalado']} · degradado: {plan['degradado']}")
    print(f"  Reversiones registradas (RF-18): {plan['reversiones']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
