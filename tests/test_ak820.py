"""Pruebas sin teclado: formatos de los paquetes y secuencias de envío.

Un teclado falso apunta lo que recibe y responde a la orden de cerrar (04 02) con la
suma de los bytes recibidos, como el de verdad. Así se comprueba todo el camino sin
tocar el AK820.

    .venv/bin/python -m unittest discover -s tests
"""
import io
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from unittest import mock

import ak820

# Órdenes que van seguidas de paquetes de datos sin respuesta (cuántos: byte 8).
CON_DATOS = {0x11, 0x27, 0x15, 0x17, 0x13, 0x28, 0x23, 0x20}


class TecladoFalso:
    def __init__(self, fallos=0):
        self.paquetes = []          # ("orden" | "dato", 64 bytes)
        self.pendientes = 0
        self.suma = 0
        self.fallos = fallos        # cuántos 04 02 responden con una suma mal
        self.respuesta = bytes(65)
        self.bloques = []           # lo que llega por la interfaz de datos (imagen)

    def recibir(self, datos):
        assert datos[0] == 0 and len(datos) == 65, "falta el report id o el tamaño no es 64"
        p = datos[1:]
        if self.pendientes:
            self.pendientes -= 1
            self.suma += sum(p)
            self.paquetes.append(("dato", p))
            return
        assert p[0] == 0x04, f"se esperaba una orden y llega {p[:4].hex()}"
        self.paquetes.append(("orden", p))
        respuesta = bytearray(65)
        if p[1] in CON_DATOS:
            self.pendientes, self.suma = p[8], 0
        elif p[1] == 0x02:
            suma = self.suma + (1 if self.fallos else 0)
            self.fallos = max(0, self.fallos - 1)
            respuesta[5:7] = (suma & 0xFFFF).to_bytes(2, "little")
        self.respuesta = bytes(respuesta)

    def ordenes(self):
        return [p[1] for tipo, p in self.paquetes if tipo == "orden"]

    def datos(self):
        return b"".join(p for tipo, p in self.paquetes if tipo == "dato")


class Conexion:
    def __init__(self, teclado):
        self.teclado = teclado

    def open_path(self, _ruta):
        pass

    def close(self):
        pass

    def send_feature_report(self, datos):
        self.teclado.recibir(bytes(datos))
        return len(datos)

    def get_feature_report(self, _id, _n):
        return list(self.teclado.respuesta)

    def write(self, datos):
        self.teclado.bloques.append(bytes(datos))
        return len(datos)

    def read(self, _n, _espera=0):
        return [0x01, 0x5A, 0x02]      # el "recibido" de cada bloque


class ReceptorFalso:
    """Imita el receptor 2.4G: apunta las tramas y contesta repitiendo sus 3 primeros bytes."""

    def __init__(self, sin_respuesta=False):
        self.tramas = []
        self.sin_respuesta = sin_respuesta

    def open_path(self, _ruta):
        pass

    def close(self):
        pass

    def write(self, datos):
        assert len(datos) == 33 and datos[0] == 0, "se esperan 33 bytes con el report id 0"
        trama = bytes(datos[1:])
        assert trama[31] == sum(trama[:31]) & 0xFF, "la suma del byte 31 no cuadra"
        self.tramas.append(trama)
        return len(datos)

    def read(self, _n, _espera=0):
        if self.sin_respuesta or not self.tramas:
            return []
        return list(self.tramas[-1][:3]) + [0] * 29

    def ordenes(self):
        return [t[0] for t in self.tramas]


class HidFalso:
    def __init__(self, teclado, receptor=None):
        self.teclado = teclado
        self.receptor = receptor            # con receptor: está por 2.4G, no por cable

    def enumerate(self, _vid=0):
        if self.receptor is not None:
            return [{"product_id": 0xFDFD, "usage_page": 0xFF60, "path": b"rx", "interface_number": 3, "product_string": "2.4G Dongle"}]
        return [{"product_id": 0x800A, "usage_page": 0xFF13, "path": b"cfg", "interface_number": 3, "product_string": "AK820"},
                {"product_id": 0x800A, "usage_page": 0xFF68, "path": b"dat", "interface_number": 2, "product_string": "AK820"}]

    def device(self):
        return self.receptor if self.receptor is not None else Conexion(self.teclado)


