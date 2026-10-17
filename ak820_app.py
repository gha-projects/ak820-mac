#!/usr/bin/env python3
"""App de la barra de menús para el Ajazz AK820 (usa ak820.py por debajo).

Cada opción del menú llama a ak820.main([...]) en un hilo aparte (para no
congelar el menú) y recoge lo que imprime. Si sale bien, el icono muestra ✓
unos segundos; si falla (o la opción es para consultar algo), sale una ventana
con el mensaje. No se usan notificaciones: macOS no enseña las de un Python
suelto sin permiso. Lo que imprime ak820.py se copia también a la salida
estándar, que 'Abrir AK820.command' guarda en ~/Library/Logs/ak820-app.log.
Solo se hace una operación a la vez: el teclado no admite dos conversaciones
seguidas sin terminar la anterior.

Los cambios de la interfaz (título, ventanas) se hacen siempre desde el
hilo principal, con un temporizador que recoge lo que dejan los hilos.
"""
import contextlib
import io
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time

import rumps

import ak820
import ak820_editor
import ak820_ventana

CARPETA = os.path.dirname(os.path.abspath(__file__))
# Dentro de AK820.app (py2app) la guía va en Contents/Resources (RESOURCEPATH).
GUIA_TECLAS = (os.path.join(os.environ["RESOURCEPATH"], "teclas.md") if "RESOURCEPATH" in os.environ
               else os.path.join(CARPETA, "docs", "teclas.md"))
REGISTRO = os.path.expanduser("~/Library/Logs/ak820-app.log")

TITULO = "⌨︎"
TITULO_OCUPADO = "⌨︎…"
TITULO_HECHO = "⌨︎ ✓"
SEGUNDOS_HECHO = 3
PROGRESO = re.compile(r"(\d+) % enviado")

COLORES = {
    "Rojo": "FF0000", "Verde": "00FF00", "Azul": "0000FF", "Blanco": "FFFFFF",
    "Morado": "8000FF", "Naranja": "FF6000", "Cian": "00FFFF",
}
EFECTOS_CON_COLOR = {"Fijo": "fijo", "Respirar": "respirar"}
REPOSOS = {"1 minuto": "1", "5 minutos": "5", "30 minutos": "30", "Nunca": "nunca"}
MODOS_FN = {"Solo mientras se mantiene (de fábrica)": "mantener", "Pulsar para activar/desactivar": "alternar"}
TIPOS_IMAGEN = ["png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff"]
SEGUNDOS_VIGILAR = 3                 # cada cuánto se mira si el teclado está conectado
PREFERENCIAS = os.path.expanduser("~/Library/Application Support/ak820-mac/app.json")
PREFERENCIAS_DEFECTO = {"hora_al_conectar": True}


def cargar_preferencias():
    preferencias = dict(PREFERENCIAS_DEFECTO)
    try:
        with open(PREFERENCIAS) as f:
            preferencias.update({k: v for k, v in json.load(f).items() if k in preferencias})
    except (OSError, ValueError, AttributeError):
        pass
    return preferencias


def guardar_preferencias(preferencias):
    os.makedirs(os.path.dirname(PREFERENCIAS), exist_ok=True)
    with open(PREFERENCIAS, "w") as f:
        json.dump(preferencias, f, indent=2)


# --- Argumentos para ak820.main (funciones puras, fáciles de probar) --------
def args_luces(efecto, color=None, brillo=5):
    """Argumentos de 'luces' para un efecto del menú."""
    if efecto == "apagado":
        return ["luces", "apagado"]
    if efecto == "espectro":
        return ["luces", "espectro", "--arcoiris", "--brillo", str(brillo)]
    if efecto == "rodar":
        return ["luces", "rodar", "--arcoiris", "--direccion", "derecha", "--brillo", str(brillo)]
    return ["luces", efecto, "--color", color, "--brillo", str(brillo)]


def args_reposo(minutos):
    return ["reposo", minutos]


def args_sistema(opciones):
    return ["sistema"] + list(opciones)


def args_imagen(ruta):
    return ["imagen", ruta]


def args_restaurar_teclas():
    """Las dos capas de teclas de fábrica (normal y con Fn)."""
    return [["teclas", "restaurar", "todo"]]


