"""nucleo.detector — lee la base NoSQL que sube el usuario y deduce su estructura.

Es la pieza que hace posible el objetivo del proyecto: en vez de obligar al
usuario a declarar un esquema, la aplicacion **lee lo que ya tiene** y deduce
colecciones, campos, tipos, dominios y relaciones. Con esa estructura detectada,
el motor puede generar los datos que faltan y completar el conjunto.

Formatos soportados:

  MongoDB    JSON con un arreglo de documentos, JSONL (una linea por documento,
             el formato de `mongoexport`) o un objeto cuyas claves son nombres
             de coleccion.
  Cassandra  el DDL de `CREATE TABLE ... (...)` y/o las filas en CSV.
  Redis      el volcado de comandos (HSET / RESP) o un JSON de clave -> objeto.
  Neo4j      sentencias Cypher `CREATE (:Etiqueta {...})` o un JSON de nodos.
  Generico   cualquier JSON o JSONL: se infiere la forma y cada clave de primer
             nivel se trata como una coleccion.

La deteccion nunca falla en silencio: si no reconoce nada devuelve un error
explicando que formatos acepta.
"""

import csv
import io
import json
import re

from . import generadores, tipos

MAX_DOCUMENTOS_MUESTRA = 2000   # cuantos registros se leen para inferir
MAX_VALORES_DOMINIO = 60        # cuantos valores distintos se guardan por campo
MAX_VALORES_RELACION = 30       # cuantos valores se guardan para probar relaciones


class ErrorDeteccion(Exception):
    pass


# ------------------------------------------------------- Extended JSON de MongoDB
# Los volcados reales de MongoDB (mongoexport, mongodump y los datasets oficiales)
# no usan JSON plano: cada valor lleva su tipo envuelto en un objeto con una
# clave que empieza por $. Sin desenvolverlo, un {"$numberInt": "3062"} se lee
# como un documento anidado y la deteccion sale entera mal.
_EXTENDED_JSON = {
    "$oid": "objectid",
    "$numberInt": "entero",
    "$numberLong": "largo",
    "$numberDouble": "flotante",
    "$numberDecimal": "decimal",
    "$date": "fecha_hora",
    "$timestamp": "timestamp",
    "$binary": "binario",
    "$uuid": "uuid",
    "$regularExpression": "texto",
    "$code": "texto",
    "$minKey": "texto",
    "$maxKey": "texto",
}


class _ExtendedJSON:
    """Valor de Extended JSON ya desenvuelto: su tipo neutral y su valor crudo."""

    __slots__ = ("tipo", "valor", "crudo")

    def __init__(self, tipo, valor, crudo):
        self.tipo = tipo
        self.valor = valor
        self.crudo = crudo

    def __repr__(self):
        return f"<{self.tipo}: {self.valor!r}>"

    def __eq__(self, otro):
        return isinstance(otro, _ExtendedJSON) and self.valor == otro.valor

    def __hash__(self):
        return hash((self.tipo, str(self.valor)))


def _desenvuelve_extended_json(valor):
    """Convierte Extended JSON en valores Python; deja el resto igual.

    Se aplica a todo el arbol, porque la envoltura puede aparecer en cualquier
    nivel: en el _id, en una fecha, dentro de un documento anidado o en un
    elemento de un arreglo.
    """
    if isinstance(valor, list):
        return [_desenvuelve_extended_json(v) for v in valor]
    if not isinstance(valor, dict):
        return valor

    claves = set(valor)
    if len(claves) == 1:
        clave = next(iter(claves))
        if clave in _EXTENDED_JSON:
            crudo = valor[clave]
            tipo = _EXTENDED_JSON[clave]
            return _ExtendedJSON(tipo, _valor_crudo(clave, crudo), crudo)
    # Una fecha puede venir como {"$date": {"$numberLong": "..."}}.
    if "$date" in claves:
        crudo = valor["$date"]
        if isinstance(crudo, dict) and "$numberLong" in crudo:
            crudo = crudo["$numberLong"]
        return _ExtendedJSON("fecha_hora", crudo, valor)
    return {k: _desenvuelve_extended_json(v) for k, v in valor.items()}


def _valor_crudo(clave, crudo):
    """Valor comparable del contenido de una envoltura de Extended JSON."""
    if isinstance(crudo, dict):
        for k in ("$numberLong", "$numberInt", "$numberDouble", "$numberDecimal",
                  "base64"):
            if k in crudo:
                return crudo[k]
        return json.dumps(crudo, sort_keys=True)
    return crudo


def _texto_de(valor):
    """El valor como cadena, desenvolviendo la envoltura si la lleva."""
    if isinstance(valor, _ExtendedJSON):
        return str(valor.valor)
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, float) and valor == int(valor):
        return str(int(valor))
    return str(valor)


def _valor_python(valor):
    """Valor en su tipo Python natural, para poder generarlo y exportarlo."""
    if not isinstance(valor, _ExtendedJSON):
        return valor
    crudo = valor.valor
    if valor.tipo in ("entero", "largo", "timestamp"):
        try:
            return int(crudo)
        except (TypeError, ValueError):
            return crudo
    if valor.tipo in ("flotante", "decimal"):
        try:
            return float(crudo)
        except (TypeError, ValueError):
            return crudo
    if valor.tipo == "booleano":
        return str(crudo).lower() == "true"
    return crudo


# --------------------------------------------------------------- tipo de valor
# El orden importa: lo especifico va antes que lo generico. En particular, una
# fecha "2024-03-12" tambien encaja en un patron de telefono laxo, asi que las
# fechas y las horas se comprueban primero.
_RE_OBJECTID = re.compile(r"^[0-9a-fA-F]{24}$")
_RE_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                      r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
_RE_URL = re.compile(r"^https?://\S+$")
_RE_FECHA_HORA = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?")
_RE_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RE_HORA = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")
_RE_INET = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_RE_TELEFONO = re.compile(r"^(\+51)?9\d{8}$")
_RE_ENTERO = re.compile(r"^-?\d+$")
_RE_FLOTANTE = re.compile(r"^-?\d+\.\d+$")