class ConTecladoFalso(unittest.TestCase):
    """Cada prueba tiene su teclado falso, sin esperas y con los archivos en una carpeta temporal."""

    fallos = 0
    receptor = None                         # una clase de receptor falso para probar el 2.4G

    def setUp(self):
        self.teclado = TecladoFalso(self.fallos)
        self.rx = self.receptor() if self.receptor else None
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        for parche in (mock.patch.object(ak820, "hid", HidFalso(self.teclado, self.rx)),
                       mock.patch.object(ak820.time, "sleep", lambda _s: None),
                       mock.patch.object(ak820, "TECLAS_GUARDADAS", os.path.join(carpeta.name, "teclas.json")),
                       mock.patch.object(ak820, "AJUSTES_GUARDADOS", os.path.join(carpeta.name, "sistema.json")),
                       mock.patch.object(ak820, "PANTALLA_GUARDADA", os.path.join(carpeta.name, "pantalla.json")),
                       mock.patch.object(ak820, "LUCES_GUARDADAS", os.path.join(carpeta.name, "luces.json")),
                       mock.patch.object(ak820, "COLORES_GUARDADOS", os.path.join(carpeta.name, "colores.json"))):
            parche.start()
            self.addCleanup(parche.stop)

    def orden(self, *argumentos):
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = ak820.main(list(argumentos))
        return codigo, salida.getvalue()


# --- Formatos -----------------------------------------------------------------
class Formatos(unittest.TestCase):
    def test_paquete_control(self):
        p = ak820.paquete_control(0x11, byte2=0x05, byte8=0x09)
        self.assertEqual(len(p), 64)
        self.assertEqual((p[0], p[1], p[2], p[8]), (0x04, 0x11, 0x05, 0x09))

    def test_entradas_de_tecla(self):
        casos = {
            "b": "02 00 05 00", "cmd+a": "02 08 04 00", "ctrl+shift+t": "02 03 17 00",
            "shift": "02 02 00 00", "volumen+": "03 e9 00 00", "play": "03 cd 00 00",
            "clic_der": "01 01 02 00", "clic_medio": "01 01 04 00", "rueda_abajo": "01 03 ff 00",
            "multi:a+s": "07 04 16 00", "multi:shift+a": "02 02 04 00", "multi:cmd+shift+4": "02 0a 21 00",
        }
        for destino, esperado in casos.items():
            with self.subTest(destino=destino):
                self.assertEqual(ak820.entrada_tecla(destino).hex(" "), esperado)
        for malo in ("nada", "cmd+", "atras", "multi:a+b+c+d", "rueda_abajo:5"):
            with self.subTest(malo=malo):
                self.assertIsNone(ak820.entrada_tecla(malo))

    def test_tabla_de_teclas(self):
        tabla = ak820.tabla_teclas({ak820.POSICION_TECLA["avpag"]: bytes([2, 0, 5, 0])})
        self.assertEqual(len(tabla), 576)
        self.assertEqual(tabla[121 * 4:121 * 4 + 4], bytes([2, 0, 5, 0]))
        self.assertEqual(tabla[-2:], b"\xaa\x55")

    def test_eventos_de_texto(self):
        eventos = ak820.eventos_texto("Ha")
        # H: pulsar Shift, pulsar h, soltar h, soltar Shift (cada uno con su espera)
        acciones = [e for e in eventos if e[3] != 0x50]
        self.assertEqual([e.hex() for e in acciones],
                         ["0000e1b0", "00000bb0", "00000b30", "0000e130", "000004b0", "00000430"])
        self.assertIsNone(ak820.eventos_texto("ñ"))

    def test_bloque_de_macros(self):
        bloque = ak820.bloque_macros([ak820.eventos_texto("hola"), ak820.eventos_doble_clic()])
        self.assertEqual(len(bloque) % 64, 0)
        self.assertEqual(bloque[-2:], b"\xaa\x55")
        primera = int.from_bytes(bloque[0:2], "little")
        segunda = int.from_bytes(bloque[4:6], "little")
        self.assertEqual(primera, 400)
        self.assertEqual(segunda, 400 + 8 + 4 * len(ak820.eventos_texto("hola")))
        self.assertEqual(bloque[segunda + 8:segunda + 12].hex(), "00000190")   # doble clic: pulsar izquierdo
        self.assertIsNone(ak820.bloque_macros([ak820.eventos_texto("a" * 200)]))  # no cabe

    def test_paquete_de_sistema(self):
        p = ak820.paquete_sistema(dict(ak820.AJUSTES_DEFECTO, reposo=1))
        self.assertEqual(p[:9].hex(" "), "00 01 00 00 00 00 01 00 02")
        self.assertEqual(p[-2:], b"\xaa\x55")
        self.assertEqual(sum(p), 0x103)          # la suma que dio el teclado de verdad

    def test_imagen_rgb565(self):
        from PIL import Image
        pixeles = ak820.pixeles_rgb565(Image.new("RGB", (300, 200), "red"))
        self.assertEqual(len(pixeles), 128 * 128 * 2)
        self.assertEqual(pixeles[:2], b"\x00\xf8")      # 0xF800 en little-endian

    def test_bloques_de_gif(self):
        lista = [(b"\x00" * 32768, 100), (b"\x00" * 32768, 30)]
        bloques = ak820.bloques_imagen(lista)
        self.assertEqual(len(bloques), 17)                # 256 + 2 × 32768 bytes → 17 × 4096
        self.assertTrue(all(len(b) == 4096 for b in bloques))
        self.assertEqual(bloques[0][:4], bytes([2, 50, 15, 0xFF]))   # n.º de fotogramas y ms/2


