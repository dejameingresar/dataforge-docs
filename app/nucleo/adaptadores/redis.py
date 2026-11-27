"""nucleo.adaptadores.redis — serializa el lote al formato de Redis.

Redis no tiene tipos ni documentos: guarda cadenas bajo claves. El adaptador
traduce cada registro a un **hash** cuya clave sigue el patron
`<coleccion>:<clave-primaria>`, que es la convencion de nombrado de Redis.

Se emiten dos formas del mismo lote:

  *.redis    Un archivo de comandos RESP, el formato que entiende
             `redis-cli --pipe`, que es la via rapida de carga masiva.
  *.txt      Los mismos comandos en texto legible (HSET ...), para revisarlos o
             pegarlos a mano en redis-cli.
"""

from .base import cabecera, json_compacto


def _a_cadena(valor):
    """Todo valor viaja como cadena: es lo unico que Redis almacena."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, (dict, list)):
        return json_compacto(valor)
    if isinstance(valor, bytes):
        import base64
        return base64.b64encode(valor).decode("ascii")
    return str(valor)


def _clave(nombre, registro, campos):
    """Clave del hash: <coleccion>:<valor de la clave primaria>."""
    for c in campos:
        if c.get("pk") and registro.get(c["nombre"]) is not None:
            return f"{nombre}:{_a_cadena(registro[c['nombre']])}"
    for candidato in ("_id", "id", "uuid", "clave"):
        if registro.get(candidato) is not None:
            return f"{nombre}:{_a_cadena(registro[candidato])}"
    return f"{nombre}:{abs(hash(json_compacto(registro))) % 10_000_000}"


def exportar(resultado, esquema, semilla, formato="resp"):
    """Devuelve {nombre_archivo: contenido} con los comandos de carga."""
    if formato == "texto":
        partes = [cabecera("#", "redis", semilla, resultado,
                           ["Pegar en redis-cli, o cargar con: redis-cli --pipe "
                            "< dataforge_redis.txt"])]
        for nombre, detalle in resultado.items():
            campos = esquema["colecciones"][nombre]["campos"]
            partes.append(f"# --- {nombre}: {len(detalle['nuevos'])} claves nuevas ---")
            for r in detalle["nuevos"]:
                clave = _clave(nombre, r, campos)
                pares = []
                for k, v in r.items():
                    pares.extend([k, _a_cadena(v)])
                argumentos = " ".join(f'"{p}"' for p in pares)
                partes.append(f"HSET {clave} {argumentos}")
            partes.append("")
        return {f"dataforge_redis_{semilla}.txt": "\n".join(partes)}

    # RESP: el protocolo de redis-cli --pipe. Cada comando es un arreglo de
    # cadenas: *<n>\r\n$<len>\r\n<dato>\r\n por cada argumento.
    salida = []
    for nombre, detalle in resultado.items():
        campos = esquema["colecciones"][nombre]["campos"]
        for r in detalle["nuevos"]:
            clave = _clave(nombre, r, campos)
            args = ["HSET", clave]
            for k, v in r.items():
                args.extend([str(k), _a_cadena(v)])
            salida.append(_resp(args))
    contenido = "".join(salida)
    return {f"dataforge_redis_{semilla}.resp": contenido}


def _resp(args):
    """Un comando en el protocolo RESP."""
    partes = [f"*{len(args)}\r\n"]
    for a in args:
        datos = a.encode("utf-8")
        partes.append(f"${len(datos)}\r\n")
        partes.append(a)
        partes.append("\r\n")
    return "".join(partes)
