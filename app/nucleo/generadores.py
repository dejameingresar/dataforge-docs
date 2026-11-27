"""nucleo.generadores — catalogo de valores sinteticos por tipo neutral.

Sin dependencias externas: todo se construye con `random` y `datetime`, de modo
que la aplicacion corre con Python 3 sin instalar nada y el lote es reproducible
a partir de la semilla.

Cada generador tiene la firma `f(rng, campo) -> valor` y devuelve el valor en su
tipo Python natural. La traduccion al tipo nativo del motor es responsabilidad
del adaptador, no de aqui.
"""

import datetime as dt
import random
import re
import uuid as _uuid

# ------------------------------------------------------------------ catalogos
# Los catalogos son deliberadamente mas grandes que los volumenes por defecto:
# una columna UNIQUE alimentada por un catalogo finito no puede superar el numero
# de elementos de ese catalogo.
NOMBRES = [
    "Luis", "Carlos", "Jose", "Juan", "Miguel", "Angel", "Jorge", "Marco", "Fernando",
    "Rodrigo", "Diego", "Cesar", "Christian", "Ricardo", "Sergio", "Andres", "Gustavo",
    "Eduardo", "Raul", "Renzo", "Aldo", "Piero", "Kevin", "Oscar", "Martin", "Daniel",
    "Gabriel", "Leonardo", "Salvador", "Gonzalo", "Hector", "Ivan", "Jaime", "Wilson",
    "Maria", "Ana", "Rosa", "Elena", "Katherine", "Nicole", "Claudia", "Cecilia",
    "Milagros", "Yolanda", "Andrea", "Pamela", "Gabriela", "Sofia", "Daniela", "Fernanda",
    "Karina", "Lourdes", "Jazmin", "Silvia", "Mercedes", "Martha", "Ruth", "Adriana",
    "Patricia", "Veronica", "Marisol", "Debora", "Sandy", "Perla", "Ariana", "Lesly",
    "Rocio", "Yordy", "Romulo", "Efrain", "Aurelio", "Wilfredo", "Yomar", "Apolo",
    "Ximena", "Valeria", "Camila", "Renata", "Antonella", "Bruno", "Fabrizio", "Matias",
]
APELLIDOS = [
    "Rodriguez", "Cardenas", "Quispe", "Mamani", "Ccahuana", "Condori", "Flores",
    "Chavez", "Rojas", "Torres", "Vargas", "Ramos", "Garcia", "Apaza", "Huaman",
    "Alarcon", "Medina", "Ayala", "Rios", "Velasquez", "Arenas", "Paredes", "Choque",
    "Zeballos", "Pinto", "Benavides", "Tapia", "Huisa", "Challco", "Cutipa", "Zevallos",
    "Gutierrez", "Justiniano", "Coila", "Yujra", "Cahuari", "Chipana", "Morales",
    "Bernal", "Zambrano", "Ramirez", "Loayza", "Borda", "Diaz", "Salas", "Huaylla",
    "Soncco", "Yaipata", "Valdivia", "Carpio", "Nina", "Anco", "Lipa", "Chura",
]
CIUDADES = [
    "Tacna", "Arequipa", "Lima", "Trujillo", "Cusco", "Piura", "Chiclayo", "Iquique",
    "Puno", "Moquegua", "Ilo", "Ica", "Huancayo", "Cajamarca", "Pucallpa", "Tarapoto",
]
PAISES = ["Peru", "Chile", "Bolivia", "Colombia", "Ecuador", "Argentina", "Brasil", "Mexico"]
CALLES = [
    "Av. Bolognesi", "Jr. San Martin", "Av. 28 de Julio", "Jr. Miguel Grau",
    "Av. Leguia", "Jr. La Marina", "Av. Coronel Mercado", "Jr. Zela", "Jr. Reycende",
    "Jr. Loreto", "Av. Almirante Grau", "Jr. San Agustin", "Av. Iberia", "Av. La Paz",
]
DOMINIOS = ["dataforge.pe", "ejemplo.com", "corp.pe", "mail.com", "empresa.pe"]
EMPRESAS = [
    "Andes Trading", "Comercial del Sur", "Inversiones Tacna", "Grupo Altiplano",
    "Distribuidora Pacifico", "Tecnologia Andina", "Servicios Integrales Lima",
    "Constructora Vial", "Agroindustria Sur", "Logistica Nacional", "Retail Express",
    "Consultora Delta", "Minera del Centro", "Pesquera Norte", "Textiles Arequipa",
]
PRODUCTOS = [
    "Laptop 14 pulgadas", "Monitor 24 pulgadas", "Teclado mecanico", "Mouse inalambrico",
    "Impresora laser", "Disco SSD 1 TB", "Memoria USB 64 GB", "Router wifi",
    "Camara web HD", "Audifonos bluetooth", "Silla ergonomica", "Escritorio modular",
    "Lampara LED", "Tablet 10 pulgadas", "Telefono IP", "Proyector portatil",
    "Cargador rapido", "Base refrigerante", "Cable HDMI", "Hub USB-C",
]
CATEGORIAS = [
    "Computo", "Perifericos", "Almacenamiento", "Redes", "Audio", "Mobiliario",
    "Iluminacion", "Accesorios", "Imagen", "Energia",
]
ESTADOS_PEDIDO = ["PENDIENTE", "CONFIRMADO", "ENVIADO", "ENTREGADO", "CANCELADO", "DEVUELTO"]
MONEDAS = ["PEN", "USD", "CLP", "BOB", "EUR"]
TITULOS = [
    "Guia de instalacion", "Manual de usuario", "Politica de privacidad",
    "Terminos del servicio", "Reporte mensual", "Acta de reunion",
    "Plan de mantenimiento", "Instructivo de seguridad", "Ficha tecnica",
    "Contrato de servicio",
]
FRASES = [
    "Registro generado para pruebas de carga y validacion de consultas.",
    "Dato sintetico reproducible a partir de la semilla configurada.",
    "Contenido de ejemplo sin correspondencia con informacion real.",
    "Pertenece al lote de prueba y puede descartarse sin riesgo.",
    "Se usa para verificar indices, agregaciones y filtros del motor.",
    "Valor de relleno para completar un conjunto incompleto.",
]
ESTADOS_GENERICOS = ["ACTIVO", "INACTIVO", "SUSPENDIDO", "PENDIENTE", "CERRADO"]
TIPOS_DOC = ["DNI", "RUC", "CE", "PASAPORTE"]


