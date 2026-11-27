"""nucleo.tipos — sistema de tipos neutral y su traduccion a cada motor NoSQL.

El proyecto no puede trabajar con el vocabulario de un solo motor: MongoDB habla
de ObjectId y Decimal128, Cassandra de text y bigint, Redis de nada (todo es
binario) y Neo4j de Point y DateTime. Por eso existe un **tipo neutral**: el
esquema se declara una vez en el vocabulario neutral y cada adaptador lo traduce
a su motor.

Aqui vive esa traduccion. Es la unica fuente de verdad de los mapeos: el
adaptador de MongoDB, el de Cassandra y el generador de DDL leen de estas tablas,
de modo que la documentacion y el codigo no pueden divergir.
"""

# ---------------------------------------------------------------- tipos neutrales
# (nombre, etiqueta para la interfaz, familia)
TIPOS_NEUTRALES = [
    ("objectid", "Identificador (ObjectId)", "identificador"),
    ("uuid", "UUID", "identificador"),
    ("texto", "Texto", "texto"),
    ("texto_largo", "Texto largo", "texto"),
    ("email", "Correo", "texto"),
    ("telefono", "Telefono", "texto"),
    ("url", "URL", "texto"),
    ("dni", "Documento de identidad", "texto"),
    ("entero", "Entero (32 bits)", "numerico"),
    ("largo", "Entero largo (64 bits)", "numerico"),
    ("decimal", "Decimal exacto", "numerico"),
    ("flotante", "Flotante", "numerico"),
    ("booleano", "Booleano", "logico"),
    ("fecha", "Fecha", "temporal"),
    ("fecha_hora", "Fecha y hora", "temporal"),
    ("hora", "Hora", "temporal"),
    ("timestamp", "Marca de tiempo (epoch)", "temporal"),
    ("enum", "Dominio cerrado", "texto"),
    ("lista", "Lista / arreglo", "coleccion"),
    ("mapa", "Documento anidado / mapa", "coleccion"),
    ("binario", "Binario", "especial"),
    ("geo", "Coordenada geografica", "especial"),
    ("inet", "Direccion IP", "especial"),
]

NEUTRALES = {nombre: etiqueta for nombre, etiqueta, _ in TIPOS_NEUTRALES}
FAMILIA = {nombre: familia for nombre, _, familia in TIPOS_NEUTRALES}

# Tipos que el generador sabe rellenar sin mas contexto que el tipo.
GENERABLES = {
    "objectid", "uuid", "texto", "texto_largo", "email", "telefono", "url", "dni",
    "entero", "largo", "decimal", "flotante", "booleano", "fecha", "fecha_hora",
    "hora", "timestamp", "enum", "inet", "geo",
}

# ------------------------------------------------------------ mapeo por motor
# Cada motor declara: el tipo nativo, si el generador debe serializar el valor a
# texto (Redis) y la nota que se muestra en la interfaz.
MONGODB = {
    "objectid": ("ObjectId", False, "BSON ObjectId de 12 bytes"),
    "uuid": ("BinData (subtype 4)", False, "UUID almacenado como BinData"),
    "texto": ("string", False, "Cadena UTF-8"),
    "texto_largo": ("string", False, "Cadena UTF-8"),
    "email": ("string", False, "Sin tipo dedicado: cadena validada"),
    "telefono": ("string", False, "Sin tipo dedicado: cadena"),
    "url": ("string", False, "Sin tipo dedicado: cadena"),
    "dni": ("string", False, "Sin tipo dedicado: cadena"),
    "entero": ("int", False, "Entero de 32 bits"),
    "largo": ("long", False, "Entero de 64 bits"),
    "decimal": ("Decimal128", False, "Decimal de 128 bits, sin perdida"),
    "flotante": ("double", False, "Coma flotante de 64 bits"),
    "booleano": ("bool", False, "true / false"),
    "fecha": ("date", False, "BSON Date (milisegundos UTC)"),
    "fecha_hora": ("date", False, "BSON Date (milisegundos UTC)"),
    "hora": ("string", False, "No hay tipo hora: cadena HH:MM:SS"),
    "timestamp": ("timestamp", False, "BSON Timestamp interno"),
    "enum": ("string", False, "Cadena restringida al dominio"),
    "lista": ("array", False, "Arreglo de valores"),
    "mapa": ("object", False, "Documento embebido"),
    "binario": ("binData", False, "BinData genérico"),
    "geo": ("GeoJSON point", False, "Objeto GeoJSON con type y coordinates"),
    "inet": ("string", False, "Sin tipo dedicado: cadena"),
}

