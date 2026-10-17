#!/usr/bin/env python3
"""Configurador mínimo del teclado Ajazz AK820 Pro para macOS.

Reloj, luces RGB e imagen de la pantalla.

Cómo funciona, en pocas palabras:
  - El teclado se conecta por USB y expone varias "interfaces HID".
  - macOS se queda con las interfaces de teclado normales, pero deja abrir
    dos interfaces "de fabricante" desde un programa normal:
      0xFF13 (configuración): paquetes de 64 bytes ("feature reports").
      0xFF68 (datos): bloques grandes, para las imágenes de la pantalla.
  - Cada cambio es una pequeña conversación: EMPEZAR -> qué vamos a cambiar
    -> los datos -> CONFIRMAR.

El protocolo lo descifró la comunidad (proyectos con licencia MIT):
gohv/EPOMAKER-Ajazz-AK820-Pro, TaxMachine/ajazz-keyboard-software-linux,
Aiacos/ajazz-control-center y gusleig/ajazz-ak820-pro-mac.

Solo funciona con el teclado conectado por CABLE USB-C (no Bluetooth ni 2.4G).
"""
import argparse
import datetime
import json
import os
import sys
import time

import hid  # paquete "hidapi" (pip install hidapi)

# --- Identificación del teclado ---------------------------------------------
VENDOR_ID = 0x0C45          # SONiX, el fabricante del chip
PRODUCT_IDS_CABLE = (0x8009, 0x800A)  # AK820 Pro por cable (según el modelo/firmware)
CONFIG_USAGE_PAGE = 0xFF13  # la interfaz por la que se configura
DATOS_USAGE_PAGE = 0xFF68   # la interfaz por la que van las imágenes

PACKET_SIZE = 64
PAUSA = 0.035               # 35 ms entre paquetes, como el programa oficial

# --- Comandos (byte 1 de los paquetes de control) ---------------------------
CMD_EMPEZAR = 0x18
CMD_CONFIRMAR = 0x02        # cierra la conversación y aplica el cambio
CMD_RELOJ = 0x28
CMD_LUCES = 0x13
CMD_GUARDAR = 0xF0          # guarda en la memoria del teclado (sobrevive al apagado)
CMD_IMAGEN = 0x72

# --- Pantalla ----------------------------------------------------------------
# Formato del programa oficial (grabación USB + análisis, documentado por
# nurlanjalil/ajazz-ak820-config y aar-rafi/aks075-linux):
#  - Imagen de 128x128 píxeles en RGB565 (2 bytes por píxel, little-endian),
#    precedida de 256 bytes de cabecera (n.º de fotogramas + duración de cada uno).
#  - EMPEZAR (byte 8 = 0) y aviso 0x72 con el "hueco" de imagen y el n.º de bloques.
#    En el programa oficial el hueco es la posición elegida en su lista + 1
#    (LCDViewList::GetCurSel() + 1), así que el primero es el 1.
#  - 9 bloques de 4096 bytes por la interfaz 0xFF68. Tras cada uno el teclado
#    responde "01 5a 02" (recibido) y hay que esperarlo antes del siguiente.
#  - Se cierra con CONFIRMAR (0x02). Nada de GUARDAR (0xF0): estropea la imagen.
#  - Clave: esperar 35 ms ANTES de cada orden (lo hace enviar()). Sin esa pausa
#    el teclado ignora el CONFIRMAR final, "carga" y vuelve a sus animaciones.
PANTALLA = 128
CABECERA = 256
BLOQUE = 4096
HUECO_IMAGEN = 1
MAX_FOTOGRAMAS = 140        # límite del teclado (config.xml oficial: gif_maxframes)

# --- Teclas (remapeo dentro del propio teclado) ------------------------------
# Formato del programa oficial (función 0x418420 de DeviceDriver.exe v1.0.0.5),
# probado en el teclado (PgDn -> "b"):
#   EMPEZAR -> 04 11 (capa normal; 04 27 = capa con Fn) con byte 8 = 9
#   -> tabla de 576 bytes (144 teclas x 4, acaba en AA 55) en 9 paquetes de 64,
#      sin leer respuesta -> CONFIRMAR -> GUARDAR.
# Cada tecla ocupa 4 bytes en la posición key_index * 4:
#   00 00 00 00                 = sin cambios (lo de fábrica)
#   02 <modificadores> <tecla> 00 = tecla o combinación (códigos USB HID);
#                                 un modificador solo: 02 <bit> 00 00
#   03 <código lo> <hi> 00        = tecla multimedia (USB "consumer")
#   01 01 <botón> 00 / 01 03 <rueda> 00 = ratón
# OJO: en modo Mac el teclado intercambia por su cuenta Win y Alt. Una tecla
# asignada aquí manda exactamente lo que se pide, sin ese intercambio.
CMD_TECLAS = 0x11
CMD_TECLAS_FN = 0x27        # la misma tabla, pero para la capa con Fn
TAM_TABLA_TECLAS = 576