# ------------------------------------------------------------------ utilidades
def _fecha_aleatoria(rng, ini, fin):
    dias = (fin - ini).days
    return ini + dt.timedelta(days=rng.randint(0, dias))


def _slug(texto):
    mapa = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    limpio = str(texto).translate(mapa).lower()
    limpio = "".join(c if (c.isalnum() or c == " ") else " " for c in limpio)
    return " ".join(limpio.split()) or "valor"


def email_de_nombre(nombre, rng, dominios=None):
    """Correo coherente con el nombre de la propia fila.

    Sin esto el generador produce "Yolanda" con el correo "cesar.cahuari8816":
    el dato existe pero es incoherente consigo mismo.
    """
    partes = _slug(nombre).split()
    if len(partes) >= 2:
        base = f"{partes[0]}.{partes[-1]}"
    elif partes:
        base = partes[0]
    else:
        base = "usuario"
    base = re.sub(r"[^a-z0-9.]", "", base)[:40]
    return f"{base}{rng.randint(1, 999)}@{rng.choice(dominios or DOMINIOS)}"


# ------------------------------------------------------ generadores semanticos
# Un campo puede declarar `generador` para pedir un valor con significado en vez
# de uno generico del tipo. Estos son los disponibles.
def nombre_persona(rng, _campo):
    return rng.choice(NOMBRES)


def apellido(rng, _campo):
    return rng.choice(APELLIDOS)


def nombre_completo(rng, _campo):
    return f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)}"


def empresa(rng, _campo):
    return rng.choice(EMPRESAS)


def ciudad(rng, _campo):
    return rng.choice(CIUDADES)