class PrepararTeclas(unittest.TestCase):
    def test_macros_compartidas_entre_capas(self):
        config = {"normal": {"avpag": {"destino": "texto:hola", "modo": "mantener"}},
                  "fn": {"avpag": {"destino": "texto:adios"}, "repag": {"destino": "doble_clic"}}}
        tablas, macros = ak820.preparar_teclas(config)
        posicion = ak820.POSICION_TECLA["avpag"] * 4
        self.assertEqual(tablas["normal"][posicion:posicion + 4].hex(" "), "06 00 03 01")
        self.assertEqual(tablas["fn"][posicion:posicion + 4].hex(" "), "06 01 00 01")
        self.assertEqual(len(macros), 3)                                     # hola, adios y el doble clic

    def test_errores(self):
        for config, texto in [({"fn": {"supr": {"destino": "b"}}}, "no se puede cambiar"),
                              ({"fn": {"borrar": {"destino": "b"}}}, "no se puede cambiar"),
                              ({"normal": {"zz": {"destino": "b"}}}, "No conozco"),
                              ({"normal": {"avpag": {"destino": "texto:ñ"}}}, "No sé escribir"),
                              ({"normal": {"avpag": {"destino": "nada"}}}, "No entiendo")]:
            with self.subTest(config=config):
                with self.assertRaisesRegex(ValueError, texto):
                    ak820.preparar_teclas(config)


# --- Secuencias de envío (con el teclado falso) -----------------------------------------
class EnvioDeTeclas(ConTecladoFalso):
    def test_secuencia_completa(self):
        config = {"normal": {"avpag": {"destino": "texto:hola"}}, "fn": {"repag": {"destino": "b"}}}
        with redirect_stdout(io.StringIO()):
            self.assertTrue(ak820.enviar_teclas(config))
        ordenes = self.teclado.ordenes()
        # macros (sin 04 18), capa normal y capa Fn, cada una cerrada (02) y guardada (F0)
        self.assertEqual(ordenes, [0x19, 0x15, 0x02, 0x18, 0x11, 0x02, 0xF0, 0x18, 0x27, 0x02, 0xF0])
        self.assertEqual(ak820.cargar_teclas(), config)

    def test_la_orden_teclas_suma_cambios(self):
        self.assertEqual(self.orden("teclas", "avpag=b")[0], 0)
        self.assertEqual(self.orden("teclas", "--fn", "repag=play")[0], 0)
        self.assertEqual(self.orden("teclas", "supr=texto:hola", "--modo", "alternar")[0], 0)
        self.assertEqual(ak820.cargar_teclas(), {
            "normal": {"avpag": {"destino": "b"},
                       "supr": {"destino": "texto:hola", "modo": "alternar", "veces": 1}},
            "fn": {"repag": {"destino": "play"}}})
        self.orden("teclas", "pgdn=defecto")                       # alias de avpag
        self.assertNotIn("avpag", ak820.cargar_teclas()["normal"])
        self.orden("teclas", "restaurar")
        self.assertEqual(ak820.cargar_teclas(), {"normal": {}, "fn": {"repag": {"destino": "play"}}})
        self.orden("teclas", "restaurar", "todo")
        self.assertEqual(ak820.cargar_teclas(), {"normal": {}, "fn": {}})

    def test_error_no_toca_el_teclado(self):
        codigo, salida = self.orden("teclas", "--fn", "supr=b")
        self.assertEqual(codigo, 1)
        self.assertIn("no se puede cambiar", salida)
        self.assertEqual(self.teclado.paquetes, [])

    def test_sin_teclado(self):
        with mock.patch.object(ak820.hid, "enumerate", lambda _vid=0: []):
            codigo, salida = self.orden("teclas", "avpag=b")
        self.assertEqual(codigo, 1)
        self.assertIn("No encuentro el teclado", salida)
        self.assertEqual(ak820.cargar_teclas(), {"normal": {}, "fn": {}})   # no se guarda


