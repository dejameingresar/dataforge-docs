"""nucleo.fuentes — conexion a motores NoSQL vivos.

Cada modulo de esta carpeta sabe dos cosas de su motor: como leer su esquema y
como escribir en el. Los drivers son **opcionales**: si no estan instalados, la
aplicacion sigue funcionando con archivos (subir un volcado, exportar) y solo la
conexion directa avisa de que falta el driver.

Esta es la capa que permite el flujo real: en vez de exportar un volcado,
importarlo y volver a exportarlo, la aplicacion se conecta a la base que ya
tiene el usuario y escribe ahi mismo.
"""

from . import cassandra, mongodb, neo4j, redis

FUENTES = {
    "mongodb": mongodb,
    "redis": redis,
    "cassandra": cassandra,
    "neo4j": neo4j,
}

ORDEN = ["mongodb", "redis", "cassandra", "neo4j"]


def fuente(motor):
    if motor not in FUENTES:
        raise ValueError(f"motor no soportado para conexion: {motor}. "
                         f"Use uno de {', '.join(ORDEN)}")
    return FUENTES[motor]


def detecta_todos(host="127.0.0.1", puertos=None):
    """Estado de los cuatro motores en esta maquina.

    Es lo que alimenta el menu del comando `generar`: informa, sin instalar
    nada, cual esta corriendo y si su driver esta disponible. `puertos` permite
    apuntar a puertos no habituales {motor: puerto}.
    """
    puertos = puertos or {}
    salida = []
    for motor in ORDEN:
        try:
            salida.append(fuente(motor).detecta(host=host, puerto=puertos.get(motor)))
        except Exception as e:  # noqa: BLE001 - un motor raro no debe tumbar el menu
            salida.append({
                "motor": motor, "nombre": motor.title(), "host": host,
                "puerto": None, "corriendo": False, "driver_instalado": False,
                "listo": False, "error": f"{type(e).__name__}: {e}",
            })
    return salida


def resumen_estado(host="127.0.0.1", puertos=None):
    """Estado de los cuatro motores, con la misma forma que `detecta_todos`.

    Es lo que consume la interfaz y el comando `generar`: cada entrada lleva
    `corriendo`, `driver_instalado` y `listo`, para que quien lo lea no tenga
    que volver a deducirlo del texto de `estado`.
    """
    salida = []
    for d in detecta_todos(host, puertos):
        if d["listo"]:
            estado = "corriendo"
        elif d["corriendo"]:
            estado = "corriendo, falta el driver"
        elif d["driver_instalado"]:
            estado = "no encontrado"
        else:
            estado = "no instalado"
        salida.append({
            "motor": d["motor"],
            "nombre": d["nombre"],
            "host": d.get("host"),
            "puerto": d.get("puerto"),
            "corriendo": d["corriendo"],
            "driver_instalado": d["driver_instalado"],
            "listo": d["listo"],
            "estado": estado,
        })
    return salida