def pais(rng, _campo):
    return rng.choice(PAISES)


def direccion(rng, _campo):
    return f"{rng.choice(CALLES)} {rng.randint(100, 1999)}, {rng.choice(CIUDADES)}"


def producto(rng, _campo):
    return rng.choice(PRODUCTOS)


def categoria(rng, _campo):
    return rng.choice(CATEGORIAS)


def titulo(rng, _campo):
    return rng.choice(TITULOS)


def descripcion(rng, _campo):
    return rng.choice(FRASES)


def estado_pedido(rng, _campo):
    return rng.choice(ESTADOS_PEDIDO)


def estado_generico(rng, _campo):
    return rng.choice(ESTADOS_GENERICOS)


def moneda(rng, _campo):
    return rng.choice(MONEDAS)


def sku(rng, _campo):
    return f"SKU-{rng.randint(10000, 99999)}"


def codigo(rng, _campo):
    prefijo = _campo.get("prefijo", "COD")
    return f"{prefijo}-{rng.randint(10000, 99999)}"


def tipo_documento(rng, _campo):
    return rng.choice(TIPOS_DOC)


def anio(rng, campo):
    """Un anio plausible: 1900..2035 por defecto, o el rango observado si cabe.

    Un campo `deadpooled_year` tiene rango observado 1..2013, y muestrear ese
    rango a ciegas produce un anio 1123. Un anio se genera como anio.
    """
    lo = int(campo.get("min") or 1980)
    hi = int(campo.get("max") or 2030)
    # Se acota a una ventana creible de anios, ampliandola si el observado la
    # excede (un catalogo puede tener anios del siglo XIX).
    lo = max(lo, 1800) if lo >= 1000 else 1980
    hi = min(max(hi, lo), 2100)
    return rng.randint(lo, hi)


def mes(rng, _campo):
    return rng.randint(1, 12)


def dia(rng, _campo):
    return rng.randint(1, 28)


def cantidad(rng, _campo):
    return rng.randint(int(_campo.get("min") or 1), int(_campo.get("max") or 100))


# --------------------------------------------------------- generadores por tipo
def _objectid(rng, _campo):
    """24 caracteres hexadecimales, el formato del ObjectId de MongoDB."""
    return "".join(rng.choice("0123456789abcdef") for _ in range(24))


def _uuid4(rng, _campo):
    # uuid4 con el azar del generador: reproducible dada la semilla. El nombre
    # lleva el sufijo para no tapar el modulo `uuid` importado arriba.
    return str(_uuid.UUID(int=rng.getrandbits(128), version=4))


def _texto(rng, _campo):
    n = int(_campo.get("largo", 20))
    silabas = ["pa", "re", "mi", "to", "la", "su", "co", "de", "na", "vi",
               "tra", "que", "za", "bo", "lu", "fi", "gen", "ra"]
    piezas, total = [], 0
    while total < max(4, n):
        pieza = rng.choice(silabas)
        piezas.append(pieza)
        total += len(pieza)
    return "".join(piezas)[:max(4, n)].capitalize()


def _texto_largo(rng, _campo):
    return " ".join(rng.choice(FRASES) for _ in range(rng.randint(2, 4)))


def _email(rng, _campo):
    usuario = f"{rng.choice(NOMBRES).lower()}.{rng.choice(APELLIDOS).lower()}"
    return f"{usuario}{rng.randint(1, 9999)}@{rng.choice(DOMINIOS)}"


def _telefono(rng, _campo):
    return f"+51 9{rng.randint(10_000_000, 99_999_999)}"


def _url(rng, _campo):
    return f"https://{_slug(rng.choice(EMPRESAS)).replace(' ', '-')}.pe/{_slug(rng.choice(CATEGORIAS))}"


def _dni(rng, _campo):
    """DNI peruano: RENIEC registra 8 digitos, sin digito verificador impreso."""
    return f"{rng.randint(10_000_000, 99_999_999)}"


def _entero(rng, _campo):
    return rng.randint(int(_campo.get("min", 1)), int(_campo.get("max", 10_000)))