class EnvioConFallos(ConTecladoFalso):
    fallos = 1

    def test_reintenta_si_la_suma_no_cuadra(self):
        codigo, salida = self.orden("teclas", "avpag=b")
        self.assertEqual(codigo, 0)
        self.assertIn("repitiendo", salida)
        self.assertEqual(self.teclado.ordenes().count(0x11), 2)


class Colores(ConTecladoFalso):
    def test_tabla(self):
        tabla = ak820.tabla_colores({"fondo": "000010", "teclas": {"avpag": "FF0000", "fn": "00FF00"}, "brillo": 5})
        self.assertEqual(len(tabla), 576)
        self.assertEqual(tabla[121 * 4:121 * 4 + 4].hex(" "), "79 ff 00 00")   # AvPág
        self.assertEqual(tabla[96 * 4:96 * 4 + 4].hex(" "), "60 00 ff 00")     # Fn
        self.assertEqual(tabla[1 * 4:1 * 4 + 4].hex(" "), "01 00 00 10")       # Esc, con el fondo
        self.assertEqual(tabla[0:4], bytes(4))                                 # hueco sin tecla
        self.assertEqual(tabla[-2:], b"\xaa\x55")

    def test_orden_colores(self):
        codigo, _ = self.orden("colores", "avpag=ff0000", "pgup=#00FF00", "--brillo", "3")
        self.assertEqual(codigo, 0)
        # efecto "personal" (18 13 datos 02 F0) y luego la tabla (18 23 ×9 02 F0)
        self.assertEqual(self.teclado.ordenes(), [0x18, 0x13, 0x02, 0xF0, 0x18, 0x23, 0x02, 0xF0])
        datos = self.teclado.datos()
        self.assertEqual((datos[0], datos[9]), (0x80, 3))
        self.assertEqual(ak820.cargar_colores()["teclas"], {"avpag": "FF0000", "repag": "00FF00"})
        self.assertEqual(ak820.cargar_luces()["efecto"], "personal")
        self.orden("colores", "avpag=defecto", "--fondo", "0000FF")
        self.assertEqual(ak820.cargar_colores(), {"fondo": "0000FF", "teclas": {"repag": "00FF00"}, "brillo": 3})
        self.orden("colores", "restaurar")
        self.assertEqual(ak820.cargar_colores(), {"fondo": "000000", "teclas": {}, "brillo": 3})

    def test_errores(self):
        for argumentos in (["avpag=rojo"], ["zz=FF0000"], ["--fondo", "123"]):
            with self.subTest(argumentos=argumentos):
                self.assertEqual(self.orden("colores", *argumentos)[0], 1)
        self.assertEqual(self.teclado.paquetes, [])