REDIS = {
    "objectid": ("string", True, "Redis no tiene tipos: se guarda el hex"),
    "uuid": ("string", True, "Cadena"),
    "texto": ("string", True, "Cadena"),
    "texto_largo": ("string", True, "Cadena"),
    "email": ("string", True, "Cadena"),
    "telefono": ("string", True, "Cadena"),
    "url": ("string", True, "Cadena"),
    "dni": ("string", True, "Cadena"),
    "entero": ("string", True, "Numero serializado como cadena"),
    "largo": ("string", True, "Numero serializado como cadena"),
    "decimal": ("string", True, "Numero serializado como cadena"),
    "flotante": ("string", True, "Numero serializado como cadena"),
    "booleano": ("string", True, "1 / 0"),
    "fecha": ("string", True, "ISO-8601"),
    "fecha_hora": ("string", True, "ISO-8601"),
    "hora": ("string", True, "HH:MM:SS"),
    "timestamp": ("string", True, "Segundos epoch como cadena"),
    "enum": ("string", True, "Cadena del dominio"),
    "lista": ("string (JSON)", True, "Arreglo serializado a JSON"),
    "mapa": ("string (JSON)", True, "Objeto serializado a JSON"),
    "binario": ("string (base64)", True, "Binario codificado en base64"),
    "geo": ("string (JSON)", True, "GeoJSON serializado"),
    "inet": ("string", True, "Cadena"),
}

CASSANDRA = {
    "objectid": ("uuid", False, "Cassandra no tiene ObjectId: se usa uuid"),
    "uuid": ("uuid", False, "Tipo uuid nativo"),
    "texto": ("text", False, "Cadena UTF-8"),
    "texto_largo": ("text", False, "Cadena UTF-8"),
    "email": ("text", False, "Sin tipo dedicado"),
    "telefono": ("text", False, "Sin tipo dedicado"),
    "url": ("text", False, "Sin tipo dedicado"),
    "dni": ("text", False, "Sin tipo dedicado"),
    "entero": ("int", False, "Entero de 32 bits"),
    "largo": ("bigint", False, "Entero de 64 bits"),
    "decimal": ("decimal", False, "Decimal de precision variable"),
    "flotante": ("double", False, "Doble precision"),
    "booleano": ("boolean", False, "true / false"),
    "fecha": ("date", False, "Dia sin hora"),
    "fecha_hora": ("timestamp", False, "Instante en milisegundos"),
    "hora": ("time", False, "Hora sin fecha, precision de nanosegundos"),
    "timestamp": ("timestamp", False, "Instante en milisegundos"),
    "enum": ("text", False, "Cadena restringida al dominio"),
    "lista": ("list<text>", False, "Coleccion de texto"),
    "mapa": ("map<text, text>", False, "Mapa de texto a texto"),
    "binario": ("blob", False, "Binario nativo"),
    "geo": ("text", False, "Sin tipo geografico nativo: GeoJSON como texto"),
    "inet": ("inet", False, "IPv4 o IPv6 nativo"),
}

NEO4J = {
    "objectid": ("String", False, "Neo4j no tiene ObjectId: se guarda el hex"),
    "uuid": ("String", False, "Sin tipo uuid nativo"),
    "texto": ("String", False, "Cadena"),
    "texto_largo": ("String", False, "Cadena"),
    "email": ("String", False, "Sin tipo dedicado"),
    "telefono": ("String", False, "Sin tipo dedicado"),
    "url": ("String", False, "Sin tipo dedicado"),
    "dni": ("String", False, "Sin tipo dedicado"),
    "entero": ("Integer", False, "Entero de 64 bits"),
    "largo": ("Integer", False, "Entero de 64 bits"),
    "decimal": ("Float", False, "No hay decimal exacto: coma flotante"),
    "flotante": ("Float", False, "Coma flotante"),
    "booleano": ("Boolean", False, "true / false"),
    "fecha": ("Date", False, "Fecha sin hora"),
    "fecha_hora": ("DateTime", False, "Instante con zona"),
    "hora": ("Time", False, "Hora con desplazamiento"),
    "timestamp": ("Integer", False, "Segundos epoch"),
    "enum": ("String", False, "Cadena restringida al dominio"),
    "lista": ("List", False, "Lista de valores"),
    "mapa": ("Map", False, "Mapa de propiedades"),
    "binario": ("String (base64)", False, "Sin binario nativo: base64"),
    "geo": ("Point", False, "Punto cartesiano o geografico (WGS-84)"),
    "inet": ("String", False, "Sin tipo de red nativo"),
}

