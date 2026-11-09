"""Convierte el manual de usuario (Markdown, subconjunto conocido) en un HTML listo para imprimir a PDF.
Uso: python3 convertir.py ENTRADA.md SALIDA.html"""
import html
import re
import sys

ENTRADA, SALIDA = sys.argv[1], sys.argv[2]


def slug(t):
    return re.sub(r"[^\w\- ]", "", t.strip().lower()).replace(" ", "-")


def inline(t):
    codigos = []

    def guarda(m):
        codigos.append(m.group(1))
        return f"\x00{len(codigos) - 1}\x00"

    t = re.sub(r"`([^`]+)`", guarda, t)
    t = html.escape(t, quote=False)

    def enlace(m):
        texto, href = m.group(1), m.group(2)
        if href.startswith("#"):
            return f'<a href="{href}">{texto}</a>'
        return f'<span class="ref">{texto}</span>'      # un fichero del repositorio: no es navegable en el PDF

    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", enlace, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<em>\1</em>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{html.escape(codigos[int(m.group(1))], quote=False)}</code>", t)


MARCA = re.compile(r"^([-*]|\d+\.) (.*)$")


def es_inicio(l):
    return (l.startswith("```") or re.match(r"#{1,6} ", l) or l.strip() == "---" or l.startswith("|")
            or MARCA.match(l))


def bloques(lineas):
    out, i, n = [], 0, len(lineas)
    while i < n:
        l = lineas[i]
        if not l.strip():
            i += 1
            continue
        if l.startswith("```"):
            j = i + 1
            while j < n and not lineas[j].startswith("```"):
                j += 1
            out.append("<pre><code>" + html.escape("\n".join(lineas[i + 1:j]), quote=False) + "</code></pre>")
            i = j + 1
            continue
        m = re.match(r"(#{1,6}) (.*)", l)
        if m:
            nivel, texto = len(m.group(1)), m.group(2)
            clase = ' class="parte"' if nivel == 1 and texto.startswith("Parte ") else ""
            out.append(f'<h{nivel} id="{slug(texto)}"{clase}>{inline(texto)}</h{nivel}>')
            i += 1
            continue
        if l.strip() == "---":
            i += 1
            continue
        if l.startswith("|"):
            filas = []
            while i < n and lineas[i].startswith("|"):
                filas.append([c.strip() for c in lineas[i].strip().strip("|").split("|")])
                i += 1
            cab, cuerpo = filas[0], filas[2:]
            t = "<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cab) + "</tr></thead><tbody>"
            t += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in f) + "</tr>" for f in cuerpo)
            out.append(t + "</tbody></table>")
            continue
        m = MARCA.match(l)
        if m:
            ordenada = m.group(1)[0].isdigit()
            items = []
            while i < n:
                m = MARCA.match(lineas[i])
                if not m or m.group(1)[0].isdigit() != ordenada:
                    break
                ancho = len(m.group(1)) + 1
                cont = [m.group(2)]
                i += 1
                while i < n:
                    s = lineas[i]
                    if not s.strip():
                        k = i
                        while k < n and not lineas[k].strip():
                            k += 1
                        if k < n and lineas[k].startswith(" " * ancho):
                            cont.extend([""] * (k - i))
                            i = k
                            continue
                        break
                    if s.startswith(" " * ancho):
                        cont.append(s[ancho:])
                        i += 1
                    elif not es_inicio(s) and not s.startswith(" "):
                        cont.append(s)              # continuación perezosa
                        i += 1
                    else:
                        break
                partes = bloques(cont)
                if len(partes) >= 1 and partes[0].startswith("<p>"):
                    partes[0] = partes[0][3:-4]      # lista compacta: el primer párrafo sin <p>
                items.append("<li>" + "".join(partes) + "</li>")
                while i < n and not lineas[i].strip() and i + 1 < n and MARCA.match(lineas[i + 1] or ""):
                    i += 1
            etiqueta = "ol" if ordenada else "ul"
            out.append(f"<{etiqueta}>" + "".join(items) + f"</{etiqueta}>")
            continue
        par = []
        while i < n and lineas[i].strip() and not (par and es_inicio(lineas[i])):
            par.append(lineas[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(par)) + "</p>")
    return out


