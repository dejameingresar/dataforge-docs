"""nucleo.adaptadores.mongodb — serializa el lote al formato de MongoDB.

Dos salidas:

  *.json     Un arreglo de documentos en Extended JSON relajado, que es lo que
             acepta `mongoimport` sin conversiones. Los tipos que JSON no tiene
             (ObjectId, Date, Decimal128, binario) se emiten con su envoltura de
             Extended JSON, no como cadena, para que se carguen como el tipo BSON
             correcto y no como texto.
  *.js       Un script de `mongosh` con insertMany, util para la demo en vivo.
"""

import datetime as dt
import re

from .base import cabecera, json_compacto


def _a_bson(valor, campo):
    """Valor Python -> forma Extended JSON del tipo BSON correspondiente."""
    if valor is None:
        return None
    tipo = campo.get("tipo") if campo else None
    if tipo == "objectid":
        return {"$oid": str(valor)}
    if tipo == "uuid":
        return {"$binary": {"base64": _b64(str(valor).encode()),
                            "subType": "04"}}
    if tipo in ("fecha", "fecha_hora"):
        return {"$date": _iso_completo(valor)}
    if tipo == "timestamp":
        return {"$timestamp": {"t": int(valor), "i": 1}}
    if tipo == "decimal":
        return {"$numberDecimal": str(valor)}
    if tipo == "binario":
        datos = valor if isinstance(valor, bytes) else str(valor).encode()
        return {"$binary": {"base64": _b64(datos), "subType": "00"}}
    if tipo == "hora":
        return str(valor)
    if isinstance(valor, (dt.date, dt.datetime)):
        return {"$date": _iso_completo(valor)}
    if isinstance(valor, dict):
        return {k: _a_bson(v, None) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_a_bson(v, None) for v in valor]
    return valor


def _iso_completo(valor):
    """Fecha en el unico formato que acepta el `$date` de Extended JSON.

    El parser oficial de MongoDB exige fecha Y hora: un `{"$date": "2021-12"}`
    o un `{"$date": "2021-12-06"}` son rechazados con "time data ... does not
    match format". Una fecha sin hora se completa a medianoche.
    """
    if isinstance(valor, dt.datetime):
        return valor.isoformat()
    if isinstance(valor, dt.date):
        return dt.datetime(valor.year, valor.month, valor.day).isoformat()
    texto = str(valor)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        return texto + "T00:00:00"
    if re.fullmatch(r"\d{4}-\d{2}", texto):
        return texto + "-01T00:00:00"
    if re.fullmatch(r"\d{4}", texto):
        return texto + "-01-01T00:00:00"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", texto):
        return texto + ":00"
    return texto


def _b64(datos):
    import base64
    return base64.b64encode(datos).decode("ascii")


def documento(registro, campos):
    """Un registro -> documento listo para serializar."""
    por_nombre = {c["nombre"]: c for c in campos}
    return {k: _a_bson(v, por_nombre.get(k)) for k, v in registro.items()}


def exportar(resultado, esquema, semilla, formato="json"):
    """Devuelve {nombre_archivo: contenido} para el lote completo."""
    salida = {}
    if formato == "script":
        partes = [cabecera("//", "mongodb", semilla, resultado,
                           ["Pegar en mongosh para cargar los documentos."])]
        for nombre, detalle in resultado.items():
            campos = esquema["colecciones"][nombre]["campos"]
            docs = [documento(r, campos) for r in detalle["nuevos"]]
            partes.append(f"// --- {nombre}: {len(docs)} documentos nuevos ---")
            partes.append(f"db.{nombre}.insertMany({json_compacto(docs)});")
            partes.append("")
        salida[f"dataforge_mongodb_{semilla}.js"] = "\n".join(partes)
        return salida

    for nombre, detalle in resultado.items():
        campos = esquema["colecciones"][nombre]["campos"]
        docs = [documento(r, campos) for r in detalle["nuevos"]]
        cab = cabecera("//", "mongodb", semilla, {nombre: detalle},
                       [f"mongoimport --db dataforge --collection {nombre} "
                        f"--file {nombre}.json"])
        salida[f"{nombre}.json"] = cab + json_compacto(docs)
    return salida
