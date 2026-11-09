"""Convierte el manual de usuario (Markdown, subconjunto conocido) en un HTML listo para imprimir a PDF,
con diseño de guía funcional: portada con banda, cabecera y pie en cada página, índice
con números de página y cajas «Quién puede», «Nota» y «Ejemplo».

Uso: python3 convertir.py ENTRADA.md SALIDA.html [paginas.json] [--titulo T] [--sub S]
  paginas.json (opcional): {título de sección: página}, de una primera impresión (ver imprimir.mjs).
  --titulo: el tipo de documento de la portada y la cabecera (por defecto «Manual de usuario»).
  --sub: la línea bajo el título de la portada (por defecto «Consola de detección y respuesta»).
"""
import html
import json
import re
import sys


def _opcion(nombre, defecto):
    if nombre in sys.argv:
        i = sys.argv.index(nombre)
        valor = sys.argv[i + 1]
        del sys.argv[i:i + 2]
        return valor
    return defecto


TITULO_DOC = _opcion("--titulo", "Manual de usuario")
LINEA_SUB = _opcion("--sub", "Consola de detección y respuesta")
ENTRADA, SALIDA = sys.argv[1], sys.argv[2]
PAGINAS = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}

SUBTITULO = "MDR de triaje asistido"
META = [("Edición", "1.0"), ("Software", "MDR 1.7"), ("Fecha", "Noviembre 2026")]


def slug(t):
    return re.sub(r"[^\w\- ]", "", t.strip().lower()).replace(" ", "-")


def plano(t):
    """El texto de un título sin marcas de Markdown (como lo pone el navegador en los marcadores)."""
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t).strip()


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
CAJAS = {"Quién puede": "quien", "Nota": "nota", "Ejemplo": "ejemplo"}


def es_inicio(l):
    return (l.startswith("```") or re.match(r"#{1,6} ", l) or l.strip() == "---" or l.startswith("|")
            or l.startswith(">") or MARCA.match(l))


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
            clase = ' class="bloque"' if nivel == 1 else ""
            out.append(f'<h{nivel} id="{slug(plano(texto))}"{clase}>{inline(texto)}</h{nivel}>')
            i += 1
            continue
        if l.strip() == "---":
            i += 1
            continue
        if l.startswith(">"):
            texto = []
            while i < n and lineas[i].startswith(">"):
                texto.append(lineas[i][1:].strip())
                i += 1
            cuerpo = " ".join(texto)
            m = re.match(r"\*\*(.+?):\*\*\s*(.*)", cuerpo)
            clase = CAJAS.get(m.group(1)) if m else None
            if clase:
                out.append(f'<div class="caja {clase}"><strong>{m.group(1)}:</strong> {inline(m.group(2))}</div>')
            else:
                out.append(f'<div class="caja nota">{inline(cuerpo)}</div>')
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
                if partes and partes[0].startswith("<p>"):
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
# fuera: el título y la nota de versión (los pone la portada) y el índice del Markdown (se genera aquí)
inicio = next(k for k, l in enumerate(texto) if l.startswith("# ") and k > 0)
cuerpo_md = texto[inicio:]

# índice con números de página: un grupo por bloque (# …) y una línea por sección (## …)
indice, grupo = [], None
for l in cuerpo_md:
    m = re.match(r"(#{1,2}) (.*)", l)
    if not m:
        continue
    t = plano(m.group(2))
    if len(m.group(1)) == 1:
        indice.append(f'<div class="ind-grupo">{html.escape(t)}</div>')
    else:
        num = re.match(r"(\d+)\.\s+(.*)", t)
        etiqueta = (f'<span class="ind-num">{num.group(1)}.</span>{html.escape(num.group(2))}' if num
                    else html.escape(t))
        pag = PAGINAS.get(t, "")
        indice.append(f'<a class="ind-linea" href="#{slug(t)}"><span class="ind-tit">{etiqueta}</span>'
                      f'<span class="ind-pag">{pag}</span></a>')

