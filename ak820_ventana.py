"""Ventana propia de la app: la página del editor dentro de un WKWebView (el motor de Safari).

Mientras la ventana está abierta, la app sale en el Dock y en Cmd+Tab, y tiene menú
Edición (sin él no funcionan Cmd+C / Cmd+V en los campos de texto). Al cerrarla vuelve a
ser solo el icono de la barra de menús. Si hay cambios sin enviar, pregunta antes.
"""
import objc
from AppKit import (NSAlert, NSAlertFirstButtonReturn, NSApp, NSApplicationActivationPolicyAccessory,
                    NSApplicationActivationPolicyRegular, NSBackingStoreBuffered, NSMakeRect, NSMakeSize,
                    NSMenu, NSMenuItem, NSModalResponseOK, NSOpenPanel, NSWindow, NSWindowStyleMaskClosable,
                    NSWindowStyleMaskMiniaturizable, NSWindowStyleMaskResizable, NSWindowStyleMaskTitled)
from Foundation import NSObject, NSURL, NSURLRequest
from WebKit import WKWebView, WKWebViewConfiguration

ESTILO = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
          NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable)
HAY_CAMBIOS = "(typeof catalogo !== 'undefined' && catalogo && typeof pendientes === 'function') ? pendientes() : 0"


def menu_principal():
    """Menú de la app mientras la ventana está abierta: AK820 y Edición."""
    principal = NSMenu.alloc().init()

    def submenu(titulo, elementos):
        item = NSMenuItem.alloc().init()
        menu = NSMenu.alloc().initWithTitle_(titulo)
        for texto, accion, tecla in elementos:
            if texto is None:
                menu.addItem_(NSMenuItem.separatorItem())
            else:
                menu.addItemWithTitle_action_keyEquivalent_(texto, accion, tecla)
        item.setSubmenu_(menu)
        principal.addItem_(item)

    submenu("AK820", [("Cerrar ventana", "performClose:", "w"), (None, None, None),
                      ("Salir de AK820", "terminate:", "q")])
    submenu("Edición", [("Deshacer", "undo:", "z"), ("Rehacer", "redo:", "Z"), (None, None, None),
                        ("Cortar", "cut:", "x"), ("Copiar", "copy:", "c"), ("Pegar", "paste:", "v"),
                        ("Seleccionar todo", "selectAll:", "a")])
    return principal


class Ventana(NSObject):
    """Crea la ventana la primera vez y la reutiliza después."""

    def initConUrl_(self, url):
        self = objc.super(Ventana, self).init()
        if self is None:
            return None
        self.url = url
        self.ventana = None
        self.web = None
        self.cerrar_ya = False
        return self

    def mostrar(self):
        if self.ventana is None:
            self.ventana = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(0, 0, 1120, 800), ESTILO, NSBackingStoreBuffered, False)
            self.ventana.setTitle_("AK820")
            self.ventana.setMinSize_(NSMakeSize(760, 560))
            self.ventana.setReleasedWhenClosed_(False)
            self.ventana.setDelegate_(self)
            self.ventana.center()
            self.ventana.setFrameAutosaveName_("AK820Ventana")      # recuerda tamaño y posición
            self.web = WKWebView.alloc().initWithFrame_configuration_(
                self.ventana.contentView().bounds(), WKWebViewConfiguration.alloc().init())
            self.web.setAutoresizingMask_(2 | 16)                    # ancho y alto flexibles
            self.web.setUIDelegate_(self)
            self.ventana.contentView().addSubview_(self.web)
            self.web.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(self.url)))
        self.cerrar_ya = False
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        NSApp.setMainMenu_(menu_principal())
        NSApp.activateIgnoringOtherApps_(True)
        self.ventana.makeKeyAndOrderFront_(None)

    def cambiarUrl_(self, url):
        """La dirección cambia si el servidor se ha reiniciado (otra clave)."""
        self.url = url
        if self.web is not None:
            self.web.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(url)))

    # --- Cerrar ------------------------------------------------------------------
    def windowShouldClose_(self, ventana):
        if self.cerrar_ya:
            return True

        def respuesta(cambios, _error):
            if cambios:
                aviso = NSAlert.alloc().init()
                aviso.setMessageText_("Hay cambios sin enviar al teclado")
                aviso.setInformativeText_("Si cierras la ventana, se pierden.")
                aviso.addButtonWithTitle_("Cerrar igualmente")
                aviso.addButtonWithTitle_("Cancelar")
                if aviso.runModal() != NSAlertFirstButtonReturn:
                    return
            self.cerrar_ya = True
            ventana.close()

        self.web.evaluateJavaScript_completionHandler_(HAY_CAMBIOS, respuesta)
        return False

    def windowWillClose_(self, _aviso):
        # Al cerrarla se vuelve a cargar la página: la próxima vez se abre con lo último.
        self.web.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(self.url)))
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    # --- Diálogos que pide la página (WKUIDelegate) ----------------------------------
    def webView_runJavaScriptAlertPanelWithMessage_initiatedByFrame_completionHandler_(self, _web, mensaje, _marco, listo):
        aviso = NSAlert.alloc().init()
        aviso.setMessageText_(mensaje)
        aviso.runModal()
        listo()

    def webView_runJavaScriptConfirmPanelWithMessage_initiatedByFrame_completionHandler_(self, _web, mensaje, _marco, listo):
        aviso = NSAlert.alloc().init()
        aviso.setMessageText_(mensaje)
        aviso.addButtonWithTitle_("Aceptar")
        aviso.addButtonWithTitle_("Cancelar")
        listo(aviso.runModal() == NSAlertFirstButtonReturn)

    def webView_runOpenPanelWithParameters_initiatedByFrame_completionHandler_(self, _web, parametros, _marco, listo):
        """Para los <input type="file"> de la página (elegir una imagen o un GIF)."""
        panel = NSOpenPanel.openPanel()
        panel.setAllowsMultipleSelection_(parametros.allowsMultipleSelection())
        panel.beginSheetModalForWindow_completionHandler_(
            self.ventana, lambda resultado: listo(panel.URLs() if resultado == NSModalResponseOK else None))
