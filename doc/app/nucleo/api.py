"""nucleo.api — la API de la aplicacion, independiente del servidor HTTP.

Toda la logica de la interfaz vive aqui y se prueba desde la terminal, de modo
que `app.py` (el servidor) solo traduce HTTP a llamadas de esta funcion.
"""

import json
import os
import time

from . import adaptadores, ejemplos, fuentes, generadores, tipos
from .conexion import completar_en_motor, leer_esquema
from .detector import ErrorDeteccion, detectar
from .motor import ErrorGeneracion, Generador, metricas, valida_relaciones

MAX_CARGA = 2_000_000     # caracteres que se aceptan en una carga
MAX_REGISTROS = 5000      # tope de registros nuevos por coleccion

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ_EJEMPLOS = os.path.join(RAIZ, "ejemplos")


def _json(cuerpo, status=200):
    # default=str cubre las fechas, horas y binarios que el lote lleva en su tipo
    # natural: la interfaz los muestra como texto sin que la serializacion falle.
    return {"status": status,
            "cuerpo": json.dumps(cuerpo, ensure_ascii=False, default=str)}


def _error(mensaje, status=400):
    return _json({"ok": False, "error": mensaje}, status)


def _cuerpo(peticion):
    """Cuerpo de la peticion como diccionario.

    Un JSON valido puede no ser un objeto: `null`, `42`, `"texto"` o `[1,2,3]`
    se parsean sin error pero no son diccionarios. Se tratan como peticion
    vacia en vez de dejar que reviente al hacer .get() mas adelante.
    """
    if not peticion:
        return {}
    datos = json.loads(peticion)
    return datos if isinstance(datos, dict) else {}


# ---------------------------------------------------------------- catalogo
def vista_catalogo():
    """Todo lo que la interfaz necesita para dibujarse al abrir."""
    return {
        "ok": True,
        "motores": [
            {
                "nombre": m,
                "titulo": tipos.MOTORES[m]["titulo"],
                "familia": tipos.MOTORES[m]["familia"],
                "descripcion": tipos.MOTORES[m]["descripcion"],
                "unidad": tipos.MOTORES[m]["unidad"],
                "unidad_plural": tipos.MOTORES[m]["unidad_plural"],
                "unidad_fila": tipos.MOTORES[m]["unidad_fila"],
                "unidad_fila_plural": tipos.MOTORES[m]["unidad_fila_plural"],
                "ejemplo_esquema": tipos.MOTORES[m]["ejemplo_esquema"],
                "formatos": [{"id": f, "etiqueta": e}
                             for f, e in adaptadores.formatos_de(m)],
                "cobertura": tipos.compatibilidad(m),
            }
            for m in tipos.ORDEN_MOTORES
        ],
        "tipos": [{"tipo": t, "etiqueta": e, "familia": f}
                  for t, e, f in tipos.TIPOS_NEUTRALES],
        "matriz_tipos": tipos.tabla_compatibilidad(),
        "ejemplos": ejemplos.catalogo(),
        "generadores": sorted(generadores.SEMANTICOS),
    }


def vista_esquema():
    """El esquema del ejemplo por defecto, para la demo inicial."""
    meta = ejemplos.EJEMPLOS["tienda_mongodb"]
    ruta = os.path.join(RAIZ_EJEMPLOS, meta["archivo"])
    with open(ruta, "r", encoding="utf-8") as fh:
        return detectar(fh.read(), meta["archivo"], meta["motor"])


# ------------------------------------------------------------------ deteccion
def detectar_carga(datos):
    """Lee lo que subio el usuario y devuelve la estructura detectada."""
    texto = datos.get("contenido") or ""
    nombre = datos.get("archivo") or ""
    motor = datos.get("motor") or None
    if len(texto) > MAX_CARGA:
        return _error(f"el archivo supera el limite de {MAX_CARGA:,} caracteres")
    try:
        esquema = detectar(texto, nombre, motor)
    except ErrorDeteccion as e:
        return _error(str(e))
    esquema["nombre_archivo"] = nombre
    return _json({"ok": True, "esquema": esquema})


