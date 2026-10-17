#!/usr/bin/env python3
"""Editor de teclas del AK820 en el navegador.

Un servidor local (solo en 127.0.0.1) sirve editor/index.html y aplica los cambios con
las funciones de ak820.py. Para que ninguna otra página web pueda reprogramar el
teclado, la API pide una clave que solo conoce la página abierta desde aquí (va en el
#fragmento de la dirección, que el navegador no manda a ningún sitio) y se comprueba la
cabecera Host.

Uso: python3 ak820_editor.py   (o, en la app, Teclas → Editor de teclas…)
"""
import contextlib
import io
import json
import os
import secrets
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import ak820

# Dentro de AK820.app (py2app) los archivos van en Contents/Resources (RESOURCEPATH).
CARPETA = os.path.join(os.environ.get("RESOURCEPATH") or os.path.dirname(os.path.abspath(__file__)), "editor")
PUERTO = 8820
MAX_CUERPO = 64 * 1024


class Copia(io.StringIO):
    """Recoge lo que imprime ak820.py y lo copia también a la salida estándar (al registro)."""

    def write(self, texto):
        if sys.__stdout__:
            sys.__stdout__.write(texto)
            sys.__stdout__.flush()
        return super().write(texto)


def catalogo():
    """Los nombres que entiende ak820.py, para los desplegables de la página."""
    return {
        "teclas": list(ak820.CODIGO_TECLA),
        "modificadores": ["ctrl", "shift", "option", "cmd"],
        "multimedia": list(ak820.MULTIMEDIA),
        "raton": list(ak820.RATON) + ["doble_clic"],
        "modos": list(ak820.MODO_MACRO),
        "no_cambiables_fn": sorted(ak820.NOMBRE_TECLA[i] for i in ak820.NO_CAMBIABLES_FN),
    }


def validar(asignacion):
    """(True, "") si la asignación vale; si no, (False, motivo)."""
    if not isinstance(asignacion, dict) or not isinstance(asignacion.get("destino"), str):
        return False, "Asignación no válida."
    try:
        ak820.entrada_asignacion(asignacion, [])
        return True, ""
    except (ValueError, TypeError, AttributeError) as e:
        return False, str(e)


def limpiar(config):
    """Solo las capas, teclas y campos conocidos, en el formato de ak820.cargar_teclas()."""
    if not isinstance(config, dict):
        raise ValueError("Configuración no válida.")
    limpia = {capa: {} for capa in ak820.CAPAS}
    for capa in ak820.CAPAS:
        teclas = config.get(capa) or {}
        if not isinstance(teclas, dict):
            raise ValueError("Configuración no válida.")
        for origen, asignacion in teclas.items():
            if not isinstance(asignacion, dict) or not isinstance(asignacion.get("destino"), str):
                raise ValueError(f"Asignación no válida en '{origen}'.")
            limpia[capa][origen] = {k: asignacion[k] for k in ("destino", "modo", "veces") if k in asignacion}
    return limpia


class Editor:
    def __init__(self, candado=None):
        self.candado = candado or threading.Lock()   # el mismo que la app: una operación a la vez
        self.clave = secrets.token_urlsafe(18)
        self.servidor = None

    def iniciar(self):
        """Arranca el servidor en un hilo (si no estaba ya) y devuelve la dirección."""
        if self.servidor is None:
            try:
                self.servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
            except OSError:                              # puerto ocupado: uno cualquiera
                self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
            self.servidor.editor = self
            threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        return self.url()

    def url(self):
        return f"http://127.0.0.1:{self.servidor.server_address[1]}/#clave={self.clave}"

    def abrir(self):
        subprocess.run(["open", self.iniciar()], check=False)

    def enviar(self, config):
        """Manda la configuración al teclado. Devuelve (bien, mensaje)."""
        if not self.candado.acquire(blocking=False):
            return False, "Espera: hay otra operación en curso con el teclado."
        try:
            salida = Copia()
            with contextlib.redirect_stdout(salida):
                try:
                    bien = ak820.enviar_teclas(config)
                except ValueError as e:
                    return False, str(e)
                except Exception as e:                     # p. ej. se desconecta a medias
                    return False, f"Error: {e}"
            lineas = [l.strip() for l in salida.getvalue().splitlines()
                      if l.strip() and "repitiendo" not in l]
            if bien:
                return True, "Teclas guardadas en el teclado."
            return False, " ".join(lineas) or "Algo ha fallado."
        finally:
            self.candado.release()


class Manejador(BaseHTTPRequestHandler):
    server_version = "AK820Editor"

    def log_message(self, formato, *args):            # sin una línea por cada petición
        pass

    # --- Comprobaciones ------------------------------------------------------
    def host_valido(self):
        puerto = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{puerto}", f"localhost:{puerto}")

    def clave_valida(self):
        return secrets.compare_digest(self.headers.get("X-Clave", ""), self.server.editor.clave)

    # --- Respuestas ------------------------------------------------------------
    def responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(datos)

    def fichero(self, nombre, tipo):
        with open(os.path.join(CARPETA, nombre), "rb") as f:
            self.responder(200, f.read(), tipo)

    def do_GET(self):
        if not self.host_valido():
            return self.responder(403, {"error": "Host no permitido"})
        ruta = self.path.split("?")[0]
        if ruta == "/":
            return self.fichero("index.html", "text/html; charset=utf-8")
        if ruta == "/api/estado":
            if not self.clave_valida():
                return self.responder(403, {"error": "clave"})
            with open(os.path.join(CARPETA, "distribucion.json"), encoding="utf-8") as f:
                distribucion = json.load(f)
            return self.responder(200, {"distribucion": distribucion, "config": ak820.cargar_teclas(),
                                        "catalogo": catalogo()})
        self.responder(404, {"error": "no existe"})

    def do_POST(self):
        if not self.host_valido():
            return self.responder(403, {"error": "Host no permitido"})
        if not self.clave_valida():
            return self.responder(403, {"error": "clave"})
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self.responder(415, {"error": "se espera JSON"})
        largo = int(self.headers.get("Content-Length") or 0)
        if not 0 < largo <= MAX_CUERPO:
            return self.responder(413, {"error": "tamaño no válido"})
        try:
            datos = json.loads(self.rfile.read(largo))
        except ValueError:
            return self.responder(400, {"error": "JSON no válido"})
        ruta = self.path.split("?")[0]
        if ruta == "/api/validar":
            bien, mensaje = validar(datos.get("asignacion") if isinstance(datos, dict) else None)
            return self.responder(200, {"ok": bien, "mensaje": mensaje})
        if ruta == "/api/enviar":
            try:
                config = limpiar(datos.get("config") if isinstance(datos, dict) else None)
            except ValueError as e:
                return self.responder(200, {"ok": False, "mensaje": str(e)})
            bien, mensaje = self.server.editor.enviar(config)
            return self.responder(200, {"ok": bien, "mensaje": mensaje, "config": ak820.cargar_teclas()})
        self.responder(404, {"error": "no existe"})


def main():
    editor = Editor()
    editor.abrir()
    print(f"Editor abierto en el navegador: {editor.url()}")
    print("Déjalo abierto mientras lo uses; para cerrarlo, Ctrl+C.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
