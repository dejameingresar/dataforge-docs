"""Estado local para sesiones, historial, cache, logs y telemetria.

No almacena cuerpos de peticion, datos generados, credenciales ni identidad del
usuario. SQLite pertenece a la instalacion local y funciona con la biblioteca
estandar de Python.
"""

from collections import OrderedDict
from contextlib import closing
import datetime as dt
import json
import os
import re
import secrets
import sqlite3
import threading
import time


_ID_SESION = re.compile(r"^[0-9a-f]{32}$")


def _ahora():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class CacheTTL:
    """Cache LRU pequeno y seguro para respuestas GET inmutables."""

    def __init__(self, ttl_segundos=60, max_entradas=32):
        self.ttl = float(ttl_segundos)
        self.max_entradas = max(1, int(max_entradas))
        self._datos = OrderedDict()
        self._lock = threading.Lock()

    def obtener(self, clave):
        with self._lock:
            entrada = self._datos.get(clave)
            if entrada is None:
                return None, False
            vence, valor = entrada
            if time.monotonic() >= vence:
                del self._datos[clave]
                return None, False
            self._datos.move_to_end(clave)
            return valor, True

    def guardar(self, clave, valor):
        with self._lock:
            self._datos[clave] = (time.monotonic() + self.ttl, valor)
            self._datos.move_to_end(clave)
            while len(self._datos) > self.max_entradas:
                self._datos.popitem(last=False)


class AlmacenEstado:
    """Persistencia de actividad anonima de la aplicacion."""

    def __init__(self, ruta_db, ruta_log, ttl_sesion=8 * 60 * 60):
        self.ruta_db = os.path.abspath(ruta_db)
        self.ruta_log = os.path.abspath(ruta_log)
        self.ttl_sesion = int(ttl_sesion)
        self._lock_log = threading.Lock()
        os.makedirs(os.path.dirname(self.ruta_db), exist_ok=True)
        os.makedirs(os.path.dirname(self.ruta_log), exist_ok=True)
        self._inicializar()

    def _conexion(self):
        con = sqlite3.connect(self.ruta_db, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA busy_timeout = 10000")
        return con

    def _inicializar(self):
        with closing(self._conexion()) as con, con:
            con.executescript("""
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS sesion (
                    id TEXT PRIMARY KEY,
                    creada_utc TEXT NOT NULL,
                    ultima_actividad_utc TEXT NOT NULL,
                    vence_epoch INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operacion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sesion_id TEXT NOT NULL,
                    fecha_utc TEXT NOT NULL,
                    ruta TEXT NOT NULL,
                    estado INTEGER NOT NULL,
                    duracion_ms INTEGER NOT NULL,
                    registros INTEGER NOT NULL DEFAULT 0,
                    motor TEXT,
                    cache_hit INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (sesion_id) REFERENCES sesion(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS ix_operacion_sesion_fecha
                    ON operacion(sesion_id, id DESC);
                CREATE INDEX IF NOT EXISTS ix_operacion_ruta
                    ON operacion(ruta);
            """)

    def obtener_sesion(self, sesion_id=None):
        ahora_epoch = int(time.time())
        ahora = _ahora()
        valida = bool(sesion_id and _ID_SESION.fullmatch(str(sesion_id)))
        with closing(self._conexion()) as con, con:
            fila = None
            if valida:
                fila = con.execute(
                    "SELECT id, vence_epoch FROM sesion WHERE id = ?",
                    (sesion_id,),
                ).fetchone()
            if fila is not None and fila["vence_epoch"] > ahora_epoch:
                vence = ahora_epoch + self.ttl_sesion
                con.execute(
                    "UPDATE sesion SET ultima_actividad_utc = ?, vence_epoch = ? WHERE id = ?",
                    (ahora, vence, sesion_id),
                )
                return {"id": sesion_id, "nueva": False, "vence_epoch": vence}

            nuevo = secrets.token_hex(16)
            vence = ahora_epoch + self.ttl_sesion
            con.execute(
                "INSERT INTO sesion(id, creada_utc, ultima_actividad_utc, vence_epoch) "
                "VALUES (?, ?, ?, ?)",
                (nuevo, ahora, ahora, vence),
            )
            return {"id": nuevo, "nueva": True, "vence_epoch": vence}

    def registrar(self, sesion_id, ruta, estado, duracion_ms, registros=0,
                  motor=None, cache=False):
        ruta = (ruta or "/").split("?")[0][:160]
        motor = str(motor)[:40] if motor else None
        with closing(self._conexion()) as con, con:
            con.execute(
                "INSERT INTO operacion(sesion_id, fecha_utc, ruta, estado, "
                "duracion_ms, registros, motor, cache_hit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (sesion_id, _ahora(), ruta, int(estado),
                 max(0, int(round(duracion_ms))), max(0, int(registros or 0)),
                 motor, 1 if cache else 0),
            )
        self._log({
            "fecha_utc": _ahora(), "evento": "peticion",
            "sesion": sesion_id[:8], "ruta": ruta, "estado": int(estado),
            "duracion_ms": max(0, int(round(duracion_ms))),
            "registros": max(0, int(registros or 0)), "motor": motor,
            "cache_hit": bool(cache),
        })

    def _log(self, evento):
        try:
            linea = json.dumps(evento, ensure_ascii=False, separators=(",", ":"))
            with self._lock_log:
                with open(self.ruta_log, "a", encoding="utf-8") as fh:
                    fh.write(linea + "\n")
        except OSError:
            return

    def historial(self, sesion_id, limite=50):
        limite = max(1, min(int(limite), 200))
        with closing(self._conexion()) as con:
            filas = con.execute(
                "SELECT fecha_utc, ruta, estado, duracion_ms, registros, motor, cache_hit "
                "FROM operacion WHERE sesion_id = ? ORDER BY id DESC LIMIT ?",
                (sesion_id, limite),
            ).fetchall()
        return [dict(fila) for fila in filas]

    def telemetria(self):
        with closing(self._conexion()) as con:
            total = con.execute("""
                SELECT COUNT(*) llamadas,
                       COALESCE(SUM(CASE WHEN estado >= 400 THEN 1 ELSE 0 END), 0) errores,
                       COALESCE(SUM(registros), 0) registros,
                       COALESCE(ROUND(AVG(duracion_ms)), 0) media_ms,
                       COALESCE(SUM(cache_hit), 0) cache_hits
                FROM operacion
            """).fetchone()
            sesiones = con.execute("SELECT COUNT(*) FROM sesion").fetchone()[0]
            rutas = con.execute(
                "SELECT ruta, COUNT(*) cantidad FROM operacion GROUP BY ruta ORDER BY cantidad DESC"
            ).fetchall()
        return {
            "llamadas": total["llamadas"],
            "errores": total["errores"],
            "registros_generados": total["registros"],
            "respuesta_media_ms": int(total["media_ms"]),
            "cache_hits": total["cache_hits"],
            "sesiones": sesiones,
            "por_ruta": {fila["ruta"]: fila["cantidad"] for fila in rutas},
        }
