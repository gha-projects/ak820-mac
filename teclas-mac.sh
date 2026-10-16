#!/bin/sh
# Convierte teclas del AK820 en teclas propias de Mac, usando la herramienta
# de macOS "hidutil". No toca el teclado: es macOS quien traduce la tecla,
# y solo para este teclado (el del portátil queda igual).
#
# Ahora mismo: Control derecho -> 🌐 (Fn/Globo).
# Por qué funciona: la 🌐 es un código propio de Apple (página 0xFF, uso 0x03)
# que el AK820 no sabe enviar, pero macOS sí acepta como destino.
#
# Se aplica a todo lo que tenga el fabricante 0x0C45 (cable, Bluetooth y 2.4G).

CONTROL_DERECHO=0x7000000E4
GLOBO=0xFF00000003

/usr/bin/hidutil property --matching '{"VendorID":0x0C45}' --set "{\"UserKeyMapping\":[
  {\"HIDKeyboardModifierMappingSrc\":$CONTROL_DERECHO,\"HIDKeyboardModifierMappingDst\":$GLOBO}
]}" >/dev/null
