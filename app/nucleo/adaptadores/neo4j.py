"""nucleo.adaptadores.neo4j — serializa el lote al formato de Neo4j.

Neo4j guarda un grafo: cada registro es un **nodo** con una etiqueta y
propiedades, y los vinculos son **relaciones**. El adaptador emite sentencias
Cypher que crean los nodos y, cuando el esquema detectado declara relaciones
entre colecciones, tambien las aristas.

  *.cypher   Sentencias CREATE para nodos y relaciones, para pegar en Neo4j
             Browser o cargar con `cypher-shell`.
  *.csv      Nodos en CSV, el formato que espera `LOAD CSV` para cargas masivas.
"""

import datetime as dt

from .base import cabecera, _comillas_cypher


def _etiqueta(nombre):
    """Etiqueta de nodo valida a partir del nombre de la coleccion."""
    limpio = "".join(c for c in str(nombre) if c.isalnum() or c == "_")
    return (limpio[:1].upper() + limpio[1:]) or "Nodo"


def _literal(valor, campo):
    """Literal Cypher del valor."""
    if valor is None:
        return "null"
    tipo = campo.get("tipo") if campo else None
    if tipo == "booleano":
        return "true" if valor else "false"
    if tipo in ("entero", "largo", "timestamp"):
        return str(int(valor))
    if tipo in ("decimal", "flotante"):
        return str(float(valor))
    if tipo == "geo" and isinstance(valor, dict):
        coords = valor.get("coordinates") or [0, 0]
        return f"point({{longitude: {coords[0]}, latitude: {coords[1]}}})"
    if tipo in ("fecha", "fecha_hora") and isinstance(valor, (dt.date, dt.datetime)):
        return f"datetime({_comillas_cypher(valor.isoformat())})"
    if tipo == "hora" and isinstance(valor, dt.time):
        return f"localtime({_comillas_cypher(valor.strftime('%H:%M:%S'))})"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, (dict, list)):
        import json
        return _comillas_cypher(json.dumps(valor, ensure_ascii=False, default=str))
    if isinstance(valor, bytes):
        import base64
        return _comillas_cypher(base64.b64encode(valor).decode("ascii"))
    return _comillas_cypher(valor)


def _propiedades(registro, campos):
    """Bloque {clave: valor} de un nodo."""
    por_nombre = {c["nombre"]: c for c in campos}
    pares = [f"{k}: {_literal(v, por_nombre.get(k))}" for k, v in registro.items()]
    return "{" + ", ".join(pares) + "}"


def exportar(resultado, esquema, semilla, formato="cypher"):
    """Devuelve {nombre_archivo: contenido}."""
    salida = {}
    if formato == "csv":
        for nombre, detalle in resultado.items():
            campos = esquema["colecciones"][nombre]["campos"]
            cabeceras = [c["nombre"] for c in campos]
            lineas = [",".join(cabeceras)]
            for r in detalle["nuevos"]:
                lineas.append(",".join(_csv(r.get(c["nombre"])) for c in campos))
            salida[f"{nombre}.csv"] = "\n".join(lineas)
        return salida

    partes = [cabecera("//", "neo4j", semilla, resultado,
                       ["Pegar en Neo4j Browser o cargar con cypher-shell."])]
    # Indice de etiqueta para que la busqueda posterior no recorra todo el grafo.
    partes.append("CREATE INDEX IF NOT EXISTS FOR (n:Nodo) ON (n.id);")
    partes.append("")
    for nombre, detalle in resultado.items():
        etiqueta = _etiqueta(nombre)
        campos = esquema["colecciones"][nombre]["campos"]
        partes.append(f"// --- {nombre}: {len(detalle['nuevos'])} nodos nuevos ---")
        for r in detalle["nuevos"]:
            partes.append(f"CREATE (:{etiqueta} {_propiedades(r, campos)});")
        partes.append("")
    # Relaciones: se derivan de los campos que apuntan a otra coleccion. Cada
    # arista se emite con los valores concretos de origen y destino, no con
    # variables: asi el archivo se puede ejecutar tal cual.
    aristas = []
    for nombre, detalle in resultado.items():
        col = esquema["colecciones"][nombre]
        pk_origen = next((c["nombre"] for c in col["campos"] if c.get("pk")), None)
        if not pk_origen:
            continue
        for campo in col["campos"]:
            if not campo.get("ref"):
                continue
            destino = campo["ref"]
            if destino not in resultado:
                continue
            et_origen, et_destino = _etiqueta(nombre), _etiqueta(destino)
            campos_destino = esquema["colecciones"][destino]["campos"]
            pk_destino = next((c["nombre"] for c in campos_destino if c.get("pk")), None)
            if not pk_destino:
                continue
            campo_pk_dest = next(c for c in campos_destino if c["nombre"] == pk_destino)
            campo_pk_orig = next(c for c in col["campos"] if c["nombre"] == pk_origen)
            tipo_rel = f"REF_{campo['nombre'].upper()}"
            for r in detalle["nuevos"]:
                valor_origen = r.get(pk_origen)
                valor_destino = r.get(campo["nombre"])
                if valor_origen is None or valor_destino is None:
                    continue
                aristas.append(
                    f"MATCH (a:{et_origen} {{{pk_origen}: "
                    f"{_literal(valor_origen, campo_pk_orig)}}}), "
                    f"(b:{et_destino} {{{pk_destino}: "
                    f"{_literal(valor_destino, campo_pk_dest)}}}) "
                    f"CREATE (a)-[:{tipo_rel}]->(b);")
    if aristas:
        partes.append("// --- Relaciones derivadas de las referencias ---")
        partes.extend(aristas)
        partes.append("")
    salida[f"dataforge_neo4j_{semilla}.cypher"] = "\n".join(partes)
    return salida


def _csv(valor):
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (dict, list)):
        import json
        valor = json.dumps(valor, ensure_ascii=False, default=str)
    texto = str(valor)
    if any(c in texto for c in ',"\n'):
        return '"' + texto.replace('"', '""') + '"'
    return texto
