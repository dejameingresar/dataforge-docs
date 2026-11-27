"""nucleo.fuentes.mongodb — lee el esquema y escribe en un MongoDB vivo.

El driver es **opcional**: si pymongo no esta instalado, el modulo se importa
igual y solo falla cuando alguien intenta conectarse, con un mensaje que dice
como instalarlo. Asi el nucleo sigue sin dependencias obligatorias.
"""

import datetime as dt
import socket

from .base import error_driver, normaliza_colecciones, normaliza_registro

MOTOR = "mongodb"
PAQUETE = "pymongo"
PUERTO = 27017
NOMBRE = "MongoDB"


def driver():
    """Devuelve el modulo pymongo, o None si no esta instalado."""
    try:
        import pymongo  # noqa: F401
        return pymongo
    except ImportError:
        return None


def esta_instalado():
    return driver() is not None


def puerto_abierto(host="127.0.0.1", puerto=PUERTO, tiempo=0.4):
    """True si hay algo escuchando en el puerto: el motor esta corriendo."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(tiempo)
        return s.connect_ex((host, puerto)) == 0


def detecta(host="127.0.0.1", puerto=None):
    """Informa si el motor esta alcanzable, con o sin driver.

    El puerto es opcional: un motor en un puerto no habitual tambien debe
    detectarse.
    """
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


def _cliente(host, puerto, usuario=None, clave=None, uri=None):
    pymongo = driver()
    if pymongo is None:
        raise RuntimeError(error_driver(NOMBRE, PAQUETE))
    # Un puerto no valido (None, negativo, texto) hace que el driver lance un
    # TypeError critico que no dice nada util. Se cae al puerto por defecto.
    if not isinstance(puerto, int) or not (0 < puerto < 65536):
        puerto = PUERTO
    if uri:
        return pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
    if usuario and clave:
        return pymongo.MongoClient(host=host, port=puerto, username=usuario,
                                   password=clave, serverSelectionTimeoutMS=3000)
    return pymongo.MongoClient(host=host, port=puerto, serverSelectionTimeoutMS=3000)


def _a_bson(valor):
    """Valor Python -> valor que BSON acepta.

    BSON no tiene un tipo `date` sin hora: `datetime.date` NO se puede codificar
    y el driver lanza InvalidDocument. Un `date` se convierte a `datetime` a
    medianoche, que es lo que MongoDB guarda de verdad. Un `time` tampoco existe
    como tipo: se guarda como la cadena HH:MM:SS.
    """
    if isinstance(valor, dt.datetime):
        return valor
    if isinstance(valor, dt.date):
        return dt.datetime(valor.year, valor.month, valor.day)
    if isinstance(valor, dt.time):
        return valor.strftime("%H:%M:%S")
    if isinstance(valor, dict):
        return {k: _a_bson(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_a_bson(v) for v in valor]
    return valor


def _documento(registro):
    """Un registro listo para escribir en MongoDB."""
    return {k: _a_bson(v) for k, v in registro.items() if k != "_clave"}


def bases(host="127.0.0.1", puerto=PUERTO, uri=None):
    """Lista de bases de datos con datos."""
    cli = _cliente(host, puerto, uri=uri)
    try:
        cli.admin.command("ping")
        return [n for n in cli.list_database_names()
                if n not in ("admin", "local", "config")]
    finally:
        cli.close()


def colecciones(base, host="127.0.0.1", puerto=PUERTO, uri=None):
    """Lista de colecciones de una base."""
    cli = _cliente(host, puerto, uri=uri)
    try:
        return cli[base].list_collection_names()
    finally:
        cli.close()


def leer(base, coleccion, limite=300, host="127.0.0.1", puerto=PUERTO, uri=None):
    """Lee una muestra de una coleccion, con los valores ya normalizados."""
    cli = _cliente(host, puerto, uri=uri)
    try:
        docs = list(cli[base][coleccion].find().limit(limite))
        return [normaliza_registro(d) for d in docs]
    finally:
        cli.close()


def leer_todo(base, colecciones_, limite=300, host="127.0.0.1", puerto=PUERTO, uri=None):
    """Lee una muestra de cada coleccion: es lo que consume el detector."""
    cli = _cliente(host, puerto, uri=uri)
    try:
        salida = {}
        for nombre in colecciones_:
            docs = list(cli[base][nombre].find().limit(limite))
            salida[nombre] = [normaliza_registro(d) for d in docs]
        return normaliza_colecciones(salida)
    finally:
        cli.close()


def cuenta(base, coleccion, host="127.0.0.1", puerto=PUERTO, uri=None):
    """Cuantos documentos tiene una coleccion de verdad."""
    cli = _cliente(host, puerto, uri=uri)
    try:
        return cli[base][coleccion].count_documents({})
    finally:
        cli.close()


def insertar(base, coleccion, documentos, host="127.0.0.1", puerto=PUERTO, uri=None):
    """Escribe los documentos generados en la coleccion real.

    Devuelve cuantos se insertaron. Los valores se convierten a lo que BSON
    acepta antes de escribir.
    """
    if not documentos:
        return 0
    cli = _cliente(host, puerto, uri=uri)
    try:
        listos = [_documento(d) for d in documentos]
        resultado = cli[base][coleccion].insert_many(listos, ordered=False)
        return len(resultado.inserted_ids)
    finally:
        cli.close()
