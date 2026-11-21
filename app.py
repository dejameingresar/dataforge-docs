#!/usr/bin/env python3
"""DataForge NoSQL — servidor de la aplicacion (solo biblioteca estandar).

    python3 app.py                # http://127.0.0.1:8000
    python3 app.py --puerto 9000
    python3 app.py --sin-navegador

No requiere `pip install`: el nucleo logico y el servidor HTTP son de Python.
La interfaz es una pagina estatica que consume nucleo/api.py.
"""

import argparse
import json
import os
import sys
import time
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.abspath(__file__))   # raiz del proyecto
APP = os.path.join(RAIZ, "app")                     # codigo de la aplicacion
sys.path.insert(0, APP)

from nucleo import api  # noqa: E402
from nucleo.observabilidad import AlmacenEstado, CacheTTL  # noqa: E402

RAIZ_WEB = os.path.join(APP, "web")
TIPOS = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}

RUTA_DATOS = os.environ.get("DATAFORGE_DATOS", os.path.join(RAIZ, "data"))
ALMACEN = AlmacenEstado(
    os.path.join(RUTA_DATOS, "dataforge.sqlite3"),
    os.path.join(RUTA_DATOS, "dataforge.jsonl"),
)
CACHE_API = CacheTTL(ttl_segundos=60, max_entradas=8)


