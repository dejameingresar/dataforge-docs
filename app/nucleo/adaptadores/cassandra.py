"""nucleo.adaptadores.cassandra — serializa el lote al formato de Cassandra.

Dos salidas:

  *.cql    El DDL (`CREATE TABLE` con la clave de particion y las claves de
           agrupamiento) seguido de los `INSERT`. Es autocontenido: se pega en
           cqlsh y crea la tabla y la llena.
  *.csv    Las filas en CSV, para `COPY tabla FROM 'archivo.csv'`, que es la via
           de carga masiva recomendada por Cassandra.
"""

import datetime as dt

from .base import cabecera, _comillas_cql

# Como se declara cada tipo neutral en CQL.
CQL = {
    "objectid": "uuid", "uuid": "uuid", "texto": "text", "texto_largo": "text",
    "email": "text", "telefono": "text", "url": "text", "dni": "text",
    "entero": "int", "largo": "bigint", "decimal": "decimal", "flotante": "double",
    "booleano": "boolean", "fecha": "date", "fecha_hora": "timestamp",
    "hora": "time", "timestamp": "timestamp", "enum": "text", "lista": "list<text>",
    "mapa": "map<text, text>", "binario": "blob", "geo": "text", "inet": "inet",
}


def _tipo_cql(campo):
    return CQL.get(campo.get("tipo"), "text")


def _literal(valor, campo):
    """Literal CQL del valor, con el tipo correcto."""
    if valor is None:
        return "NULL"
    tipo = campo.get("tipo")
    if tipo == "booleano":
        return "true" if valor else "false"
    if tipo in ("entero", "largo", "flotante", "decimal"):
        return str(valor)
    if tipo == "timestamp":
        if isinstance(valor, (dt.date, dt.datetime)):
            return str(int(dt.datetime(valor.year, valor.month, valor.day).timestamp() * 1000)) \
                if isinstance(valor, dt.date) and not isinstance(valor, dt.datetime) \
                else str(int(valor.timestamp() * 1000))
        return str(valor)
    if tipo == "fecha":
        texto = valor.isoformat() if isinstance(valor, dt.date) else str(valor)
        return _comillas_cql(texto)
    if tipo == "hora":
        texto = valor.strftime("%H:%M:%S") if isinstance(valor, dt.time) else str(valor)
        return _comillas_cql(texto)
    if tipo == "lista":
        return "[" + ", ".join(_comillas_cql(v) for v in valor) + "]"
    if tipo == "mapa":
        pares = ", ".join(f"{_comillas_cql(k)}: {_comillas_cql(v)}"
                          for k, v in valor.items())
        return "{" + pares + "}"
    if tipo == "binario":
        datos = valor if isinstance(valor, bytes) else str(valor).encode()
        return "0x" + datos.hex()
    if isinstance(valor, (dt.date, dt.datetime)):
        return _comillas_cql(valor.isoformat())
    if isinstance(valor, (dict, list)):
        import json
        return _comillas_cql(json.dumps(valor, ensure_ascii=False, default=str))
    return _comillas_cql(valor)


def _clave_particion(campos):
    """La clave primaria: los campos marcados pk, o los dos primeros."""
    pk = [c["nombre"] for c in campos if c.get("pk")]
    if not pk:
        pk = [campos[0]["nombre"]]
    return pk


def exportar(resultado, esquema, semilla, formato="cql"):
    """Devuelve {nombre_archivo: contenido}."""
    salida = {}
    if formato == "csv":
        for nombre, detalle in resultado.items():
            campos = esquema["colecciones"][nombre]["campos"]
            nombres = [c["nombre"] for c in campos]
            lineas = [",".join(nombres)]
            for r in detalle["nuevos"]:
                lineas.append(",".join(_csv(r.get(c["nombre"])) for c in campos))
            salida[f"{nombre}.csv"] = "\n".join(lineas)
        return salida

    partes = [cabecera("--", "cassandra", semilla, resultado,
                       ["Ejecutar en cqlsh. Las tablas ya incluyen su clave primaria."])]
    for nombre, detalle in resultado.items():
        campos = esquema["colecciones"][nombre]["campos"]
        pk = _clave_particion(campos)
        partes.append(f"-- --- {nombre}: {len(detalle['nuevos'])} filas nuevas ---")
        partes.append(f"CREATE TABLE IF NOT EXISTS {nombre} (")
        definiciones = [f"    {c['nombre']} {_tipo_cql(c)}" for c in campos]
        definiciones.append(f"    PRIMARY KEY ({', '.join(pk)})")
        partes.append(",\n".join(definiciones))
        partes.append(");")
        if detalle["nuevos"]:
            nombres = ", ".join(c["nombre"] for c in campos)
            for r in detalle["nuevos"]:
                valores = ", ".join(_literal(r.get(c["nombre"]), c) for c in campos)
                partes.append(f"INSERT INTO {nombre} ({nombres}) VALUES ({valores});")
        partes.append("")
    salida[f"dataforge_cassandra_{semilla}.cql"] = "\n".join(partes)
    return salida


def _csv(valor):
    """Valor para CSV: entre comillas si contiene coma o comilla."""
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
