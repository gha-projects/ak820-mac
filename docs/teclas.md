# Remapeo de teclas dentro del teclado

Estado (17 de octubre de 2026): **funciona** en el AK820 con PID 0x800A, por cable.
Los cambios se guardan en el propio teclado: valen en cualquier ordenador y también
por Bluetooth o 2.4G, sin instalar nada.

```
python3 ak820.py teclas avpag=b                    # una tecla
python3 ak820.py teclas repag=cmd+a                # combinación
python3 ak820.py teclas avpag=volumen+ supr=play   # multimedia
python3 ak820.py teclas supr=clic_der              # ratón
python3 ak820.py teclas --fn avpag=siguiente       # capa con Fn (Fn + AvPág)
python3 ak820.py teclas restaurar                  # capa normal de fábrica
python3 ak820.py teclas --fn restaurar             # capa con Fn de fábrica
python3 ak820.py teclas lista                      # todos los nombres
```

- Cada envío manda **la tabla entera de esa capa**: los cambios anteriores de esa capa se
  sustituyen. Pon todos los cambios en la misma orden.
- Los orígenes se llaman como están **rotulados** en el teclado (`win`, `alt`…). En modo
  Mac el teclado intercambia Win y Alt por su cuenta; una tecla cambiada manda
  exactamente lo que se pide (`cmd`, `option`…), sin ese intercambio.
- En la capa con Fn no se pueden cambiar Esc, Inicio ni Win (el programa oficial tampoco).

## Probado en el teclado

| Prueba | Resultado |
|---|---|
| AvPág → `b`, RePág → `x` | ✅ |
| RePág → `cmd+a` (selecciona todo) | ✅ |
| AvPág → `volumen+` | ✅ |
| Supr → `clic_der` | ✅ (con el bit USB `02`; `04` es el botón central) |
| Fn + AvPág → `play` | ✅ |
| Todas las teclas asignadas a sí mismas | ⚠️ Cmd/Option se cambiaron: el modo Mac deja de intercambiar Win y Alt |

## De dónde sale

Ningún proyecto de la comunidad lo tenía para este firmware (solo expone las
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
2. `04 11 … [8]=09` (capa normal) o `04 27 … [8]=09` (capa con Fn)
3. La tabla: **576 bytes** = 144 teclas × 4, terminada en `AA 55`, en 9 paquetes de 64
   seguidos, **sin leer respuesta**, con 35 ms entre ellos
4. `04 02` (confirmar) y `04 F0` (guardar)

El programa oficial espera **35 ms antes y después de cada orden**. Sin la pausa de
antes, el teclado ignora la tabla.

Cada tecla ocupa los bytes `key_index × 4` a `key_index × 4 + 3`:

| Bytes | Significado |
|---|---|
| `00 00 00 00` | Sin cambios (lo de fábrica) |
| `02 <mods> <tecla> 00` | Tecla o combinación. Mods: Ctrl `01`, Shift `02`, Alt/Option `04`, Win/Cmd `08` (los derechos: `10 20 40 80`) |
| `02 <mods> 00 00` | Solo modificadores |
| `03 <lo> <hi> 00` | Multimedia (USB "consumer"): play `CD`, siguiente `B5`, anterior `B6`, stop `B7`, silencio `E2`, vol+ `E9`, vol− `EA` |
| `01 01 <botones> 00` | Clic de ratón: izq. `01`, der. `02`, central `04`, atrás `08`, adelante `10` |
| `01 03 <rueda> 00` | Rueda: `01` arriba, `FF` abajo |

Otros tipos que usa el programa oficial y aún no están en `ak820.py`: macros
(`07 …`, necesitan subir también la macro), `05 02 xx` (funciones internas) y
`05 03 00 00` (probablemente "desactivar tecla").