def _tipo_de_valor(valor):
    """Tipo neutral mas probable de un valor Python."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return "booleano"
    if isinstance(valor, _ExtendedJSON):
        return valor.tipo
    if isinstance(valor, int):
        return "largo" if abs(valor) > 2_147_483_647 else "entero"
    if isinstance(valor, float):
        return "flotante"
    if isinstance(valor, dict):
        return "mapa"
    if isinstance(valor, list):
        return "lista"
    if isinstance(valor, bytes):
        return "binario"
    if isinstance(valor, str):
        if _RE_OBJECTID.match(valor):
            return "objectid"
        if _RE_UUID.match(valor):
            return "uuid"
        if _RE_EMAIL.match(valor):
            return "email"
        if _RE_URL.match(valor):
            return "url"
        if _RE_FECHA_HORA.match(valor):
            return "fecha_hora"
        if _RE_FECHA.match(valor):
            return "fecha"
        if _RE_HORA.match(valor):
            return "hora"
        if _RE_INET.match(valor):
            return "inet"
        # Un telefono movil peruano tiene 9 digitos y empieza por 9; el patron no
        # admite guiones, que es lo que hacia que una fecha como 2024-03-12 se
        # leyera como telefono.
        if _RE_TELEFONO.match(valor.replace(" ", "")):
            return "telefono"
        # Un numero guardado COMO TEXTO no es un numero: en JSON un entero real
        # viene sin comillas. Un "40123456" entre comillas es un codigo (un DNI,
        # un codigo postal), y tratarlo como entero lo convierte en 1675 al
        # generarlo. El CSV si castea, asi que ahi el valor llega ya como int.
        return "texto_largo" if len(valor) > 120 else "texto"
    return "texto"


def _tipo_predominante(conteo):
    """Tipo de la columna a partir del recuento de tipos observados."""
    if not conteo:
        return "texto"
    # Varios tipos de datos mezclados en la misma columna: el campo es de
    # verdad heterogeneo (un "valor" que a veces es numero y a veces texto), y
    # quedarse con el mas especifico lo deformaria. Gana el mas frecuente.
    if len(conteo) > 1:
        return max(conteo, key=conteo.get)
    # Un solo tipo observado: se devuelve tal cual.
    return next(iter(conteo))


def _valor_dominio(valor):
    """Forma textual con la que un valor entra en el dominio observado."""
    if isinstance(valor, float):
        return repr(valor)[:30]
    return _a_texto(valor)[:100]


def _parece_dominio(valores):
    """True si los valores observados parecen un dominio cerrado y no texto libre.

    Un dominio se reconoce porque sus valores son tokens: una sola palabra, sin
    espacios y cortos (ORO, ENTREGADO, Computo). Un nombre de persona o el
    titulo de un producto llevan espacios, asi que no se confunden con un
    dominio aunque la muestra sea pequena.
    """
    if not valores:
        return False
    for v in valores:
        if not v or len(v) > 30 or " " in v:
            return False
    return True


# Nombres de campo que, por si solos, anuncian un dominio cerrado: un "estado" o
# un "nivel" tienen un catalogo finito aunque la muestra no lo repita todavia.
_RE_NOMBRE_DOMINIO = re.compile(
    r"(estado|status|situacion|nivel|nivel_|categoria|tipo|tipo_|moneda|currency|"
    r"sexo|genero|prioridad|rol|role|modalidad|segmento|clase|grupo|turno|grado|"
    r"region|zona|sede|pais_iso)", re.I)


def _nombre_sugiere_dominio(nombre):
    return bool(_RE_NOMBRE_DOMINIO.search(str(nombre)))


def _acumula(perfil, clave, valor):
    """Suma un valor observado al perfil de un campo."""
    p = perfil.setdefault(clave, {
        "tipos": {}, "nulos": 0, "total": 0, "valores": {}, "ejemplos": [],
        "min": None, "max": None, "largos": [], "n_elementos": 0, "elementos": {},
        "desborde": False, "muestra_valores": [], "distintos": 0,
    })
    p["total"] += 1
    if valor is None:
        p["nulos"] += 1
        return p
    # Los valores de Extended JSON se desenvuelven: para perfilar y para
    # comparar interesa el valor, no su envoltura.
    if isinstance(valor, _ExtendedJSON):
        texto = _texto_de(valor)
        p["tipos"][valor.tipo] = p["tipos"].get(valor.tipo, 0) + 1
        if texto not in p["valores"]:
            p["distintos"] += 1
        if len(p["valores"]) < MAX_VALORES_DOMINIO:
            p["valores"][texto] = p["valores"].get(texto, 0) + 1
        elif texto not in p["valores"]:
            p["desborde"] = True
        if len(p["muestra_valores"]) < MAX_VALORES_RELACION:
            p["muestra_valores"].append(texto)
        if valor.tipo in ("entero", "largo", "flotante", "decimal"):
            try:
                n = float(valor.valor)
                p["min"] = n if p["min"] is None else min(p["min"], n)
                p["max"] = n if p["max"] is None else max(p["max"], n)
            except (TypeError, ValueError):
                pass
        if len(p["ejemplos"]) < 3:
            p["ejemplos"].append(texto[:80])
        return p
    t = _tipo_de_valor(valor)
    if t:
        p["tipos"][t] = p["tipos"].get(t, 0) + 1
    if isinstance(valor, (str, int, float, bool)):
        texto = _valor_dominio(valor)
        if texto not in p["valores"]:
            p["distintos"] += 1
        if len(p["valores"]) < MAX_VALORES_DOMINIO:
            p["valores"][texto] = p["valores"].get(texto, 0) + 1
        elif texto not in p["valores"]:
            # Hay mas valores distintos de los que se guardan: el campo no es un
            # dominio cerrado y no debe proponerse como enum.
            p["desborde"] = True
        # Los valores concretos se guardan para poder comprobar si este campo
        # apunta a otra coleccion (sus valores existirian como claves alli).
        if len(p["muestra_valores"]) < MAX_VALORES_RELACION:
            p["muestra_valores"].append(texto)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            p["min"] = valor if p["min"] is None else min(p["min"], valor)
            p["max"] = valor if p["max"] is None else max(p["max"], valor)
        if isinstance(valor, str):
            p["largos"].append(len(valor))
    if isinstance(valor, list):
        p["n_elementos"] = max(p["n_elementos"], len(valor))
        for v in valor:
            et = _tipo_de_valor(v)
            p["elementos"][et] = p["elementos"].get(et, 0) + 1
    if len(p["ejemplos"]) < 3:
        p["ejemplos"].append(_ejemplo(valor))
    return p


def _ejemplo(valor):
    """Version corta y serializable de un valor, para mostrarla en la interfaz."""
    if isinstance(valor, bytes):
        return f"<{len(valor)} bytes>"
    if isinstance(valor, (dict, list)):
        texto = json.dumps(valor, ensure_ascii=False, default=str)
        return texto[:80] + ("..." if len(texto) > 80 else "")
    return _a_texto(valor)[:80]


def _a_texto(valor):
    """Texto de un valor, sin reventar con enteros de miles de digitos.

    Python limita la conversion de cadena a entero (4300 digitos por defecto)
    y lanza ValueError al pasarla. Un volcado con un entero enorme no deberia
    tumbar la aplicacion: se compara sin convertir y se colapsa a un marcador.
    """
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, int):
        if -10 ** 30 < valor < 10 ** 30:
            return str(valor)
        return ("-" if valor < 0 else "") + "##"
    return str(valor)


def _normaliza_valor(valor):
    """Valor listo para el motor: sin envolturas de Extended JSON, en su tipo."""
    if isinstance(valor, _ExtendedJSON):
        return _valor_python(valor)
    if isinstance(valor, dict):
        return {k: _normaliza_valor(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_normaliza_valor(v) for v in valor]
    return valor


def _perfila_registros(registros):
    """Perfila una lista de registros (documentos, filas, nodos)."""
    perfil = {}
    for reg in registros:
        if not isinstance(reg, dict):
            continue
        for clave, valor in reg.items():
            _acumula(perfil, str(clave), _desenvuelve_extended_json(valor))
    return perfil


# ----------------------------------------------------------- perfil -> campo
def _campo_desde_perfil(nombre, p, es_pk=False, coleccion=None):
    """Convierte el perfil observado de una columna en un campo del esquema."""
    tipo = _tipo_predominante(p["tipos"])
    valores = list(p["valores"])

    campo = {
        "nombre": nombre,
        "tipo": tipo,
        "nullable": p["nulos"] > 0,
        "observado": {
            "total": p["total"],
            "nulos": p["nulos"],
            "distintos": p["distintos"],
            "frecuencia_nulos": round(p["nulos"] / p["total"], 4) if p["total"] else 0.0,
            "ejemplos": p["ejemplos"],
            "muestra_valores": p["muestra_valores"],
        },
    }
    if p["min"] is not None and p["max"] is not None:
        # Un valor numerico enorme (miles de digitos) no cabe en un float: si
        # se usa para calcular un rango, revienta con OverflowError. Se acota a
        # la banda de los enteros grandes, que es informacion suficiente para
        # el campo.
        def _acota(v):
            try:
                f = float(v)
                if f != f or f in (float("inf"), float("-inf")):
                    return 1e18 if v > 0 else -1e18
                return f
            except (OverflowError, ValueError, TypeError):
                return 1e18 if (isinstance(v, (int, float)) and v > 0) else -1e18
        pmin, pmax = _acota(p["min"]), _acota(p["max"])
        if pmin != pmax:
            campo["min"] = pmin
            campo["max"] = pmax
        else:
            # Un unico valor observado no define un rango: se propone una banda
            # alrededor de ese valor en vez de dejar el campo sin referencias.
            centro = abs(pmin) or 1
            margen = centro * 0.5 if centro > 1 else 1
            campo["min"] = round(pmin - margen, 6)
            campo["max"] = round(pmin + margen, 6)
    if p["largos"]:
        campo["largo"] = max(p["largos"])
    if p["n_elementos"]:
        campo["n_elementos"] = p["n_elementos"]
    if p["elementos"]:
        campo["elemento"] = max(p["elementos"], key=p["elementos"].get)

    # Dominio cerrado: pocos valores distintos y todos con forma de token. Hace
    # falta ademas que los valores se repitan (un dominio se repite) o que el
    # nombre del campo lo anuncie; si no, un identificador con valores todos
    # distintos (un SKU, una clave) se confundiria con un dominio. Un campo cuyo
    # nombre anuncia un dominio (nivel, estado) se acepta incluso con un solo
    # valor observado, que es el caso de una muestra muy pequena.
    hay_repeticion = len(valores) < p["total"]
    anuncia = _nombre_sugiere_dominio(nombre)
    minimo = 1 if anuncia else 2
    if (tipo in ("texto", "texto_largo") and not es_pk and not p["desborde"]
            and minimo <= len(valores) <= 12 and _parece_dominio(valores)
            and (hay_repeticion or anuncia)):
        campo["tipo"] = "enum"
        campo["enum"] = sorted(valores)
        return campo

    # Sin dominio: si el nombre del campo sugiere un valor con significado, se
    # propone el generador semantico correspondiente. Se aplica tambien a los
    # campos numericos: un `founded_year` es un entero, pero un entero que
    # significa un anio, no un numero cualquiera.
    pista = _pista_de_campo(nombre, coleccion)
    if pista:
        tipo_sug, gen_sug = pista
        compatible = (tipo in ("texto", "texto_largo")
                      or tipo_sug in ("entero", "largo")
                      or tipo == tipo_sug)
        if compatible:
            campo["sugerencia"] = {"tipo": tipo_sug, "generador": gen_sug}
            if gen_sug:
                campo["generador"] = gen_sug
            # Un `id` numerico guardado como texto pasa a entero: es lo que el
            # valor realmente es, y evita generar "Fige" donde habia "1001".
            if tipo_sug != tipo and tipo in ("texto", "texto_largo"):
                campo["tipo"] = tipo_sug
    return campo


# En una coleccion de productos, un campo "nombre" es el nombre del producto y no
# el de una persona. La coleccion da el contexto que el nombre del campo solo no
# da.
_CONTEXTO_COLECCION = [
    (re.compile(r"producto|articulo|item|inventario|catalogo|sku", re.I),
     {"nombre": ("producto", "producto"), "titulo": ("producto", "producto")}),
    (re.compile(r"empresa|proveedor|compania|organizacion|vendedor", re.I),
     {"nombre": ("empresa", "empresa")}),
    (re.compile(r"categoria|rubro|familia", re.I),
     {"nombre": ("categoria", "categoria")}),
]


def _pista_de_campo(nombre, coleccion=None):
    """Sugerencia (tipo, generador) para un campo, mirando tambien su coleccion."""
    if coleccion:
        for patron, mapa in _CONTEXTO_COLECCION:
            if patron.search(str(coleccion)):
                clave = str(nombre).lower()
                if clave in mapa:
                    return mapa[clave]
    return generadores.pista_semantica(nombre)


def _campo_unico_probable(campo):
    """Un campo con todos los valores distintos es candidato a unico.

    Pero "todos distintos en la muestra" no basta: `metacritic` con 3 valores
    distintos en 3 documentos parece unico y no lo es. Solo se marca unico si la
    muestra es lo bastante grande para que la coincidencia signifique algo.
    """
    if campo["tipo"] not in ("texto", "email", "url", "telefono", "objectid",
                             "uuid", "entero", "largo", "dni"):
        return False
    return campo.get("observado", {}).get("total", 0) >= 10


# Tipos con los que se puede identificar un registro: un codigo, un documento,
# una clave. Un decimal o una fecha no identifican nada.
_TIPOS_CLAVE = ("objectid", "uuid", "texto", "texto_largo", "email", "url",
                "telefono", "dni", "entero", "largo")
# Entre los candidatos, un identificador de texto es mas probable que un numero:
# un `title` identifica una pelicula, un `released` solo parece unico.
_TIPOS_CLAVE_TEXTO = ("objectid", "uuid", "texto", "texto_largo", "email", "url",
                      "telefono", "dni")


def _esquema_desde_colecciones(colecciones, motor, formato):
    """Convierte colecciones de registros en un esquema neutral completo."""
    salida = {}
    total_registros = 0
    for nombre, registros in colecciones.items():
        registros = [r for r in registros if isinstance(r, dict)][:MAX_DOCUMENTOS_MUESTRA]
        if not registros:
            continue
        perfil = _perfila_registros(registros)
        # La clave primaria se decide primero, para que ese campo no acabe
        # convertido en un dominio cerrado.
        pk_nombre = None
        for candidato in ("_id", "id", "uuid", "pk"):
            p = perfil.get(candidato)
            if p and p["nulos"] == 0 and p["distintos"] == p["total"]:
                pk_nombre = candidato
                break
        # Una clave sintetica de Redis (`_clave`) tambien identifica al registro
        # cuando no hay un campo id explicito.
        if pk_nombre is None:
            p = perfil.get("_clave")
            if p and p["nulos"] == 0 and p["distintos"] == p["total"]:
                pk_nombre = "_clave"
        # Si ningun campo se llama como una clave, la clave es el campo con
        # valores todos distintos y sin nulos: un `codigo`, una `clave`, un
        # `dni`. Se prefiere el TEXTO al numero: un `title` identifica una
        # pelicula, mientras que un `released` (el anio) solo parece unico
        # porque la muestra es corta. Sin clave, la coleccion a la que otra
        # apunta no tendria destino y la relacion quedaria sin resolver.
        if pk_nombre is None:
            candidatos = []
            for nombre_campo, p in perfil.items():
                tipo_c = _tipo_predominante(p["tipos"])
                if (p["total"] and not p["nulos"]
                        and p["distintos"] == p["total"]
                        and tipo_c in _TIPOS_CLAVE):
                    candidatos.append((nombre_campo, tipo_c, p))
            if candidatos:
                # Se prefiere el campo que MAS valores distintos aporta: un
                # `tagline` con 37 valores en 37 nodos parece unico, pero un
                # `title` con 44 en 45 es el identificador real. El primero del
                # diccionario no sirve: en el dataset oficial de Neo4j el title
                # aparece antes que el tagline y aun asi hay que desempatar por
                # cobertura. A igualdad, gana el texto sobre el numero.
                candidatos.sort(key=lambda c: (
                    c[1] not in _TIPOS_CLAVE_TEXTO,
                    -c[2]["distintos"],
                    -c[2]["total"],
                ))
                pk_nombre = candidatos[0][0]
        campos = []
        for nombre_campo, p in perfil.items():
            campo = _campo_desde_perfil(nombre_campo, p, es_pk=(nombre_campo == pk_nombre),
                                        coleccion=nombre)
            if nombre_campo == pk_nombre:
                campo["pk"] = True
                campo["nullable"] = False
                campo["unique"] = True
            elif (p["distintos"] == p["total"] and p["total"] >= 10
                  and not p["nulos"] and _campo_unico_probable(campo)):
                campo["unique"] = True
            # Documentos anidados: se perfila su interior para poder generarlos.
            if campo["tipo"] == "mapa":
                hijos = [r.get(nombre_campo) for r in registros
                         if isinstance(r.get(nombre_campo), dict)]
                if hijos:
                    sub = _perfila_registros(hijos)
                    campo["campos"] = [_campo_desde_perfil(k, v, coleccion=nombre)
                                       for k, v in sub.items()]
            # `_clave` es la clave real de Redis, que el lector agrega para
            # saber de que hash vino cada registro. Sirve como clave interna,
            # pero no es un campo del usuario: se marca como interno para que
            # no aparezca en el esquema que se muestra.
            if nombre_campo == "_clave":
                campo["interno"] = True
            campos.append(campo)
        # La muestra se guarda con los valores ya en su tipo Python natural, para
        # que el motor y los adaptadores no tengan que conocer el Extended JSON.
        muestra = [{k: _normaliza_valor(v) for k, v in r.items()} for r in registros[:20]]
        salida[nombre] = {
            "nombre": nombre,
            "registros_observados": len(registros),
            "campos": campos,
            "claves": [pk_nombre] if pk_nombre else [],
            "origen": formato,
            "muestra": muestra,
        }
        total_registros += len(registros)
    if not salida:
        raise ErrorDeteccion("no se pudo inferir ninguna coleccion con registros")
    _infiere_relaciones(salida)
    return {
        "motor": motor,
        "formato": formato,
        "colecciones": salida,
        "total_registros": total_registros,
    }


def _infiere_relaciones(salida):
    """Marca como relacion los campos que apuntan a otra coleccion.

    Se comprueba por dos vias, en este orden:
      1. el nombre del campo (id_cliente / cliente_id apuntan a `clientes`);
      2. los valores: si todos los valores observados existen entre las claves
         de otra coleccion, el campo es una referencia a esa coleccion.
    """
    nombres = list(salida)
    for nombre, col in salida.items():
        for campo in col["campos"]:
            if campo.get("pk") or campo.get("ref"):
                continue
            objetivo = _por_nombre(campo["nombre"], nombre, nombres)
            if objetivo is None:
                objetivo = _por_valores(campo, nombre, salida)
            if objetivo:
                campo["ref"] = objetivo
                # Una referencia se genera eligiendo una clave existente, no un
                # valor aleatorio del tipo: se retiran los generadores.
                campo.pop("generador", None)
                campo.pop("sugerencia", None)
                campo.pop("unique", None)
                campo.pop("enum", None)
                if campo["tipo"] == "enum":
                    campo["tipo"] = "texto"


def _por_nombre(nombre_campo, nombre_actual, nombres):
    """Coleccion a la que apunta un campo por su nombre.

    Reconoce tanto el sufijo (`id_cliente`, `cliente_id`) como el prefijo
    (`codigo_libro`, `dni_socio`), que es la forma habitual de nombrar una clave
    foranea con el nombre del campo al que apunta en la tabla destino.
    """
    fname = nombre_campo.lower()
    for otro in nombres:
        if otro == nombre_actual:
            continue
        for b in {otro.lower(), otro.lower().rstrip("s"), otro.lower() + "s"}:
            if fname in {f"id_{b}", f"{b}_id", f"{b}id", f"{b}_uuid", f"uuid_{b}",
                         f"{b}_key", f"id_{b}_ref"}:
                return otro
            # Prefijo: el campo empieza por un calificativo y termina con el
            # nombre de la coleccion (codigo_libro -> libro, dni_socio -> socio).
            for prefijo in ("id_", "codigo_", "cod_", "dni_", "numero_", "num_",
                            "clave_", "ref_", "sku_", "uuid_"):
                if fname == prefijo + b:
                    return otro
            if fname.endswith("_" + b) and not fname.startswith(b + "_"):
                return otro
    return None


def _por_valores(campo, nombre_actual, salida):
    """Busca la coleccion cuyas claves contienen los valores observados del campo.

    Es el respaldo del nombre: si todos los valores que aparecen en este campo
    existen como claves de otra coleccion, el campo es una referencia a esa
    coleccion aunque su nombre no lo diga.
    """
    obs = campo.get("observado") or {}
    valores = {v for v in (obs.get("muestra_valores") or []) if v not in ("", "None")}
    if len(valores) < 1:
        return None
    for otro, col in salida.items():
        if otro == nombre_actual:
            continue
        pk = next((c for c in col["campos"] if c.get("pk")), None)
        if not pk:
            continue
        claves = set(pk.get("observado", {}).get("muestra_valores") or [])
        # Todos los valores del campo deben existir como clave en la otra
        # coleccion. Se exige al menos uno para no emparejar campos vacios.
        if claves and valores and valores <= claves:
            return otro
    return None


# --------------------------------------------------------------- mongo / json
def _es_jsonl(texto):
    """True si el texto son objetos JSON uno por linea (mongoexport)."""
    lineas = [l for l in texto.splitlines() if l.strip()]
    if len(lineas) < 2:
        return False
    return all(l.lstrip().startswith("{") and l.rstrip().endswith("}") for l in lineas[:3])


def _lee_json(texto):
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    except ValueError:
        # Un entero de miles de digitos hace fallar a json.loads con un
        # ValueError que no es JSONDecodeError: Python limita la conversion de
        # cadena a entero. Se sube el limite para ese caso y se reintenta.
        import sys
        anterior = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(0)  # 0 = sin limite
            return json.loads(texto)
        except (json.JSONDecodeError, ValueError):
            raise ErrorDeteccion("el contenido no es JSON valido ni JSONL")
        finally:
            sys.set_int_max_str_digits(anterior)
    if _es_jsonl(texto):
        docs = []
        for linea in texto.splitlines():
            linea = linea.strip()
            if not linea:
                continue
            try:
                docs.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
        if docs:
            return docs
    raise ErrorDeteccion("el contenido no es JSON valido ni JSONL (una linea por documento)")


def _nombre_coleccion(nombre_archivo):
    base = re.sub(r"\.(json|jsonl|txt|bson|csv|redis|cql|cypher)$", "",
                  nombre_archivo or "datos", flags=re.I)
    base = re.sub(r"[^0-9a-zA-Z_]+", "_", base).strip("_").lower()
    return base or "datos"


def _colecciones_de_json(datos, nombre_archivo):
    """Separa el JSON en colecciones: una por clave de primer nivel o una sola."""
    if isinstance(datos, list):
        return {_nombre_coleccion(nombre_archivo): datos}
    if isinstance(datos, dict):
        valores_lista = {k: v for k, v in datos.items()
                         if isinstance(v, list) and v and isinstance(v[0], dict)}
        if valores_lista and len(valores_lista) == len(datos):
            return valores_lista
        for clave in ("documentos", "documents", "datos", "data", "items", "registros"):
            if clave in datos and isinstance(datos[clave], list):
                return {_nombre_coleccion(nombre_archivo): datos[clave]}
        return {_nombre_coleccion(nombre_archivo): [datos]}
    raise ErrorDeteccion("el JSON debe ser un arreglo de documentos o un objeto")


def detecta_json(texto, nombre_archivo="datos.json"):
    """Deteccion para JSON, JSONL y volcados de MongoDB."""
    datos = _lee_json(texto)
    return _esquema_desde_colecciones(_colecciones_de_json(datos, nombre_archivo),
                                      "mongodb", "JSON / JSONL")


# ----------------------------------------------------------------- cassandra
_RE_CREATE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
                        r"(?:(\w+)\s*\.\s*)?(\w+)\s*\((.*?)\)\s*(?:WITH|;|$)",
                        re.I | re.S)
_RE_TIPOS_CQL = {
    "uuid": "uuid", "timeuuid": "uuid", "text": "texto", "varchar": "texto",
    "ascii": "texto", "int": "entero", "bigint": "largo", "smallint": "entero",
    "tinyint": "entero", "varint": "largo", "decimal": "decimal", "double": "flotante",
    "float": "flotante", "boolean": "booleano", "timestamp": "fecha_hora",
    "date": "fecha", "time": "hora", "blob": "binario", "inet": "inet",
    "counter": "largo", "duration": "texto",
}


def _tipo_cql_a_neutral(texto):
    t = texto.strip().lower()
    m = re.match(r"(list|set)<\s*([\w<>]+)\s*>", t)
    if m:
        return "lista", _tipo_cql_a_neutral(m.group(2))[0]
    m = re.match(r"map<\s*([\w<>]+)\s*,\s*([\w<>]+)\s*>", t)
    if m:
        return "mapa", None
    return _RE_TIPOS_CQL.get(t, "texto"), None


def detecta_cql(texto, nombre_archivo="esquema.cql"):
    """Deteccion para el DDL de Cassandra (CREATE TABLE)."""
    colecciones = {}
    for m in _RE_CREATE.finditer(texto):
        nombre = m.group(2)
        cuerpo = m.group(3)
        campos, pk = [], []
        for linea in _parte_columnas(cuerpo):
            linea = linea.strip()
            if not linea:
                continue
            mpk = re.match(r"PRIMARY\s+KEY\s*\(\((.*?)\)\)", linea, re.I)
            if mpk:
                pk = [c.strip() for c in mpk.group(1).split(",")]
                continue
            # `PRIMARY KEY (id)` de una sola columna, sin el doble parentesis.
            mpk1 = re.match(r"^PRIMARY\s+KEY\s*\((.+?)\)\s*$", linea, re.I)
            if mpk1:
                pk = [c.strip() for c in mpk1.group(1).split(",")]
                continue
            if re.match(r"^PRIMARY\s+KEY", linea, re.I):
                continue
            mcol = re.match(r"^(\w+)\s+([\w<>]+(?:\s*,\s*[\w<>]+)?)", linea, re.I)
            if not mcol:
                continue
            nombre_col = mcol.group(1)
            if nombre_col.upper() in ("PRIMARY", "CLUSTERING", "WITH", "COMPACT",
                                      "STATIC"):
                continue
            tipo, elemento = _tipo_cql_a_neutral(mcol.group(2))
            campos.append({"nombre": nombre_col, "tipo": tipo, "elemento": elemento,
                           "nullable": True,
                           "observado": {"total": 0, "nulos": 0, "distintos": 0,
                                         "ejemplos": []}})
        if not campos:
            continue
        for c in campos:
            if c["nombre"] in pk:
                c["pk"] = True
                c["nullable"] = False
        colecciones[nombre] = {"nombre": nombre, "campos": campos, "claves": pk,
                               "origen": "DDL CQL", "registros_observados": 0,
                               "muestra": []}
    if not colecciones:
        raise ErrorDeteccion(
            "no se encontro ninguna sentencia CREATE TABLE; pegue el DDL de "
            "Cassandra (DESCRIBE TABLE ...) o un volcado con sus filas")
    _infiere_relaciones(colecciones)
    return {"motor": "cassandra", "formato": "DDL CQL", "colecciones": colecciones,
            "total_registros": 0}


def _parte_columnas(cuerpo):
    """Separa por comas de primer nivel, respetando parentesis y comillas."""
    piezas, actual, nivel, comilla = [], [], 0, None
    for ch in cuerpo:
        if comilla:
            actual.append(ch)
            if ch == comilla:
                comilla = None
            continue
        if ch in "'\"":
            comilla = ch
            actual.append(ch)
            continue
        if ch == "(":
            nivel += 1
        elif ch == ")":
            nivel -= 1
        if ch == "," and nivel == 0:
            piezas.append("".join(actual))
            actual = []
            continue
        actual.append(ch)
    if actual:
        piezas.append("".join(actual))
    return piezas


def detecta_csv(texto, nombre_archivo="datos.csv", motor="cassandra"):
    """Deteccion para filas en CSV: cabecera + tipos inferidos por columna."""
    try:
        lector = csv.DictReader(io.StringIO(texto))
        if not lector.fieldnames:
            raise ErrorDeteccion("el CSV no tiene cabecera; se necesita la primera fila "
                                 "con los nombres de columna")
        filas = []
        for i, fila in enumerate(lector):
            if i >= MAX_DOCUMENTOS_MUESTRA:
                break
            filas.append({k: _castea(v) for k, v in fila.items() if k})
        if not filas:
            raise ErrorDeteccion("el CSV no tiene filas de datos")
    except csv.Error as e:
        # Un CSV con saltos de linea dentro de campos sin cerrar, o con
        # comillas desbalanceadas, hace que el lector lance csv.Error. No es un
        # volcado valido, asi que se trata como tal.
        raise ErrorDeteccion(f"el CSV no se pudo leer: {e}")
    return _esquema_desde_colecciones({_nombre_coleccion(nombre_archivo): filas},
                                      motor, "CSV")


def _castea(valor):
    """Convierte el texto del CSV a un valor tipado cuando es evidente."""
    if valor is None or valor == "":
        return None
    v = valor.strip()
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lower() in ("null", "none", "na", "n/a"):
        return None
    return v


# --------------------------------------------------------------------- redis
def detecta_redis(texto, nombre_archivo="datos.redis"):
    """Deteccion para volcados de Redis: comandos RESP/HSET o JSON clave -> objeto."""
    try:
        datos = json.loads(texto)
        if isinstance(datos, dict):
            por_coleccion = {}
            for clave, valor in datos.items():
                prefijo = str(clave).split(":")[0] or "registro"
                registro = dict(valor) if isinstance(valor, dict) else {"valor": valor}
                # La clave completa se conserva como campo: es lo que identifica
                # al registro en Redis.
                registro.setdefault("_clave", str(clave))
                por_coleccion.setdefault(prefijo, []).append(registro)
            if por_coleccion:
                return _esquema_desde_colecciones(por_coleccion, "redis",
                                                  "JSON clave -> objeto")
    except json.JSONDecodeError:
        pass

    registros = []
    patron_hset = re.compile(r"HSET\s+(\S+)\s+(.+)", re.I)
    for linea in texto.splitlines():
        m = patron_hset.search(linea)
        if not m:
            continue
        clave, resto = m.group(1), m.group(2)
        partes = re.findall(r'"([^"]*)"|(\S+)', resto)
        pares = [a or b for a, b in partes]
        doc = {"_clave": clave}
        for i in range(0, len(pares) - 1, 2):
            doc[pares[i]] = _castea(pares[i + 1])
        registros.append(doc)
    if registros:
        prefijo = str(registros[0].get("_clave", "registro")).split(":")[0] or "registro"
        return _esquema_desde_colecciones({prefijo: registros}, "redis", "comandos HSET")

    raise ErrorDeteccion(
        "no se reconocio un volcado de Redis; se aceptan los comandos HSET o un "
        "JSON donde cada clave apunta al objeto que representa al registro")


# --------------------------------------------------------------------- neo4j
_RE_NODO = re.compile(r"\(\s*(?:(\w+)\s*)?(?::\s*(\w+))?\s*(\{[^{}]*\})?\s*\)")
_RE_PROPIEDAD = re.compile(r"(\w+)\s*:\s*(\"[^\"]*\"|'[^']*'|-?\d+\.?\d*|true|false|null)")
# `ON CREATE SET n.prop = valor`: la forma que usa el dataset oficial de Neo4j
# (MERGE ... ON CREATE SET), donde las propiedades NO van en el bloque {}.
_RE_ON_CREATE = re.compile(r"ON\s+CREATE\s+SET\s+(.+)", re.I)
_RE_ASIGNACION = re.compile(
    r"(\w+)\.(\w+)\s*=\s*(\"[^\"]*\"|'[^']*'|\[[^\]]*\]|-?\d+\.?\d*|true|false|null)")
_RE_RELACION = re.compile(r"-\[:?\s*(\w+)?\s*\]->")
_RESERVADAS = {"CREATE", "MATCH", "MERGE", "SET", "RETURN", "WHERE", "DELETE",
               "WITH", "REMOVE", "ON", "UNWIND"}


def detecta_cypher(texto, nombre_archivo="grafo.cypher"):
    """Deteccion para sentencias Cypher: nodos con etiqueta y propiedades."""
    try:
        datos = json.loads(texto)
        if isinstance(datos, list) and datos and isinstance(datos[0], dict):
            por_etiqueta = {}
            for nodo in datos:
                etiqueta = (nodo.get("label") or nodo.get("etiqueta")
                            or nodo.get("_label") or "Nodo")
                props = nodo.get("props") or nodo.get("propiedades") or {
                    k: v for k, v in nodo.items()
                    if k not in ("label", "etiqueta", "_label", "props", "propiedades")}
                por_etiqueta.setdefault(etiqueta, []).append(props)
            if por_etiqueta:
                return _esquema_desde_colecciones(por_etiqueta, "neo4j", "JSON de nodos")
    except json.JSONDecodeError:
        pass

    # En Cypher el patron es (variable:Etiqueta {props}); la etiqueta es lo que
    # define la coleccion, la variable no. Las propiedades pueden venir en el
    # bloque {} (CREATE) o en un `ON CREATE SET n.prop = valor` (MERGE).
    #
    # MERGE es idempotente: `MERGE (m:Movie {title:'The Matrix'})` repetido cien
    # veces sigue siendo UN nodo. El dataset oficial de Neo4j esta escrito asi,
    # y contar cada aparicion como un nodo nuevo infla la coleccion y hace que
    # el identificador parezca tener duplicados. Los nodos de MERGE se
    # deduplican por su bloque de propiedades; los de CREATE no, porque CREATE
    # siempre crea un nodo nuevo.
    por_etiqueta, relaciones = {}, []
    variables = {}       # variable -> etiqueta, para resolver el ON CREATE SET
    vistos_merge = {}    # (etiqueta, bloque) -> indice del nodo ya creado
    for m in _RE_NODO.finditer(texto):
        etiqueta = m.group(2)
        bloque = m.group(3)
        if not etiqueta or etiqueta.upper() in _RESERVADAS:
            continue
        props = {}
        if bloque:
            for pm in _RE_PROPIEDAD.finditer(bloque):
                props[pm.group(1)] = _castea(pm.group(2).strip("\"'"))
        # ¿La sentencia es MERGE o CREATE? Se mira la palabra que precede al
        # parentesis. Un nodo dentro de un MATCH es una BUSQUEDA, no una
        # definicion: no crea nada y no debe contarse como un registro.
        antes = texto[max(0, m.start() - 12):m.start()].upper()
        if "MATCH" in antes and "MERGE" not in antes and "CREATE" not in antes:
            if m.group(1):
                variables[m.group(1)] = etiqueta
            continue
        es_merge = "MERGE" in antes
        if es_merge and bloque:
            # El mismo nodo puede declararse con bloques distintos: el dataset
            # oficial escribe `{title:'The Matrix'}` al principio y
            # `{title:"The Devil's Advocate", released:1997, tagline:'...'}`
            # despues. Es UN nodo. Se identifica por la clave de merge (la
            # primera propiedad del bloque), no por el bloque entero.
            primera = next(iter(props)) if props else None
            clave = (etiqueta, primera, str(props.get(primera)))
            if clave in vistos_merge:
                indice = vistos_merge[clave]
                # Se completa el nodo con las propiedades que aporte esta
                # aparicion y no tuviera aun.
                for k, v in props.items():
                    por_etiqueta[etiqueta][indice].setdefault(k, v)
                if m.group(1):
                    variables[m.group(1)] = etiqueta
                continue
            vistos_merge[clave] = len(por_etiqueta.get(etiqueta, []))
        por_etiqueta.setdefault(etiqueta, []).append(props)
        if m.group(1):
            variables[m.group(1)] = etiqueta
    # Propiedades declaradas con ON CREATE SET, aplicadas a su nodo.
    for m in _RE_ON_CREATE.finditer(texto):
        for am in _RE_ASIGNACION.finditer(m.group(1)):
            variable, prop, valor = am.group(1), am.group(2), am.group(3)
            etiqueta = variables.get(variable)
            if not etiqueta or etiqueta not in por_etiqueta:
                continue
            crudo = valor.strip()
            if crudo[:1] in "\"'" and crudo[-1:] == crudo[:1]:
                crudo = crudo[1:-1]
            elif crudo.startswith("["):
                crudo = [v.strip().strip("\"'") for v in crudo[1:-1].split(",") if v.strip()]
            else:
                crudo = _castea(crudo)
            # La propiedad se asigna al nodo de esa variable: el ultimo nodo
            # creado con esa variable es el que el SET describe.
            for reg in reversed(por_etiqueta[etiqueta]):
                if prop not in reg:
                    reg[prop] = crudo
                    break
    for m in _RE_RELACION.finditer(texto):
        if m.group(1):
            relaciones.append(m.group(1))
    if not por_etiqueta:
        raise ErrorDeteccion(
            "no se encontraron nodos en el Cypher; se esperan sentencias del tipo "
            "CREATE (:Etiqueta {propiedad: valor}) o un JSON de nodos")
    esquema = _esquema_desde_colecciones(por_etiqueta, "neo4j", "sentencias Cypher")
    esquema["relaciones"] = sorted(set(relaciones))
    return esquema


# ------------------------------------------------------------- punto de entrada
def detectar(texto, nombre_archivo="", motor=None):
    """Detecta el motor y la estructura del contenido subido por el usuario.

    Devuelve {motor, formato, colecciones, ...}. Lanza ErrorDeteccion con un
    mensaje util si no reconoce el formato.
    """
    if not texto or not texto.strip():
        raise ErrorDeteccion("el archivo esta vacio")
    nombre = (nombre_archivo or "").lower()
    texto = texto.strip()

    if motor:
        motor = motor.lower()
        if motor == "mongodb":
            return detecta_json(texto, nombre_archivo)
        if motor == "redis":
            return detecta_redis(texto, nombre_archivo)
        if motor == "cassandra":
            if re.search(r"create\s+table", texto, re.I):
                return detecta_cql(texto, nombre_archivo)
            return detecta_csv(texto, nombre_archivo)
        if motor == "neo4j":
            return detecta_cypher(texto, nombre_archivo)

    bajo = texto.lower()
    if re.search(r"create\s+table", bajo):
        return detecta_cql(texto, nombre_archivo)
    if re.search(r"\b(create|merge)\s*\(\s*\w*\s*:", bajo) or "-[:" in texto:
        return detecta_cypher(texto, nombre_archivo)
    if re.search(r"\bhset\b", bajo):
        return detecta_redis(texto, nombre_archivo)
    primera = texto.splitlines()[0]
    if nombre.endswith(".csv") or ("," in primera
                                   and not primera.lstrip().startswith(("{", "["))):
        try:
            return detecta_csv(texto, nombre_archivo)
        except ErrorDeteccion:
            pass
    return detecta_json(texto, nombre_archivo)


def extension_de_motor(motor):
    return tipos.MOTORES.get(motor, {}).get("extension", ".txt")
