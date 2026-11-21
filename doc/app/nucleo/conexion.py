"""nucleo.conexion — puente entre un motor vivo y el esquema neutral.

`nucleo.fuentes` sabe hablar con cada motor; `nucleo.detector` y `nucleo.motor`
trabajan con el esquema neutral. Esta capa los une:

  motor vivo  ->  leer esquema y muestra  ->  esquema neutral  ->  generar
                                                                     |
  motor vivo  <-  escribir los registros nuevos  <-------------------+

Asi, el mismo nucleo que completa un archivo completa una base de datos que esta
corriendo, sin exportar ni importar nada.
"""

from . import detector, fuentes, tipos
from .motor import Generador, metricas, valida_relaciones

MAX_MUESTRA = 300


def _tipos_desde_datos(colecciones):
    """Esquema neutral a partir de muestras de datos (MongoDB y Redis).

    Se reutiliza el detector, que ya sabe inferir tipos, dominios y relaciones
    de una lista de registros. Es el mismo camino que un archivo subido: no hay
    dos detectores que puedan divergir.
    """
    return detector._esquema_desde_colecciones(
        colecciones, motor="", formato="conexion directa")


def _esquema_cassandra(keyspace, host, puerto, usuario, clave):
    """Esquema neutral a partir del esquema REAL de Cassandra.

    Aqui no se infiere nada: system_schema declara los tipos y la clave de
    particion. Es la via buena cuando el motor la ofrece.
    """
    real = fuentes.cassandra.esquema(keyspace, host, puerto, usuario, clave)
    colecciones = {}
    for nombre, datos in real.items():
        campos = []
        for nombre_col, tipo_cql, kind, _ in datos["columnas"]:
            tipo_neutral, elemento = detector._tipo_cql_a_neutral(tipo_cql)
            campo = {
                "nombre": nombre_col,
                "tipo": tipo_neutral,
                "elemento": elemento,
                "nullable": kind not in ("partition_key", "clustering"),
                "observado": {"total": 0, "nulos": 0, "distintos": 0, "ejemplos": []},
            }
            if nombre_col in datos["pk"]:
                campo["pk"] = True
                campo["nullable"] = False
            campos.append(campo)
        colecciones[nombre] = {
            "nombre": nombre,
            "campos": campos,
            "claves": datos["pk"],
            "origen": f"system_schema ({datos['keyspace']}.{datos['tabla']})",
            "registros_observados": 0,
            "muestra": [],
            "tabla_real": datos["tabla"],
            "keyspace_real": datos["keyspace"],
        }
    return {"motor": "cassandra", "formato": "esquema del motor",
            "colecciones": colecciones, "total_registros": 0}


def _enriquece_con_datos(esquema, muestras, max_por_coleccion=MAX_MUESTRA):
    """Completa un esquema con lo que se ve en los datos reales.

    El esquema del motor dice los tipos; los datos dicen cuantos registros hay,
    cuales son los dominios y que campos apuntan a otra coleccion. Se combinan:
    el tipo declarado manda, y lo observado rellena el resto.
    """
    for nombre, col in esquema["colecciones"].items():
        docs = muestras.get(col.get("tabla_real") or nombre)
        if not docs and nombre in muestras:
            docs = muestras[nombre]
        if not docs:
            continue
        docs = docs[:max_por_coleccion]
        col["registros_observados"] = len(docs)
        col["muestra"] = docs[:20]
        perfil = detector._perfila_registros(docs)
        # Los campos que ya declaraba el motor conservan su tipo; se les anade
        # lo observado (dominios, nulos, ejemplos).
        declarados = {c["nombre"]: c for c in col["campos"]}
        for nombre_campo, p in perfil.items():
            if nombre_campo in declarados:
                campo = declarados[nombre_campo]
                campo["observado"] = {
                    "total": p["total"], "nulos": p["nulos"],
                    "distintos": p["distintos"], "ejemplos": p["ejemplos"],
                    "muestra_valores": p["muestra_valores"],
                    "frecuencia_nulos": round(p["nulos"] / p["total"], 4) if p["total"] else 0.0,
                }
                if campo["tipo"] in ("texto", "texto_largo"):
                    valores = list(p["valores"])
                    if (2 <= len(valores) <= 12 and not p["desborde"]
                            and detector._parece_dominio(valores)):
                        campo["tipo"] = "enum"
                        campo["enum"] = sorted(valores)
            else:
                # Un campo que aparece en los datos y no en el esquema declarado
                # (Cassandra lo permite si se anadio despues): se agrega.
                col["campos"].append(
                    detector._campo_desde_perfil(nombre_campo, p, coleccion=nombre))
    # Las relaciones se infieren con los datos ya en su sitio.
    detector._infiere_relaciones(esquema["colecciones"])
    return esquema