texto = open(ENTRADA, encoding="utf-8").read().splitlines()
# la portada sustituye al título y a la nota de versión (que remite a ficheros del repositorio)
inicio = next(k for k, l in enumerate(texto) if l.startswith("## Para quién es"))
cuerpo = "\n".join(bloques(texto[inicio:]))

PORTADA = """
<section class="portada">
  <div class="marca">MDR · consola de triaje</div>
  <h1 class="titulo">Manual de usuario</h1>
  <p class="sub">MDR de triaje asistido: detección refinada, respuesta con control humano</p>
  <dl>
    <div><dt>Versión</dt><dd>9 de noviembre de 2026</dd></div>
    <div><dt>Para</dt><dd>Analistas del SOC y administración del MDR</dd></div>
    <div><dt>Cubre</dt><dd>Puesta en marcha, consola web, configuración y referencia</dd></div>
  </dl>
</section>
"""

CSS = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm; }
:root { --tinta:#1a1f27; --suave:#4a5361; --linea:#d9dee6; --acento:#0e7490; --fondo:#f4f6f9; }
* { box-sizing: border-box; }
body { margin:0; font-family: "Ubuntu Sans", "DejaVu Sans", sans-serif; font-size: 10.2pt; line-height: 1.5;
       color: var(--tinta); }
.portada { height: 250mm; display:flex; flex-direction:column; justify-content:center; break-after: page; }
.portada .marca { font-size: 10pt; letter-spacing: .08em; text-transform: uppercase; color: var(--acento); font-weight:700; }
.portada .titulo { font-size: 38pt; line-height:1.1; margin: 10mm 0 4mm; border:0; padding:0; }
.portada .sub { font-size: 14pt; color: var(--suave); max-width: 140mm; margin:0 0 18mm; }
.portada dl { margin:0; border-top: 2px solid var(--acento); padding-top: 6mm; display:grid; gap: 3mm; }
.portada dl div { display:grid; grid-template-columns: 30mm 1fr; }
.portada dt { color: var(--suave); } .portada dd { margin:0; font-weight:600; }
h1, h2, h3 { line-height: 1.25; break-after: avoid; page-break-after: avoid; }
h1 { font-size: 20pt; margin: 0 0 6mm; }
h1.parte { break-before: page; font-size: 22pt; color: var(--acento); border-bottom: 2px solid var(--acento); padding-bottom: 3mm; }
h2 { font-size: 14.5pt; margin: 8mm 0 3mm; padding-bottom: 1.5mm; border-bottom: 1px solid var(--linea); }
h3 { font-size: 11.5pt; margin: 6mm 0 2mm; }
p { margin: 0 0 2.6mm; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin: 0 0 1.2mm; }
li > ul, li > ol { margin-top: 1.2mm; }
code { font-family: "Ubuntu Mono", "DejaVu Sans Mono", monospace; font-size: 9.6pt; background: var(--fondo);
       border: 1px solid #e3e7ee; border-radius: 3px; padding: 0 1.2mm; }
pre { background: #10151c; color: #e6ebf1; border-radius: 4px; padding: 3mm 4mm; margin: 0 0 3mm;
      white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; border: 0; padding: 0; color: inherit; font-size: 9.4pt; }
table { width: 100%; border-collapse: collapse; margin: 1mm 0 4mm; font-size: 9.3pt; break-inside: auto; }
thead { display: table-header-group; }
tr { break-inside: avoid; page-break-inside: avoid; }
th { text-align: left; background: var(--fondo); color: var(--suave); font-weight: 700; border-bottom: 1.5px solid var(--linea); }
th, td { padding: 1.6mm 2.2mm; vertical-align: top; border-bottom: 1px solid var(--linea); }
a { color: var(--acento); text-decoration: none; }
.ref { color: var(--suave); }
strong { font-weight: 700; }
#índice + ul { columns: 2; column-gap: 10mm; }
#índice + ul > li { break-inside: avoid; }
"""

doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Manual de usuario · MDR de triaje asistido</title><style>{CSS}</style></head>
<body>{PORTADA}<main>{cuerpo}</main></body></html>"""
open(SALIDA, "w", encoding="utf-8").write(doc)
print("ok", SALIDA, len(doc))