class Receptor24G(ConTecladoFalso):
    receptor = ReceptorFalso

    def test_trama(self):
        trama = next(ak820.tramas_24g(0x05, ak820.datos_24g(ak820.paquete_luces(0x07, 255, 0, 0, False, 5, 0, 0))))
        # la que funcionó en el teclado de verdad (luces fijas en rojo)
        self.assertEqual(trama.hex(" "), "05 10 00 07 ff 00 00 00 00 00 00 00 05 00 00 00 00 aa 55 "
                                         "00 00 00 00 00 00 00 00 00 00 00 00 1f")

    def test_luces_ajustes_y_reloj(self):
        self.assertEqual(self.orden("luces", "fijo", "--color", "00FF00")[0], 0)
        self.assertEqual(self.orden("sistema", "--fn-modo", "alternar")[0], 0)
        self.assertEqual(self.orden("reloj", "--hora", "2026-10-17 09:30")[0], 0)   # sábado
        self.assertEqual(self.rx.ordenes(), [0x05, 0x07, 0x0C])
        luces, sistema, reloj = self.rx.tramas
        self.assertEqual(luces[3:8].hex(" "), "07 00 ff 00 00")
        self.assertEqual(sistema[3:12].hex(" "), "00 01 00 00 00 01 02 00 02")
        self.assertEqual(reloj[3:17].hex(" "), "00 01 5a 1a 0a 11 09 1e 00 00 06 00 00 00")
        self.assertEqual(reloj[17:19], b"\xaa\x55")
        self.assertEqual(self.teclado.paquetes, [])                  # nada por el cable
        self.assertEqual(ak820.cargar_ajustes()["fn"], 1)

    def test_teclas_y_macros(self):
        self.assertEqual(self.orden("teclas", "avpag=texto:hola", "repag=b")[0], 0)
        ordenes = self.rx.ordenes()
        macros = [t for t in self.rx.tramas if t[0] == 0x09]
        normal = [t for t in self.rx.tramas if t[0] == 0x10]
        self.assertEqual((len(normal), ordenes.count(0x12)), (21, 21))   # 20 trozos de 28 y uno de 16
        self.assertEqual([t[1] for t in normal[-2:]], [28, 16])
        self.assertEqual([t[2] for t in normal], list(range(21)))
        self.assertEqual(b"".join(t[3:3 + t[1]] for t in normal)[121 * 4:121 * 4 + 4].hex(" "), "06 00 00 01")
        self.assertEqual(ordenes[:len(macros)], [0x09] * len(macros))  # las macros, lo primero
        self.assertEqual(macros[-1][1], ak820.longitud_macros([ak820.eventos_texto("hola")]) % 28)
        self.assertEqual(ak820.cargar_teclas()["normal"]["repag"], {"destino": "b"})

    def test_colores_e_imagen_no(self):
        codigo, salida = self.orden("colores", "avpag=FF0000")
        self.assertEqual(codigo, 1)
        self.assertIn("solo se pueden cambiar por cable", salida)
        codigo, salida = self.orden("imagen", "prueba")
        self.assertEqual(codigo, 1)
        self.assertIn("solo se puede cambiar por cable", salida)
        self.assertEqual(self.rx.tramas, [])

    def test_buscar(self):
        codigo, salida = self.orden("buscar")
        self.assertEqual(codigo, 0)
        self.assertIn("receptor 2.4G", salida)


class ReceptorSinTeclado(ConTecladoFalso):
    receptor = staticmethod(lambda: ReceptorFalso(sin_respuesta=True))

    def test_sin_respuesta(self):
        codigo, salida = self.orden("luces", "fijo")
        self.assertEqual(codigo, 1)
        self.assertIn("no ha confirmado", salida)
        self.assertEqual(len(self.rx.tramas), 3)                       # lo intenta 3 veces


ESPECTRO_FALSO = """#!/bin/sh
while true; do echo "255 200 150 100 50 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 255"; sleep 0.01; done
"""


