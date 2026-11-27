"""nucleo.fuentes.base — utilidades comunes de la conexion a motores vivos.

Lo que llega de un motor real no es JSON: es un ObjectId de pymongo, un Decimal128,
un datetime. Aqui se normaliza a los tipos que el detector ya entiende, y en el
sentido contrario: lo que se va a escribir se convierte al tipo nativo del motor.
"""

import datetime as dt

# Tipos de los drivers que no son de Python y hay que convertir. Se identifican
# por el nombre del tipo para no importar el driver aqui: asi este modulo sigue
# funcionando aunque el driver no este instalado.
_TIPOS_DRIVER = {
    "ObjectId": "objectid",
    "Decimal128": "decimal",
    "Binary": "binario",
    "UUID": "uuid",
    "Point": "geo",
}


def tipo_de_driver(valor):
    """Nombre del tipo del driver, o None si es un tipo normal de Python."""
    return _TIPOS_DRIVER.get(type(valor).__name__)


def normaliza_valor(valor):
    """Valor de un driver -> valor que el detector entiende.

    Un ObjectId se vuelve su hexadecimal; un Decimal128, su numero; una fecha se
    deja como fecha. Se hace recursivamente porque estos tipos aparecen dentro de
    documentos anidados y de arreglos.
    """
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    if isinstance(valor, (dt.datetime, dt.date, dt.time)):
        return valor
    if isinstance(valor, bytes):
        return valor
    tipo = tipo_de_driver(valor)
    if tipo == "objectid":
        return str(valor)
    if tipo == "decimal":
        try:
            return float(valor.to_decimal())
        except Exception:  # noqa: BLE001 - si el driver cambia, se degrada
            return str(valor)
    if tipo == "binario":
        try:
            return bytes(valor)
        except Exception:  # noqa: BLE001
            return str(valor)
    if tipo in ("uuid", "geo"):
        return str(valor)
    if isinstance(valor, dict):
        return {k: normaliza_valor(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [normaliza_valor(v) for v in valor]
    return str(valor)


def normaliza_registro(registro):
    """Un documento completo, normalizado."""
    if not isinstance(registro, dict):
        return {}
    return {k: normaliza_valor(v) for k, v in registro.items()}


def normaliza_colecciones(colecciones):
    """{coleccion: [documentos]} con todos sus valores normalizados."""
    return {n: [normaliza_registro(d) for d in docs if isinstance(d, dict)]
            for n, docs in colecciones.items()}


def error_driver(motor, paquete, detalle=""):
    """Mensaje util cuando falta el driver de un motor."""
    return (
        f"Para conectar a {motor} hace falta su driver de Python, que no esta "
        f"instalado. Se instala con:\n"
        f"    pip install {paquete}\n"
        f"El resto de la aplicacion funciona sin el: la deteccion de motores, la "
        f"lectura de volcados y la exportacion a los cuatro formatos no lo "
        f"necesitan.{(' Detalle: ' + detalle) if detalle else ''}"
    )
