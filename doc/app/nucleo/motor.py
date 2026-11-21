"""nucleo.motor — genera los datos que faltan para completar la base del usuario.

Responsabilidades:

  1. tomar la estructura detectada (nucleo.detector) y generar los registros que
     faltan hasta el volumen pedido, respetando tipos, dominios, claves y
     relaciones;
  2. ser determinista: la misma semilla produce exactamente el mismo lote, de
     modo que un error se puede reproducir;
  3. medir la calidad del resultado (completitud, unicidad, dominios, integridad
     referencial), que es la evidencia de los objetivos medibles.

No depende de ningun motor: produce estructuras de datos en memoria y quien las
serializa es el adaptador correspondiente (nucleo.adaptadores).
"""

import random

from . import tipos
from .generadores import GENERADORES, email_de_nombre, generar_valor

# Tipos neutrales que el generador sabe rellenar: los que tienen un generador
# propio mas los compuestos, que se construyen a partir de otros.
GENERABLES_DISPONIBLES = set(GENERADORES) | {"enum", "lista", "mapa"}

# Un correo debe pertenecer a la misma fila que el nombre: se resuelve al final,
# cuando la fila ya esta completa, en vez de sortearlo por separado.
_RE_EMAIL_DERIVABLE = ("email", "correo", "mail")


def _es_campo_email(nombre, campo):
    if campo.get("generador") == "email" or campo.get("tipo") == "email":
        return True
    return any(str(nombre).lower().startswith(p) for p in _RE_EMAIL_DERIVABLE)


def _nombre_de_la_fila(registro):
    """Nombre con el que derivar el correo, si la fila tiene uno."""
    for clave in ("nombre", "nombres", "nombre_completo", "razon_social", "empresa"):
        valor = registro.get(clave)
        if isinstance(valor, str) and valor.strip():
            return valor
    return None


class ErrorGeneracion(Exception):
    pass


def _valor_unico(rng, campo, usados, max_intentos=800):
    """Valor que no se repite dentro de su columna unica.

    Si el campo tiene un generador semantico de catalogo finito (un `titulo`,
    una `ciudad`), no hay forma de sacar mas valores distintos de los que tiene
    el catalogo. En ese caso se recurre al generador generico del tipo, que si
    produce valores ilimitados, en vez de rendirse y abortar la generacion.
    """
    for _ in range(max_intentos):
        valor = generar_valor(rng, campo)
        clave = _hashable(valor)
        if clave is None or clave not in usados:
            usados.add(clave)
            return valor
    # El catalogo del generador semantico se agoto: se usa el generico del tipo,
    # que no depende de un catalogo.
    if campo.get("generador"):
        generico = dict(campo)
        generico.pop("generador", None)
        for _ in range(max_intentos):
            valor = generar_valor(rng, generico)
            clave = _hashable(valor)
            if clave is None or clave not in usados:
                usados.add(clave)
                return valor
    raise ErrorGeneracion(
        f"agotados los valores unicos para el campo '{campo['nombre']}': "
        "reduce el volumen o amplia el dominio del generador"
    )


def _hashable(valor):
    """Version comparable de un valor, para poder meterla en un conjunto."""
    if isinstance(valor, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in valor.items()))
    if isinstance(valor, list):
        return tuple(_hashable(v) for v in valor)
    if isinstance(valor, bytes):
        return valor
    return valor


def _coacciona(valor, campo):
    """Ajusta el valor al tipo declarado (el generador ya devuelve el tipo natural)."""
    if valor is None:
        return None
    tipo = campo.get("tipo")
    if tipo in ("entero", "largo", "timestamp"):
        return int(valor)
    if tipo in ("decimal", "flotante"):
        return round(float(valor), int(campo.get("escala", 6)))
    if tipo == "booleano":
        return bool(valor)
    # El texto no se recorta al largo observado: ese largo es lo que medía la
    # muestra, no un limite del campo, y recortarlo destruye valores validos
    # (un "P-1" observado de 3 caracteres convertia "COD-12345" en "COD").
    return valor


