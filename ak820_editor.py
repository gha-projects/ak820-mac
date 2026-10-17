#!/usr/bin/env python3
"""La ventana de AK820 (teclas, luces, pantalla y ajustes) servida como página web local.

Un servidor local (solo en 127.0.0.1) sirve editor/index.html y aplica los cambios con
ak820.py. La app la enseña en su propia ventana (ak820_ventana.py); sin la app se abre
en el navegador. Para que ninguna otra página web pueda tocar el teclado, la API pide
una clave que solo conoce la página abierta desde aquí (va en el #fragmento de la
dirección, que el navegador no manda a ningún sitio) y se comprueba la cabecera Host.

Uso: python3 ak820_editor.py   (o, en la app, Abrir AK820…)
"""
import contextlib
import io
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import ak820

# Dentro de AK820.app (py2app) los archivos van en Contents/Resources (RESOURCEPATH).
CARPETA = os.path.join(os.environ.get("RESOURCEPATH") or os.path.dirname(os.path.abspath(__file__)), "editor")
PUERTO = 8820
MAX_CUERPO = 64 * 1024
MAX_IMAGEN = 30 * 1024 * 1024
PROGRESO = re.compile(r"(\d+) % enviado")
COLOR = re.compile(r"^[0-9A-Fa-f]{6}$")
BLOQUEOS = ("win", "altf4", "alttab")
OCUPADO = "Espera: hay otra operación en curso con el teclado."
OCUPADO_MUSICA = "El modo música está en marcha: páralo para cambiar otras cosas."
SIN_TECLADO = ("No encuentro el teclado. Conéctalo con el cable USB-C o con el receptor 2.4G "
               "(por Bluetooth no se puede configurar).")


class Ocupado(Exception):
    """Otra operación (de la ventana o del menú de la app) está usando el teclado."""

    def __init__(self, mensaje=OCUPADO):
        super().__init__(mensaje)


class Copia(io.StringIO):
    """Recoge lo que imprime ak820.py, lo copia a la salida estándar (al registro) y
    avisa del % enviado de las imágenes."""

    def __init__(self, al_progresar=None):
        super().__init__()
        self.al_progresar = al_progresar

    def write(self, texto):
        if sys.__stdout__:
            sys.__stdout__.write(texto)
            sys.__stdout__.flush()
        encontrado = PROGRESO.search(texto)
        if encontrado and self.al_progresar:
            self.al_progresar(int(encontrado.group(1)))
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
        "efectos": [e for e in ak820.EFECTOS if e != "apagado"],
        "teclas_con_luz": list(ak820.POSICION_LUZ),
        "direcciones": list(ak820.DIRECCIONES),
        "reposo": list(ak820.REPOSO),
        "modos_fn": list(ak820.MODO_FN),
        "modos_musica": list(ak820.MODO_MUSICA),
    }


def conexion():
    """"cable", "2.4g" (con el receptor) o None."""
    try:
        if ak820.buscar_interfaz() is not None:
            return "cable"
        if ak820.buscar_receptor() is not None:
            return "2.4g"
    except Exception:                              # hidapi puede fallar un instante al (des)conectar
        pass
    return None


def pantalla_para_pagina():
    """Qué se ve en la pantalla y cuál fue la última imagen subida (sin la ruta del archivo)."""
    info = ak820.info_pantalla()
    return {"modo": info["modo"], "nombre": info["nombre"], "fecha": info["fecha"], "hay_vista": bool(info["vista"])}


def ajustes_para_pagina():
    """Los ajustes del sistema guardados, con los nombres de las opciones de 'sistema'."""
    ajustes = ak820.cargar_ajustes()
    reposo = {v: k for k, v in ak820.REPOSO.items()}
    fn = {v: k for k, v in ak820.MODO_FN.items()}
    return {"fn": fn.get(ajustes["fn"], "mantener"), "reposo": reposo.get(ajustes["reposo"], "5"),
            "respuesta": ajustes["respuesta"],
            "bloquear": {b: bool(ajustes["bloquear_" + b]) for b in BLOQUEOS}}


# --- Validación de lo que manda la página --------------------------------------------
def validar(asignacion):
    """(True, "") si la asignación de una tecla vale; si no, (False, motivo)."""
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


def numero(valor, minimo, maximo, nombre):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{nombre} no válido.") from None
    if not minimo <= n <= maximo:
        raise ValueError(f"{nombre} tiene que ir de {minimo} a {maximo}.")
    return n


