"""nucleo.fuentes.redis — lee el esquema y escribe en un Redis vivo.

Redis no tiene colecciones ni documentos: guarda valores bajo claves. La
convencion que usa esta aplicacion (y la habitual) es `<coleccion>:<id>` con un
hash por registro. Aqui se lee por ese patron y se escribe igual.
"""

import socket

from .base import error_driver

MOTOR = "redis"
PAQUETE = "redis"
PUERTO = 6379
NOMBRE = "Redis"


def driver():
    try:
        import redis  # noqa: F401
        return redis
    except ImportError:
        return None


def esta_instalado():
    return driver() is not None


def puerto_abierto(host="127.0.0.1", puerto=PUERTO, tiempo=0.4):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(tiempo)
        return s.connect_ex((host, puerto)) == 0


def detecta(host="127.0.0.1", puerto=None):
    """Informa si el motor esta alcanzable, con o sin driver.

    El puerto se puede pasar: un motor en un puerto no habitual (una prueba, una
    instalacion paralela) tambien debe detectarse.
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


def _cliente(host, puerto, clave=None, base=0, url=None):
    """Cliente de Redis, compatible con servidores antiguos.

    Las versiones modernas del cliente mandan `HELLO` al conectar, que es un
    comando que **no existe antes de Redis 6**: contra un Redis 3.x (el que
    instala `winget` en Windows) la conexion falla con "unknown command HELLO".
    Se fija `protocol=2`, que es lo que hace que el cliente no lo mande y use
    RESP2, el protocolo que cualquier version entiende.
    """
    r = driver()
    if r is None:
        raise RuntimeError(error_driver(NOMBRE, PAQUETE))
    opciones = {"socket_connect_timeout": 3, "decode_responses": True}
    # `protocol` existe en las versiones nuevas del cliente; en las viejas el
    # parametro no esta y el cliente ya usa RESP2 por defecto.
    try:
        if url:
            return r.from_url(url, protocol=2, **opciones)
        return r.Redis(host=host, port=puerto or PUERTO, password=clave, db=base,
                       protocol=2, **opciones)
    except TypeError:
        if url:
            return r.from_url(url, **opciones)
        return r.Redis(host=host, port=puerto or PUERTO, password=clave, db=base,
                       **opciones)


def prefijos(host="127.0.0.1", puerto=PUERTO, clave=None, url=None, tope=200):
    """Colecciones detectadas: el prefijo antes de los dos puntos en las claves."""
    cli = _cliente(host, puerto, clave, url=url)
    try:
        cli.ping()
        prefijos_vistos = {}
        for i, k in enumerate(cli.scan_iter(count=200)):
            if i >= 5000:
                break
            base = str(k).split(":")[0]
            prefijos_vistos[base] = prefijos_vistos.get(base, 0) + 1
        return sorted(prefijos_vistos)
    finally:
        cli.close()


def leer(coleccion, limite=300, host="127.0.0.1", puerto=PUERTO, clave=None,
         url=None):
    """Lee los registros de una coleccion (las claves `<coleccion>:*`)."""
    cli = _cliente(host, puerto, clave, url=url)
    try:
        registros = []
        for k in cli.scan_iter(match=f"{coleccion}:*", count=200):
            if len(registros) >= limite:
                break
            if cli.type(k) != "hash":
                continue
            datos = cli.hgetall(k)
            if datos:
                datos.setdefault("_clave", str(k))
                registros.append(datos)
        return registros
    finally:
        cli.close()


def leer_todo(colecciones_, limite=300, host="127.0.0.1", puerto=PUERTO,
              clave=None, url=None):
    """Muestra de cada coleccion, para el detector."""
    return {c: leer(c, limite, host, puerto, clave, url) for c in colecciones_}


def cuenta(coleccion, host="127.0.0.1", puerto=PUERTO, clave=None, url=None):
    cli = _cliente(host, puerto, clave, url=url)
    try:
        return sum(1 for _ in cli.scan_iter(match=f"{coleccion}:*", count=500))
    finally:
        cli.close()


def _a_cadena(valor):
    """Redis solo almacena cadenas: todo valor se serializa."""
    import json
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False, default=str)
    if isinstance(valor, bytes):
        import base64
        return base64.b64encode(valor).decode("ascii")
    return str(valor)


def _escribe_hash(cli, nombre, datos):
    """Escribe un hash, con el comando que la version del servidor entienda.

    `HSET` con varios pares campo-valor existe desde Redis 4. Antes habia que
    usar `HMSET` para escribir varios campos de una vez. Contra un Redis 3.x
    (el que instala `winget` en Windows) `HSET` con varios pares falla con
    "wrong number of arguments". Se prueba el moderno y, si el servidor no lo
    admite, se cae al antiguo.
    """
    try:
        cli.hset(nombre, mapping=datos)
    except Exception:  # noqa: BLE001 - el servidor es antiguo
        cli.hmset(nombre, datos)


def insertar(coleccion, registros, host="127.0.0.1", puerto=PUERTO, clave=None,
             url=None, campos_clave=None):
    """Escribe los registros como hashes bajo `<coleccion>:<id>`."""
    if not registros:
        return 0
    cli = _cliente(host, puerto, clave, url=url)
    escritos = 0
    try:
        for i, reg in enumerate(registros):
            identificador = None
            for candidato in (campos_clave or []) + ["_id", "id", "uuid", "clave"]:
                if reg.get(candidato) is not None:
                    identificador = reg[candidato]
                    break
            if identificador is None:
                identificador = i + 1
            nombre = f"{coleccion}:{identificador}"
            # El campo `_clave` lo agrega el LECTOR para saber de que clave vino
            # el registro. Al escribir no debe guardarse: es metadato de la
            # lectura, y si se escribe queda un valor inventado dentro del motor.
            datos = {k: _a_cadena(v) for k, v in reg.items() if k != "_clave"}
            if datos:
                _escribe_hash(cli, nombre, datos)
                escritos += 1
        return escritos
    finally:
        cli.close()