class Generador:
    """Completa una estructura detectada con los registros que le faltan."""

    def __init__(self, esquema, semilla=2026, enums=None, campos=None):
        """esquema: salida de nucleo.detector.detectar().

        enums:  dominio sobrescrito por la interfaz {campo: [valores]}.
        campos: ajustes por campo {coleccion: {campo: {...parches...}}}.
        """
        self.esquema = esquema
        self.rng = random.Random(semilla)
        self.semilla = semilla
        self.enums = dict(enums or {})
        self.campos = dict(campos or {})
        self._usados = {}
        # Relaciones que se dejan sin resolver porque su destino forma un ciclo
        # con la coleccion que se esta generando. Se llena al romper el ciclo.
        self._relaciones_omitidas = {}

    # ------------------------------------------------------------ resolucion
    def _campo_efectivo(self, coleccion, campo):
        """Campo con los ajustes que el usuario haya hecho en la interfaz."""
        parche = (self.campos.get(coleccion) or {}).get(campo["nombre"])
        if parche:
            combinado = dict(campo)
            combinado.update(parche)
            return combinado
        return campo

    def _dominio(self, coleccion, campo):
        """Dominio de un enum: el detectado o el que fijo el usuario."""
        clave = f"{coleccion}.{campo['nombre']}"
        if clave in self.enums and self.enums[clave]:
            return list(self.enums[clave])
        if campo["nombre"] in self.enums and self.enums[campo["nombre"]]:
            return list(self.enums[campo["nombre"]])
        return campo.get("enum") or ["ACTIVO"]

    # ------------------------------------------------------------ generacion
    def _genera_registro(self, coleccion, campos, disponibles, claves):
        """Un registro completo y coherente con las claves y relaciones."""
        registro = {}
        for campo in campos:
            nombre = campo["nombre"]
            efectivo = self._campo_efectivo(coleccion, campo)
            # Clave primaria: un valor que no se repita, ni entre los registros
            # nuevos ni contra los que ya existian.
            if campo.get("pk"):
                usados = self._usados.setdefault((coleccion, nombre), set())
                if campo["tipo"] == "entero":
                    n = len(usados) + 1
                    while _hashable(n) in usados:
                        n += 1
                    usados.add(_hashable(n))
                    registro[nombre] = n
                else:
                    registro[nombre] = _valor_unico(self.rng, efectivo, usados)
                continue
            # Relacion (clave foranea) hacia otra coleccion.
            if campo.get("ref"):
                destino = campo["ref"]
                # Si esta relacion es la que forma el ciclo, se deja vacia: su
                # destino todavia no existe y no se puede apuntar a el.
                if nombre in self._relaciones_omitidas.get(coleccion, ()):
                    registro[nombre] = None
                    continue
                valores = disponibles.get(destino) or []
                if not valores:
                    raise ErrorGeneracion(
                        f"no hay registros en '{destino}' para completar la relacion "
                        f"'{coleccion}.{nombre}': genere primero esa coleccion")
                registro[nombre] = self.rng.choice(valores)
                continue
            # Dominio cerrado.
            if efectivo.get("tipo") == "enum" or efectivo.get("enum"):
                opciones = self._dominio(coleccion, efectivo)
                registro[nombre] = self.rng.choice(opciones)
                continue
            # Campo unico: hay que garantizar que no se repita.
            if campo.get("unique"):
                registro[nombre] = _valor_unico(
                    self.rng, efectivo, self._usados.setdefault((coleccion, nombre), set()))
                continue
            registro[nombre] = _coacciona(generar_valor(self.rng, efectivo), efectivo)

        # Coherencia interna: el correo se deriva del nombre de esta misma fila.
        # Si el correo es unico, se insiste hasta dar con uno libre en vez de
        # sortearlo aparte del nombre.
        nombre_fila = _nombre_de_la_fila(registro)
        if nombre_fila:
            for campo in campos:
                nombre_campo = campo["nombre"]
                if not _es_campo_email(nombre_campo, campo) or \
                        not isinstance(registro.get(nombre_campo), str):
                    continue
                if campo.get("unique"):
                    usados = self._usados.setdefault((coleccion, nombre_campo), set())
                    for _ in range(300):
                        candidato = email_de_nombre(nombre_fila, self.rng)
                        if candidato not in usados:
                            usados.add(candidato)
                            registro[nombre_campo] = candidato
                            break
                else:
                    registro[nombre_campo] = email_de_nombre(nombre_fila, self.rng)
        return registro

    def generar_coleccion(self, nombre, n_nuevos, disponibles, existentes=None):
        """Genera n_nuevos registros nuevos para una coleccion."""
        col = self.esquema["colecciones"][nombre]
        campos = [self._campo_efectivo(nombre, c) for c in col["campos"]]
        nuevos = []
        intentos, tope = 0, n_nuevos * 40 + 200
        while len(nuevos) < n_nuevos and intentos < tope:
            intentos += 1
            registro = self._genera_registro(nombre, campos, disponibles, col.get("claves"))
            nuevos.append(registro)
        if len(nuevos) < n_nuevos:
            raise ErrorGeneracion(
                f"{nombre}: solo se pudieron generar {len(nuevos)}/{n_nuevos} registros; "
                "las restricciones son demasiado estrictas para el volumen pedido")
        return nuevos

    def completar(self, volumenes=None):
        """Completa el esquema detectado hasta los volumenes pedidos.

        volumenes: {coleccion: total_deseado}. Si una coleccion ya tiene
        registros observados, solo se generan los que faltan.
        Devuelve {coleccion: {"existentes": [...], "nuevos": [...], "total": n}}.
        """
        volumenes = dict(volumenes or {})
        resultado = {}
        disponibles = {}
        # Dos pasadas: primero las colecciones que no dependen de nadie, para que
        # las relaciones tengan destino cuando se generen las dependientes.
        pendientes = list(self.esquema["colecciones"])
        resueltas = set()
        while pendientes:
            progreso = False
            for nombre in list(pendientes):
                col = self.esquema["colecciones"][nombre]
                refs = {c["ref"] for c in col["campos"] if c.get("ref")}
                if refs - resueltas:
                    continue
                resultado[nombre] = self._completa_una(nombre, volumenes.get(nombre),
                                                      disponibles)
                disponibles[nombre] = resultado[nombre]["referencias"]
                resueltas.add(nombre)
                pendientes.remove(nombre)
                progreso = True
            if not progreso:
                # Ciclo de referencias: se rompe generando en orden alfabetico.
                # La coleccion que rompe el ciclo no puede apuntar a las que
                # todavia no se generaron, asi que se marca para que sus
                # relaciones hacia las pendientes se dejen vacias en vez de
                # fallar. Las que apunten hacia atras si se resuelven.
                nombre = sorted(pendientes)[0]
                col = self.esquema["colecciones"][nombre]
                pendientes_set = set(pendientes)
                omitir = {c["nombre"] for c in col["campos"]
                          if c.get("ref") in pendientes_set}
                if omitir:
                    self._relaciones_omitidas[nombre] = omitir
                resultado[nombre] = self._completa_una(nombre, volumenes.get(nombre),
                                                      disponibles)
                disponibles[nombre] = resultado[nombre]["referencias"]
                resueltas.add(nombre)
                pendientes.remove(nombre)
        return resultado

    def _completa_una(self, nombre, total_deseado, disponibles):
        """Genera lo que falta de una coleccion y devuelve el detalle."""
        col = self.esquema["colecciones"][nombre]
        existentes = col.get("muestra") or []
        n_existentes = int(col.get("registros_observados", len(existentes)))
        if total_deseado is None:
            total_deseado = n_existentes
        total_deseado = int(total_deseado)
        n_nuevos = max(0, total_deseado - n_existentes)
        # Los valores de clave que ya existen se reservan ANTES de generar, para
        # que un registro nuevo no repita la clave de uno que ya estaba. Sin
        # esto, una clave entera que empieza en 1 choca con el primer existente.
        campos_pk = [c for c in col["campos"] if c.get("pk")]
        for c in campos_pk:
            usados = self._usados.setdefault((nombre, c["nombre"]), set())
            for reg in existentes:
                valor = reg.get(c["nombre"])
                if valor is not None:
                    usados.add(_hashable(valor))
        nuevos = self.generar_coleccion(nombre, n_nuevos, disponibles, existentes) \
            if n_nuevos else []
        # Valores de clave que las colecciones dependientes podran referenciar:
        # se incluyen los existentes para que una relacion pueda apuntar a ellos.
        referencias = []
        for registro in existentes + nuevos:
            for c in campos_pk:
                if registro.get(c["nombre"]) is not None:
                    referencias.append(registro[c["nombre"]])
        return {
            "coleccion": nombre,
            "existentes": existentes,
            "n_existentes": n_existentes,
            "nuevos": nuevos,
            "n_generados": len(nuevos),
            "total": n_existentes + len(nuevos),
            "referencias": referencias,
        }