def cargar_ejemplo(datos):
    """Carga uno de los conjuntos de ejemplo que trae la aplicacion."""
    nombre = datos.get("nombre")
    if nombre not in ejemplos.EJEMPLOS:
        return _error(f"ejemplo desconocido: {nombre}")
    meta = ejemplos.EJEMPLOS[nombre]
    ruta = os.path.join(RAIZ_EJEMPLOS, meta["archivo"])
    if not os.path.isfile(ruta):
        return _error(f"falta el archivo del ejemplo: {meta['archivo']}")
    with open(ruta, "r", encoding="utf-8") as fh:
        contenido = fh.read()
    return detectar_carga({"contenido": contenido, "archivo": meta["archivo"],
                           "motor": meta["motor"]})


# ---------------------------------------------------------------- generacion
def _normaliza_volumenes(bruto, esquema):
    """Acota los volumenes pedidos al esquema detectado."""
    vol = {}
    for nombre, n in (bruto or {}).items():
        if nombre not in esquema["colecciones"]:
            continue
        vol[nombre] = max(0, min(int(n), MAX_REGISTROS))
    return vol


def _construye(datos):
    """Arma el generador a partir de la peticion y completa el lote."""
    esquema = datos.get("esquema")
    if not esquema or "colecciones" not in esquema:
        raise ValueError("falta el esquema detectado: primero hay que analizar la carga")
    volumenes = _normaliza_volumenes(datos.get("volumenes"), esquema)
    semilla = int(datos.get("semilla", 2026))
    g = Generador(esquema, semilla=semilla, enums=datos.get("enums"),
                  campos=datos.get("campos"))
    t0 = time.perf_counter()
    resultado = g.completar(volumenes)
    return esquema, resultado, semilla, time.perf_counter() - t0


def generar(datos):
    """Completa el lote y devuelve las metricas y una muestra."""
    try:
        esquema, resultado, semilla, elapsed = _construye(datos)
    except (ValueError, ErrorGeneracion) as e:
        return _error(str(e))
    m = metricas(resultado, esquema)
    problemas = valida_relaciones(resultado, esquema)
    return _json({
        "ok": True,
        "semilla": semilla,
        "metricas": m,
        "problemas_relacion": problemas,
        "resumen": {
            "colecciones": len(resultado),
            "existentes": m["totales"]["existentes"],
            "generados": m["totales"]["generados"],
            "total": m["totales"]["total"],
            "completitud": m["totales"]["completitud"],
            "generado_en_ms": round(elapsed * 1000, 2),
        },
        "muestra": {n: d["nuevos"][:5] for n, d in resultado.items()},
        "detalle": {n: {"n_existentes": d["n_existentes"],
                        "n_generados": d["n_generados"],
                        "total": d["total"],
                        "campos": len(esquema["colecciones"][n]["campos"])}
                    for n, d in resultado.items()},
    })


def exportar(datos):
    """Serializa el lote al formato nativo del motor elegido."""
    try:
        esquema, resultado, semilla, _ = _construye(datos)
    except (ValueError, ErrorGeneracion) as e:
        return _error(str(e))
    motor = datos.get("motor") or esquema.get("motor") or "mongodb"
    formato = datos.get("formato")
    try:
        archivos = adaptadores.exportar(motor, resultado, esquema, semilla, formato)
    except ValueError as e:
        return _error(str(e))
    total = sum(len(c.encode("utf-8")) for c in archivos.values())
    return _json({
        "ok": True,
        "motor": motor,
        "formato": formato or adaptadores.formatos_de(motor)[0][0],
        "archivos": [{"nombre": n, "contenido": c, "bytes": len(c.encode("utf-8"))}
                     for n, c in archivos.items()],
        "bytes_totales": total,
        "filas_generadas": sum(d["n_generados"] for d in resultado.values()),
    })


