"""nucleo.fuentes.cassandra — lee el esquema y escribe en un Cassandra vivo.

De Cassandra se leen dos cosas distintas: el **esquema** (que es lo que hace
falta para generar, y viene de las tablas del sistema) y los **datos** (una
muestra de cada tabla). El esquema es mas fiable que los datos: declara los
tipos y la clave de particion sin depender de una muestra.
"""

import socket

from .base import error_driver, normaliza_registro

MOTOR = "cassandra"
PAQUETE = "cassandra-driver"
PUERTO = 9042
NOMBRE = "Cassandra"


def driver():
    try:
        import cassandra  # noqa: F401
        return cassandra
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


def _cluster(host, puerto, usuario=None, clave=None):
    c = driver()
    if c is None:
        raise RuntimeError(error_driver(NOMBRE, PAQUETE))
    auth = {"username": usuario, "password": clave} if usuario and clave else None
    cluster = c.cluster.Cluster([host], port=puerto, auth_provider=(
        c.auth.PlainTextAuthProvider(**auth) if auth else None))
    return cluster.connect()


def keyspaces(host="127.0.0.1", puerto=PUERTO, usuario=None, clave=None):
    """Keyspaces con datos (se excluyen los del sistema)."""
    ses = _cluster(host, puerto, usuario, clave)
    try:
        filas = ses.execute(
            "SELECT keyspace_name FROM system_schema.keyspaces")
        return sorted(r.keyspace_name for r in filas
                      if not r.keyspace_name.startswith("system"))
    finally:
        ses.shutdown()


def tablas(keyspace, host="127.0.0.1", puerto=PUERTO, usuario=None, clave=None):
    """Tablas de un keyspace."""
    ses = _cluster(host, puerto, usuario, clave)
    try:
        filas = ses.execute(
            "SELECT table_name FROM system_schema.tables WHERE keyspace_name = %s",
            [keyspace])
        return sorted(r.table_name for r in filas)
    finally:
        ses.shutdown()


def esquema(keyspace, host="127.0.0.1", puerto=PUERTO, usuario=None, clave=None):
    """Esquema real de las tablas, leido de system_schema.

    Es la via buena: los tipos y la clave de particion vienen declarados por el
    propio motor, sin inferir nada de una muestra.
    """
    ses = _cluster(host, puerto, usuario, clave)
    try:
        filas = ses.execute(
            "SELECT table_name, column_name, kind, position, type "
            "FROM system_schema.columns WHERE keyspace_name = %s", [keyspace])
        por_tabla = {}
        for f in filas:
            t = por_tabla.setdefault(f.table_name, {"columnas": [], "pk": []})
            t["columnas"].append((f.column_name, f.type, f.kind, f.position or 0))
            if f.kind in ("partition_key", "clustering"):
                t["pk"].append((f.position or 0, f.column_name, f.kind))
        # El nombre de la coleccion se antepone al keyspace para que dos
        # keyspaces no choquen si tienen una tabla con el mismo nombre.
        salida = {}
        for tabla, datos in por_tabla.items():
            datos["pk"].sort()
            salida[f"{keyspace}.{tabla}"] = {
                "columnas": datos["columnas"],
                "pk": [c for _, c, _ in datos["pk"]],
                "tabla": tabla,
                "keyspace": keyspace,
            }
        return salida
    finally:
        ses.shutdown()


def leer(keyspace, tabla, limite=300, host="127.0.0.1", puerto=PUERTO,
         usuario=None, clave=None):
    """Muestra de una tabla, con los valores normalizados."""
    ses = _cluster(host, puerto, usuario, clave)
    try:
        filas = ses.execute(f'SELECT * FROM {keyspace}."{tabla}" LIMIT %s', [limite])
        return [normaliza_registro(dict(f._asdict())) for f in filas]
    finally:
        ses.shutdown()


def leer_todo(keyspace, tablas_, limite=300, host="127.0.0.1", puerto=PUERTO,
              usuario=None, clave=None):
    """Muestra de cada tabla. Se abre una sola conexion para todas."""
    ses = _cluster(host, puerto, usuario, clave)
    try:
        salida = {}
        for tabla in tablas_:
            filas = ses.execute(f'SELECT * FROM {keyspace}."{tabla}" LIMIT %s',
                                [limite])
            salida[tabla] = [normaliza_registro(dict(f._asdict())) for f in filas]
        return salida
    finally:
        ses.shutdown()


def cuenta(keyspace, tabla, host="127.0.0.1", puerto=PUERTO, usuario=None,
           clave=None):
    """Cuenta de una tabla.

    En Cassandra un COUNT(*) es caro: recorre toda la particion. Se usa un
    LIMIT alto para acotarlo, y se declara que el numero es una cota inferior.
    """
    ses = _cluster(host, puerto, usuario, clave)
    try:
        filas = ses.execute(
            f'SELECT COUNT(*) AS n FROM {keyspace}."{tabla}" LIMIT 100000')
        return filas.one().n if filas else 0
    finally:
        ses.shutdown()


def insertar(keyspace, tabla, columnas, registros, host="127.0.0.1", puerto=PUERTO,
             usuario=None, clave=None):
    """Escribe los registros generados en la tabla real."""
    if not registros:
        return 0
    ses = _cluster(host, puerto, usuario, clave)
    escritos = 0
    try:
        marcadores = ", ".join(["%s"] * len(columnas))
        nombres = ", ".join(columnas)
        sentencia = (f'INSERT INTO {keyspace}."{tabla}" ({nombres}) '
                     f'VALUES ({marcadores})')
        preparada = ses.prepare(sentencia)
        for reg in registros:
            valores = [reg.get(c) for c in columnas]
            ses.execute(preparada, valores)
            escritos += 1
        return escritos
    finally:
        ses.shutdown()