def args_luces(datos):
    """Argumentos de 'luces' para lo que pide la página. Lanza ValueError si algo no vale."""
    if not isinstance(datos, dict) or datos.get("efecto") not in ak820.EFECTOS:
        raise ValueError("Efecto de luz no válido.")
    color = str(datos.get("color", "FFFFFF")).lstrip("#")
    if not COLOR.match(color):
        raise ValueError("Color no válido.")
    direccion = datos.get("direccion", "izquierda")
    if direccion not in ak820.DIRECCIONES:
        raise ValueError("Dirección no válida.")
    argumentos = ["luces", datos["efecto"], "--color", color.upper(),
                  "--brillo", str(numero(datos.get("brillo", 5), 0, 5, "El brillo")),
                  "--velocidad", str(numero(datos.get("velocidad", 3), 0, 5, "La velocidad")),
                  "--direccion", direccion]
    if datos.get("arcoiris"):
        argumentos.append("--arcoiris")
    return argumentos


def limpiar_colores(datos):
    """Los colores tecla a tecla en el formato de ak820.cargar_colores(). Lanza ValueError."""
    if not isinstance(datos, dict) or not isinstance(datos.get("teclas", {}), dict):
        raise ValueError("Colores no válidos.")
    fondo = ak820.color_valido(datos.get("fondo", "000000"))
    if fondo is None:
        raise ValueError("Color de fondo no válido.")
    teclas = {}
    for tecla, color in datos.get("teclas", {}).items():
        if tecla not in ak820.POSICION_LUZ or ak820.color_valido(color) is None:
            raise ValueError(f"Color no válido en '{tecla}'.")
        teclas[tecla] = ak820.color_valido(color)
    return {"fondo": fondo, "teclas": teclas, "brillo": numero(datos.get("brillo", 5), 1, 5, "El brillo")}


def args_sistema(datos):
    """Argumentos de 'sistema' para lo que pide la página. Lanza ValueError si algo no vale."""
    if not isinstance(datos, dict):
        raise ValueError("Ajustes no válidos.")
    if datos.get("fabrica"):
        return ["sistema", "--fabrica"]
    if datos.get("fn") not in ak820.MODO_FN or datos.get("reposo") not in ak820.REPOSO:
        raise ValueError("Ajustes no válidos.")
    bloquear = datos.get("bloquear") or {}
    argumentos = ["sistema", "--fn-modo", datos["fn"], "--reposo", datos["reposo"],
                  "--respuesta", str(numero(datos.get("respuesta", 2), 1, 5, "El tiempo de respuesta"))]
    si = [b for b in BLOQUEOS if bloquear.get(b)]
    no = [b for b in BLOQUEOS if not bloquear.get(b)]
    if si:
        argumentos += ["--bloquear", *si]
    if no:
        argumentos += ["--desbloquear", *no]
    return argumentos


