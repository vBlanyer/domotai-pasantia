"""Variante con validación humana REAL. Una acción que alcanza el servicio (BLOQUEAR_PUERTO,
provocada) + confianza baja -> el perfil empresarial la DEGRADA a BLOQUEAR_IP y exige aprobación.
Corre el mismo punto de decisión dos veces: RECHAZAR (no ejecuta) y APROBAR (ejecuta la acción
degradada por SSH). Muestra que la decisión humana gobierna la ejecución y la lógica de continuidad.

Uso:  python3 lab/scripts/demo-validacion-humana.py
Requiere el laboratorio en marcha y el índice RAG. Escenario provocado (ver 5B): el baseline casi
nunca dispara validación humana; aquí se fuerza para ejercitar el camino RF-08.
"""
import json, subprocess, os, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from prototipo import ingesta, adaptador_wazuh
from prototipo import analisis, orden as ordenm, conector, verificacion, validacion
from prototipo import perfil as perfilm, catalogo as catm, rag, justificador_llm

VICT_C, VICT_IP, ATAC_C, ATAC_IP, WAZUH_C = (
    "clab-red-cliente-objetivo-vuln", "192.168.1.30",
    "clab-red-cliente-puesto", "192.168.1.10", "clab-red-cliente-wazuh")

def dexec(c, cmd):
    cp = subprocess.run(["docker", "exec", c, "sh", "-c", cmd], capture_output=True, text=True)
    return (cp.stdout + cp.stderr).strip()
def barra(t): print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)

def preparar_ataque():
    dexec(VICT_C, f"iptables -D INPUT -s {ATAC_IP} -j DROP 2>/dev/null")
    for i in range(1, 4):
        dexec(ATAC_C, f"sshpass -p x_{i} ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 "
                      f"-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no "
                      f"-o PreferredAuthentications=password msfadmin@{VICT_IP} id 2>/dev/null")
    time.sleep(5)

def alerta_fresca():
    for l in reversed(dexec(WAZUH_C, "tail -60 /var/ossec/logs/alerts/alerts.json").splitlines()):
        try: d = json.loads(l)
        except Exception: continue
        if str(d.get("rule", {}).get("id")) in ("5760","5763","5710","5712","5716") and d.get("data", {}).get("srcip"):
            return ingesta.normalizar(d, adaptador_wazuh.adaptador("demo-humano"))
    return None

def iptables():
    return dexec(VICT_C, "iptables -L INPUT -n | tail -n +3") or "(sin reglas)"

def main():
    print("Lanzando fuerza bruta SSH real...")
    preparar_ataque()
    alerta = alerta_fresca()
    if not alerta:
        print("Sin alerta SSH fresca."); return 1

    perfil = perfilm.cargar(os.path.join(REPO, "prototipo/perfiles/empresarial.yml"))
    catalogo = catm.cargar_catalogo(os.path.join(REPO, "prototipo/catalogo.yml"))
    indice = rag.cargar_indice()
    recuperar_fn = lambda a: rag.recuperar(rag.construir_consulta(a), indice, rag.embedder_llama, k=3)

    barra("1 · TRIAJE — confianza baja (el auditor no tiene postura del activo)")
    ctx = analisis.enriquecer(alerta, {}, perfil)          # hallazgos vacíos -> postura None -> confianza 0.5
    clas = analisis.clasificar(alerta, ctx)
    rag_r = justificador_llm.justificar_con_rag(alerta, ctx, clas["clase"], justificador_llm.generador_llama, recuperar_fn)
    print(f"  Alerta: regla {alerta['regla_id']} · origen {alerta['origen_ip']} -> {alerta['activo']} ({alerta['servicio']})")
    print(f"  Clase: {clas['clase']} · Confianza: {clas['confianza']} (postura={ctx['postura']})")
    print(f"  Justificación RAG ({rag_r['justificador']}, pasajes {rag_r['pasajes_usados']}):")
    print("   ", rag_r['texto'].replace("\n", " ")[:280])

    barra("2 · DECISIÓN — acción que alcanza el servicio (escenario provocado)")
    accion_prop, params = "BLOQUEAR_PUERTO", {"puerto": "80"}
    impacto = catalogo[accion_prop]["impacto"]
    print(f"  Acción considerada: {accion_prop} {params} · impacto: {impacto}")
    print("  (el baseline propondría BLOQUEAR_IP; se provoca una acción disruptiva para ejercitar")
    print("   la continuidad y la validación humana — como en 5B, documentado)")
    filtro = perfilm.filtrar(perfil, accion_prop, params, catalogo, alerta['activo'], alerta['servicio'], clas['confianza'])
    print(f"  Filtro empresarial: resultado={filtro['resultado']} · acción final={filtro['accion_final']} · requiere_humano={filtro['requiere_humano']}")
    print("  -> DEGRADA la acción disruptiva a una localizada y EXIGE aprobación humana.")

    decision = {"id_decision": "demo-humano", "activo": alerta['activo'], "clase": clas['clase'],
                "prioridad": clas['prioridad'], "confianza": clas['confianza'], "justificacion": rag_r['texto'],
                "accion_propuesta": accion_prop, "impacto": impacto,
                "resultado_filtro": filtro['resultado'], "accion_final": filtro['accion_final'],
                "requiere_humano": filtro['requiere_humano']}

    barra("3 · VALIDACIÓN HUMANA — Beat A: el analista RECHAZA")
    ver_a = validacion.pedir(decision, alerta, leer=lambda _p: "rechazar")
    print(f"  veredicto -> {ver_a['veredicto']}  => NO se ejecuta nada.")
    print("  iptables tras rechazar:", iptables())

    barra("4 · VALIDACIÓN HUMANA — Beat B: el analista APRUEBA")
    ver_b = validacion.pedir(decision, alerta, leer=lambda _p: "aprobar")
    print(f"  veredicto -> {ver_b['veredicto']}")
    o = ordenm.construir(decision, alerta)
    print(f"  Orden ejecutable: {o['accion_id']} params={o['params']} sobre {o['nodo_objetivo']} ({o['nodo_ip']})")
    ejec = conector.ejecutar_orden(o, catalogo, conector.ejecutor_ssh_lab, alerta.get('timestamp', ''))
    verif = verificacion.confirmar(o, catalogo, conector.ejecutor_ssh_lab)
    print(f"  Ejecución por SSH: éxito={ejec.get('exito')} · comando: {ejec.get('comando_ejecutado')}")
    print(f"  Verificación: verificado={verif.get('verificado')}")

    barra("5 · EFECTO — la víctima tras la aprobación")
    print("  iptables INPUT:", iptables())
    print("  atacante alcanza .30:22?:", dexec(ATAC_C, f"nc -z -w4 {VICT_IP} 22 && echo ALCANZABLE || echo BLOQUEADO"))
    print("\n== FIN VARIANTE ==  (para dejar el lab neutro: docker exec %s iptables -D INPUT -s %s -j DROP)" % (VICT_C, ATAC_IP))
    return 0

if __name__ == "__main__":
    sys.exit(main())
