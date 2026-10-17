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
python3 ak820.py teclas avpag=texto:Hola           # macro: el teclado escribe "Hola"
python3 ak820.py teclas avpag=texto:hola --veces 3 # ...y lo repite 3 veces
python3 ak820.py teclas avpag=multi:a+s            # Multi-Key: A y S a la vez
python3 ak820.py teclas restaurar                  # capa normal de fábrica
python3 ak820.py teclas --fn restaurar             # capa con Fn de fábrica
python3 ak820.py teclas lista                      # todos los nombres
```

- Cada envío manda **la tabla entera de esa capa**: los cambios anteriores de esa capa se
  sustituyen. Pon todos los cambios en la misma orden.
- Los orígenes se llaman como están **rotulados** en el teclado (`win`, `alt`…). En modo
  Mac el teclado intercambia Win y Alt por su cuenta; una tecla cambiada manda
  exactamente lo que se pide (`cmd`, `option`…), sin ese intercambio.
- En la capa con Fn no se pueden cambiar Esc, Inicio ni Win (el programa oficial tampoco),
  ni Supr (el teclado ignora el cambio).

## Probado en el teclado

| Prueba | Resultado |
|---|---|
| AvPág → `b`, RePág → `x` | ✅ |
| RePág → `cmd+a` (selecciona todo) | ✅ |
| AvPág → `volumen+` | ✅ |
| Supr → `clic_der` | ✅ (con el bit USB `02`; `04` es el botón central) |
| Fn + AvPág → `play` | ✅ |
| AvPág → macro "hola", 3 veces / "Hola", 2 veces | ✅ |
| AvPág → `multi:a+s` (Multi-Key) | ✅ escribe "as" |
| AvPág → macro "hola" `--modo mantener` | ✅ se repite mientras se mantiene |
| AvPág → macro "hola" `--modo alternar` | ✅ un toque empieza, otro para |
| `sistema --fn-modo alternar` + Fn + AvPág → `b` | ✅ un toque a Fn activa la capa Fn, otro la quita |
| RePág → `multi:shift+a` (se guarda como `shift+a`) | ✅ escribe "A" |
| AvPág → `doble_clic` (macro de dos clics) | ✅ selecciona la palabra |
| Supr → `clic_medio`; Fn + AvPág → `clic_medio` | ✅ también en la capa Fn |
| `rueda_abajo` / `rueda_arriba` (también con Fn) | ✅ una muesca por pulsación |
| `anterior`, `siguiente`, `silencio`, `volumen-`; Fn → `brillo-`, `brillo+` | ✅ |
| AvPág → macro "hola" `--modo paso` (modo 4) | ✅ cada pulsación escribe la siguiente letra |
| AvPág → Multi-Key `07 E1 04 00` (Shift + A) | ⚠️ escribe "a": macOS ignora el Shift |
| Ratón `01 01 03` (el "doble clic" del programa oficial) | ⚠️ pulsa izquierdo y derecho a la vez: en el Mac, clic derecho |
| Rueda `01 03 05` (cinco muescas) | ⚠️ baja solo una: el teclado ignora el valor |
| Ratón botones 4/5 (`08`/`10`, atrás/adelante) | ❌ el ratón del teclado solo declara 3 botones; el Mac los descarta |
| Fn + Supr → `b` | ❌ el teclado no deja cambiarla |
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
| `01 01 <botones> 00` | Clic de ratón: izq. `01`, der. `02`, central `04` (el oficial también ofrece atrás `08` y adelante `10`, pero el ratón del teclado solo declara 3 botones) |
| `01 03 <rueda> 00` | Rueda: `01` arriba, `FF` abajo (una muesca por pulsación) |
| `06 <macro> <modo> <veces>` | Lanza la macro n.º `<macro>`. Modos del programa oficial: 0 una vez, 1 N veces, 2 hasta volver a pulsar, 3 mientras se mantiene, 4 "al hacer clic" (cada pulsación escribe la siguiente tecla de la macro; `--modo paso`) |
| `07 <t1> <t2> <t3>` | "Multi-Key": hasta 3 teclas normales a la vez (códigos USB; hueco libre `00`) |

En el Multi-Key, el programa oficial también deja poner modificadores (`E0`–`E7`), pero
el teclado los manda como teclas normales y macOS los ignora: `07 E1 04 00` escribe "a",
no "A". Por eso `multi:shift+a` se guarda como la combinación `02 02 04 00`.

Otros tipos del programa oficial que no están en `ak820.py`: `05 02 xx` (abrir programa, web o enviar texto: los ejecuta
el programa del PC, no el teclado) y `05 03 00 00` (probablemente "desactivar tecla").

## Macros

Se suben antes de la tabla de teclas (función `0x42d6f0` del programa oficial):

1. `04 19` → `04 15 … [8]=<n.º de paquetes>` → bloque en paquetes de 64 sin leer
   respuesta → `04 02`. No lleva `04 18` delante.
2. Bloque (máx. 3584 bytes): índice de 100 entradas de 4 bytes (bytes 0–1 = posición
   del cuerpo de cada macro); desde el byte 400, cada macro: n.º de eventos (2 bytes),
   6 bytes a 0 y eventos de 4 bytes:
   - `00 00 <tecla> B0` pulsar, `00 00 <tecla> 30` soltar (códigos USB; Shift = `E1`…)
   - `<ms> <ms> 00 50` esperar (mínimo 10 ms; el oficial pone una tras cada acción)
   - `00 00 <botón> 90` / `10` pulsar / soltar botón del ratón
3. Se rellena hasta múltiplo de 64 dejando sitio para `AA 55` en los dos últimos bytes.

**Comprobación:** al `04 02` final el teclado responde con la **suma de los bytes
recibidos** (bytes 5–6 de la respuesta). Pasa igual con la tabla de teclas. `ak820.py`
la compara y repite el envío si no coincide: la primera subida de macros a veces se
pierde (probablemente mientras el teclado borra su memoria).

Los textos se escriben con la distribución inglesa de EE. UU. (letras, números,
espacio y símbolos básicos). En un Mac con teclado en español, los símbolos pueden
salir distintos; las letras y números salen bien.