class Musica(ConTecladoFalso):
    def setUp(self):
        super().setUp()
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        ruta = os.path.join(carpeta.name, "espectro")
        with open(ruta, "w") as f:
            f.write(ESPECTRO_FALSO)
        os.chmod(ruta, 0o755)
        parche = mock.patch.object(ak820, "ruta_espectro", lambda: ruta)
        parche.start()
        self.addCleanup(parche.stop)

    def test_colores(self):
        teclas = ak820.teclas_con_posicion()
        self.assertEqual(len(teclas), 81)
        bandas = [255] + [0] * 19 + [255]
        colores = dict((p, c) for p, *c in ak820.colores_musica(teclas, bandas, "verde-amarillo-rojo", 0))
        self.assertEqual(colores[ak820.POSICION_LUZ["ctrl"]], [0, 255, 0])      # abajo a la izquierda: verde
        self.assertEqual(colores[ak820.POSICION_LUZ["esc"]], [255, 0, 0])       # arriba a la izquierda: rojo
        self.assertEqual(colores[ak820.POSICION_LUZ["g"]], [0, 0, 0])           # en medio, banda en silencio

    def test_por_cable(self):
        parar = threading.Event()
        threading.Timer(0.5, parar.set).start()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ak820.musica("arcoiris", parar), 0)
        ordenes = self.teclado.ordenes()
        self.assertGreater(ordenes.count(0x20), 2)
        self.assertEqual(set(ordenes), {0x20, 0x02})                  # en vivo: ni 04 18 ni 04 F0
        cuadro = self.teclado.datos()[-512:]
        self.assertIn(cuadro[0], ak820.POSICION_LUZ.values())            # [n.º, R, G, B] seguidos
        self.assertEqual(cuadro[81 * 4:], bytes(512 - 81 * 4))

    def test_servidor(self):
        import ak820_editor
        editor = ak820_editor.Editor()
        bien, _ = editor.empezar_musica("verde-amarillo-rojo")
        self.assertTrue(bien)
        threading.Event().wait(0.3)          # (time.sleep no espera en estas pruebas)
        self.assertEqual(editor.musica_modo, "verde-amarillo-rojo")
        self.assertEqual(editor.orden(["luces", "fijo"]), (False, ak820_editor.OCUPADO_MUSICA))
        editor.parar_musica()
        self.assertIsNone(editor.musica_modo)
        self.assertFalse(editor.candado.locked())
        self.assertIn(0x20, self.teclado.ordenes())


class MusicaPorReceptor(Musica):
    receptor = ReceptorFalso

    def test_por_cable(self):
        pass

    def test_servidor(self):
        pass

    def test_por_receptor(self):
        parar = threading.Event()
        threading.Timer(0.3, parar.set).start()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ak820.musica("rojo", parar), 0)
        trama = self.rx.tramas[-1]
        self.assertEqual(trama[:6].hex(" "), "0b 18 00 07 00 00")            # orden 0B, 24 bytes, modo rojo (7)
        self.assertEqual(trama[6:12].hex(" "), "06 05 04 02 01 00")      # alturas en filas (0-6)


class OtrasOrdenes(ConTecladoFalso):
    def test_sistema(self):
        codigo, _ = self.orden("sistema", "--fn-modo", "alternar")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.teclado.ordenes(), [0x18, 0x17, 0x02])
        self.assertEqual(self.teclado.datos()[5], 1)
        self.assertEqual(ak820.cargar_ajustes()["fn"], 1)

    def test_reloj(self):
        codigo, _ = self.orden("reloj", "--hora", "2026-10-17 12:34")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.teclado.ordenes(), [0x18, 0x28, 0x02])
        self.assertEqual(self.teclado.datos()[3:8], bytes([26, 10, 17, 12, 34]))
        self.assertEqual(ak820.modo_pantalla(), "reloj")

    def test_luces(self):
        codigo, _ = self.orden("luces", "fijo", "--color", "0000FF", "--brillo", "3")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.teclado.ordenes(), [0x18, 0x13, 0xF0])
        datos = self.teclado.datos()
        self.assertEqual((datos[0], datos[3], datos[9], datos[10]), (0x07, 0xFF, 3, 0))
        self.assertEqual(ak820.cargar_luces()["color"], "0000FF")

    def test_imagen(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "foto.png")
            Image.new("RGB", (128, 128), "blue").save(ruta)
            codigo, _ = self.orden("imagen", ruta)
        self.assertEqual(codigo, 0)
        aviso = [p for tipo, p in self.teclado.paquetes if tipo == "orden" and p[1] == 0x72][0]
        self.assertEqual((aviso[2], aviso[8], aviso[9]), (1, 9, 0))       # hueco 1, 9 bloques
        self.assertEqual(len(self.teclado.bloques), 9)
        self.assertTrue(all(len(b) == 4097 for b in self.teclado.bloques))  # 0 + 4096
        self.assertEqual(ak820.modo_pantalla(), "imagen")