def comparar_motores(datos):
    """Exporta el mismo lote a los cuatro motores y compara el resultado.

    Es la evidencia de la compatibilidad: un unico esquema neutral produce los
    cuatro formatos nativos sin tocar el esquema.
    """
    try:
        esquema, resultado, semilla, _ = _construye(datos)
    except (ValueError, ErrorGeneracion) as e:
        return _error(str(e))
    comparativa = []
    for motor in tipos.ORDEN_MOTORES:
        formato = adaptadores.formatos_de(motor)[0][0]
        archivos = adaptadores.exportar(motor, resultado, esquema, semilla, formato)
        comparativa.append({
            "motor": motor,
            "titulo": tipos.MOTORES[motor]["titulo"],
            "familia": tipos.MOTORES[motor]["familia"],
            "formato": formato,
            "archivos": [{"nombre": n, "bytes": len(c.encode("utf-8"))}
                         for n, c in archivos.items()],
            "bytes": sum(len(c.encode("utf-8")) for c in archivos.values()),
            "cobertura_tipos": tipos.compatibilidad(motor)["cobertura"],
        })
    return _json({"ok": True, "semilla": semilla, "comparativa": comparativa,
                  "filas_generadas": sum(d["n_generados"] for d in resultado.values())})


# ------------------------------------------------------------------ conexion
def vista_motores(datos=None):
    """Estado de los motores NoSQL de la maquina, para el menu de conexion."""
    datos = datos or {}
    host = datos.get("host") or "127.0.0.1"
    puertos = datos.get("puertos") or {}
    if datos.get("motor") and datos.get("puerto"):
        puertos[datos["motor"]] = int(datos["puerto"])
    return _json({"ok": True, "host": host,
                  "motores": fuentes.resumen_estado(host, puertos)})


def vista_destinos(datos):
    """Que bases, keyspaces o prefijos se pueden elegir en un motor."""
    motor = (datos.get("motor") or "").lower()
    if motor not in fuentes.FUENTES:
        return _error(f"motor no soportado: {motor}")
    host = datos.get("host") or "127.0.0.1"
    puerto = datos.get("puerto")
    try:
        if motor == "mongodb":
            destinos = fuentes.mongodb.bases(host, puerto or 27017, datos.get("uri"))
        elif motor == "cassandra":
            destinos = fuentes.cassandra.keyspaces(host, puerto or 9042,
                                                   datos.get("usuario"),
                                                   datos.get("clave"))
        elif motor == "redis":
            destinos = fuentes.redis.prefijos(host, puerto or 6379,
                                              datos.get("clave"), datos.get("uri"))
        else:
            destinos = fuentes.neo4j.etiquetas(host, puerto or 7687,
                                               datos.get("usuario"),
                                               datos.get("clave"), datos.get("uri"))
    except Exception as e:  # noqa: BLE001 - el menu muestra el motivo
        return _error(f"no se pudo consultar {motor}: {e}")
    return _json({"ok": True, "motor": motor, "destinos": destinos})


def conectar(datos):
    """Lee el esquema de un motor vivo y lo devuelve en el vocabulario neutral."""
    motor = (datos.get("motor") or "").lower()
    if motor not in fuentes.FUENTES:
        return _error(f"motor no soportado: {motor}")
    try:
        esquema = leer_esquema(
            motor, destino=datos.get("destino"), host=datos.get("host") or "127.0.0.1",
            puerto=datos.get("puerto"), usuario=datos.get("usuario"),
            clave=datos.get("clave"), uri=datos.get("uri"),
            limite=int(datos.get("limite") or 300))
    except Exception as e:  # noqa: BLE001 - se explica el motivo, no se cae
        return _error(f"no se pudo conectar a {motor}: {e}")
    if not esquema.get("colecciones"):
        return _error(f"{motor} respondio, pero no hay datos que detectar en "
                      f"'{datos.get('destino') or 'el destino elegido'}'")
    return _json({"ok": True, "esquema": esquema})