cuerpo = "\n".join(bloques(cuerpo_md))

PORTADA = f"""
<section class="portada">
  <div class="banda"><div class="marca">MDR · CONSOLA DE TRIAJE</div></div>
  <div class="raya"></div>
  <div class="centro">
    <div class="tipo">{TITULO_DOC.upper()}</div>
    <h1 class="titulo">{SUBTITULO}</h1>
    <div class="sub">{LINEA_SUB}</div>
    <dl>{''.join(f'<dt>{k}:</dt><dd>{v}</dd>' for k, v in META)}</dl>
  </div>
  <div class="banda-pie"></div>
</section>
"""

AZUL, NARANJA = "#2F6E9B", "#F0652A"
CSS = f"""
@page {{
  size: A4; margin: 24mm 20mm 22mm 20mm;
  @top-left {{ content: "{TITULO_DOC} - {SUBTITULO}"; font: 8.5pt "Ubuntu Sans", "DejaVu Sans", sans-serif; color: #5b6573;
               vertical-align: bottom; padding-bottom: 2.5mm; border-bottom: 0.6pt solid {AZUL}; }}
  @top-center {{ content: ""; border-bottom: 0.6pt solid {AZUL}; }}
  @top-right {{ content: ""; font: 8.5pt "Ubuntu Sans", "DejaVu Sans", sans-serif; color: #5b6573;
                vertical-align: bottom; padding-bottom: 2.5mm; border-bottom: 0.6pt solid {AZUL}; }}
  @bottom-center {{ content: counter(page); font: 8.5pt "Ubuntu Sans", "DejaVu Sans", sans-serif; color: #3a424d; }}
}}
@page :first {{ margin: 0; @top-left {{ content: none; border: 0 }} @top-center {{ content: none; border: 0 }}
  @top-right {{ content: none; border: 0 }} @bottom-center {{ content: none }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Ubuntu Sans", "DejaVu Sans", sans-serif; font-size: 10pt; line-height: 1.45; color: #1d232b;
        text-align: justify; hyphens: auto; }}

/* portada */
.portada {{ position: relative; width: 210mm; height: 297mm; break-after: page; text-align: center; }}
.portada .banda {{ height: 47mm; background: {AZUL}; display: flex; align-items: center; justify-content: center; }}
.portada .marca {{ color: #fff; font-weight: 700; font-size: 17pt; letter-spacing: .14em; }}
.portada .raya {{ height: 2.2mm; background: {NARANJA}; }}
.portada .centro {{ padding-top: 34mm; }}
.portada .tipo {{ font-size: 15pt; color: #3a424d; letter-spacing: .02em; }}
.portada .titulo {{ font-size: 28pt; color: {AZUL}; margin: 13mm 0 1mm; border: 0; padding: 0; text-align: center; }}
.portada .sub {{ font-size: 17pt; font-weight: 700; color: {AZUL}; }}
.portada dl {{ display: grid; grid-template-columns: 1fr 1fr; column-gap: 4mm; row-gap: 2.6mm; width: 110mm;
               margin: 36mm auto 0; font-size: 11pt; }}
.portada dt {{ text-align: right; color: #5a86ad; }} .portada dd {{ margin: 0; text-align: left; }}
.portada .banda-pie {{ position: absolute; left: 0; right: 0; bottom: 0; height: 17mm; background: {AZUL}; }}

/* índice */
.indice {{ break-after: page; }}
.indice h1 {{ font-size: 17pt; color: {AZUL}; margin: 2mm 0 4mm; padding-bottom: 3mm; border-bottom: 0.8pt solid {AZUL}; }}
.ind-grupo {{ color: {AZUL}; font-weight: 700; font-size: 11pt; margin: 2.8mm 0 0.6mm; }}
.ind-linea {{ display: flex; justify-content: space-between; color: #1d232b; font-weight: 700; font-size: 10pt;
              padding: 0.45mm 0; text-decoration: none; text-align: left; }}
.ind-num {{ display: inline-block; min-width: 7mm; }}
.ind-pag {{ min-width: 10mm; text-align: right; }}

/* títulos */
h1, h2, h3, h4 {{ line-height: 1.25; break-after: avoid; page-break-after: avoid; text-align: left; }}
h1.bloque {{ break-before: page; font-size: 22pt; color: {AZUL}; margin: 6mm 0 7mm; padding-top: 5mm; position: relative; }}
h1.bloque::before {{ content: ""; position: absolute; top: 0; left: 0; width: 24mm; height: 1.4mm; background: {NARANJA}; }}
h2 {{ font-size: 14pt; color: {AZUL}; margin: 8mm 0 4mm; padding-bottom: 2.5mm; border-bottom: 0.6pt solid {AZUL}; }}
h3 {{ font-size: 11pt; color: {AZUL}; margin: 5.5mm 0 2mm; }}
h4 {{ font-size: 10pt; color: #5a86ad; margin: 4mm 0 1.5mm; }}
p {{ margin: 0 0 2.4mm; }}
p:has(+ table), p:has(+ ul), p:has(+ ol), h3 + p:has(+ table) {{ break-after: avoid; }}
ul, ol {{ margin: 0 0 3mm; padding-left: 6mm; }}
li {{ margin: 0 0 1mm; }}
ul li::marker {{ color: {AZUL}; }}
li > ul, li > ol {{ margin-top: 1mm; }}

/* tablas */
table {{ width: 100%; border-collapse: collapse; margin: 1.5mm 0 4.5mm; font-size: 9pt; text-align: left;
         border-top: 1.2pt solid #1d232b; border-bottom: 1.2pt solid #1d232b; }}
thead {{ display: table-header-group; }}
th {{ background: {AZUL}; color: #fff; font-weight: 700; padding: 1.8mm 2.4mm; vertical-align: top; }}
td {{ padding: 1.4mm 2.4mm; vertical-align: top; hyphens: manual; }}
th {{ hyphens: manual; }}
tbody tr:nth-child(odd) td {{ background: #F4F6F9; }}
tr {{ break-inside: avoid; page-break-inside: avoid; }}

/* cajas */
.caja {{ border-radius: 2mm; padding: 2.6mm 3.6mm; margin: 2mm 0 4mm; font-size: 9pt; break-inside: avoid; text-align: left; }}
.caja.quien {{ background: #FDEDE6; border: 0.6pt solid {NARANJA}; }} .caja.quien strong:first-child {{ color: {NARANJA}; }}
.caja.nota {{ background: #EAF2F7; }} .caja.nota strong:first-child {{ color: {AZUL}; }}
.caja.ejemplo {{ background: #F5F7F9; border: 0.6pt solid #E1E6EB; }} .caja.ejemplo strong:first-child {{ color: #5a86ad; }}

/* código */
code {{ font-family: "Ubuntu Mono", "DejaVu Sans Mono", monospace; font-size: 9.2pt; background: #F2F4F7; border-radius: 2px; padding: 0 1mm; }}
pre {{ background: #F2F4F7; border-left: 1mm solid {AZUL}; border-radius: 1mm; padding: 2.6mm 3.6mm; margin: 1.5mm 0 3.5mm;
       white-space: pre-wrap; break-inside: avoid; text-align: left; }}
pre code {{ background: none; padding: 0; font-size: 9pt; }}
a {{ color: inherit; text-decoration: none; }}
.ref {{ color: #3a424d; }}
"""

doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>{TITULO_DOC} · {SUBTITULO}</title><style>{CSS}</style></head>
<body>{PORTADA}
<section class="indice"><h1>Índice</h1>{''.join(indice)}</section>
<main>{cuerpo}</main></body></html>"""
open(SALIDA, "w", encoding="utf-8").write(doc)
print("ok", SALIDA, len(doc))
