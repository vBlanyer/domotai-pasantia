"""Demo en vivo del lazo completo del prototipo contra el laboratorio, narrando 3 vistas
(víctima / atacante / triaje). Lanza una fuerza bruta SSH real, deja que Wazuh alerte, corre el
motor de triaje con RAG y el conector SSH real, y muestra el bloqueo y su verificación.

Uso:  python3 lab/scripts/demo-lazo-vivo.py
Requiere el laboratorio en marcha (sh lab/lab.sh up) y el índice RAG (python3 -m prototipo.rag --indexar).
"""
import json, subprocess, os, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from lab.dataset import esquema
from prototipo import triaje, orden as ordenm, conector, verificacion
from prototipo import perfil as perfilm, catalogo as catm, rag, justificador_llm

VICT_C, VICT_IP, ATAC_C, ATAC_IP, WAZUH_C = (
    "clab-red-cliente-objetivo-vuln", "192.168.1.30",
    "clab-red-cliente-puesto", "192.168.1.10", "clab-red-cliente-wazuh")

def dexec(c, cmd):
    cp = subprocess.run(["docker", "exec", c, "sh", "-c", cmd], capture_output=True, text=True)
    return (cp.stdout + cp.stderr).strip()
def barra(t): print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)

def preparar_ataque():
    """Deja el lab neutro y lanza una ráfaga de fuerza bruta SSH real desde el atacante."""
    dexec(VICT_C, f"iptables -D INPUT -s {ATAC_IP} -j DROP 2>/dev/null")
    for i in range(1, 6):
        dexec(ATAC_C, f"sshpass -p mal_{i} ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 "
                      f"-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no "
                      f"-o PreferredAuthentications=password msfadmin@{VICT_IP} id 2>/dev/null")
    time.sleep(5)

def alerta_fresca():
    for l in reversed(dexec(WAZUH_C, "tail -60 /var/ossec/logs/alerts/alerts.json").splitlines()):
        try: d = json.loads(l)
        except Exception: continue
        if str(d.get("rule", {}).get("id")) in ("5760","5763","5710","5712","5716") and d.get("data", {}).get("srcip"):
            return esquema.normalizar_alerta(d, "demo-vivo")
    return None

def main():
    print("Lanzando fuerza bruta SSH real desde el atacante...")
    preparar_ataque()
    alerta = alerta_fresca()
    if not alerta:
        print("No hay alerta SSH fresca en Wazuh."); return 1

    perfil = perfilm.cargar(os.path.join(REPO, "prototipo/perfiles/empresarial.yml"))
    catalogo = catm.cargar_catalogo(os.path.join(REPO, "prototipo/catalogo.yml"))
    hallazgos = json.load(open(os.path.join(REPO, "lab/campañas/2026-08-31-evaluacion/hallazgos.json"), encoding="utf-8"))
    indice = rag.cargar_indice()
    recuperar_fn = lambda a: rag.recuperar(rag.construir_consulta(a), indice, rag.embedder_llama, k=3)

    barra("0 · La alerta que Wazuh acaba de generar (fuerza bruta SSH real)")
    print(f"  regla {alerta['regla_id']} (nivel {alerta['nivel_wazuh']}) · MITRE {alerta['mitre']}")
    print(f"  origen {alerta['origen_ip']} -> {alerta['activo']} ({alerta['servicio']}) · familia {alerta['familia']}")
    print(f"  evento: {alerta['evento_crudo']}")

    barra("1 · VÍCTIMA (objetivo-vuln .30) — estado ANTES")
    for ln in dexec(VICT_C, "grep 'Failed password' /var/log/auth.log | tail -3").splitlines():
        print("   ", ln)
    print("  iptables INPUT:", dexec(VICT_C, "iptables -L INPUT -n | tail -n +3") or "(sin reglas)")

    barra("2 · ATACANTE (puesto .10)")
    print("  puerto 22 antes del bloqueo:",
          dexec(ATAC_C, f"nc -z -w3 {VICT_IP} 22 && echo ALCANZABLE || echo no"))

    barra("3 · TRIAJE — clasifica y justifica CON RAG")
    capturado = {}
    def just_rag(al, ctx, clase):
        r = justificador_llm.justificar_con_rag(al, ctx, clase, justificador_llm.generador_llama, recuperar_fn)
        capturado.update(r); return r["texto"]
    ts = alerta.get("timestamp", "")
    decision = triaje.procesar(alerta, hallazgos, perfil, "empresarial", catalogo, "demo-vivo", ts, justificar_fn=just_rag)
    print(f"  Clase: {decision['clase']} · Prioridad: {decision['prioridad']} · Confianza: {decision['confianza']}")
    print(f"  Pasajes RAG: {capturado.get('pasajes_usados')}  ·  justificador: {capturado.get('justificador')}")
    print("  Justificación:", (decision['justificacion'] or "").replace("\n", " ")[:360])
    print(f"  Acción: {decision['accion_propuesta']} · impacto {decision['impacto']} · filtro {decision['resultado_filtro']} "
          f"· final {decision['accion_final']} · requiere_humano {decision['requiere_humano']}")

    barra("4 · VALIDACIÓN HUMANA (demo: aprobar)")
    print(f"  -> APROBAR {decision['accion_final']} contra {alerta['origen_ip']}")

    barra("5 · EJECUCIÓN por SSH (conector real) y VERIFICACIÓN")
    o = ordenm.construir(decision, alerta)
    if o is None:
        print("  (la decisión no produce orden ejecutable)"); return 0
    print(f"  Orden: {o['accion_id']} params={o['params']} sobre {o['nodo_objetivo']} ({o['nodo_ip']})")
    ejec = conector.ejecutar_orden(o, catalogo, conector.ejecutor_ssh_lab, ts)
    verif = verificacion.confirmar(o, catalogo, conector.ejecutor_ssh_lab)
    print(f"  Ejecución: éxito={ejec.get('exito')} · comando: {ejec.get('comando_ejecutado')}")
    print(f"  Verificación: verificado={verif.get('verificado')}")

    barra("6 · EFECTO — víctima y atacante DESPUÉS")
    print("  iptables INPUT:", dexec(VICT_C, "iptables -L INPUT -n | tail -n +3"))
    print("  atacante alcanza .30:22?:", dexec(ATAC_C, f"nc -z -w4 {VICT_IP} 22 && echo ALCANZABLE || echo BLOQUEADO"))
    print("\n== FIN DEMO ==  (para dejar el lab neutro: docker exec %s iptables -D INPUT -s %s -j DROP)" % (VICT_C, ATAC_IP))
    return 0

if __name__ == "__main__":
    sys.exit(main())
