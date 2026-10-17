#!/usr/bin/env python3
"""App de la barra de menús para el Ajazz AK820 (usa ak820.py por debajo).

Cada opción del menú llama a ak820.main([...]) en un hilo aparte (para no
congelar el menú), recoge lo que imprime y lo enseña como notificación.
Solo se hace una operación a la vez: el teclado no admite dos conversaciones
seguidas sin terminar la anterior.

Los cambios de la interfaz (título, notificaciones) se hacen siempre desde el
hilo principal, con un temporizador que recoge lo que dejan los hilos.
"""
import contextlib
import io
import os
import queue
import subprocess
import threading

import rumps

import ak820

CARPETA = os.path.dirname(os.path.abspath(__file__))
GUIA_TECLAS = os.path.join(CARPETA, "docs", "teclas.md")

TITULO = "⌨︎"
TITULO_OCUPADO = "⌨︎…"

COLORES = {
    "Rojo": "FF0000", "Verde": "00FF00", "Azul": "0000FF", "Blanco": "FFFFFF",
    "Morado": "8000FF", "Naranja": "FF6000", "Cian": "00FFFF",
}
EFECTOS_CON_COLOR = {"Fijo": "fijo", "Respirar": "respirar"}
REPOSOS = {"1 minuto": "1", "5 minutos": "5", "30 minutos": "30", "Nunca": "nunca"}
TIPOS_IMAGEN = ["png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff"]


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


def args_imagen(ruta):
    return ["imagen", ruta]


def args_restaurar_teclas():
    """Las dos capas de teclas de fábrica (normal y con Fn)."""
    return [["teclas", "restaurar"], ["teclas", "--fn", "restaurar"]]


def resumen(salida, codigo, solo_ultima=False):
    """Las líneas útiles de lo que imprime ak820.py, para una notificación."""
    lineas = [l.strip() for l in salida.splitlines() if l.strip()]
    errores = [l.split("error:", 1)[1].strip() for l in lineas if "error:" in l]
    if errores:                                    # error de argumentos (argparse)
        return "Error: " + errores[-1]
    lineas = [l for l in lineas if "% enviado" not in l and not l.startswith("Para volver")
              and not l.startswith("(Cada vez")]
    if codigo != 0 and any("No encuentro el teclado" in l or "No veo ningún" in l for l in lineas):
        return "No encuentro el teclado. Conéctalo por cable USB-C (la configuración no va por Bluetooth)."
    lineas = lineas[-1:] if solo_ultima else lineas[-3:]
    return " ".join(lineas) or ("Hecho." if codigo == 0 else "Algo ha fallado.")


def notificar(titulo, mensaje):
    """Notificación de macOS. Sin identificador de app (Python suelto) usa osascript."""
    from Foundation import NSBundle
    if NSBundle.mainBundle().bundleIdentifier():
        rumps.notification("AK820", titulo, mensaje)
    else:
        texto = mensaje.replace("\\", "\\\\").replace('"', '\\"')
        subtitulo = titulo.replace('"', '\\"')
        subprocess.run(["osascript", "-e",
                        f'display notification "{texto}" with title "AK820" subtitle "{subtitulo}"'],
                       check=False)


class AppAK820(rumps.App):
    def __init__(self):
        super().__init__("AK820", title=TITULO, quit_button="Salir")
        self.candado = threading.Lock()
        self.mensajes = queue.Queue()      # (título, mensaje) que dejan los hilos
        self.estado_teclado = None          # texto para el primer elemento del menú
        self.hilo = None
        self.brillo = 5
        self.ultima_luz = None              # (efecto, color) para reaplicar al cambiar el brillo

        self.item_estado = rumps.MenuItem("Comprobar teclado", callback=self.comprobar)
        self.items_brillo = {}
        self.menu = [
            self.item_estado,
            None,
            rumps.MenuItem("Poner el reloj en hora", callback=self.reloj),
            self.menu_luces(),
            rumps.MenuItem("Imagen o GIF en la pantalla…", callback=self.imagen),
            self.menu_reposo(),
            self.menu_teclas(),
            None,
        ]
        rumps.Timer(self.atender, 0.3).start()

    # --- Construcción del menú -------------------------------------------------
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

    def menu_teclas(self):
        teclas = rumps.MenuItem("Teclas")
        teclas.add(rumps.MenuItem("Restaurar teclas de fábrica", callback=self.restaurar_teclas))
        teclas.add(rumps.MenuItem("Abrir guía de teclas", callback=self.guia_teclas))
        return teclas

    # --- Acciones ------------------------------------------------------------
    def comprobar(self, _):
        self.ejecutar("Teclado", [["buscar"]], es_comprobacion=True)

    def reloj(self, _):
        self.ejecutar("Reloj", [["reloj"]])

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

    def accion_reposo(self, minutos):
        def callback(_):
            self.ejecutar("Reposo", [args_reposo(minutos)])
        return callback

    def imagen(self, _):
        ruta = elegir_imagen()
        if ruta:
            if self.ejecutar("Pantalla", [args_imagen(ruta)]):
                notificar("Pantalla", "Enviando… un GIF grande puede tardar hasta 30 s.")

    def restaurar_teclas(self, _):
        self.ejecutar("Teclas", args_restaurar_teclas())

    def guia_teclas(self, _):
        subprocess.run(["open", GUIA_TECLAS], check=False)

    # --- Ejecución en segundo plano -------------------------------------------
    def ejecutar(self, titulo, lista_args, es_comprobacion=False):
        """Lanza una o varias órdenes de ak820.py en un hilo. False si ya hay una en curso."""
        if not self.candado.acquire(blocking=False):
            notificar(titulo, "Espera: hay otra operación en curso.")
            return False
        self.title = TITULO_OCUPADO
        self.hilo = threading.Thread(target=self._trabajo, args=(titulo, lista_args, es_comprobacion),
                                     daemon=True)
        self.hilo.start()
        return True

    def _trabajo(self, titulo, lista_args, es_comprobacion):
        try:
            mensajes = []
            codigo = 0
            for argumentos in lista_args:
                salida = io.StringIO()
                with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
                    try:
                        codigo = ak820.main(argumentos) or 0
                    except SystemExit as e:          # argparse sale así si algo no cuadra
                        codigo = e.code if isinstance(e.code, int) else 1
                    except Exception as e:           # p. ej. el teclado se desconecta a medias
                        print(f"Error: {e}")
                        codigo = 1
                mensajes.append(resumen(salida.getvalue(), codigo, solo_ultima=es_comprobacion))
                if codigo != 0:
                    break
            if es_comprobacion:
                self.estado_teclado = ("Teclado: conectado por cable ✓" if codigo == 0
                                       else "Teclado: no está conectado por cable")
            self.mensajes.put((titulo, " ".join(dict.fromkeys(mensajes))))
        finally:
            self.candado.release()

    def atender(self, _):
        """Temporizador del hilo principal: aplica lo que dejan los hilos."""
        self.title = TITULO_OCUPADO if self.candado.locked() else TITULO
        if self.estado_teclado:
            self.item_estado.title = self.estado_teclado
        while not self.mensajes.empty():
            notificar(*self.mensajes.get())


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
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    # Sin icono en el Dock: solo en la barra de menús.
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    AppAK820().run()


if __name__ == "__main__":
    main()