# ------------------------------------------------------------------ metricas
def metricas(resultado, esquema):
    """Metricas de calidad del lote completado: evidencia de los objetivos."""
    m = {
        "colecciones": {},
        "totales": {"existentes": 0, "generados": 0, "total": 0,
                    "campos_obligatorios": 0, "campos_vacios": 0},
    }
    for nombre, detalle in resultado.items():
        col = esquema["colecciones"][nombre]
        campos = col["campos"]
        nuevos = detalle["nuevos"]
        n = len(nuevos)
        obligatorios = [c for c in campos if not c.get("nullable", True)]
        vacios = sum(1 for r in nuevos for c in obligatorios
                     if r.get(c["nombre"]) is None)
        total_celdas = n * len(obligatorios)
        unicos_total = unicos_ok = 0
        for c in campos:
            if not (c.get("unique") or c.get("pk")):
                continue
            unicos_total += 1
            valores = [r.get(c["nombre"]) for r in nuevos if r.get(c["nombre"]) is not None]
            if len(set(_hashable(v) for v in valores)) == len(valores):
                unicos_ok += 1
        dominios = {}
        for c in campos:
            if c.get("tipo") != "enum" and not c.get("enum"):
                continue
            opciones = set(c.get("enum") or [])
            valores = [r.get(c["nombre"]) for r in nuevos]
            dominios[c["nombre"]] = {
                "declarado": sorted(opciones),
                "cumple": all(v in opciones for v in valores) if opciones else True,
            }
        m["colecciones"][nombre] = {
            "n_existentes": detalle["n_existentes"],
            "n_generados": n,
            "total": detalle["total"],
            "campos": len(campos),
            "completitud": (1.0 - vacios / total_celdas) if total_celdas else 1.0,
            "unicos_total": unicos_total,
            "unicos_respetados": unicos_ok,
            "dominios": dominios,
        }
        m["totales"]["existentes"] += detalle["n_existentes"]
        m["totales"]["generados"] += n
        m["totales"]["total"] += detalle["total"]
        m["totales"]["campos_obligatorios"] += total_celdas
        m["totales"]["campos_vacios"] += vacios
    t = m["totales"]
    t["completitud"] = (1.0 - t["campos_vacios"] / t["campos_obligatorios"]) \
        if t["campos_obligatorios"] else 1.0
    t["unicos_respetados"] = sum(c["unicos_respetados"] for c in m["colecciones"].values())
    t["unicos_total"] = sum(c["unicos_total"] for c in m["colecciones"].values())
    t["colecciones"] = len(resultado)
    return m