# --- Macros ----------------------------------------------------------------
# Formato del programa oficial (función 0x42d6f0 de DeviceDriver.exe v1.0.0.5):
#   04 19 -> 04 15 con byte 8 = n.º de paquetes -> bloque de macros en paquetes
#   de 64 bytes (sin leer respuesta) -> 04 02.
# Bloque (máx. 3584 bytes): índice de 100 entradas de 4 bytes (posición de cada
# macro, 2 bytes), y desde el byte 400 el cuerpo de cada macro: n.º de eventos
# (2 bytes) + 6 bytes a 0 + eventos de 4 bytes:
#   00 00 <tecla> B0 = pulsar      00 00 <tecla> 30 = soltar
#   <ms lo> <ms hi> 00 50 = esperar (mínimo 10 ms; el oficial pone una tras cada acción)
# El bloque se rellena hasta múltiplo de 64 (con al menos 1 byte libre) y acaba en AA 55.
# Una tecla lanza la macro n.º i con la entrada 06 i <modo> <veces> en la tabla de
# teclas (modos del oficial: 0 una vez, 1 N veces, 2 hasta volver a pulsar,
# 3 mientras se mantiene, 4 "al hacer clic": cada pulsación escribe la siguiente tecla).
# --- Ajustes del sistema (reposo) -------------------------------------------
# Función 0x414060 del programa oficial: EMPEZAR -> 04 17 01 ... [8]=01 -> datos
# -> CONFIRMAR (sin GUARDAR). El paquete de datos lleva varios ajustes a la vez:
#   [1]=01  [2..4]=desactivar tecla Win / Alt+F4 / Alt+Tab (0 = no)
#   [5]=fn_switch  [6]=sleep_time (reposo)  [8]=key_respondtime  [62..63]=AA 55
# Valores por defecto del programa oficial: fn_switch 0, sleep_time 2, key_respondtime 2.
# (gohv ponía el reposo en el byte 8, que en realidad es el tiempo de respuesta.)
#   fn_switch: 0 = la capa Fn solo mientras se mantiene Fn, 1 = Fn la activa/desactiva.
#   key_respondtime: nivel 1-5 de antirrebote (por cable, de ~2 ms a ~18 ms).
# Como el teclado no deja leer los ajustes, se recuerdan los últimos enviados en
# AJUSTES_GUARDADOS para no pisar unos al cambiar otros.
CMD_SISTEMA = 0x17
REPOSO = {"nunca": 0, "1": 1, "5": 2, "30": 3}     # minutos -> valor
MODO_FN = {"mantener": 0, "alternar": 1}
AJUSTES_DEFECTO = {"bloquear_win": 0, "bloquear_altf4": 0, "bloquear_alttab": 0,
                   "fn": 0, "reposo": 2, "respuesta": 2}
AJUSTES_GUARDADOS = os.path.expanduser("~/Library/Application Support/ak820-mac/sistema.json")

CMD_MACROS = 0x19
CMD_MACROS_DATOS = 0x15
# Modos de reproducción (valores del desplegable del programa oficial, 0x4101c0).
MODO_MACRO = {"una": 0, "veces": 1, "alternar": 2, "mantener": 3, "paso": 4}
TAM_MACROS = 0xE00
INICIO_MACROS = 400
PAUSA_MACRO_MS = 15         # espera entre pulsaciones dentro de una macro

# El teclado no deja leer sus teclas, así que se recuerdan las asignaciones de las dos
# capas en TECLAS_GUARDADAS ({"normal": {tecla: asignación}, "fn": {...}}). Cada envío
# manda las dos capas y todas las macros juntas: el bloque de macros es uno solo para
# las dos capas, y mandar solo una capa borraría las macros de la otra.
TECLAS_GUARDADAS = os.path.expanduser("~/Library/Application Support/ak820-mac/teclas.json")
# Lo último que se mandó a la pantalla ("reloj" o "imagen"): poner la hora vuelve a enseñar
# el reloj, así que la app solo la pone sola si la pantalla ya estaba en el reloj.
PANTALLA_GUARDADA = os.path.expanduser("~/Library/Application Support/ak820-mac/pantalla.json")
CAPAS = {"normal": CMD_TECLAS, "fn": CMD_TECLAS_FN}
NOMBRE_CAPA = {"normal": "capa normal", "fn": "capa con Fn"}

# Posición (key_index) de cada tecla física, sacada de la distribución oficial.
POSICION_TECLA = {
    "esc": 1, **{f"f{n}": n + 1 for n in range(1, 13)}, "supr": 119,
    "`": 19, **{str(n % 10): 19 + n for n in range(1, 11)}, "-": 30, "=": 31,
    "borrar": 103, "inicio": 117, "tab": 37,
    **dict(zip("qwertyuiop", range(38, 48))), "[": 48, "]": 49, "\\": 67,
    "repag": 118, "bloqmayus": 55, **dict(zip("asdfghjkl", range(56, 65))),
    ";": 65, "'": 66, "enter": 85, "avpag": 121,
    "shift": 73, **dict(zip("zxcvbnm", range(74, 81))), ",": 81, ".": 82, "/": 83,
    "shift_der": 84, "arriba": 101, "ctrl": 91, "win": 92, "alt": 93,
    "espacio": 94, "alt_der": 95, "ctrl_der": 98,
    "izquierda": 99, "abajo": 100, "derecha": 102,
}
# Otros nombres para las mismas teclas (inglés / rotulado de las teclas).
for alias, nombre in {"pgdn": "avpag", "pgup": "repag", "home": "inicio", "delete": "supr",
                      "backspace": "borrar", "capslock": "bloqmayus", "space": "espacio"}.items():
    POSICION_TECLA[alias] = POSICION_TECLA[nombre]
# Nombre principal de cada posición (el primero; los alias van después).
NOMBRE_TECLA = {}
for nombre, indice in POSICION_TECLA.items():
    NOMBRE_TECLA.setdefault(indice, nombre)
# Teclas que no se pueden cambiar en la capa con Fn: las que el programa oficial no deja
# (fnlayer_disable) y Supr, que el teclado ignora (probado: Fn + Supr = b no hace nada).
NO_CAMBIABLES_FN = {POSICION_TECLA[t] for t in ("esc", "borrar", "inicio", "\\", "win", "supr")}

# Modificadores (bits del primer byte de una combinación, estándar USB).
MODIFICADOR = {"ctrl": 0x01, "shift": 0x02, "option": 0x04, "alt": 0x04, "cmd": 0x08, "win": 0x08,
               "ctrl_der": 0x10, "shift_der": 0x20, "option_der": 0x40, "alt_der": 0x40,
               "cmd_der": 0x80, "win_der": 0x80}

# Teclas multimedia (USB "consumer"). Las 7 primeras son las del programa oficial.
MULTIMEDIA = {"play": 0xCD, "siguiente": 0xB5, "anterior": 0xB6, "stop": 0xB7,
              "silencio": 0xE2, "volumen+": 0xE9, "volumen-": 0xEA,
              "brillo+": 0x6F, "brillo-": 0x70}

