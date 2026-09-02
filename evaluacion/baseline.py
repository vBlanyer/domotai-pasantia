"""El nivel de regla de Wazuh binarizado como clasificador VP/FP, con barrido de umbral."""
from evaluacion import metricas

def predecir(nivel, umbral):
    return nivel >= umbral

def verdad_binaria(filas):
    return [f["etiqueta"] == "VP" for f in filas]

def barrido(filas, rango=range(3, 13)):
    verd = verdad_binaria(filas)
    puntos = []
    for t in rango:
        pred = [predecir(f["nivel_wazuh"], t) for f in filas]
        mat = metricas.matriz(pred, verd)
        puntos.append({"umbral": t, "matriz": mat, "f1": metricas.f1(mat)})
    def clave(p):
        f1 = p["f1"]
        # Desempate: con F1 empatado gana el MAYOR umbral (la regla más selectiva que aún alcanza F1 máx).
        return (f1 if isinstance(f1, (int, float)) else -1.0, p["umbral"])
    optimo = max(puntos, key=clave)
    return {"puntos": puntos, "optimo": optimo}
