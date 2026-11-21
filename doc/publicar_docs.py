#!/usr/bin/env python3
"""doc/publicar_docs.py — publica la documentacion tecnica como sitio estatico.

La rubrica pide la documentacion tecnica en un sitio publicado, con el detalle
de cada clase, metodo y propiedad. En lugar de GitHub Pages (que requiere que
el repositorio sea publico y aqui es privado), se genera un sitio estatico y se
publica en el mismo hosting estatico que sirve el instalador.

El sitio incluye:
  - portada con el estado verificado del proyecto
  - el README
  - los cinco diagramas en SVG (arquitectura, clases, despliegue, modelo ER, flujo)
  - el diccionario de datos
  - la matriz de tipos
  - el catalogo de formatos
  - el manual tecnico
  - la referencia de clases: cada clase con sus atributos y sus metodos

Uso:
    python3 doc/publicar_docs.py             # genera el sitio en doc/_site
    python3 doc/publicar_docs.py --surge     # genera y publica (necesita surge)
"""

import argparse
import ast
import datetime as dt
import os
import shutil
import subprocess
import sys
import json
import html

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
DOC = os.path.join(RAIZ, "doc")
SITE = os.path.join(DOC, "_site")
NUCLEO = os.path.join(RAIZ, "app", "nucleo")

CSS = """
body{font-family:"Segoe UI",system-ui,-apple-system,sans-serif;color:#0f172a;
     margin:0;padding:0;line-height:1.65;background:#f8fafc}
header{background:#0f766e;color:#fff;padding:28px 32px}
header h1{margin:0;font-size:22px}
header p{margin:6px 0 0;opacity:.9;font-size:14px}
main{max-width:1000px;margin:0 auto;padding:28px 24px 60px}
nav{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;
    margin-bottom:26px}
nav a{color:#0f766e;text-decoration:none;font-weight:600;margin-right:16px;
      font-size:14px}
nav a:hover{text-decoration:underline}
h2{color:#0f766e;font-size:18px;margin:34px 0 12px;
   border-bottom:2px solid #e2e8f0;padding-bottom:6px}
h3{color:#134e4a;font-size:15px;margin:22px 0 8px}
img{max-width:100%;border:1px solid #e2e8f0;border-radius:10px;margin:12px 0;
    background:#fff}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}
th,td{border:1px solid #e2e8f0;padding:8px 12px;text-align:left}
th{background:#f1f5f9;font-weight:600}
code{background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:13px}
pre{background:#0f172a;color:#e2e8f0;padding:16px;border-radius:10px;
    overflow-x:auto;font-size:13px}
pre code{background:none;color:inherit}
.clase{border:1px solid #e2e8f0;border-radius:10px;background:#fff;
       padding:16px 20px;margin:14px 0}
.clase h3{margin:0 0 10px;color:#0f766e}
.attrs,.metodos{margin:6px 0}
.attrs li,.metodos li{font-family:ui-monospace,Consolas,monospace;font-size:13px}
.etiqueta{display:inline-block;background:#ccfbf1;color:#0f766e;border-radius:4px;
          padding:1px 8px;font-size:12px;font-weight:600;margin-left:8px}
footer{border-top:1px solid #e2e8f0;margin-top:40px;padding-top:16px;
       color:#64748b;font-size:13px}
"""


