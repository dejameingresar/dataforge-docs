"""nucleo.ejemplos — conjuntos de ejemplo para probar la aplicacion sin subir nada.

Cada ejemplo es un archivo real del formato que produce el motor, de modo que
pasa por el mismo detector que usaria un archivo subido por el usuario: no hay
un camino especial para los ejemplos. Asi, si el detector se rompe, los ejemplos
tambien fallan y la prueba lo detecta.

El dominio es una tienda en linea con clientes, pedidos, productos y resenas,
que ejercita tipos variados (ObjectId, decimal, fecha, enum, lista, documento
anidado) y relaciones entre colecciones.
"""

EJEMPLOS = {
    "tienda_mongodb": {
        "nombre": "tienda_mongodb",
        "titulo": "Tienda en linea — MongoDB",
        "motor": "mongodb",
        "archivo": "tienda_mongodb.json",
        "descripcion": ("Volcado JSON con tres colecciones (clientes, productos, "
                        "pedidos) y una relacion de pedidos hacia clientes. "
                        "Incompleto a proposito: solo tiene unos pocos registros."),
    },
    "tienda_cassandra": {
        "nombre": "tienda_cassandra",
        "titulo": "Tienda en linea — Cassandra",
        "motor": "cassandra",
        "archivo": "tienda_cassandra.cql",
        "descripcion": ("DDL de Cassandra con tres tablas y sus claves de particion, "
                        "sin filas: la aplicacion genera todo el contenido."),
    },
    "tienda_redis": {
        "nombre": "tienda_redis",
        "titulo": "Tienda en linea — Redis",
        "motor": "redis",
        "archivo": "tienda_redis.json",
        "descripcion": ("Mapa clave -> objeto con los registros de la tienda, el "
                        "formato que exporta la propia aplicacion."),
    },
    "tienda_neo4j": {
        "nombre": "tienda_neo4j",
        "titulo": "Tienda en linea — Neo4j",
        "motor": "neo4j",
        "archivo": "tienda_neo4j.cypher",
        "descripcion": ("Sentencias Cypher con nodos de cliente, producto y pedido, "
                        "y las relaciones entre ellos."),
    },
}


def catalogo():
    """Lista de ejemplos para pintar la interfaz."""
    return [{"nombre": e["nombre"], "titulo": e["titulo"], "motor": e["motor"],
             "archivo": e["archivo"], "descripcion": e["descripcion"]}
            for e in EJEMPLOS.values()]
