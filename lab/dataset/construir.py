"""Orquestador: normaliza + etiqueta + puebla la partición -> etiquetado.jsonl."""
import json, os, sys, yaml
from lab.dataset import esquema, etiquetar as etq

def construir(campañas, particion_map, resoluciones):
    salida = []
    for c in campañas:
        ficha = c["ficha"]
        cid = ficha.get("id")
        # I3: una campaña sin partición asignada NO debe colarse como
        # particion=None (violaría el esquema, spec §7); es un error de
        # configuración que hay que atajar explícitamente.
        if cid not in particion_map:
            raise ValueError(f"campaña {cid!r} no tiene partición asignada en particion.yml")
        parte = particion_map[cid]
        for cruda in c["alertas"]:
            reg = esquema.normalizar_alerta(cruda, cid)
            reg = etq.etiquetar(reg, c["hallazgos"], ficha, resoluciones)
            reg["particion"] = parte
            salida.append(reg)
    return salida

def _cargar_campaña(dir_camp):
    with open(os.path.join(dir_camp, "campaña.yml"), encoding="utf-8") as f:
        ficha = yaml.safe_load(f)
    with open(os.path.join(dir_camp, "hallazgos.json"), encoding="utf-8") as f:
        hallazgos = json.load(f)
    alertas = []
    with open(os.path.join(dir_camp, "alerts.json"), encoding="utf-8") as f:
        for l in f:
            l = l.strip()
            if l:
                try:
                    alertas.append(json.loads(l))
                except json.JSONDecodeError:
                    continue
    return {"alertas": alertas, "hallazgos": hallazgos, "ficha": ficha}

def main(argv):
    raiz_campañas, particion_yml, resoluciones_yml, salida = argv[1:5]
    with open(particion_yml, encoding="utf-8") as f:
        pobj = yaml.safe_load(f) or {}
    particion_map = {}
    for cid in pobj.get("entrenamiento", []) or []:
        particion_map[cid] = "entrenamiento"
    for cid in pobj.get("evaluacion", []) or []:
        particion_map[cid] = "evaluacion"
    with open(resoluciones_yml, encoding="utf-8") as f:
        resoluciones = yaml.safe_load(f) or {}
    campañas = []
    for nombre in sorted(os.listdir(raiz_campañas)):
        d = os.path.join(raiz_campañas, nombre)
        if os.path.isdir(d):
            campañas.append(_cargar_campaña(d))
    regs = construir(campañas, particion_map, resoluciones)
    with open(salida, "w", encoding="utf-8") as f:
        for r in regs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    pend = sum(1 for r in regs if r["etiqueta"] == "PENDIENTE")
    print(f"{len(regs)} alertas etiquetadas -> {salida}  ({pend} PENDIENTE por resolver a mano)")

if __name__ == "__main__":
    main(sys.argv)