class Manejador(BaseHTTPRequestHandler):
    server_version = "DataForgeNoSQL/2.0"

    def _sesion(self):
        if getattr(self, "_sesion_actual", None):
            return self._sesion_actual
        valor = None
        try:
            galletas = SimpleCookie(self.headers.get("Cookie", ""))
            if "DFSESSION" in galletas:
                valor = galletas["DFSESSION"].value
        except Exception:  # una cabecera malformada crea otra sesion
            valor = None
        sesion = ALMACEN.obtener_sesion(valor)
        self._sesion_actual = sesion["id"]
        if sesion["nueva"]:
            self._cookie_pendiente = (
                f"DFSESSION={sesion['id']}; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800"
            )
        return self._sesion_actual

    def log_message(self, formato, *args):  # salida limpia en la demo
        sys.stderr.write(f"  {formato % args}\n")

    def _anota_peticion(self, ruta, respuesta, t0, sesion, cache=False):
        """Registra la llamada para el dashboard, sin sacar datos del cuerpo
        mas alla del motor y de cuantos registros se generaron."""
        try:
            motor = None
            registros = 0
            datos = json.loads(respuesta.get("cuerpo", "{}"))
            motor = datos.get("motor")
            if datos.get("total_escrito") is not None:
                registros = datos.get("total_escrito") or 0
            tot = (datos.get("metricas") or {}).get("totales") or {}
            if tot.get("generados") is not None:
                registros = tot.get("generados") or 0
            ALMACEN.registrar(
                sesion, ruta, respuesta.get("status", 500),
                (time.time() - t0) * 1000, registros, motor, cache,
            )
        except Exception:  # noqa: BLE001 - el registro nunca debe romper nada
            pass

    def _envia(self, status, cuerpo, tipo="application/json; charset=utf-8",
               cabeceras=None):
        if isinstance(cuerpo, str):
            cuerpo = cuerpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if getattr(self, "_cookie_pendiente", None):
            self.send_header("Set-Cookie", self._cookie_pendiente)
            self._cookie_pendiente = None
        for nombre, valor in (cabeceras or {}).items():
            self.send_header(nombre, str(valor))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _estatico(self, camino_rel):
        # Se resuelve dentro de app/web y se comprueba, sin salir de la carpeta.
        limpio = os.path.normpath(camino_rel).lstrip("./")
        destino = os.path.join(RAIZ_WEB, limpio)
        if not os.path.abspath(destino).startswith(os.path.abspath(RAIZ_WEB) + os.sep):
            return self._envia(403, "403", "text/plain; charset=utf-8")
        if os.path.isdir(destino):
            destino = os.path.join(destino, "index.html")
        if not os.path.isfile(destino):
            return self._envia(404, f"no existe: {limpio}", "text/plain; charset=utf-8")
        ext = os.path.splitext(destino)[1]
        with open(destino, "rb") as fh:
            self._envia(200, fh.read(), TIPOS.get(ext, "application/octet-stream"))

    def do_PUT(self):
        self._metodo_no_soportado()

    def do_DELETE(self):
        self._metodo_no_soportado()

    def do_PATCH(self):
        self._metodo_no_soportado()

    def do_HEAD(self):
        self._metodo_no_soportado()

    def _metodo_no_soportado(self):
        """Respuesta limpia para los metodos que la API no implementa.

        Sin estos metodos, BaseHTTPRequestHandler responde 501 con su pagina de
        error en HTML, que no es lo que espera un cliente de la API.
        """
        self._envia(405, json.dumps({
            "ok": False,
            "error": f"metodo {self.command} no permitido; use GET o POST"
        }))

    def do_POST(self):
        t0 = time.time()
        sesion = self._sesion()
        try:
            largo = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._envia(400, "Content-Length no valido",
                              "text/plain; charset=utf-8")
        bruto = self.rfile.read(largo) if largo else b""
        # Un cuerpo que no sea UTF-8 valido no debe tumbar el servidor: se
        # decodifica reemplazando lo ilegible, y el parser de JSON rechaza el
        # resultado con un error limpio.
        cuerpo = bruto.decode("utf-8", errors="replace")
        try:
            r = api.ruta("POST", self.path, cuerpo=cuerpo)
        except Exception as e:  # noqa: BLE001 - nunca debe caerse el hilo
            r = {"status": 500,
                 "cuerpo": json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})}
        self._anota_peticion(self.path, r, t0, sesion)
        self._envia(r["status"], r["cuerpo"])

    def do_GET(self):
        t0 = time.time()
        try:
            camino = self.path.split("?")[0]
            if camino.startswith("/api/"):
                sesion = self._sesion()
                if camino == "/api/sesion":
                    r = {"status": 200, "cuerpo": json.dumps({
                        "ok": True, "sesion": sesion,
                        "persistencia": "SQLite local",
                        "privacidad": "no se almacenan cuerpos ni credenciales",
                    })}
                    self._anota_peticion(self.path, r, t0, sesion)
                    return self._envia(r["status"], r["cuerpo"])
                if camino == "/api/historial":
                    r = {"status": 200, "cuerpo": json.dumps({
                        "ok": True, "operaciones": ALMACEN.historial(sesion),
                    }, ensure_ascii=False)}
                    self._anota_peticion(self.path, r, t0, sesion)
                    return self._envia(r["status"], r["cuerpo"])
                if camino == "/api/telemetria":
                    r = {"status": 200, "cuerpo": json.dumps({
                        "ok": True, "telemetria": ALMACEN.telemetria(),
                    }, ensure_ascii=False)}
                    self._anota_peticion(self.path, r, t0, sesion)
                    return self._envia(r["status"], r["cuerpo"])

                cacheable = camino in ("/api/catalogo", "/api/esquema")
                r, hit = CACHE_API.obtener(camino) if cacheable else (None, False)
                consulta = self.path.split("?")[1].split("&") if "?" in self.path else []
                if r is None:
                    r = api.ruta("GET", self.path, query=consulta)
                    if cacheable and r["status"] == 200:
                        CACHE_API.guardar(camino, r)
                self._anota_peticion(self.path, r, t0, sesion, hit)
                cabeceras = {"X-DataForge-Cache": "HIT" if hit else "MISS"}
                return self._envia(r["status"], r["cuerpo"], cabeceras=cabeceras)
            if camino in ("/", "/index.html"):
                return self._estatico("index.html")
            return self._estatico(camino.lstrip("/"))
        except Exception as e:  # noqa: BLE001 - nunca debe caerse el hilo
            self._envia(500, json.dumps({"ok": False,
                                         "error": f"{type(e).__name__}: {e}"}))


def main():
    ap = argparse.ArgumentParser(description="DataForge NoSQL · generador de datos")
    ap.add_argument("--puerto", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--sin-navegador", action="store_true",
                    help="no abrir el navegador automaticamente")
    args = ap.parse_args()

    if not os.path.isdir(RAIZ_WEB):
        print(f"ERROR: falta la interfaz en {RAIZ_WEB}", file=sys.stderr)
        return 1

    servidor = ThreadingHTTPServer((args.host, args.puerto), Manejador)
    url = f"http://{args.host}:{args.puerto}/"
    print("=" * 64)
    print("  DataForge NoSQL · generador de datos para bases de datos NoSQL")
    print(f"  Motores: {', '.join(api.tipos.ORDEN_MOTORES)}")
    print(f"  Abrir:   {url}")
    print("  Ctrl+C para detener")
    print("=" * 64)
    if not args.sin_navegador:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  servidor detenido")
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