# --- App y editor -------------------------------------------------------------------
class App(unittest.TestCase):
    def test_argumentos(self):
        import ak820_app
        self.assertEqual(ak820_app.args_luces("fijo", "FF0000", 3), ["luces", "fijo", "--color", "FF0000", "--brillo", "3"])
        self.assertEqual(ak820_app.args_restaurar_teclas(), [["teclas", "restaurar", "todo"]])

    def test_resumen(self):
        import ak820_app
        self.assertIn("No encuentro el teclado", ak820_app.resumen("No encuentro el teclado por cable.", 1))
        self.assertEqual(ak820_app.resumen("a\nb\nc\nd", 0), "b\nc\nd")
        self.assertEqual(ak820_app.resumen("a\nb\nc\nd", 0, completo=True), "a\nb\nc\nd")


class HoraAlConectar(unittest.TestCase):
    def test_pone_la_hora_al_conectar_solo_con_el_reloj_en_pantalla(self):
        import ak820_app
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        with mock.patch.object(ak820_app, "PREFERENCIAS", os.path.join(carpeta.name, "app.json")), \
             mock.patch.object(ak820, "PANTALLA_GUARDADA", os.path.join(carpeta.name, "pantalla.json")):
            app = ak820_app.AppAK820()
            llamadas = []
            app.ejecutar = lambda _titulo, argumentos, **_kw: llamadas.append(argumentos) or True
            for cable, receptor, modo, esperadas, estado in [
                    (False, False, "reloj", 0, "sin conectar"), (True, False, "reloj", 1, "por cable"),
                    (True, False, "reloj", 1, "por cable"), (False, False, "reloj", 1, "sin conectar"),
                    (True, False, "imagen", 1, "por cable"), (False, True, "reloj", 2, "receptor 2.4G")]:
                ak820.guardar_modo_pantalla(modo)
                with mock.patch.object(ak820, "buscar_interfaz", lambda *_a, c=cable: {"path": b"x"} if c else None), \
                     mock.patch.object(ak820, "buscar_receptor", lambda r=receptor: {"path": b"rx"} if r else None):
                    app.vigilar(None)
                self.assertEqual(len(llamadas), esperadas)
                self.assertIn(estado, app.item_estado.title)
            self.assertEqual(llamadas[0], [["reloj"]])