# Ratón: (tipo, valor). Tipo 1 = botones (bits USB: 1 izq., 2 der., 4 central), 3 = rueda
# (01 arriba, FF abajo: una muesca por pulsación; el teclado ignora valores mayores). El programa
# oficial también ofrece botón 4/5 (08/10), pero el ratón del teclado solo declara 3
# botones y el Mac los descarta. Su "doble clic" (01 01 03) pulsa izquierdo y derecho a la
# vez (en el Mac hace de clic derecho); el doble clic se hace con una macro.
RATON = {"clic": (0x01, 0x01), "clic_der": (0x01, 0x02), "clic_medio": (0x01, 0x04),
         "rueda_arriba": (0x03, 0x01), "rueda_abajo": (0x03, 0xFF)}

# "Multi-Key" del programa oficial: hasta 3 teclas a la vez, 07 <t1> <t2> <t3>. El
# programa oficial admite modificadores (códigos USB E0-E7), pero el teclado los manda
# junto a las teclas normales y macOS los ignora (multi:shift+a escribe "a"). Por eso
# un multi con modificadores se convierte en la combinación normal (02).

# Teclas que se pueden asignar como destino (códigos USB HID).
CODIGO_TECLA = {
    **{c: 0x04 + i for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")},
    **{str(n % 10): 0x1D + n for n in range(1, 11)},
    "enter": 0x28, "esc": 0x29, "borrar": 0x2A, "tab": 0x2B, "espacio": 0x2C,
    "-": 0x2D, "=": 0x2E, "[": 0x2F, "]": 0x30, "\\": 0x31, ";": 0x33, "'": 0x34,
    "`": 0x35, ",": 0x36, ".": 0x37, "/": 0x38, "bloqmayus": 0x39,
    **{f"f{n}": 0x39 + n for n in range(1, 13)}, **{f"f{n}": 0x5B + n for n in range(13, 25)},
    "imprpant": 0x46, "insert": 0x49, "inicio": 0x4A, "repag": 0x4B, "supr": 0x4C,
    "fin": 0x4D, "avpag": 0x4E, "derecha": 0x4F, "izquierda": 0x50, "abajo": 0x51,
    "arriba": 0x52,
}
for alias, nombre in {"pgdn": "avpag", "pgup": "repag", "home": "inicio", "end": "fin",
                      "delete": "supr", "backspace": "borrar", "space": "espacio"}.items():
    CODIGO_TECLA[alias] = CODIGO_TECLA[nombre]

# --- Efectos de luz (byte 0 del paquete de luces) ---------------------------
# El firmware no tiene "fijo" ni "apagado" de verdad: "fijo" es "respirar" a
# velocidad 0 y "apagado" es "una tecla" con brillo 0 (igual que la comunidad).
EFECTOS = {
    "fijo": 0x07, "apagado": 0x02,
    "una-tecla": 0x02, "una-tecla-off": 0x03, "brillos": 0x04, "lluvia": 0x05,
    "colores": 0x06, "respirar": 0x07, "espectro": 0x08, "ondas": 0x09,
    "desplazar": 0x0A, "rodar": 0x0B, "girar": 0x0C, "explosion": 0x0D,
    "lanzar": 0x0E, "ondulas": 0x0F, "fluir": 0x10, "latido": 0x11,
    "inclinar": 0x12, "lanzadera": 0x13,
}
DIRECCIONES = {"izquierda": 0, "abajo": 1, "arriba": 2, "derecha": 3}


def paquete_control(comando, byte2=0x00, byte8=0x01):
    """Paquete de control: [0]=0x04, [1]=comando, [2]=byte2, [8]=byte8."""
    p = bytearray(PACKET_SIZE)
    p[0] = 0x04
    p[1] = comando
    p[2] = byte2
    p[8] = byte8
    return bytes(p)


def paquete_hora(t):
    """Paquete con la fecha y la hora (valores normales, no BCD)."""
    p = bytearray(PACKET_SIZE)
    p[1] = 0x01
    p[2] = 0x5A
    p[3] = t.year - 2000
    p[4] = t.month
    p[5] = t.day
    p[6] = t.hour
    p[7] = t.minute
    p[8] = t.second
    p[10] = 0x04
    p[62] = 0xAA            # marca de final de paquete
    p[63] = 0x55
    return bytes(p)


def paquete_luces(efecto, r, g, b, arcoiris, brillo, velocidad, direccion):
    """Paquete de luces. Brillo y velocidad van de 0 a 5."""
    p = bytearray(PACKET_SIZE)
    p[0] = efecto
    p[1] = r
    p[2] = g
    p[3] = b
    p[8] = 1 if arcoiris else 0
    p[9] = min(brillo, 5)
    p[10] = min(velocidad, 5)
    p[11] = direccion
    p[14] = 0x55            # marca de final (aquí va al revés que en el reloj)
    p[15] = 0xAA
    return bytes(p)


def pixeles_rgb565(imagen):
    """Recorta una imagen de Pillow al centro, la deja en 128x128 y la pasa a RGB565."""
    from PIL import ImageOps
    imagen = ImageOps.fit(imagen.convert("RGB"), (PANTALLA, PANTALLA))
    datos = bytearray()
    for r, g, b in imagen.getdata():
        datos += (((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)).to_bytes(2, "little")
    return bytes(datos)


def entrada_tecla(destino):
    """Los 4 bytes de una tecla para un destino como 'b', 'cmd+c', 'volumen+' o 'clic_der'.

    Devuelve None si no se entiende el destino.
    """
    destino = destino.lower()
    if destino.startswith("multi:"):
        teclas = destino[len("multi:"):].split("+")
        mods = [t for t in teclas if t in MODIFICADOR]
        normales = [t for t in teclas if t not in MODIFICADOR]
        if mods:
            return entrada_tecla("+".join(mods + normales)) if len(normales) <= 1 else None
        if not 1 <= len(normales) <= 3 or any(t not in CODIGO_TECLA for t in normales):
            return None
        codigos = [CODIGO_TECLA[t] for t in normales]
        return bytes([0x07] + codigos + [0x00] * (3 - len(codigos)))
    if destino in MULTIMEDIA:
        codigo = MULTIMEDIA[destino]
        return bytes([0x03, codigo & 0xFF, codigo >> 8, 0x00])
    if destino in RATON:
        tipo, valor = RATON[destino]
        return bytes([0x01, tipo, valor, 0x00])
    *mods, final = destino.split("+")
    if any(m not in MODIFICADOR for m in mods):
        return None
    bits = 0
    for m in mods:
        bits |= MODIFICADOR[m]
    if final in CODIGO_TECLA:
        return bytes([0x02, bits, CODIGO_TECLA[final], 0x00])
    if final in MODIFICADOR:                     # un modificador (o varios) sin tecla
        return bytes([0x02, bits | MODIFICADOR[final], 0x00, 0x00])
    return None


def eventos_texto(texto):
    """Eventos de macro (4 bytes cada uno) para escribir un texto (teclado inglés de EE. UU.).

    Devuelve None si hay algún carácter que no se sabe escribir.
    """
    con_shift = dict(zip('!@#$%^&*()_+{}|:"~<>?', '1234567890-=[]\\;\'`,./'))
    espera = PAUSA_MACRO_MS.to_bytes(2, "little") + b"\x00\x50"
    eventos = []
    for c in texto:
        if c == " ":
            teclas = ["espacio"]
        elif c.isupper() and c.lower() in CODIGO_TECLA:
            teclas = ["shift", c.lower()]
        elif c in con_shift:
            teclas = ["shift", con_shift[c]]
        elif c in CODIGO_TECLA:
            teclas = [c]
        else:
            return None
        codigos = [0xE1 if t == "shift" else CODIGO_TECLA[t] for t in teclas]
        for codigo in codigos:                       # pulsar (Shift primero)
            eventos += [bytes([0, 0, codigo, 0xB0]), espera]
        for codigo in reversed(codigos):             # soltar (Shift el último)
            eventos += [bytes([0, 0, codigo, 0x30]), espera]
    return eventos


def eventos_doble_clic():
    """Eventos de macro para un doble clic izquierdo (pulsar y soltar dos veces)."""
    espera = PAUSA_MACRO_MS.to_bytes(2, "little") + b"\x00\x50"
    clic = [bytes([0, 0, 0x01, 0x90]), espera, bytes([0, 0, 0x01, 0x10]), espera]
    return clic * 2


def bloque_macros(macros):
    """Bloque de macros listo para enviar: lista de macros, cada una una lista de eventos."""
    bloque = bytearray(TAM_MACROS)
    posicion = INICIO_MACROS
    for i, eventos in enumerate(macros):
        bloque[i * 4:i * 4 + 2] = posicion.to_bytes(2, "little")
        bloque[posicion:posicion + 2] = len(eventos).to_bytes(2, "little")
        cuerpo = b"".join(eventos)
        bloque[posicion + 8:posicion + 8 + len(cuerpo)] = cuerpo
        posicion += 8 + len(cuerpo)
    paquetes = posicion // PACKET_SIZE + (1 if posicion % PACKET_SIZE == 0 else 2)
    tam = paquetes * PACKET_SIZE
    if tam > TAM_MACROS:
        return None                                  # no caben
    bloque[tam - 2:tam] = b"\xaa\x55"
    return bytes(bloque[:tam])


def tabla_teclas(cambios):
    """Tabla de 576 bytes: {posición: 4 bytes}; el resto, sin cambios (ceros)."""
    tabla = bytearray(TAM_TABLA_TECLAS)
    for posicion, entrada in cambios.items():
        tabla[posicion * 4:posicion * 4 + 4] = entrada
    tabla[-2:] = b"\xaa\x55"
    return bytes(tabla)


def imagen_de_prueba():
    """8 franjas numeradas de 16 filas (= un bloque cada una) y una raya negra en el centro.

    Si algo falla, la foto dice qué bloque (franja) y cuánto se ha movido (la raya).
    """
    from PIL import Image, ImageDraw, ImageFont
    colores = ["red", "orange", "yellow", "lime", "cyan", "blue", "purple", "magenta"]
    imagen = Image.new("RGB", (PANTALLA, PANTALLA))
    dibujo = ImageDraw.Draw(imagen)
    fuente = ImageFont.load_default(size=13)
    for n, color in enumerate(colores):
        y = n * 16
        dibujo.rectangle((0, y, PANTALLA - 1, y + 15), fill=color)
        dibujo.text((4, y + 1), str(n + 1), fill="black", font=fuente)
    dibujo.line((PANTALLA // 2, 0, PANTALLA // 2, PANTALLA - 1), fill="black", width=2)
    return imagen


def fotogramas(imagen):
    """Lista de (píxeles RGB565, duración en ms). Una imagen fija es un solo fotograma."""
    from PIL import ImageSequence
    if not getattr(imagen, "is_animated", False):
        return [(pixeles_rgb565(imagen), 0)]
    lista = []
    for fotograma in ImageSequence.Iterator(imagen):
        duracion = fotograma.info.get("duration") or 100
        # El programa oficial solo permite entre 30 y 500 ms por fotograma.
        lista.append((pixeles_rgb565(fotograma), min(max(duracion, 30), 500)))
    return lista


def bloques_imagen(lista):
    """Cabecera + fotogramas, rellenado con 0xFF hasta completar bloques de 4096 bytes."""
    cabecera = bytearray(b"\xff" * CABECERA)
    cabecera[0] = len(lista)                     # n.º de fotogramas
    for i, (_, duracion) in enumerate(lista):
        cabecera[1 + i] = max(1, duracion // 2)  # en pasos de 2 ms; 1 como mínimo, como el oficial
    datos = bytes(cabecera) + b"".join(pixeles for pixeles, _ in lista)
    n = -(-len(datos) // BLOQUE)                 # bloques necesarios (9 para una imagen fija)
    datos += b"\xff" * (n * BLOQUE - len(datos))
    return [datos[i * BLOQUE:(i + 1) * BLOQUE] for i in range(n)]


# --- Comunicación con el teclado --------------------------------------------
def buscar_interfaz(usage_page=CONFIG_USAGE_PAGE):
    """Devuelve la interfaz del teclado con ese usage page (por defecto, la de configuración)."""
    for info in hid.enumerate(VENDOR_ID):
        if info["product_id"] in PRODUCT_IDS_CABLE and info["usage_page"] == usage_page:
            return info
    return None


def enviar(dispositivo, paquete):
    """Manda un paquete y lee la respuesta (el teclado lo necesita para actuar)."""
    time.sleep(PAUSA)       # el programa oficial también espera antes de cada orden
    # hidapi pide delante el número de "report", que aquí es 0.
    dispositivo.send_feature_report(bytes([0x00]) + paquete)
    time.sleep(PAUSA)
    try:
        return bytes(dispositivo.get_feature_report(0x00, PACKET_SIZE + 1))
    except OSError:
        return None  # la respuesta suele hacer solo de "acuse de recibo"; si falla, seguimos


# --- Comandos del programa ---------------------------------------------------
def cmd_buscar(_args):
    todas = hid.enumerate(VENDOR_ID)
    if not todas:
        print("No veo ningún teclado AK820. ¿Está conectado por cable USB-C?")
        return 1
    print("Interfaces del teclado que ve tu Mac:")
    for i in todas:
        marca = "  <- configuración" if i["usage_page"] == CONFIG_USAGE_PAGE else ""
        print(f"  PID 0x{i['product_id']:04X}  interfaz {i['interface_number']}  "
              f"usage page 0x{i['usage_page']:04X}  {i['product_string']}{marca}")
    if buscar_interfaz() is None:
        print("\nNo aparece la interfaz de configuración (PID 0x8009/0x800A, 0xFF13).")
        print("Si estás por Bluetooth o con el receptor 2.4G, conéctalo por cable.")
        return 1
    print("\nTodo bien: el teclado está listo para configurarse.")
    return 0


def cmd_reloj(args):
    info = buscar_interfaz()
    if info is None:
        print("No encuentro el teclado por cable. Prueba primero: python3 ak820.py buscar")
        return 1
    if args.hora:
        t = datetime.datetime.strptime(args.hora, "%Y-%m-%d %H:%M")
    else:
        t = datetime.datetime.now()

    dispositivo = hid.device()
    dispositivo.open_path(info["path"])
    try:
        enviar(dispositivo, paquete_control(CMD_EMPEZAR))
        enviar(dispositivo, paquete_control(CMD_RELOJ))
        enviar(dispositivo, paquete_hora(t))
        enviar(dispositivo, paquete_control(CMD_CONFIRMAR, byte8=0x00))
        time.sleep(0.1)     # margen para que el teclado aplique la hora
    finally:
        dispositivo.close()
    guardar_modo_pantalla("reloj")
    print(f"Reloj del teclado puesto a {t:%d/%m/%Y %H:%M:%S}. Mira la pantalla.")
    return 0


def cmd_luces(args):
    info = buscar_interfaz()
    if info is None:
        print("No encuentro el teclado por cable. Prueba primero: python3 ak820.py buscar")
        return 1
    color = args.color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    brillo, velocidad = args.brillo, args.velocidad
    if args.efecto == "fijo":
        velocidad = 0
    elif args.efecto == "apagado":
        brillo, velocidad = 0, 0

    datos = paquete_luces(EFECTOS[args.efecto], r, g, b, args.arcoiris,
                          brillo, velocidad, DIRECCIONES[args.direccion])
    dispositivo = hid.device()
    dispositivo.open_path(info["path"])
    try:
        enviar(dispositivo, paquete_control(CMD_EMPEZAR))
        enviar(dispositivo, paquete_control(CMD_LUCES))
        enviar(dispositivo, datos)
        enviar(dispositivo, paquete_control(CMD_GUARDAR))
        time.sleep(0.1)
    finally:
        dispositivo.close()
    print(f"Luces: {args.efecto}, color #{color.upper()}, brillo {brillo}, velocidad {velocidad}. Mira el teclado.")
    return 0


def paquete_sistema(ajustes):
    """Paquete de ajustes del sistema (formato del programa oficial)."""
    p = bytearray(PACKET_SIZE)
    p[1] = 0x01
    p[2] = ajustes["bloquear_win"]
    p[3] = ajustes["bloquear_altf4"]
    p[4] = ajustes["bloquear_alttab"]
    p[5] = ajustes["fn"]
    p[6] = ajustes["reposo"]
    p[8] = ajustes["respuesta"]
    p[62] = 0xAA
    p[63] = 0x55
    return bytes(p)


def cargar_ajustes():
    """Los últimos ajustes del sistema enviados (o los de fábrica si no hay)."""
    ajustes = dict(AJUSTES_DEFECTO)
    try:
        with open(AJUSTES_GUARDADOS) as f:
            ajustes.update({k: v for k, v in json.load(f).items() if k in ajustes})
    except (OSError, ValueError):
        pass
    return ajustes


def enviar_ajustes(ajustes):
    """Manda los ajustes del sistema y, si el teclado los recibe bien, los recuerda."""
    info = buscar_interfaz()
    if info is None:
        print("No encuentro el teclado por cable. Prueba primero: python3 ak820.py buscar")
        return 1
    datos = paquete_sistema(ajustes)
    dispositivo = hid.device()
    dispositivo.open_path(info["path"])
    try:
        enviar(dispositivo, paquete_control(CMD_EMPEZAR, byte8=0x00))
        enviar(dispositivo, paquete_control(CMD_SISTEMA, byte2=0x01, byte8=0x01))
        time.sleep(PAUSA)
        dispositivo.send_feature_report(bytes([0x00]) + datos)   # sin leer respuesta, como el oficial
        time.sleep(PAUSA)
        respuesta = enviar(dispositivo, paquete_control(CMD_CONFIRMAR, byte8=0x00))
    finally:
        dispositivo.close()
    if respuesta and int.from_bytes(respuesta[5:7], "little") != sum(datos) & 0xFFFF:
        print("El teclado no ha recibido bien el ajuste. Prueba otra vez.")
        return 1
    os.makedirs(os.path.dirname(AJUSTES_GUARDADOS), exist_ok=True)
    with open(AJUSTES_GUARDADOS, "w") as f:
        json.dump(ajustes, f, indent=2)
    return 0


def describir_ajustes(ajustes):
    reposo = {v: k for k, v in REPOSO.items()}[ajustes["reposo"]]
    bloqueadas = [n for n, k in (("Win", "bloquear_win"), ("Alt+F4", "bloquear_altf4"),
                                 ("Alt+Tab", "bloquear_alttab")) if ajustes[k]]
    return "\n".join([
        f"  Reposo: {'nunca' if reposo == 'nunca' else reposo + ' min'} (solo con batería)",
        f"  Tecla Fn: {'activa/desactiva la capa Fn' if ajustes['fn'] else 'capa Fn solo mientras se mantiene'}",
        f"  Tiempo de respuesta: nivel {ajustes['respuesta']} (1 rápido ... 5 lento)",
        f"  Bloqueadas: {', '.join(bloqueadas) if bloqueadas else 'ninguna'}",
    ])


def cmd_reposo(args):
    ajustes = cargar_ajustes()
    ajustes["reposo"] = REPOSO[args.minutos]
    if enviar_ajustes(ajustes):
        return 1
    if args.minutos == "nunca":
        print("Reposo desactivado: las luces no se apagarán solas.")
    else:
        print(f"Reposo: las luces se apagarán tras {args.minutos} min sin tocar el teclado.")
    return 0


def cmd_sistema(args):
    ajustes = cargar_ajustes()
    cambios = {"fn": MODO_FN.get(args.fn_modo), "respuesta": args.respuesta,
               "reposo": REPOSO.get(args.reposo)}
    for nombre, clave in (("win", "bloquear_win"), ("altf4", "bloquear_altf4"),
                          ("alttab", "bloquear_alttab")):
        if nombre in (args.bloquear or []):
            cambios[clave] = 1
        if nombre in (args.desbloquear or []):
            cambios[clave] = 0
    cambios = {k: v for k, v in cambios.items() if v is not None}
    if args.fabrica:
        ajustes, cambios = dict(AJUSTES_DEFECTO), {"todo": True}
    if not cambios:
        print("Últimos ajustes del sistema enviados (el teclado no deja leerlos):")
        print(describir_ajustes(ajustes))
        return 0
    ajustes.update({k: v for k, v in cambios.items() if k in ajustes})
    if enviar_ajustes(ajustes):
        return 1
    print("Ajustes del sistema enviados:")
    print(describir_ajustes(ajustes))
    return 0


def modo_pantalla():
    """'reloj' o 'imagen': lo último que se mandó a la pantalla desde este Mac."""
    try:
        with open(PANTALLA_GUARDADA) as f:
            return "imagen" if json.load(f).get("modo") == "imagen" else "reloj"
    except (OSError, ValueError, AttributeError):
        return "reloj"


def guardar_modo_pantalla(modo):
    os.makedirs(os.path.dirname(PANTALLA_GUARDADA), exist_ok=True)
    with open(PANTALLA_GUARDADA, "w") as f:
        json.dump({"modo": modo}, f)


def cargar_teclas():
    """Las asignaciones de teclas enviadas por última vez (vacías = todo de fábrica)."""
    config = {capa: {} for capa in CAPAS}
    try:
        with open(TECLAS_GUARDADAS) as f:
            guardado = json.load(f)
        for capa in CAPAS:
            config[capa].update(guardado.get(capa) or {})
    except (OSError, ValueError, AttributeError):
        pass
    return config


def guardar_teclas(config):
    os.makedirs(os.path.dirname(TECLAS_GUARDADAS), exist_ok=True)
    with open(TECLAS_GUARDADAS, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def entrada_asignacion(asignacion, macros):
    """Los 4 bytes de una asignación ({"destino": ..., "modo": ..., "veces": ...}).

    Si es una macro, añade sus eventos a 'macros' (la lista común de las dos capas).
    Lanza ValueError con un mensaje para el usuario si no se entiende.
    """
    destino = str(asignacion.get("destino", ""))
    if destino.lower() == "doble_clic":
        eventos = eventos_doble_clic()
        modo, veces = "una", 1
    elif destino.lower().startswith("texto:"):
        texto = destino[len("texto:"):]
        eventos = eventos_texto(texto) if texto else None
        if not eventos:
            raise ValueError(f"No sé escribir '{texto}' con una macro "
                             "(solo letras sin tilde, números, espacio y símbolos básicos).")
        modo = asignacion.get("modo") or "una"
        veces = int(asignacion.get("veces") or 1)
        if modo not in MODO_MACRO or not 1 <= veces <= 255:
            raise ValueError(f"Modo o repeticiones no válidos en '{destino}'.")
    else:
        entrada = entrada_tecla(destino)
        if entrada is None:
            raise ValueError(f"No entiendo '{destino}'. Nombres válidos: python3 ak820.py teclas lista")
        return entrada
    if len(macros) >= 100:
        raise ValueError("Como mucho caben 100 macros.")
    macros.append(eventos)
    return bytes([0x06, len(macros) - 1, MODO_MACRO[modo], veces])


def preparar_teclas(config):
    """Tablas de las dos capas y bloque de macros (o None) para una configuración.

    Lanza ValueError con un mensaje para el usuario si algo no vale.
    """
    macros = []
    tablas = {}
    for capa in CAPAS:
        cambios = {}
        for origen, asignacion in config.get(capa, {}).items():
            posicion = POSICION_TECLA.get(origen)
            if posicion is None:
                raise ValueError(f"No conozco la tecla '{origen}'.")
            if capa == "fn" and posicion in NO_CAMBIABLES_FN:
                raise ValueError(f"'{origen}' no se puede cambiar en la capa con Fn.")
            try:
                cambios[posicion] = entrada_asignacion(asignacion, macros)
            except ValueError as e:
                raise ValueError(f"{origen} ({NOMBRE_CAPA[capa]}): {e}") from None
        tablas[capa] = tabla_teclas(cambios)
    bloque = bloque_macros(macros) if macros else None
    if macros and bloque is None:
        raise ValueError("Las macros no caben en la memoria del teclado (3,5 KB). Acórtalas.")
    return tablas, bloque


def subir_macros(dispositivo, bloque):
    """Sube el bloque de macros. Al cerrar, el teclado responde con la suma de los bytes
    recibidos (bytes 5-6); si no coincide se repite: la primera vez a veces se pierde
    (probablemente mientras borra su memoria de macros)."""
    for intento in range(1, 4):
        enviar(dispositivo, paquete_control(CMD_MACROS, byte8=0x00))
        enviar(dispositivo, paquete_control(CMD_MACROS_DATOS, byte8=len(bloque) // PACKET_SIZE))
        time.sleep(0.03)
        for i in range(0, len(bloque), PACKET_SIZE):
            dispositivo.send_feature_report(bytes([0x00]) + bloque[i:i + PACKET_SIZE])
            time.sleep(PAUSA)
        time.sleep(0.03)
        respuesta = enviar(dispositivo, paquete_control(CMD_CONFIRMAR, byte8=0x00))
        if respuesta and int.from_bytes(respuesta[5:7], "little") == sum(bloque) & 0xFFFF:
            return True
        print(f"  Las macros no han llegado bien (intento {intento}); repitiendo...")
    return False


def subir_tabla(dispositivo, comando, tabla):
    """Sube la tabla de una capa (con la misma comprobación de la suma) y la guarda."""
    for intento in range(1, 4):
        enviar(dispositivo, paquete_control(CMD_EMPEZAR, byte8=0x00))
        enviar(dispositivo, paquete_control(comando, byte8=TAM_TABLA_TECLAS // PACKET_SIZE))
        for i in range(0, TAM_TABLA_TECLAS, PACKET_SIZE):
            # Los trozos de la tabla van seguidos y sin leer respuesta (como el oficial).
            dispositivo.send_feature_report(bytes([0x00]) + tabla[i:i + PACKET_SIZE])
            time.sleep(PAUSA)
        respuesta = enviar(dispositivo, paquete_control(CMD_CONFIRMAR, byte8=0x00))
        if respuesta and int.from_bytes(respuesta[5:7], "little") == sum(tabla) & 0xFFFF:
            enviar(dispositivo, paquete_control(CMD_GUARDAR, byte8=0x00))
            return True
        print(f"  La tabla de teclas no ha llegado bien (intento {intento}); repitiendo...")
    return False


def enviar_teclas(config):
    """Manda las macros y las dos capas y, si todo llega bien, recuerda la configuración.

    Devuelve True si ha ido bien; si no, imprime el motivo. Lanza ValueError si la
    configuración no vale (antes de tocar el teclado).
    """
    tablas, bloque = preparar_teclas(config)
    info = buscar_interfaz()
    if info is None:
        print("No encuentro el teclado por cable. Prueba primero: python3 ak820.py buscar")
        return False
    dispositivo = hid.device()
    dispositivo.open_path(info["path"])
    try:
        if bloque and not subir_macros(dispositivo, bloque):
            print("No consigo guardar las macros en el teclado. Prueba otra vez.")
            return False
        for capa, comando in CAPAS.items():
            if not subir_tabla(dispositivo, comando, tablas[capa]):
                print("No consigo guardar las teclas en el teclado. Prueba otra vez.")
                return False
    finally:
        dispositivo.close()
    guardar_teclas(config)
    return True


def describir_asignacion(asignacion):
    destino = asignacion["destino"]
    if destino.lower().startswith("texto:"):
        modo = asignacion.get("modo") or "una"
        if modo == "veces":
            return f"{destino} ({asignacion.get('veces', 1)} veces)"
        if modo != "una":
            return f"{destino} (modo {modo})"
    return destino


def describir_teclas(config):
    lineas = []
    for capa in CAPAS:
        cambios = config.get(capa, {})
        resumen = ", ".join(f"{origen}={describir_asignacion(a)}" for origen, a in cambios.items())
        lineas.append(f"  {NOMBRE_CAPA[capa][0].upper()}{NOMBRE_CAPA[capa][1:]}: {resumen or 'de fábrica'}")
    return "\n".join(lineas)


def cmd_teclas(args):
    if args.cambios == ["lista"]:
        print("Teclas que se pueden cambiar (origen, como están rotuladas):")
        print("  " + " ".join(sorted(POSICION_TECLA)))
        print("Destinos: una tecla, o una combinación con '+' (p. ej. cmd+c, ctrl+shift+t):")
        print("  " + " ".join(sorted(CODIGO_TECLA)))
        print("Modificadores:", " ".join(sorted(MODIFICADOR)))
        print("Multimedia:", " ".join(MULTIMEDIA))
        print("Ratón:", " ".join(RATON), "doble_clic")
        print("Para devolver una sola tecla a lo de fábrica: tecla=defecto (p. ej. avpag=defecto)")
        return 0
    config = cargar_teclas()
    if not args.cambios:
        print("Teclas cambiadas (las últimas enviadas desde este Mac):")
        print(describir_teclas(config))
        return 0
    capa = "fn" if args.fn else "normal"
    if args.cambios == ["restaurar", "todo"]:
        config = {c: {} for c in CAPAS}
    elif args.cambios == ["restaurar"]:
        config[capa] = {}
    elif args.cambios != ["reenviar"]:
        for cambio in args.cambios:
            origen, igual, destino = cambio.partition("=")
            origen = origen.lower()
            if not igual or origen not in POSICION_TECLA or not destino:
                print(f"No entiendo '{cambio}'. Usa origen=destino; nombres válidos: python3 ak820.py teclas lista")
                return 1
            nombre = NOMBRE_TECLA[POSICION_TECLA[origen]]
            if destino.lower() == "defecto":
                config[capa].pop(nombre, None)
                continue
            asignacion = {"destino": destino}
            if destino.lower().startswith("texto:"):
                asignacion["modo"] = args.modo or ("veces" if args.veces > 1 else "una")
                asignacion["veces"] = args.veces
            config[capa][nombre] = asignacion
    try:
        if not enviar_teclas(config):
            return 1
    except ValueError as e:
        print(e)
        return 1
    print("Teclas guardadas en el teclado:")
    print(describir_teclas(config))
    return 0


def cmd_imagen(args):
    control_info = buscar_interfaz()
    datos_info = buscar_interfaz(DATOS_USAGE_PAGE)
    if control_info is None or datos_info is None:
        print("No encuentro el teclado por cable. Prueba primero: python3 ak820.py buscar")
        return 1
    from PIL import Image
    if args.archivo == "prueba":
        imagen = imagen_de_prueba()
    else:
        imagen = Image.open(args.archivo)
    lista = fotogramas(imagen)
    if len(lista) > MAX_FOTOGRAMAS:
        print(f"El GIF tiene {len(lista)} fotogramas; el teclado admite {MAX_FOTOGRAMAS}. "
              f"Se envían los primeros {MAX_FOTOGRAMAS}.")
        lista = lista[:MAX_FOTOGRAMAS]
    bloques = bloques_imagen(lista)
    if len(lista) > 1:
        print(f"GIF animado: {len(lista)} fotogramas, {len(bloques)} bloques "
              f"(unos {len(bloques) * 45 // 1000 + 1} s).")

    aviso = bytearray(paquete_control(CMD_IMAGEN, byte2=HUECO_IMAGEN, byte8=len(bloques) & 0xFF))
    aviso[9] = len(bloques) >> 8                     # el n.º de bloques ocupa dos bytes
    control = hid.device()
    control.open_path(control_info["path"])
    datos = hid.device()
    datos.open_path(datos_info["path"])
    try:
        enviar(control, paquete_control(CMD_EMPEZAR, byte8=0x00))
        enviar(control, bytes(aviso))
        avance = 0
        for n, bloque in enumerate(bloques, 1):
            datos.write(b"\x00" + bloque)
            if not datos.read(PACKET_SIZE + 1, 3000):   # espera el "recibido"
                print(f"El teclado no ha confirmado el bloque {n}/{len(bloques)}.")
                print("Vuelve a la pantalla normal con: python3 ak820.py reloj")
                return 1
            if n * 10 // len(bloques) > avance or n == len(bloques):
                avance = n * 10 // len(bloques)
                print(f"  {n * 100 // len(bloques)} % enviado")
        enviar(control, paquete_control(CMD_CONFIRMAR, byte8=0x00))
        time.sleep(0.1)
    finally:
        control.close()
        datos.close()
    guardar_modo_pantalla("imagen")
    print("Imagen enviada. Mira la pantalla del teclado.")
    print("Para volver al reloj: python3 ak820.py reloj")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Configurador del Ajazz AK820 Pro para Mac")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("buscar", help="comprobar que el Mac ve el teclado (no cambia nada)")
    r = sub.add_parser("reloj", help="poner en hora la pantalla del teclado")
    r.add_argument("--hora", help="hora concreta, formato 'AAAA-MM-DD HH:MM' (por defecto, ahora)")
    l = sub.add_parser("luces", help="cambiar las luces RGB")
    l.add_argument("efecto", choices=EFECTOS, help="efecto de luz")
    l.add_argument("--color", default="FFFFFF", help="color en hexadecimal, p. ej. FF0000 (rojo)")
    l.add_argument("--brillo", type=int, default=5, help="0 a 5 (por defecto 5)")
    l.add_argument("--velocidad", type=int, default=3, help="0 a 5 (por defecto 3)")
    l.add_argument("--direccion", choices=DIRECCIONES, default="izquierda")
    l.add_argument("--arcoiris", action="store_true", help="usar todos los colores en vez de uno")
    s = sub.add_parser("reposo", help="apagar las luces tras un tiempo sin usar el teclado")
    s.add_argument("minutos", choices=REPOSO, help="1, 5, 30 o nunca")
    si = sub.add_parser("sistema", help="otros ajustes: tecla Fn, tiempo de respuesta, bloquear Win/Alt+F4/Alt+Tab")
    si.add_argument("--fn-modo", choices=MODO_FN,
                    help="mantener: la capa Fn solo mientras se mantiene Fn; alternar: Fn la activa/desactiva")
    si.add_argument("--respuesta", type=int, choices=range(1, 6), metavar="1-5",
                    help="tiempo de respuesta de las teclas (antirrebote): 1 rápido ... 5 lento; de fábrica 2")
    si.add_argument("--reposo", choices=REPOSO, help="igual que la orden 'reposo'")
    si.add_argument("--bloquear", nargs="+", choices=["win", "altf4", "alttab"], help="bloquear teclas/atajos")
    si.add_argument("--desbloquear", nargs="+", choices=["win", "altf4", "alttab"])
    si.add_argument("--fabrica", action="store_true", help="volver a los ajustes de fábrica")
    i = sub.add_parser("imagen", help="poner una imagen en la pantalla del teclado")
    i.add_argument("archivo", help="foto o dibujo (JPG, PNG...), o 'prueba' para los 4 colores")
    t = sub.add_parser("teclas", help="cambiar lo que escribe cada tecla (se guarda en el teclado)")
    t.add_argument("cambios", nargs="*",
                   help="origen=destino (p. ej. avpag=b, repag=cmd+c, supr=volumen+, avpag=texto:hola, "
                        "avpag=defecto); 'restaurar' (la capa), 'restaurar todo', 'reenviar' o 'lista'. "
                        "Sin nada, enseña las teclas cambiadas")
    t.add_argument("--fn", action="store_true", help="cambiar la capa con Fn (Fn + tecla) en vez de la normal")
    t.add_argument("--veces", type=int, default=1, choices=range(1, 256), metavar="N",
                   help="para las macros (texto:...): cuántas veces se repiten al pulsar (1 a 255)")
    t.add_argument("--modo", choices=MODO_MACRO,
                   help="cómo se reproducen las macros: una (por defecto), veces (con --veces), "
                        "alternar (hasta volver a pulsar), mantener (mientras se mantiene), "
                        "paso (cada pulsación escribe la siguiente tecla)")
    args = parser.parse_args(argv)
    ordenes = {"buscar": cmd_buscar, "reloj": cmd_reloj, "luces": cmd_luces,
               "imagen": cmd_imagen, "teclas": cmd_teclas, "reposo": cmd_reposo,
               "sistema": cmd_sistema}
    return ordenes[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