# --- El servidor ---------------------------------------------------------------------
class Editor:
    def __init__(self, candado=None):
        self.candado = candado or threading.Lock()   # el mismo que la app: una operación a la vez
        self.clave = secrets.token_urlsafe(18)
        self.servidor = None
        self.progreso = None                         # % de la imagen que se está enviando
        self.musica_modo = None                      # el modo música en marcha, o None
        self.musica_error = ""
        self._parar_musica = threading.Event()
        self._hilo_musica = None

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
        """Abre la página en el navegador (sin la app)."""
        subprocess.run(["open", self.iniciar()], check=False)

    def _con_teclado(self, funcion):
        """Ejecuta funcion() con el teclado reservado, recogiendo lo que imprime.

        Devuelve (resultado, líneas impresas). Lanza Ocupado si el teclado está en uso.
        """
        if not self.candado.acquire(blocking=False):
            raise Ocupado(OCUPADO_MUSICA if self.musica_modo else OCUPADO)
        self.progreso = None
        try:
            salida = Copia(self.apuntar_progreso)
            with contextlib.redirect_stdout(salida):
                resultado = funcion()
            return resultado, [l.strip() for l in salida.getvalue().splitlines() if l.strip()]
        finally:
            self.progreso = None
            self.candado.release()

    def apuntar_progreso(self, porcentaje):
        self.progreso = porcentaje

    def orden(self, argumentos):
        """Ejecuta una orden de ak820.py. Devuelve (bien, mensaje)."""
        def correr():
            try:
                return ak820.main(argumentos) or 0
            except SystemExit as e:                     # argparse sale así si algo no cuadra
                return e.code if isinstance(e.code, int) else 1
        try:
            codigo, lineas = self._con_teclado(correr)
        except Ocupado as e:
            return False, str(e)
        except Exception as e:                          # p. ej. se desconecta a medias
            return False, f"Error: {e}"
        if codigo != 0 and any("No encuentro el teclado" in l for l in lineas):
            return False, SIN_TECLADO
        lineas = [l for l in lineas if "% enviado" not in l and "repitiendo" not in l
                  and not l.startswith("Para volver")]
        return codigo == 0, "\n".join(lineas[-5:]) or ("Hecho." if codigo == 0 else "Algo ha fallado.")

    def enviar(self, config):
        """Manda la configuración de teclas al teclado. Devuelve (bien, mensaje)."""
        try:
            bien, lineas = self._con_teclado(lambda: ak820.enviar_teclas(config))
        except Ocupado as e:
            return False, str(e)
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Error: {e}"
        if bien:
            return True, "Teclas guardadas en el teclado."
        if any("No encuentro el teclado" in l for l in lineas):
            return False, SIN_TECLADO
        return False, " ".join(l for l in lineas if "repitiendo" not in l) or "Algo ha fallado."

    def colores(self, config):
        """Manda los colores tecla a tecla. Devuelve (bien, mensaje)."""
        try:
            bien, lineas = self._con_teclado(lambda: ak820.enviar_colores(config))
        except Ocupado as e:
            return False, str(e)
        except Exception as e:
            return False, f"Error: {e}"
        if bien:
            return True, "Colores guardados en el teclado."
        if any("No encuentro el teclado" in l for l in lineas):
            return False, SIN_TECLADO
        return False, " ".join(l for l in lineas if "repitiendo" not in l) or "Algo ha fallado."

    # --- Modo música (en un hilo, con el teclado reservado mientras dura) -----------------------
    def empezar_musica(self, modo):
        """Pone en marcha el modo música. Devuelve (bien, mensaje)."""
        if modo not in ak820.MODO_MUSICA:
            return False, "Modo de música no válido."
        if self.musica_modo:
            self.parar_musica()
        if not self.candado.acquire(blocking=False):
            return False, OCUPADO
        self.musica_modo, self.musica_error = modo, ""
        self._parar_musica.clear()

        def tocar():
            salida = Copia()
            try:
                with contextlib.redirect_stdout(salida):
                    codigo = ak820.musica(modo, self._parar_musica)
                if codigo != 0:
                    lineas = [l.strip() for l in salida.getvalue().splitlines() if l.strip()]
                    texto = " ".join(lineas[-2:])
                    self.musica_error = SIN_TECLADO if "No encuentro el teclado" in texto else texto
            except Exception as e:
                self.musica_error = f"Error: {e}"
            finally:
                self.musica_modo = None
                self.candado.release()

        self._hilo_musica = threading.Thread(target=tocar, daemon=True)
        self._hilo_musica.start()
        return True, "Modo música en marcha."

    def parar_musica(self):
        self._parar_musica.set()
        if self._hilo_musica is not None:
            self._hilo_musica.join(timeout=3)
        return True, "Modo música parado."

    def imagen(self, datos):
        """Pone en la pantalla una imagen o GIF (los bytes del archivo). Devuelve (bien, mensaje)."""
        from PIL import Image
        with tempfile.NamedTemporaryFile(delete=False) as archivo:
            archivo.write(datos)
        try:
            try:
                with Image.open(archivo.name) as prueba:
                    prueba.verify()
            except Exception:
                return False, "Ese archivo no es una imagen que se pueda leer."
            return self.orden(["imagen", archivo.name])
        finally:
            os.unlink(archivo.name)