class Editor(ConTecladoFalso):
    def setUp(self):
        super().setUp()
        import ak820_editor
        parche = mock.patch.object(ak820_editor, "PUERTO", 0)        # un puerto libre cualquiera
        parche.start()
        self.addCleanup(parche.stop)
        self.editor = ak820_editor.Editor()
        self.base = self.editor.iniciar().split("#")[0].rstrip("/")
        self.addCleanup(self.editor.servidor.server_close)      # (las limpiezas van al revés:
        self.addCleanup(self.editor.servidor.shutdown)          #  primero se para, luego se cierra)

    def pedir(self, ruta, cuerpo=None, clave=True, host=None, crudo=None, tipo="image/png"):
        datos = crudo if crudo is not None else json.dumps(cuerpo).encode() if cuerpo is not None else None
        peticion = urllib.request.Request(self.base + ruta, data=datos)
        if clave:
            peticion.add_header("X-Clave", self.editor.clave)
        if datos is not None:
            peticion.add_header("Content-Type", tipo if crudo is not None else "application/json")
        if host:
            peticion.add_header("Host", host)
        try:
            with urllib.request.urlopen(peticion) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_seguridad(self):
        self.assertEqual(self.pedir("/api/estado", clave=False)[0], 403)
        self.assertEqual(self.pedir("/api/estado", host="otra.web:80")[0], 403)
        self.assertEqual(self.pedir("/api/enviar", {"config": {}}, clave=False)[0], 403)
        self.assertEqual(self.teclado.paquetes, [])

    def test_estado_y_envio(self):
        codigo, cuerpo = self.pedir("/api/estado")
        estado = json.loads(cuerpo)
        self.assertEqual(codigo, 200)
        self.assertEqual(len(estado["distribucion"]), 81)
        nombres = {t["nombre"] for t in estado["distribucion"]} - {None}
        self.assertTrue(nombres <= set(ak820.POSICION_TECLA))
        config = {"normal": {"avpag": {"destino": "cmd+a"}}, "fn": {}}
        respuesta = json.loads(self.pedir("/api/enviar", {"config": config})[1])
        self.assertTrue(respuesta["ok"], respuesta)
        self.assertEqual(respuesta["config"], config)
        self.assertIn(0x11, self.teclado.ordenes())

    def test_luces(self):
        respuesta = json.loads(self.pedir("/api/luces", {"luces": {"efecto": "respirar", "color": "#00ff00",
                                                                    "brillo": 4, "velocidad": 2}})[1])
        self.assertTrue(respuesta["ok"], respuesta)
        self.assertEqual(self.teclado.ordenes(), [0x18, 0x13, 0xF0])
        self.assertEqual(respuesta["luces"]["color"], "00FF00")
        for malo in ({"efecto": "nada"}, {"efecto": "fijo", "color": "verde"}, {"efecto": "fijo", "brillo": 9}):
            with self.subTest(malo=malo):
                self.assertFalse(json.loads(self.pedir("/api/luces", {"luces": malo})[1])["ok"])
        self.assertEqual(self.teclado.ordenes(), [0x18, 0x13, 0xF0])     # los malos no llegan

    def test_sistema(self):
        ajustes = {"fn": "alternar", "reposo": "30", "respuesta": 3, "bloquear": {"win": True}}
        respuesta = json.loads(self.pedir("/api/sistema", {"ajustes": ajustes})[1])
        self.assertTrue(respuesta["ok"], respuesta)
        self.assertEqual(respuesta["ajustes"], {"fn": "alternar", "reposo": "30", "respuesta": 3,
                                                "bloquear": {"win": True, "altf4": False, "alttab": False}})
        self.assertEqual(self.teclado.datos()[2:9].hex(" "), "01 00 00 01 03 00 03")
        respuesta = json.loads(self.pedir("/api/sistema", {"ajustes": {"fabrica": True}})[1])
        self.assertEqual(respuesta["ajustes"]["reposo"], "5")

    def test_imagen_y_reloj(self):
        from PIL import Image
        png = io.BytesIO()
        Image.new("RGB", (64, 64), "red").save(png, "PNG")
        respuesta = json.loads(self.pedir("/api/imagen", crudo=png.getvalue())[1])
        self.assertTrue(respuesta["ok"], respuesta)
        self.assertEqual((len(self.teclado.bloques), respuesta["pantalla"]), (9, "imagen"))
        malo = json.loads(self.pedir("/api/imagen", crudo=b"esto no es una imagen")[1])
        self.assertFalse(malo["ok"])
        respuesta = json.loads(self.pedir("/api/reloj", {})[1])
        self.assertEqual((respuesta["ok"], respuesta["pantalla"]), (True, "reloj"))
        conexion = json.loads(self.pedir("/api/conexion")[1])
        self.assertEqual((conexion["conexion"], conexion["ocupado"]), ("cable", False))

    def test_colores(self):
        colores = {"fondo": "#000010", "teclas": {"avpag": "ff0000", "fn": "00FF00"}, "brillo": 4}
        respuesta = json.loads(self.pedir("/api/colores", {"colores": colores})[1])
        self.assertTrue(respuesta["ok"], respuesta)
        self.assertEqual(respuesta["colores"], {"fondo": "000010", "teclas": {"avpag": "FF0000", "fn": "00FF00"}, "brillo": 4})
        self.assertEqual(respuesta["luces"]["efecto"], "personal")
        for malo in ({"teclas": {"zz": "FF0000"}}, {"teclas": {"avpag": "rojo"}}, {"fondo": "1"}, {"brillo": 0}):
            with self.subTest(malo=malo):
                self.assertFalse(json.loads(self.pedir("/api/colores", {"colores": malo})[1])["ok"])

    def test_ocupado(self):
        self.editor.candado.acquire()
        try:
            respuesta = json.loads(self.pedir("/api/luces", {"luces": {"efecto": "fijo"}})[1])
        finally:
            self.editor.candado.release()
        self.assertEqual((respuesta["ok"], respuesta["mensaje"]), (False, "Espera: hay otra operación en curso con el teclado."))

    def test_validar(self):
        bien = json.loads(self.pedir("/api/validar", {"asignacion": {"destino": "texto:hola", "modo": "paso"}})[1])
        mal = json.loads(self.pedir("/api/validar", {"asignacion": {"destino": "texto:ñ"}})[1])
        self.assertTrue(bien["ok"])
        self.assertFalse(mal["ok"])


if __name__ == "__main__":
    unittest.main()