def _largo(rng, _campo):
    return rng.randint(int(_campo.get("min", 1)), int(_campo.get("max", 10_000_000)))


def _decimal(rng, _campo):
    minimo = float(_campo.get("min", 1.0))
    maximo = float(_campo.get("max", 5000.0))
    return round(rng.uniform(minimo, maximo), int(_campo.get("escala", 2)))


def _flotante(rng, _campo):
    minimo = float(_campo.get("min", 0.0))
    maximo = float(_campo.get("max", 1.0))
    return round(rng.uniform(minimo, maximo), 6)


def _booleano(rng, _campo):
    return rng.random() < float(_campo.get("probabilidad", 0.75))


def _fecha(rng, _campo):
    return _fecha_aleatoria(rng, dt.date(2015, 1, 1), dt.date(2026, 12, 31))


def _fecha_hora(rng, _campo):
    d = _fecha_aleatoria(rng, dt.date(2015, 1, 1), dt.date(2026, 12, 31))
    return dt.datetime(d.year, d.month, d.day, rng.randint(0, 23), rng.randint(0, 59),
                       rng.randint(0, 59))


def _hora(rng, _campo):
    return dt.time(rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59))


def _timestamp(rng, _campo):
    d = _fecha_aleatoria(rng, dt.date(2015, 1, 1), dt.date(2026, 12, 31))
    return int(dt.datetime(d.year, d.month, d.day,
                           rng.randint(0, 23), rng.randint(0, 59)).timestamp())


def _inet(rng, _campo):
    return f"{rng.randint(10, 250)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def _geo(rng, _campo):
    # Tacna como centro, con dispersion de unos kilometros.
    return {"type": "Point",
            "coordinates": [round(-70.25 + rng.uniform(-0.2, 0.2), 6),
                            round(-17.99 + rng.uniform(-0.2, 0.2), 6)]}


def _binario(rng, _campo):
    n = int(_campo.get("bytes", 16))
    return bytes(rng.getrandbits(8) for _ in range(n))


GENERADORES = {
    "objectid": _objectid,
    "uuid": _uuid4,
    "texto": _texto,
    "texto_largo": _texto_largo,
    "email": _email,
    "telefono": _telefono,
    "url": _url,
    "dni": _dni,
    "entero": _entero,
    "largo": _largo,
    "decimal": _decimal,
    "flotante": _flotante,
    "booleano": _booleano,
    "fecha": _fecha,
    "fecha_hora": _fecha_hora,
    "hora": _hora,
    "timestamp": _timestamp,
    "inet": _inet,
    "geo": _geo,
    "binario": _binario,
}

SEMANTICOS = {
    "nombre_persona": nombre_persona,
    "apellido": apellido,
    "nombre_completo": nombre_completo,
    "empresa": empresa,
    "ciudad": ciudad,
    "pais": pais,
    "direccion": direccion,
    "producto": producto,
    "categoria": categoria,
    "titulo": titulo,
    "descripcion": descripcion,
    "estado_pedido": estado_pedido,
    "estado_generico": estado_generico,
    "moneda": moneda,
    "sku": sku,
    "codigo": codigo,
    "tipo_documento": tipo_documento,
    "anio": anio,
    "mes": mes,
    "dia": dia,
    "cantidad": cantidad,
}

