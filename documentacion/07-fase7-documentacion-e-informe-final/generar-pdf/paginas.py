"""Lee los marcadores de un PDF de Chromium y escribe {título: página} para el índice.
Sin dependencias: Chromium escribe los objetos sin comprimir en flujos de objetos.
Uso: python3 paginas.py entrada.pdf salida.json"""
import json
import re
import sys

b = open(sys.argv[1], "rb").read()
objs = {int(m.group(1)): m.group(2) for m in re.finditer(rb"(\d+) 0 obj\s*(.*?)endobj", b, re.S)}


def ref(texto, clave):
    m = re.search(rb"/" + clave + rb"\s+(\d+) 0 R", texto)
    return int(m.group(1)) if m else None


# orden de las páginas: recorrer el árbol /Pages desde el catálogo
raiz = next(o for o in objs.values() if re.search(rb"/Type\s*/Catalog", o))
orden = []


def recorrer(n):
    o = objs[n]
    if re.search(rb"/Type\s*/Pages\b", o):
        for k in re.findall(rb"(\d+) 0 R", re.search(rb"/Kids\s*\[(.*?)\]", o, re.S).group(1)):
            recorrer(int(k))
    else:
        orden.append(n)


recorrer(ref(raiz, b"Pages"))
pagina = {n: i + 1 for i, n in enumerate(orden)}


def texto_pdf(t):
    t = t.strip()
    if t.startswith(b"<"):
        return bytes.fromhex(t[1:-1].decode()).decode("utf-16-be").lstrip("﻿")
    s = t[1:-1]
    s = re.sub(rb"\\([()\\])", rb"\1", s)
    return s.decode("latin-1")


salida = {}
for o in objs.values():
    m = re.search(rb"/Title\s*(\(.*?\)|<[0-9A-Fa-f]*>)\s*/Dest\s*\[(\d+) 0 R", o, re.S)
    if m:
        salida.setdefault(texto_pdf(m.group(1)), pagina.get(int(m.group(2))))
json.dump(salida, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", len(salida), "marcadores,", len(orden), "páginas")
