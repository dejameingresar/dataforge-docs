"""nucleo.fuentes.neo4j — lee el esquema y escribe en un Neo4j vivo.

De Neo4j se leen las **etiquetas** de nodo (que son las colecciones) y una
muestra de los nodos de cada una con sus propiedades. Las relaciones se leen
aparte, porque en un grafo son de primera clase y no un campo.
"""

import socket

from .base import error_driver, normaliza_registro

MOTOR = "neo4j"
PAQUETE = "neo4j"
PUERTO = 7687
NOMBRE = "Neo4j"


def driver():
    try:
        import neo4j  # noqa: F401
        return neo4j
    except ImportError:
        return None


def esta_instalado():
    return driver() is not None


def puerto_abierto(host="127.0.0.1", puerto=PUERTO, tiempo=0.4):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(tiempo)
        return s.connect_ex((host, puerto)) == 0


def detecta(host="127.0.0.1", puerto=None):
    """Informa si el motor esta alcanzable. El puerto es opcional: un
    motor en un puerto no habitual tambien debe detectarse."""
    puerto = puerto or PUERTO
    alcanzable = puerto_abierto(host, puerto)
    return {
        "motor": MOTOR,
        "nombre": NOMBRE,
        "host": host,
        "puerto": puerto,
        "corriendo": alcanzable,
        "driver_instalado": esta_instalado(),
        "listo": alcanzable and esta_instalado(),
    }


def _sesion(host, puerto, usuario=None, clave=None, uri=None):
    n = driver()
    if n is None:
        raise RuntimeError(error_driver(NOMBRE, PAQUETE))
    if uri:
        manejador = n.GraphDatabase.driver(uri)
    else:
        manejador = n.GraphDatabase.driver(
            f"bolt://{host}:{puerto}", auth=(usuario or "neo4j", clave or ""))
    return manejador, manejador.session()


def etiquetas(host="127.0.0.1", puerto=PUERTO, usuario=None, clave=None, uri=None):
    """Etiquetas de nodo con al menos un nodo (son las colecciones)."""
    manejador, ses = _sesion(host, puerto, usuario, clave, uri)
    try:
        filas = ses.run("CALL db.labels() YIELD label RETURN label ORDER BY label")
        return [r["label"] for r in filas]
    finally:
        ses.close()
        manejador.close()


def tipos_relacion(host="127.0.0.1", puerto=PUERTO, usuario=None, clave=None,
                   uri=None):
    """Tipos de relacion del grafo."""
    manejador, ses = _sesion(host, puerto, usuario, clave, uri)
    try:
        filas = ses.run("CALL db.relationshipTypes() YIELD relationshipType "
                        "RETURN relationshipType ORDER BY relationshipType")
        return [r["relationshipType"] for r in filas]
    finally:
        ses.close()
        manejador.close()


def leer(etiqueta, limite=300, host="127.0.0.1", puerto=PUERTO, usuario=None,
         clave=None, uri=None):
    """Muestra de los nodos de una etiqueta, con sus propiedades."""
    manejador, ses = _sesion(host, puerto, usuario, clave, uri)
    try:
        # El nombre de la etiqueta se interpola porque Cypher no admite
        # parametros en la etiqueta; se valida antes para no inyectar nada.
        if not etiqueta.replace("_", "").isalnum():
            raise ValueError(f"etiqueta invalida: {etiqueta!r}")
        filas = ses.run(f"MATCH (n:`{etiqueta}`) RETURN n LIMIT $limite",
                        limite=limite)
        salida = []
        for r in filas:
            props = dict(r["n"])
            salida.append(normaliza_registro(props))
        return salida
    finally:
        ses.close()
        manejador.close()


def leer_todo(etiquetas_, limite=300, host="127.0.0.1", puerto=PUERTO,
              usuario=None, clave=None, uri=None):
    """Muestra de cada etiqueta. Se abre una sola conexion."""
    manejador, ses = _sesion(host, puerto, usuario, clave, uri)
    try:
        salida = {}
        for etiqueta in etiquetas_:
            if not etiqueta.replace("_", "").isalnum():
                continue
            filas = ses.run(f"MATCH (n:`{etiqueta}`) RETURN n LIMIT $limite",
                            limite=limite)
            salida[etiqueta] = [normaliza_registro(dict(r["n"])) for r in filas]
        return salida
    finally:
        ses.close()
        manejador.close()


def cuenta(etiqueta, host="127.0.0.1", puerto=PUERTO, usuario=None, clave=None,
           uri=None):
    """Cuantos nodos tiene una etiqueta."""
    manejador, ses = _sesion(host, puerto, usuario, clave, uri)
    try:
        if not etiqueta.replace("_", "").isalnum():
            raise ValueError(f"etiqueta invalida: {etiqueta!r}")
        filas = ses.run(f"MATCH (n:`{etiqueta}`) RETURN count(n) AS n")
        return filas.single()["n"]
    finally:
        ses.close()
        manejador.close()


def insertar(etiqueta, registros, host="127.0.0.1", puerto=PUERTO, usuario=None,
             clave=None, uri=None):
    """Crea los nodos generados en el grafo real."""
    if not registros:
        return 0
    if not etiqueta.replace("_", "").isalnum():
        raise ValueError(f"etiqueta invalida: {etiqueta!r}")
    manejador, ses = _sesion(host, puerto, usuario, clave, uri)
    try:
        # Se crean de a lotes: un CREATE por nodo en una transaccion por nodo
        # seria lentisimo, y UNWIND permite pasar la lista entera de una vez.
        filas = ses.run(
            f"UNWIND $lote AS props CREATE (n:`{etiqueta}`) SET n = props "
            f"RETURN count(n) AS n", lote=registros)
        return filas.single()["n"]
    finally:
        ses.close()
        manejador.close()