def leer_esquema(motor, destino=None, host="127.0.0.1", puerto=None,
                 usuario=None, clave=None, uri=None, limite=MAX_MUESTRA):
    """Lee el esquema de un motor vivo y lo devuelve en el vocabulario neutral.

    destino: la base (MongoDB), el keyspace (Cassandra) o el prefijo (Redis).
             En Neo4j se ignora: las etiquetas son globales.
    """
    f = fuentes.fuente(motor)
    puerto = puerto or getattr(f, "PUERTO", None)

    if motor == "mongodb":
        nombres = fuentes.mongodb.colecciones(destino, host, puerto, uri)
        muestras = fuentes.mongodb.leer_todo(destino, nombres, limite, host, puerto, uri)
        esquema = _tipos_desde_datos(muestras)
        esquema["motor"] = "mongodb"
        esquema["formato"] = f"conexion directa ({destino})"
        esquema["destino"] = destino
        return esquema

    if motor == "redis":
        nombres = [destino] if destino else fuentes.redis.prefijos(host, puerto, clave, uri)
        muestras = fuentes.redis.leer_todo(nombres, limite, host, puerto, clave, uri)
        esquema = _tipos_desde_datos(muestras)
        esquema["motor"] = "redis"
        esquema["formato"] = "conexion directa"
        esquema["destino"] = destino
        return esquema

    if motor == "cassandra":
        esquema = _esquema_cassandra(destino, host, puerto, usuario, clave)
        tablas = [c["tabla_real"] for c in esquema["colecciones"].values()]
        muestras = fuentes.cassandra.leer_todo(destino, tablas, limite, host, puerto,
                                               usuario, clave)
        esquema = _enriquece_con_datos(esquema, muestras)
        esquema["destino"] = destino
        return esquema

    if motor == "neo4j":
        nombres = fuentes.neo4j.etiquetas(host, puerto, usuario, clave, uri)
        muestras = fuentes.neo4j.leer_todo(nombres, limite, host, puerto, usuario,
                                           clave, uri)
        esquema = _tipos_desde_datos(muestras)
        esquema["motor"] = "neo4j"
        esquema["formato"] = "conexion directa (grafo)"
        esquema["relaciones"] = fuentes.neo4j.tipos_relacion(host, puerto, usuario,
                                                             clave, uri)
        return esquema

    raise ValueError(f"motor no soportado: {motor}")


def completar_en_motor(esquema, volumenes, motor, destino=None, host="127.0.0.1",
                       puerto=None, usuario=None, clave=None, uri=None, semilla=2026,
                       enums=None, campos=None):
    """Genera los registros que faltan y los ESCRIBE en el motor vivo.

    Devuelve el detalle de lo escrito. No exporta ningun archivo: escribe.
    """
    f = fuentes.fuente(motor)
    puerto = puerto or getattr(f, "PUERTO", None)
    generador = Generador(esquema, semilla=semilla, enums=enums, campos=campos)
    resultado = generador.completar(volumenes)
    problemas = valida_relaciones(resultado, esquema)

    escrito = {}
    for nombre, detalle in resultado.items():
        nuevos = detalle["nuevos"]
        if not nuevos:
            escrito[nombre] = {"escritos": 0, "error": None}
            continue
        col = esquema["colecciones"][nombre]
        try:
            if motor == "mongodb":
                n = fuentes.mongodb.insertar(destino, nombre, nuevos, host, puerto, uri)
            elif motor == "redis":
                n = fuentes.redis.insertar(nombre, nuevos, host, puerto, clave, uri)
            elif motor == "cassandra":
                columnas = [c["nombre"] for c in col["campos"]]
                n = fuentes.cassandra.insertar(destino, col.get("tabla_real", nombre),
                                               columnas, nuevos, host, puerto,
                                               usuario, clave)
            elif motor == "neo4j":
                n = fuentes.neo4j.insertar(nombre, nuevos, host, puerto, usuario,
                                           clave, uri)
            else:
                raise ValueError(f"motor no soportado: {motor}")
            escrito[nombre] = {"escritos": n, "error": None}
        except Exception as e:  # noqa: BLE001 - se informa y se sigue con las demas
            escrito[nombre] = {"escritos": 0, "error": f"{type(e).__name__}: {e}"}

    return {
        "resultado": resultado,
        "metricas": metricas(resultado, esquema),
        "problemas_relacion": problemas,
        "escrito": escrito,
        "total_escrito": sum(v["escritos"] for v in escrito.values()),
        "errores": {k: v["error"] for k, v in escrito.items() if v["error"]},
    }