def resumen(salida, codigo, solo_ultima=False, completo=False):
    """Las líneas útiles de lo que imprime ak820.py, para enseñarlas en una ventana."""
    lineas = [l.strip() for l in salida.splitlines() if l.strip()]
    errores = [l.split("error:", 1)[1].strip() for l in lineas if "error:" in l]
    if errores:                                    # error de argumentos (argparse)
        return "Error: " + errores[-1]
    lineas = [l for l in lineas if "% enviado" not in l and not l.startswith("Para volver")
              and not l.startswith("(Cada vez")]
    if codigo != 0 and any(aviso in l for l in lineas
                           for aviso in ("No encuentro el teclado", "No veo ningún", "No aparece la interfaz")):
        return ("No encuentro el teclado por cable. Conéctalo con el cable USB-C y ponlo en modo "
                "cable: por Bluetooth o 2.4G no se puede configurar.")
    if solo_ultima:
        lineas = lineas[-1:]
    elif not completo:
        lineas = lineas[-3:]
    return "\n".join(lineas) or ("Hecho." if codigo == 0 else "Algo ha fallado.")


def ventana(titulo, mensaje):
    """Ventana con un mensaje, delante de todo (la app no tiene icono en el Dock)."""
    from AppKit import NSApp
    NSApp.activateIgnoringOtherApps_(True)
    rumps.alert(title=f"AK820 · {titulo}", message=mensaje, ok="Vale")


def notificar(titulo, mensaje):
    """Notificación de macOS. Solo dentro de AK820.app: un Python suelto no tiene permiso."""
    if getattr(sys, "frozen", False):
        try:
            rumps.notification("AK820", titulo, mensaje)
        except Exception:
            pass


class Salida(io.StringIO):
    """Recoge lo que imprime ak820.py, lo copia al registro y apunta el progreso."""

    def __init__(self, al_progresar):
        super().__init__()
        self.al_progresar = al_progresar

    def write(self, texto):
        if sys.__stdout__:
            sys.__stdout__.write(texto)
            sys.__stdout__.flush()
        encontrado = PROGRESO.search(texto)
        if encontrado:
            self.al_progresar(int(encontrado.group(1)))
        return super().write(texto)


