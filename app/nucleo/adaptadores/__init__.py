"""nucleo.adaptadores — un modulo por motor NoSQL soportado.

Cada adaptador expone `exportar(resultado, esquema, semilla, formato)` y
devuelve un diccionario {nombre_archivo: contenido}. Anadir un motor nuevo es
anadir un modulo aqui y su entrada en nucleo.tipos.MOTORES.
"""

from . import cassandra, mongodb, neo4j, redis

ADAPTADORES = {
    "mongodb": mongodb,
    "redis": redis,
    "cassandra": cassandra,
    "neo4j": neo4j,
}

# Formatos de exportacion que ofrece cada motor, con su etiqueta.
FORMATOS = {
    "mongodb": [("json", "Documentos JSON (mongoimport)"),
                ("script", "Script de mongosh (insertMany)")],
    "redis": [("resp", "Comandos RESP (redis-cli --pipe)"),
              ("texto", "Comandos en texto (HSET)")],
    "cassandra": [("cql", "DDL + INSERT para cqlsh"),
                  ("csv", "CSV para COPY FROM")],
    "neo4j": [("cypher", "Sentencias Cypher (CREATE)"),
              ("csv", "CSV para LOAD CSV")],
}


def exportar(motor, resultado, esquema, semilla, formato=None):
    """Exporta el lote con el adaptador del motor indicado."""
    if motor not in ADAPTADORES:
        raise ValueError(f"motor no soportado: {motor}. "
                         f"Use uno de {', '.join(sorted(ADAPTADORES))}")
    formatos_validos = [f for f, _ in FORMATOS.get(motor, [])]
    if formato is None:
        formato = formatos_validos[0] if formatos_validos else "default"
    if formato not in formatos_validos:
        raise ValueError(f"formato '{formato}' no valido para {motor}. "
                         f"Use uno de {', '.join(formatos_validos)}")
    return ADAPTADORES[motor].exportar(resultado, esquema, semilla, formato)


def formatos_de(motor):
    return FORMATOS.get(motor, [])
