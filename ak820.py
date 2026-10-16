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
# Descubierto a base de pruebas con el teclado (octubre de 2026):
#  - La imagen es de 128x128 píxeles en RGB565 (2 bytes por píxel, little-endian),
#    precedida de 256 bytes de cabecera (n.º de fotogramas + duración de cada uno).
#  - Se manda en 9 bloques por la interfaz 0xFF68. Cada bloque son 4096 bytes
#    seguidos de un paquete corto de exactamente 27 bytes (con otro tamaño, o sin
#    él, el teclado se queda en "loading" esperando).
#  - El teclado guarda cada paquete USB en un hueco de 64 bytes, así que el
#    paquete corto ocupa 64: cada bloque llena 4160 bytes de su memoria. Por eso
#    la imagen se coloca cada 4160 bytes, no cada 4123.
#  - Tras cada bloque responde "01 5a 02" (recibido). Hay que esperarlo: si se
#    manda el siguiente antes, se pierden datos (el primero tarda unos 130 ms).
PANTALLA = 128
CABECERA = 256
BLOQUE = 4096
COLA = 27
HUECO_BLOQUE = 4160
N_BLOQUES = 9

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


def bloques_imagen(pixeles):
    """Cabecera + píxeles, repartidos en los 9 bloques (4096 + 27 bytes cada uno)."""
    memoria = bytearray(b"\xff" * (N_BLOQUES * HUECO_BLOQUE))
    memoria[0] = 1          # un fotograma
    memoria[1] = 50         # su duración (no importa con uno solo)
    memoria[CABECERA:CABECERA + len(pixeles)] = pixeles
    return [bytes(memoria[i * HUECO_BLOQUE:i * HUECO_BLOQUE + BLOQUE + COLA])
            for i in range(N_BLOQUES)]


# --- Comunicación con el teclado --------------------------------------------
def buscar_interfaz(usage_page=CONFIG_USAGE_PAGE):
    """Devuelve la interfaz del teclado con ese usage page (por defecto, la de configuración)."""
    for info in hid.enumerate(VENDOR_ID):
        if info["product_id"] in PRODUCT_IDS_CABLE and info["usage_page"] == usage_page:
            return info
    return None


def enviar(dispositivo, paquete):
    """Manda un paquete y lee la respuesta (el teclado lo necesita para actuar)."""
    # hidapi pide delante el número de "report", que aquí es 0.
    dispositivo.send_feature_report(bytes([0x00]) + paquete)
    time.sleep(PAUSA)
    try:
        dispositivo.get_feature_report(0x00, PACKET_SIZE + 1)
    except OSError:
        pass  # la respuesta solo hace de "acuse de recibo"; si falla, seguimos


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
    bloques = bloques_imagen(pixeles_rgb565(imagen))

    control = hid.device()
    control.open_path(control_info["path"])
    datos = hid.device()
    datos.open_path(datos_info["path"])
    try:
        enviar(control, paquete_control(CMD_EMPEZAR))
        enviar(control, paquete_control(CMD_IMAGEN, byte2=0x02, byte8=N_BLOQUES))
        # Tras el aviso el teclado prepara su memoria; si el primer paquete llega
        # antes, lo pierde y toda la imagen sale corrida 32 píxeles.
        time.sleep(0.3)
        for n, bloque in enumerate(bloques, 1):
            datos.write(b"\x00" + bloque[:BLOQUE])
            datos.write(b"\x00" + bloque[BLOQUE:])
            if not datos.read(PACKET_SIZE + 1, 3000):   # espera el "recibido"
                print(f"El teclado no ha confirmado el bloque {n}/{N_BLOQUES}.")
                print("Vuelve a la pantalla normal con: python3 ak820.py reloj")
                return 1
            # "Recibido" no es "guardado": si el siguiente bloque llega mientras
            # aún lo guarda, se cuelan trozos del anterior (rayitas de su color).
            time.sleep(0.5)
            print(f"  bloque {n}/{N_BLOQUES} enviado")
        enviar(control, paquete_control(CMD_GUARDAR))
        time.sleep(0.1)
    finally:
        control.close()
        datos.close()
    print("Imagen enviada. Mira la pantalla del teclado.")
    print("Para volver al reloj: python3 ak820.py reloj")
    return 0


def main():
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
    i = sub.add_parser("imagen", help="EXPERIMENTAL (funciona a veces): poner una imagen en la pantalla")
    i.add_argument("archivo", help="foto o dibujo (JPG, PNG...), o 'prueba' para los 4 colores")
    args = parser.parse_args()
    ordenes = {"buscar": cmd_buscar, "reloj": cmd_reloj, "luces": cmd_luces, "imagen": cmd_imagen}
    return ordenes[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