MOTORES = {
    "mongodb": {
        "nombre": "mongodb",
        "titulo": "MongoDB",
        "familia": "documental",
        "mapa": MONGODB,
        "extension": ".json",
        "unidad": "coleccion",
        "unidad_plural": "colecciones",
        "unidad_fila": "documento",
        "unidad_fila_plural": "documentos",
        "drivers": "pymongo",
        "descripcion": ("Base documental: cada registro es un documento BSON con "
                        "esquema flexible dentro de una coleccion."),
        "ejemplo_esquema": "_id, nombre, fecha_alta",
    },
    "redis": {
        "nombre": "redis",
        "titulo": "Redis",
        "familia": "clave-valor",
        "mapa": REDIS,
        "extension": ".redis",
        "unidad": "espacio de claves",
        "unidad_plural": "espacios de claves",
        "unidad_fila": "clave (hash)",
        "unidad_fila_plural": "claves (hash)",
        "drivers": "redis",
        "descripcion": ("Almacen clave-valor en memoria: cada registro es un hash "
                        "bajo una clave; todo valor viaja como cadena."),
        "ejemplo_esquema": "usuario:1001 -> {nombre, fecha_alta}",
    },
    "cassandra": {
        "nombre": "cassandra",
        "titulo": "Cassandra",
        "familia": "columnar",
        "mapa": CASSANDRA,
        "extension": ".cql",
        "unidad": "tabla",
        "unidad_plural": "tablas",
        "unidad_fila": "fila",
        "unidad_fila_plural": "filas",
        "drivers": "cassandra-driver",
        "descripcion": ("Base columnar: los datos se organizan en tablas por clave "
                        "de particion, pensadas para escritura masiva."),
        "ejemplo_esquema": "usuario (id uuid PRIMARY KEY, nombre text)",
    },
    "neo4j": {
        "nombre": "neo4j",
        "titulo": "Neo4j",
        "familia": "grafos",
        "mapa": NEO4J,
        "extension": ".cypher",
        "unidad": "etiqueta de nodo",
        "unidad_plural": "etiquetas de nodo",
        "unidad_fila": "nodo",
        "unidad_fila_plural": "nodos",
        "drivers": "neo4j",
        "descripcion": ("Base de grafos: cada registro es un nodo con etiqueta y "
                        "propiedades, unido a otros nodos por relaciones."),
        "ejemplo_esquema": "(:Usuario {nombre, fecha_alta})",
    },
}

ORDEN_MOTORES = ["mongodb", "redis", "cassandra", "neo4j"]


def nativo(tipo_neutral, motor):
    """Tipo nativo del motor para un tipo neutral; devuelve None si no existe."""
    mapa = MOTORES.get(motor, {}).get("mapa", {})
    entrada = mapa.get(tipo_neutral)
    return entrada[0] if entrada else None


def serializa_a_texto(tipo_neutral, motor):
    """True si el motor guarda el valor como cadena (caso de Redis)."""
    mapa = MOTORES.get(motor, {}).get("mapa", {})
    entrada = mapa.get(tipo_neutral)
    return bool(entrada[1]) if entrada else False


def nota(tipo_neutral, motor):
    """Explicacion del mapeo, para mostrarla en la interfaz."""
    mapa = MOTORES.get(motor, {}).get("mapa", {})
    entrada = mapa.get(tipo_neutral)
    return entrada[2] if entrada else ""


def _entrada(tipo_neutral, motor):
    return MOTORES.get(motor, {}).get("mapa", {}).get(tipo_neutral)


def es_aproximado(tipo_neutral, motor):
    """True si el motor no tiene un tipo nativo y guarda el valor como texto.

    Es la diferencia entre "Cassandra tiene un tipo uuid" y "Neo4j no tiene
    uuid y lo guarda como String": ambas son compatibles, pero solo la primera
    es nativa, y la interfaz debe poder decirlo.
    """
    entrada = _entrada(tipo_neutral, motor)
    if not entrada:
        return True
    nativo_ = entrada[0].lower()
    return nativo_.startswith(("string", "text", "varchar")) and tipo_neutral not in (
        "texto", "texto_largo", "email", "telefono", "url", "dni", "enum")


def compatibilidad(motor):
    """Cobertura del sistema de tipos neutral para un motor.

    Distingue los tipos que el motor guarda de forma nativa de los que tiene que
    aproximar (normalmente a texto). La cobertura es la fraccion de tipos
    neutrales que el motor almacena sin aproximar.
    """
    mapa = MOTORES[motor]["mapa"]
    nativos, aproximados = 0, []
    for tipo, _, _ in TIPOS_NEUTRALES:
        if tipo not in mapa:
            aproximados.append((tipo, "-"))
        elif es_aproximado(tipo, motor):
            aproximados.append((tipo, mapa[tipo][0]))
        else:
            nativos += 1
    return {
        "motor": motor,
        "tipos_cubiertos": len(mapa),
        "tipos_totales": len(TIPOS_NEUTRALES),
        "tipos_nativos": nativos,
        "tipos_aproximados": len(aproximados),
        "cobertura": nativos / len(TIPOS_NEUTRALES),
        "aproximados": aproximados,
    }


def tabla_compatibilidad():
    """Matriz tipo neutral x motor, que es lo que se publica en la interfaz."""
    filas = []
    for tipo, etiqueta, familia in TIPOS_NEUTRALES:
        fila = {"tipo": tipo, "etiqueta": etiqueta, "familia": familia}
        for motor in ORDEN_MOTORES:
            fila[motor] = nativo(tipo, motor) or "-"
            fila[motor + "_aproximado"] = es_aproximado(tipo, motor)
        filas.append(fila)
    return filas