# Nombres de campo que sugieren un generador semantico. La deteccion los usa
# para proponer un valor con sentido en vez de texto generico.
PISTAS = [
    (re.compile(r"^(email|correo|mail)", re.I), "email", "email"),
    (re.compile(r"^(telefono|celular|phone|movil)", re.I), "telefono", "telefono"),
    (re.compile(r"^(dni|ruc|documento|cedula|identificacion)", re.I), "dni", "dni"),
    (re.compile(r"^(url|enlace|link|sitio|web)", re.I), "url", "url"),
    (re.compile(r"^(nombre_completo|nombres_apellidos|full_name)", re.I), "nombre_completo", "nombre_completo"),
    (re.compile(r"^(nombre|nombres|first_name|given_name)", re.I), "nombre_persona", "nombre_persona"),
    (re.compile(r"^(apellido|apellidos|last_name|surname)", re.I), "apellido", "apellido"),
    (re.compile(r"^(empresa|compania|company|razon_social)", re.I), "empresa", "empresa"),
    (re.compile(r"^(ciudad|distrito|localidad|city)", re.I), "ciudad", "ciudad"),
    (re.compile(r"^(pais|country)", re.I), "pais", "pais"),
    (re.compile(r"^(direccion|domicilio|address)", re.I), "direccion", "direccion"),
    (re.compile(r"^(producto|articulo|item|nombre_producto)", re.I), "producto", "producto"),
    (re.compile(r"^(categoria|rubro|categoria_nombre)", re.I), "categoria", "categoria"),
    (re.compile(r"^(titulo|title|asunto|encabezado)", re.I), "titulo", "titulo"),
    (re.compile(r"^(descripcion|detalle|observacion|comentario|nota)", re.I), "descripcion", "descripcion"),
    (re.compile(r"^(estado|status|situacion)", re.I), "estado_generico", "estado_generico"),
    (re.compile(r"^(moneda|currency|divisa)", re.I), "moneda", "moneda"),
    (re.compile(r"^(sku|codigo_barras|barcode)", re.I), "sku", "sku"),
    # Numeros de documento: un "numero" de pedido es un codigo con prefijo, no
    # texto libre.
    (re.compile(r"^(numero|nro|num_|folio|referencia|ref_|codigo|code|factura|"
                r"guia|orden|boleta|comprobante|expediente|ticket)", re.I),
     "texto", "codigo"),
    # Componentes de una fecha por separado: un `founded_year` es un anio, no un
    # entero cualquiera (el rango observado de deadpooled_year llega a 1).
    (re.compile(r"(_year|_anio|^anio$|^year$|_yr$)", re.I), "entero", "anio"),
    (re.compile(r"(_month|_mes|^mes$|^month$)", re.I), "entero", "mes"),
    (re.compile(r"(_day|_dia|^dia$|^day$)", re.I), "entero", "dia"),
    # Un `id` guardado como texto cuyos valores son todos numericos (el caso de
    # Redis, donde todo es cadena) debe generarse como numero, no como texto: un
    # identificador "1001" se espera "1003", no "Fige".
    (re.compile(r"^(id|_id|identificador|numero_id|id_\w+)$", re.I), "entero", None),
]


def pista_semantica(nombre_campo):
    """Sugiere (tipo_neutral, generador) a partir del nombre del campo, o None.

    Un generador None significa que solo se propone el tipo, sin un generador
    semantico (el generico del tipo sirve).
    """
    for patron, tipo, generador in PISTAS:
        if patron.search(str(nombre_campo)):
            return tipo, generador
    return None


def generar_valor(rng, campo):
    """Valor para un campo del esquema neutral, segun su tipo y generador."""
    tipo = campo.get("tipo", "texto")
    generador = campo.get("generador")
    if generador and generador in SEMANTICOS:
        return SEMANTICOS[generador](rng, campo)
    if tipo == "enum":
        opciones = campo.get("enum") or ESTADOS_GENERICOS
        return rng.choice(opciones)
    if tipo == "lista":
        elemento = campo.get("elemento", "texto")
        n = int(campo.get("n_elementos", rng.randint(1, 4)))
        sub = {"tipo": elemento, "enum": campo.get("enum_elemento")}
        return [generar_valor(rng, sub) for _ in range(n)]
    if tipo == "mapa":
        subcampos = campo.get("campos") or []
        if subcampos:
            return {c["nombre"]: generar_valor(rng, c) for c in subcampos}
        clave_t, valor_t = campo.get("clave", "texto"), campo.get("valor", "texto")
        return {generar_valor(rng, {"tipo": clave_t}): generar_valor(rng, {"tipo": valor_t})
                for _ in range(int(campo.get("n_pares", 2)))}
    fn = GENERADORES.get(tipo)
    if fn is None:
        return None
    return fn(rng, campo)