def valida_relaciones(resultado, esquema):
    """Comprueba que ninguna relacion apunte a una clave que no exista."""
    problemas = []
    for nombre, detalle in resultado.items():
        col = esquema["colecciones"][nombre]
        for campo in col["campos"]:
            if not campo.get("ref"):
                continue
            destino = campo["ref"]
            if destino not in resultado:
                problemas.append(
                    f"{nombre}.{campo['nombre']}: la coleccion referenciada "
                    f"'{destino}' no esta en el lote")
                continue
            claves_destino = set(_hashable(v) for v in resultado[destino]["referencias"])
            huerfanos = sum(
                1 for r in detalle["nuevos"] + detalle["existentes"]
                if r.get(campo["nombre"]) is not None
                and _hashable(r[campo["nombre"]]) not in claves_destino)
            if huerfanos:
                problemas.append(
                    f"{nombre}.{campo['nombre']}: {huerfanos} registros apuntan a "
                    f"'{destino}' sin clave existente")
    return problemas


def tipos_soportados():
    """Tipos neutrales que el generador sabe rellenar."""
    return sorted(GENERABLES_DISPONIBLES)


def compatibilidad_motor(motor):
    """Cobertura del sistema de tipos neutral para un motor."""
    return tipos.compatibilidad(motor)