class AppAK820(rumps.App):
    def __init__(self):
        super().__init__("AK820", title=TITULO, quit_button="Salir")
        self.candado = threading.Lock()
        self.mensajes = queue.Queue()      # (título, mensaje, bien, avisar) que dejan los hilos
        self.preferencias = cargar_preferencias()
        self.conectado = None               # None hasta la primera comprobación
        self.reloj_pendiente = False        # poner la hora en cuanto el teclado esté libre
        self.hilo = None
        self.progreso = None                # % de la imagen que se está enviando
        self.hecho_hasta = 0                # hasta cuándo se ve el ✓ en el icono
        self.brillo = 5
        self.ultima_luz = None              # (efecto, color) para reaplicar al cambiar el brillo
        self.editor = ak820_editor.Editor(self.candado)   # se arranca al abrirlo la primera vez
        self.ventana = None                                 # la ventana propia, al abrirla

        self.item_estado = rumps.MenuItem("Comprobar teclado", callback=self.comprobar)
        self.items_brillo = {}
        self.menu = [
            self.item_estado,
            rumps.MenuItem("Abrir AK820…", callback=self.abrir_editor),
            None,
            self.menu_reloj(),
            self.menu_luces(),
            rumps.MenuItem("Imagen o GIF en la pantalla…", callback=self.imagen),
            self.menu_reposo(),
            self.menu_sistema(),
            self.menu_teclas(),
            None,
        ]
        rumps.Timer(self.atender, 0.3).start()
        rumps.Timer(self.vigilar, SEGUNDOS_VIGILAR).start()

    # --- Construcción del menú -------------------------------------------------
    def menu_reloj(self):
        reloj = rumps.MenuItem("Reloj")
        reloj.add(rumps.MenuItem("Poner en hora ahora", callback=self.reloj))
        self.item_hora_auto = rumps.MenuItem("Ponerla sola al conectar el teclado",
                                             callback=self.cambiar_hora_auto)
        self.item_hora_auto.state = int(self.preferencias["hora_al_conectar"])
        reloj.add(self.item_hora_auto)
        reloj.add(None)
        aviso = rumps.MenuItem("(no se pone sola si la pantalla tiene una imagen)")
        reloj.add(aviso)
        return reloj

    def menu_luces(self):
        luces = rumps.MenuItem("Luces")
        for nombre, efecto in EFECTOS_CON_COLOR.items():
            sub = rumps.MenuItem(nombre)
            for color, hexa in COLORES.items():
                sub.add(rumps.MenuItem(color, callback=self.accion_luz(efecto, hexa)))
            luces.add(sub)
        luces.add(rumps.MenuItem("Espectro (arcoíris)", callback=self.accion_luz("espectro")))
        luces.add(rumps.MenuItem("Ola de colores", callback=self.accion_luz("rodar")))
        luces.add(rumps.MenuItem("Apagadas", callback=self.accion_luz("apagado")))
        luces.add(None)
        brillo = rumps.MenuItem("Brillo")
        for n in range(1, 6):
            item = rumps.MenuItem(str(n), callback=self.accion_brillo(n))
            item.state = int(n == self.brillo)
            self.items_brillo[n] = item
            brillo.add(item)
        luces.add(brillo)
        return luces

    def menu_reposo(self):
        reposo = rumps.MenuItem("Reposo (solo con batería)")
        for nombre, minutos in REPOSOS.items():
            reposo.add(rumps.MenuItem(nombre, callback=self.accion_reposo(minutos)))
        return reposo

    def menu_sistema(self):
        sistema = rumps.MenuItem("Sistema")
        fn = rumps.MenuItem("Tecla Fn")
        for nombre, modo in MODOS_FN.items():
            fn.add(rumps.MenuItem(nombre, callback=self.accion_sistema(["--fn-modo", modo])))
        sistema.add(fn)
        respuesta = rumps.MenuItem("Tiempo de respuesta de las teclas")
        for n in range(1, 6):
            nombre = f"Nivel {n}" + (" (de fábrica)" if n == 2 else "")
            respuesta.add(rumps.MenuItem(nombre, callback=self.accion_sistema(["--respuesta", str(n)])))
        sistema.add(respuesta)
        sistema.add(None)
        sistema.add(rumps.MenuItem("Ver ajustes actuales", callback=self.accion_sistema([])))
        sistema.add(rumps.MenuItem("Ajustes de fábrica", callback=self.accion_sistema(["--fabrica"])))
        return sistema

    def menu_teclas(self):
        teclas = rumps.MenuItem("Teclas")
        teclas.add(rumps.MenuItem("Editor de teclas…", callback=self.abrir_editor))
        teclas.add(None)
        teclas.add(rumps.MenuItem("Restaurar teclas de fábrica", callback=self.restaurar_teclas))
        teclas.add(rumps.MenuItem("Abrir guía de teclas", callback=self.guia_teclas))
        return teclas

    # --- Acciones ------------------------------------------------------------
    def comprobar(self, _):
        self.ejecutar("Teclado", [["buscar"]], es_comprobacion=True, avisar="siempre")

    def reloj(self, _):
        self.ejecutar("Reloj", [["reloj"]])

    def cambiar_hora_auto(self, item):
        item.state = int(not item.state)
        self.preferencias["hora_al_conectar"] = bool(item.state)
        guardar_preferencias(self.preferencias)

    def accion_luz(self, efecto, color=None):
        def callback(_):
            self.ultima_luz = (efecto, color)
            self.ejecutar("Luces", [args_luces(efecto, color, self.brillo)])
        return callback

    def accion_brillo(self, n):
        def callback(_):
            self.brillo = n
            for m, item in self.items_brillo.items():
                item.state = int(m == n)
            if self.ultima_luz and self.ultima_luz[0] != "apagado":
                efecto, color = self.ultima_luz
                self.ejecutar("Luces", [args_luces(efecto, color, n)])
        return callback

    def accion_sistema(self, opciones):
        def callback(_):
            self.ejecutar("Sistema", [args_sistema(opciones)], avisar="siempre")
        return callback

    def accion_reposo(self, minutos):
        def callback(_):
            self.ejecutar("Reposo", [args_reposo(minutos)], avisar="siempre")
        return callback

    def imagen(self, _):
        ruta = elegir_imagen()
        if ruta:
            self.ejecutar("Pantalla", [args_imagen(ruta)])

    def restaurar_teclas(self, _):
        self.ejecutar("Teclas", args_restaurar_teclas())

    def abrir_editor(self, _):
        url = self.editor.iniciar()
        if self.ventana is None:
            self.ventana = ak820_ventana.Ventana.alloc().initConUrl_(url)
        self.ventana.mostrar()

    def guia_teclas(self, _):
        subprocess.run(["open", GUIA_TECLAS], check=False)

    # --- Ejecución en segundo plano -------------------------------------------
    def ejecutar(self, titulo, lista_args, es_comprobacion=False, avisar="error"):
        """Lanza una o varias órdenes de ak820.py en un hilo. False si ya hay una en curso.

        avisar: "siempre" (el resultado sale en una ventana), "error" (solo si falla) o
        "nunca" (para lo que hace la app por su cuenta; queda en el registro)."""
        if not self.candado.acquire(blocking=False):
            if avisar != "nunca":
                ventana(titulo, "Espera: hay otra operación en curso.")
            return False
        self.progreso = None
        self.title = TITULO_OCUPADO
        self.hilo = threading.Thread(target=self._trabajo,
                                     args=(titulo, lista_args, es_comprobacion, avisar), daemon=True)
        self.hilo.start()
        return True

    def _trabajo(self, titulo, lista_args, es_comprobacion, avisar):
        try:
            mensajes = []
            codigo = 0
            for argumentos in lista_args:
                salida = Salida(self.apuntar_progreso)
                with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
                    try:
                        codigo = ak820.main(argumentos) or 0
                    except SystemExit as e:          # argparse sale así si algo no cuadra
                        codigo = e.code if isinstance(e.code, int) else 1
                    except Exception as e:           # p. ej. el teclado se desconecta a medias
                        print(f"Error: {e}")
                        codigo = 1
                mensajes.append(resumen(salida.getvalue(), codigo, solo_ultima=es_comprobacion,
                                        completo=avisar == "siempre"))
                if codigo != 0:
                    break
            self.mensajes.put((titulo, "\n".join(dict.fromkeys(mensajes)), codigo == 0, avisar))
        finally:
            self.candado.release()

    def apuntar_progreso(self, porcentaje):
        self.progreso = porcentaje

    def atender(self, _):
        """Temporizador del hilo principal: aplica lo que dejan los hilos."""
        if self.candado.locked():
            self.title = TITULO_OCUPADO if self.progreso is None else f"⌨︎ {self.progreso} %"
        elif time.monotonic() < self.hecho_hasta:
            self.title = TITULO_HECHO
        else:
            self.title = TITULO
        while not self.mensajes.empty():
            titulo, mensaje, bien, avisar = self.mensajes.get()
            if bien:
                self.hecho_hasta = time.monotonic() + SEGUNDOS_HECHO
                self.title = TITULO_HECHO
                if titulo == "Pantalla":            # tarda: avisa por si estás en otra cosa
                    notificar("Pantalla", "La imagen ya está en la pantalla del teclado.")
            if avisar == "siempre" or (avisar == "error" and not bien):
                ventana(titulo, mensaje)

    def vigilar(self, _):
        """Temporizador: ve si el teclado está conectado por cable y, al conectarlo, pone la hora."""
        try:
            conectado = ak820.buscar_interfaz() is not None
        except Exception:                    # hidapi puede fallar un instante al (des)conectar
            return
        if conectado != self.conectado:
            self.conectado = conectado
            self.item_estado.title = ("Teclado: conectado por cable ✓" if conectado
                                      else "Teclado: sin conectar por cable")
            self.reloj_pendiente = conectado
        if self.reloj_pendiente and not self.candado.locked():
            self.reloj_pendiente = False
            if self.preferencias["hora_al_conectar"] and ak820.modo_pantalla() == "reloj":
                if not self.ejecutar("Reloj", [["reloj"]], avisar="nunca"):
                    self.reloj_pendiente = True


def elegir_imagen():
    """Selector de archivos de macOS; devuelve la ruta elegida o None."""
    from AppKit import NSApp, NSOpenPanel, NSModalResponseOK
    panel = NSOpenPanel.openPanel()
    panel.setTitle_("Elige una imagen o un GIF para la pantalla del teclado")
    panel.setAllowedFileTypes_(TIPOS_IMAGEN)
    panel.setAllowsMultipleSelection_(False)
    NSApp.activateIgnoringOtherApps_(True)      # que el selector salga delante
    if panel.runModal() == NSModalResponseOK:
        return panel.URLs()[0].path()
    return None


def main():
    if getattr(sys, "frozen", False):
        # En AK820.app nadie recoge la salida: se manda al registro, como hace el .command.
        registro = open(REGISTRO, "a", buffering=1)
        os.dup2(registro.fileno(), 1)
        os.dup2(registro.fileno(), 2)
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    # Sin icono en el Dock: solo en la barra de menús.
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    AppAK820().run()


if __name__ == "__main__":
    main()