def generar_en_motor(datos):
    """Genera lo que falta y lo ESCRIBE en el motor vivo."""
    esquema = datos.get("esquema")
    motor = (datos.get("motor") or "").lower()
    if not esquema or "colecciones" not in esquema:
        return _error("falta el esquema: primero hay que conectar")
    try:
        r = completar_en_motor(
            esquema, _normaliza_volumenes(datos.get("volumenes"), esquema), motor,
            destino=datos.get("destino"), host=datos.get("host") or "127.0.0.1",
            puerto=datos.get("puerto"), usuario=datos.get("usuario"),
            clave=datos.get("clave"), uri=datos.get("uri"),
            semilla=int(datos.get("semilla", 2026)), enums=datos.get("enums"),
            campos=datos.get("campos"))
    except (ValueError, ErrorGeneracion) as e:
        return _error(str(e))
    return _json({
        "ok": True,
        "motor": motor,
        "total_escrito": r["total_escrito"],
        "escrito": r["escrito"],
        "errores": r["errores"],
        "problemas_relacion": r["problemas_relacion"],
        "resumen": {
            "generados": r["metricas"]["totales"]["generados"],
            "total": r["metricas"]["totales"]["total"],
            "completitud": r["metricas"]["totales"]["completitud"],
            "colecciones": r["metricas"]["totales"]["colecciones"],
        },
    })


# --------------------------------------------------------------------- rutas
def ruta(metodo, camino, cuerpo=None, query=None):
    """Punto de entrada unico de la API. Devuelve {status, cuerpo}."""
    camino = (camino or "/").split("?")[0]
    try:
        if camino == "/api/catalogo" and metodo == "GET":
            return _json(vista_catalogo())

        if camino == "/api/esquema" and metodo == "GET":
            return _json({"ok": True, "esquema": vista_esquema()})

        if camino == "/api/salud" and metodo == "GET":
            return _json({"ok": True, "servicio": "DataForge NoSQL", "version": "2.0",
                          "motores": tipos.ORDEN_MOTORES,
                          "capacidades": ["sesiones", "historial", "cache", "logs", "telemetria"]})

        if camino == "/api/detectar" and metodo == "POST":
            return detectar_carga(_cuerpo(cuerpo))

        if camino == "/api/ejemplo" and metodo == "POST":
            return cargar_ejemplo(_cuerpo(cuerpo))

        if camino == "/api/generar" and metodo == "POST":
            return generar(_cuerpo(cuerpo))

        if camino == "/api/exportar" and metodo == "POST":
            return exportar(_cuerpo(cuerpo))

        if camino == "/api/comparar" and metodo == "POST":
            return comparar_motores(_cuerpo(cuerpo))

        if camino == "/api/motores" and metodo == "GET":
            return vista_motores()

        if camino == "/api/motores" and metodo == "POST":
            return vista_motores(_cuerpo(cuerpo))

        if camino == "/api/destinos" and metodo == "POST":
            return vista_destinos(_cuerpo(cuerpo))

        if camino == "/api/conectar" and metodo == "POST":
            return conectar(_cuerpo(cuerpo))

        if camino == "/api/generar-en-motor" and metodo == "POST":
            return generar_en_motor(_cuerpo(cuerpo))

        return _error(f"ruta no encontrada: {metodo} {camino}", 404)
    except json.JSONDecodeError as e:
        return _error(f"JSON invalido en la peticion: {e}")
    except ValueError as e:
        return _error(str(e))
    except ErrorGeneracion as e:
        return _error(str(e))
    except Exception as e:  # noqa: BLE001 - la interfaz muestra el error, no se cae
        return _error(f"{type(e).__name__}: {e}", 500)