class Manejador(BaseHTTPRequestHandler):
    server_version = "AK820Editor"

    def log_message(self, formato, *args):            # sin una línea por cada petición
        pass

    # --- Comprobaciones ------------------------------------------------------
    def host_valido(self):
        puerto = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{puerto}", f"localhost:{puerto}")

    def clave_valida(self):
        # La copia de la pantalla va en un <img>, que no puede mandar cabeceras: ahí va en la dirección.
        clave = self.headers.get("X-Clave") or parse_qs(urlparse(self.path).query).get("clave", [""])[0]
        return secrets.compare_digest(clave, self.server.editor.clave)

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

    def resultado(self, bien, mensaje, **extra):
        self.responder(200, {"ok": bien, "mensaje": mensaje, **extra})

    def do_GET(self):
        if not self.host_valido():
            return self.responder(403, {"error": "Host no permitido"})
        ruta = self.path.split("?")[0]
        if ruta == "/":
            with open(os.path.join(CARPETA, "index.html"), "rb") as f:
                return self.responder(200, f.read(), "text/html; charset=utf-8")
        if not self.clave_valida():
            return self.responder(403, {"error": "clave"})
        editor = self.server.editor
        if ruta == "/api/estado":
            with open(os.path.join(CARPETA, "distribucion.json"), encoding="utf-8") as f:
                distribucion = json.load(f)
            return self.responder(200, {
                "distribucion": distribucion, "config": ak820.cargar_teclas(), "catalogo": catalogo(),
                "luces": ak820.cargar_luces(), "colores": ak820.cargar_colores(), "pantalla": pantalla_para_pagina(),
                "ajustes": ajustes_para_pagina(), "conexion": conexion(), "musica": editor.musica_modo})
        if ruta == "/api/pantalla-vista":
            vista = ak820.info_pantalla()["vista"]
            if not vista:
                return self.responder(404, {"error": "no hay"})
            with open(vista, "rb") as f:
                return self.responder(200, f.read(), "image/gif" if vista.endswith(".gif") else "image/png")
        if ruta == "/api/conexion":
            return self.responder(200, {"conexion": conexion(), "ocupado": editor.candado.locked(),
                                        "musica": editor.musica_modo, "musica_error": editor.musica_error,
                                        "progreso": editor.progreso})
        self.responder(404, {"error": "no existe"})

    def do_POST(self):
        if not self.host_valido():
            return self.responder(403, {"error": "Host no permitido"})
        if not self.clave_valida():
            return self.responder(403, {"error": "clave"})
        ruta = self.path.split("?")[0]
        tipo = self.headers.get("Content-Type", "")
        largo = int(self.headers.get("Content-Length") or 0)
        editor = self.server.editor

        if ruta == "/api/imagen":                     # el archivo tal cual, no JSON
            if not (tipo.startswith("image/") or tipo == "application/octet-stream"):
                return self.responder(415, {"error": "se espera una imagen"})
            if not 0 < largo <= MAX_IMAGEN:
                return self.resultado(False, "La imagen es demasiado grande (máximo 30 MB).")
            bien, mensaje = editor.imagen(self.rfile.read(largo))
            return self.resultado(bien, mensaje, pantalla=pantalla_para_pagina())

        if not tipo.startswith("application/json"):
            return self.responder(415, {"error": "se espera JSON"})
        if not 0 < largo <= MAX_CUERPO:
            return self.responder(413, {"error": "tamaño no válido"})
        try:
            datos = json.loads(self.rfile.read(largo))
        except ValueError:
            return self.responder(400, {"error": "JSON no válido"})
        if not isinstance(datos, dict):
            return self.responder(400, {"error": "JSON no válido"})

        if ruta == "/api/validar":
            return self.resultado(*validar(datos.get("asignacion")))
        if ruta == "/api/enviar":
            try:
                config = limpiar(datos.get("config"))
            except ValueError as e:
                return self.resultado(False, str(e))
            bien, mensaje = editor.enviar(config)
            return self.resultado(bien, mensaje, config=ak820.cargar_teclas())
        if ruta == "/api/luces":
            try:
                argumentos = args_luces(datos.get("luces"))
            except ValueError as e:
                return self.resultado(False, str(e))
            bien, mensaje = editor.orden(argumentos)
            return self.resultado(bien, mensaje, luces=ak820.cargar_luces())
        if ruta == "/api/colores":
            try:
                config = limpiar_colores(datos.get("colores"))
            except ValueError as e:
                return self.resultado(False, str(e))
            bien, mensaje = editor.colores(config)
            return self.resultado(bien, mensaje, colores=ak820.cargar_colores(), luces=ak820.cargar_luces())
        if ruta == "/api/musica":
            if datos.get("accion") == "parar":
                bien, mensaje = editor.parar_musica()
            else:
                bien, mensaje = editor.empezar_musica(datos.get("modo"))
            return self.resultado(bien, mensaje, musica=editor.musica_modo)
        if ruta == "/api/apagar":
            bien, mensaje = editor.orden(["luces", "apagado"])
            return self.resultado(bien, mensaje)
        if ruta == "/api/reloj":
            bien, mensaje = editor.orden(["reloj"])
            return self.resultado(bien, mensaje, pantalla=pantalla_para_pagina())
        if ruta == "/api/sistema":
            try:
                argumentos = args_sistema(datos.get("ajustes"))
            except ValueError as e:
                return self.resultado(False, str(e))
            bien, mensaje = editor.orden(argumentos)
            return self.resultado(bien, mensaje, ajustes=ajustes_para_pagina())
        self.responder(404, {"error": "no existe"})


def main():
    editor = Editor()
    editor.abrir()
    print(f"Abierto en el navegador: {editor.url()}")
    print("Déjalo abierto mientras lo uses; para cerrarlo, Ctrl+C.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
