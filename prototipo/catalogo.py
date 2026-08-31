"""El catálogo de acciones como dato: impacto, reversión y comando por acción."""
import yaml

def cargar_catalogo(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)

def impacto_de(catalogo, accion_id):
    return catalogo[accion_id]["impacto"]
