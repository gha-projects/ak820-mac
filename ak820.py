#!/usr/bin/env python3
"""Configurador mínimo del teclado Ajazz AK820 Pro para macOS.

Paso 1: encontrar el teclado y sincronizar el reloj de su pantalla.

Cómo funciona, en pocas palabras:
  - El teclado se conecta por USB y expone varias "interfaces HID".
  - macOS se queda con las interfaces de teclado normales, pero deja abrir
    una interfaz "de fabricante" (usage page 0xFF13) desde un programa normal.
  - Por esa interfaz mandamos paquetes de 64 bytes ("feature reports").
  - Cada cambio es una pequeña conversación: EMPEZAR -> qué vamos a cambiar
    -> los datos -> TERMINAR.

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
PRODUCT_ID_CABLE = 0x8009   # AK820 Pro conectado por cable
CONFIG_USAGE_PAGE = 0xFF13  # la interfaz por la que se configura

PACKET_SIZE = 64
PAUSA = 0.035               # 35 ms entre paquetes, como el programa oficial

# --- Comandos (byte 1 de los paquetes de control) ---------------------------
CMD_EMPEZAR = 0x18
CMD_TERMINAR = 0xF0
CMD_RELOJ = 0x28


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


# --- Comunicación con el teclado --------------------------------------------
def buscar_interfaz():
    """Devuelve la interfaz de configuración del teclado, o None."""
    for info in hid.enumerate(VENDOR_ID, PRODUCT_ID_CABLE):
        if info["usage_page"] == CONFIG_USAGE_PAGE:
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
        print("\nNo aparece la interfaz de configuración (PID 0x8009, 0xFF13).")
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
        enviar(dispositivo, paquete_control(CMD_TERMINAR))
    finally:
        dispositivo.close()
    print(f"Reloj del teclado puesto a {t:%d/%m/%Y %H:%M:%S}. Mira la pantalla.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Configurador del Ajazz AK820 Pro para Mac")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("buscar", help="comprobar que el Mac ve el teclado (no cambia nada)")
    r = sub.add_parser("reloj", help="poner en hora la pantalla del teclado")
    r.add_argument("--hora", help="hora concreta, formato 'AAAA-MM-DD HH:MM' (por defecto, ahora)")
    args = parser.parse_args()
    return {"buscar": cmd_buscar, "reloj": cmd_reloj}[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