def _lee(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def clases_html():
    """Referencia de clases, metodos y propiedades, leida del codigo."""
    modulos = [os.path.join(RAIZ, "app.py")]
    for directorio, _, nombres in os.walk(NUCLEO):
        modulos.extend(os.path.join(directorio, n) for n in sorted(nombres) if n.endswith(".py"))
    partes = []
    vistas = set()
    for ruta in modulos:
        archivo = os.path.relpath(ruta, RAIZ).replace(os.sep, "/")
        if not os.path.isfile(ruta):
            continue
        arbol = ast.parse(_lee(ruta))
        for nodo in arbol.body:
            if not isinstance(nodo, ast.ClassDef) or (archivo, nodo.name) in vistas:
                continue
            vistas.add((archivo, nodo.name))
            doc = ast.get_docstring(nodo) or ""
            attrs, metodos = [], []
            for sub in nodo.body:
                if isinstance(sub, ast.FunctionDef):
                    if sub.name == "__init__":
                        for linea in ast.walk(sub):
                            if (isinstance(linea, ast.Assign)
                                    and isinstance(linea.targets[0], ast.Attribute)):
                                attrs.append(linea.targets[0].attr)
                    elif not sub.name.startswith("_"):
                        args = [a.arg for a in sub.args.args if a.arg != "self"]
                        if args:
                            args = args[:1] + ["*"] + args[1:] if len(args) > 2 else args
                        metodos.append((sub.name, args, ast.get_docstring(sub)))
            bloque = [f'<div class="clase"><h3>{nodo.name}'
                      f'<span class="etiqueta">{archivo}</span></h3>']
            if doc:
                bloque.append(f"<p>{doc.splitlines()[0]}</p>")
            if attrs:
                bloque.append('<div class="attrs"><b>Propiedades</b><ul>')
                bloque += [f"<li>{a}</li>" for a in dict.fromkeys(attrs)]
                bloque.append("</ul></div>")
            if metodos:
                bloque.append('<div class="metodos"><b>Metodos</b><ul>')
                for nombre, args, _ in metodos:
                    bloque.append(f"<li>{nombre}({', '.join(args)})</li>")
                bloque.append("</ul></div>")
            bloque.append("</div>")
            partes.append("\n".join(bloque))
    return "\n".join(partes)


def portada():
    resumen = os.path.join(DOC, "reportes", "avance2", "resumen.json")
    estado = "Pruebas locales pendientes de ejecutar."
    if os.path.isfile(resumen):
        datos = json.loads(_lee(resumen))
        estado = (f"{datos['exitosas']}/{datos['comprobaciones']} comprobaciones locales "
                  f"sin fallo. Ejecucion UTC: {datos['fecha_utc']}.")
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DataForge NoSQL — documentacion tecnica</title>
<style>{CSS}</style></head><body>
<header>
  <h1>DataForge NoSQL</h1>
  <p>Generador de datos sinteticos para bases de datos NoSQL &middot;
     documentacion tecnica generada desde el codigo</p>
</header><main>
<nav>
  <a href="index.html">Portada</a>
  <a href="readme.html">README</a>
  <a href="diagramas.html">Diagramas</a>
  <a href="clases.html">Clases</a>
  <a href="diccionario-datos.html">Diccionario</a>
  <a href="matriz-tipos.html">Tipos</a>
  <a href="catalogo-formatos.html">Formatos</a>
  <a href="manual-tecnico.html">Manual</a>
</nav>

<h2>Estado verificado</h2>
<p>{html.escape(estado)}</p>
<p>La evidencia incluye salidas de las suites. La ejecucion en GitHub y el
despliegue publico deben verificarse en el repositorio publicado.</p>

<h2>Que hace</h2>
<p>Lee una base de datos NoSQL incompleta, deduce su estructura y genera los
registros que faltan para completarla, respetando tipos, dominios y relaciones.
Un mismo esquema produce salida valida para MongoDB, Redis, Cassandra y Neo4j
gracias a un vocabulario neutral de 23 tipos.</p>

<h2>Instalacion</h2>
<pre><code>python app.py</code></pre>

<footer>Generado el {dt.date.today().isoformat()} por
<code>doc/publicar_docs.py</code>. Esta pagina se reconstruye desde el codigo,
igual que el resto de la documentacion.</footer>
</main></body></html>"""


def envoltura(titulo, cuerpo, activo="index.html"):
    enlaces = [("index.html", "Portada"), ("readme.html", "README"),
               ("diagramas.html", "Diagramas"), ("clases.html", "Clases"),
               ("diccionario-datos.html", "Diccionario"),
               ("matriz-tipos.html", "Tipos"),
               ("catalogo-formatos.html", "Formatos"),
               ("manual-tecnico.html", "Manual")]
    nav = "".join(
        f'<a href="{u}"{" style=\"color:#0f172a;text-decoration:underline\"" if u == activo else ""}>{t}</a>'
        for u, t in enlaces)
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo} — DataForge NoSQL</title>
<style>{CSS}</style></head><body>
<header><h1>{titulo}</h1><p>DataForge NoSQL &middot; documentacion tecnica</p>
</header><main>
<nav>{nav}</nav>
{cuerpo}
<footer>Generado el {dt.date.today().isoformat()} desde el codigo.</footer>
</main></body></html>"""


def md_a_html(texto):
    """Markdown minimo a HTML: lo justo para los documentos del proyecto."""
    import re
    lineas = texto.splitlines()
    salida, en_tabla, en_pre = [], False, False
    for linea in lineas:
        if linea.strip().startswith("```"):
            salida.append("</pre>" if en_pre else "<pre><code>")
            en_pre = not en_pre
            continue
        if en_pre:
            salida.append(linea.replace("&", "&amp;").replace("<", "&lt;"))
            continue
        if linea.startswith("|"):
            celdas = [c.strip() for c in linea.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in celdas):
                continue
            etiqueta = "th" if not en_tabla else "td"
            if not en_tabla:
                salida.append("<table>")
                en_tabla = True
            salida.append("<tr>" + "".join(f"<{etiqueta}>{c}</{etiqueta}>"
                                           for c in celdas) + "</tr>")
            continue
        if en_tabla:
            salida.append("</table>")
            en_tabla = False
        if linea.startswith("#"):
            nivel = len(linea) - len(linea.lstrip("#"))
            salida.append(f"<h{min(nivel + 1, 4)}>{linea.lstrip('# ').strip()}</h{min(nivel + 1, 4)}>")
        elif linea.startswith(("- ", "* ")):
            salida.append(f"<li>{linea[2:]}</li>")
        elif linea.startswith("!["):
            m = re.search(r"\((.*?)\)", linea)
            if m:
                salida.append(f'<img src="{os.path.basename(m.group(1))}" alt="">')
        elif linea.strip():
            txt = linea
            for a, b in [("**", "b"), ("`", "code")]:
                if a in txt:
                    txt = txt.replace(a, f"<{b}>", 1)
                    j = txt.rfind(a)
                    if j > 0:
                        txt = txt[:j] + f"</{b}>" + txt[j + len(a):]
            txt = txt.replace("`", "")
            salida.append(f"<p>{txt}</p>")
    if en_tabla:
        salida.append("</table>")
    if en_pre:
        salida.append("</pre>")
    return "\n".join(salida)


def main():
    ap = argparse.ArgumentParser(description="Publica la documentacion como sitio")
    ap.add_argument("--surge", action="store_true", help="publicar en surge.sh")
    ap.add_argument("--dominio", default="dataforge-nosql-docs.surge.sh")
    args = ap.parse_args()

    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE)

    # Copiar los diagramas para que las etiquetas <img> resuelvan.
    for svg in ("arquitectura", "clases", "despliegue", "modelo-er", "flujo", "estado-er"):
        src = os.path.join(DOC, f"{svg}.svg")
        if os.path.isfile(src):
            shutil.copy(src, SITE)

    escritos = []

    def escribe(nombre, html):
        with open(os.path.join(SITE, nombre), "w", encoding="utf-8") as f:
            f.write(html)
        escritos.append(nombre)

    escribe("index.html", portada())
    escribe("readme.html", envoltura("README", md_a_html(_lee(
        os.path.join(RAIZ, "README.md"))), "readme.html"))
    escribe("manual-tecnico.html", envoltura("Manual tecnico", md_a_html(_lee(
        os.path.join(DOC, "manual-tecnico.md"))), "manual-tecnico.html"))
    escribe("diccionario-datos.html", envoltura("Diccionario de datos", md_a_html(_lee(
        os.path.join(DOC, "diccionario-datos.md"))), "diccionario-datos.html"))
    escribe("diccionario-estado.html", envoltura("Diccionario de actividad", md_a_html(_lee(
        os.path.join(DOC, "diccionario-estado.md")))))
    escribe("matriz-tipos.html", envoltura("Matriz de tipos", md_a_html(_lee(
        os.path.join(DOC, "matriz-tipos.md"))), "matriz-tipos.html"))
    escribe("catalogo-formatos.html", envoltura("Catalogo de formatos", md_a_html(_lee(
        os.path.join(DOC, "catalogo-formatos.md"))), "catalogo-formatos.html"))
    escribe("clases.html", envoltura(
        "Clases, metodos y propiedades",
        "<p>Leido del codigo con <code>ast</code>: si una clase cambia, esta "
        "pagina cambia con ella.</p>" + clases_html(), "clases.html"))

    diagramas = [
        ("Arquitectura de componentes", "arquitectura.svg"),
        ("Diagrama de clases", "clases.svg"),
        ("Diagrama de despliegue", "despliegue.svg"),
        ("Modelo entidad-relacion del ejemplo", "modelo-er.svg"),
        ("Modelo de actividad persistente", "estado-er.svg"),
        ("Flujo de una carga", "flujo.svg"),
    ]
    cuerpo = "\n".join(f"<h2>{t}</h2><img src=\"{s}\" alt=\"{t}\">"
                       for t, s in diagramas)
    escribe("diagramas.html", envoltura("Diagramas", cuerpo, "diagramas.html"))

    print(f"Sitio generado en {SITE}")
    for e in escritos:
        print(f"  {e}")

    if args.surge:
        print("\nPublicando en surge.sh...")
        r = subprocess.run(["surge", "--project", SITE, "--domain", args.dominio],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print(f"Publicado en https://{args.dominio}")
        else:
            print("No se pudo publicar:")
            print(r.stdout[-500:], r.stderr[-500:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
