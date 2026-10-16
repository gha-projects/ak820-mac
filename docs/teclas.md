# Remapeo de teclas dentro del teclado

Estado (17 de octubre de 2026): **funciona** en el AK820 con PID 0x800A, por cable.
Los cambios se guardan en el propio teclado: valen en cualquier ordenador y también
por Bluetooth o 2.4G, sin instalar nada.

```
python3 ak820.py teclas avpag=b          # PgDn escribe "b"
python3 ak820.py teclas repag=f14 avpag=f15
python3 ak820.py teclas restaurar        # todas las teclas de fábrica
python3 ak820.py teclas lista            # nombres que entiende
```

Cada envío manda la **tabla entera**: los cambios anteriores se sustituyen.

## De dónde sale

Ningún proyecto de la comunidad lo tenía para este firmware (solo exponen las
interfaces 0xFF13 y 0xFF68; los que remapean usan otro protocolo, 0xFF67, de firmwares
más nuevos). Lo hemos sacado del **programa oficial de Windows** (instalador
"AJAZZ_AK820 PRO … 0.85英寸彩屏 … V1.0.0.5"), sin ejecutarlo:

1. El instalador es Inno Setup: sus archivos van en un bloque LZMA ("zlb\x1a") que
   Python descomprime.
2. Inno transforma las instrucciones CALL/JMP de los .exe para comprimir mejor; se
   deshace con su algoritmo ("TransformCallInstructions" v3).
3. Con Capstone se desensambla `DeviceDriver.exe`. La función `0x418420` sube la tabla
   de teclas; `config.xml` declara el 0x800A igual que el 0x8009, y
   `rgb-keyboard.xml` da la posición (`key_index`) de cada una de las 81 teclas.

## El formato

Por la interfaz de configuración (0xFF13), feature reports de 64 bytes (report id 0):

1. `04 18 …` (empezar, byte 8 = 0)
2. `04 11 … [8]=09` (capa normal; `04 27` sería la capa con Fn) — 9 paquetes de datos
3. La tabla: **576 bytes** = 144 teclas × 4, terminada en `AA 55`, en 9 paquetes de 64
   seguidos, **sin leer respuesta**, con 35 ms entre ellos
4. `04 02` (confirmar) y `04 F0` (guardar)

El programa oficial espera **35 ms antes y después de cada orden**. Sin la pausa de
antes, el teclado ignora la tabla.

Cada tecla ocupa los bytes `key_index × 4` a `key_index × 4 + 3`:

| Bytes | Significado | Probado |
|---|---|---|
| `00 00 00 00` | Sin cambios (lo de fábrica) | ✅ |
| `02 00 <código USB> 00` | Escribe esa tecla | ✅ (PgDn → b, PgUp → x) |
| `02 <modificadores> <código> 00` | Tecla con modificadores | sin probar |
| `02 <bit> 00 00` | Un modificador solo (Ctrl, Shift…) | ⚠️ Asignar Cmd/Ctrl/Option a sí mismos los descolocó (Cmd hacía de Option) |

Del mismo código salen otros tipos aún sin probar: multimedia (`03 <código> …`),
ratón (`01 …`), macros (`07 …`), combinaciones (`03 …`) y el "por defecto" que usa el
programa oficial (`05 03 00 00`).

## Pendiente

- Entender el formato de los modificadores.
- La capa con Fn (`04 27`).
- Teclas multimedia (volumen, reproducir…) y macros.
