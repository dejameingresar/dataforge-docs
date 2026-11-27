"""nucleo.adaptadores.base — utilidades comunes a los adaptadores de motor.

Un adaptador sabe dos cosas: como se llama cada tipo neutral en su motor y como
se serializa un registro a su formato nativo. Todo lo que comparten vive aqui.
"""

import datetime as dt
import json


def _iso(valor):
    if isinstance(valor, dt.datetime):
        return valor.isoformat()
    if isinstance(valor, dt.date):
        return valor.isoformat()
    if isinstance(valor, dt.time):
        return valor.strftime("%H:%M:%S")
    return str(valor)


def _comillas_cql(texto):
    return "'" + str(texto).replace("'", "''") + "'"


def _comillas_cypher(texto):
    return '"' + str(texto).replace("\\", "\\\\").replace('"', '\\"') + '"'


def resumen_lote(resultado):
    """Conteo de existentes/generados/total, que encabeza todos los archivos."""
    filas = []
    for nombre, detalle in resultado.items():
        filas.append((nombre, detalle["n_existentes"], detalle["n_generados"],
                      detalle["total"]))
    return filas


def cabecera(comentario, motor, semilla, resultado, extra=None):
    """Cabecera de comentarios comun a los archivos exportados."""
    lineas = [
        f"{comentario} Lote de datos sinteticos generado por DataForge NoSQL",
        f"{comentario} Motor destino: {motor}",
        f"{comentario} Semilla: {semilla}  (la misma semilla reproduce el mismo lote)",
        f"{comentario}",
        f"{comentario} {'coleccion':<24} {'existian':>9} {'generados':>10} {'total':>8}",
        f"{comentario} {'-' * 24} {'-' * 9} {'-' * 10} {'-' * 8}",
    ]
    for nombre, existentes, generados, total in resumen_lote(resultado):
        lineas.append(f"{comentario} {nombre:<24} {existentes:>9} {generados:>10} {total:>8}")
    if extra:
        lineas.append(comentario)
        lineas.extend(f"{comentario} {e}" for e in extra)
    lineas.append("")
    return "\n".join(lineas)


def json_compacto(valor):
    return json.dumps(valor, ensure_ascii=False, default=str)
