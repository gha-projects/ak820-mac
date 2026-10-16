# Imagen en la pantalla desde macOS: lo que sabemos

Estado (17 de octubre de 2026): **funciona** en el AK820 con PID 0x800A, por cable
(`python3 ak820.py imagen foto.png`).

## La solución, en corto

Formato exacto del programa oficial (sacado de su código, ver más abajo):

1. `04 18` (byte 8 = 0) → `04 72 01 00 00 00 00 00 09 00` (9 bloques)
2. 9 bloques de 4096 bytes por la interfaz 0xFF68, esperando tras cada uno el
   "recibido" (`01 5a 02`): 256 bytes de cabecera (`[0]=1` fotograma, `[1]=1`, resto
   `FF`) + 128×128 píxeles RGB565 little-endian + relleno `FF`
3. `04 02` — y nada de `F0`

**Y esperar 35 ms antes de cada orden**, como hace el programa oficial. Sin esa pausa
el teclado ignora el `04 02` final: la pantalla "carga" y vuelve a sus animaciones.
Ese detalle es lo que nos tuvo toda la noche dando vueltas; lo que sigue es la historia.

Los repos de la comunidad daban la subida de imágenes por imposible en macOS ("la
interfaz 0xFF68 se cuelga"). No lo es: solo hay que avisar antes al teclado.

## Lo confirmado con el teclado (AK820, PID 0x800A, por cable)

- **Aviso por la interfaz de configuración (0xFF13)**, como "feature reports":
  `EMPEZAR` (`04 18 … [8]=01`) y luego `04 72 02 … [8]=09` (9 bloques).
  Sin este aviso, escribir en 0xFF68 se queda colgado (lo que vio la comunidad).
- **Los datos van por 0xFF68** como "output reports" (`hid.write`), sin colgarse.
- **Formato**: 128×128 píxeles, RGB565 *little-endian* (los colores salen bien),
  precedido de 256 bytes de cabecera (`[0]` = número de fotogramas). La pantalla admite GIF.
- **"Recibido"**: tras cada 4096 bytes, el teclado responde por 0xFF68 con
  `01 5a 02 00…`. El primer bloque tarda ~130 ms; los siguientes ~38 ms; el último ~115 ms.
- **La animación de Ajazz / "loading"** significa que el teclado sigue esperando datos.
  Se sale con `python3 ak820.py reloj`. Hay que hacerlo **antes de cada prueba**, o los
  datos nuevos se mezclan con la subida anterior.

## Lo que hemos probado

| Envío (9 bloques) | Resultado |
|---|---|
| 4096 bytes cada uno, esperando el "recibido" | Los 9 confirmados, pero se queda en "loading" (cerrando con `F0`, con `02`, o añadiendo un paquete corto al final) |
| 4096 + paquete vacío | macOS no deja enviar paquetes vacíos (`write` devuelve -1) |
| 4096 + 63 bytes | "loading" |
| 4096 + 64 bytes | "loading" |
| **4096 + 27 bytes**, imagen colocada cada 4160 bytes | **Se ve la imagen**, pero no siempre: unas veces perfecta, otras corrida ±32 píxeles o con rayitas del bloque anterior, otras "loading" |

Por qué "cada 4160 bytes": el teclado guarda cada paquete USB en un hueco de 64 bytes,
así que el paquete corto de 27 ocupa 64 y cada bloque llena 4160 bytes de su memoria
(se vio en las fotos: sin tenerlo en cuenta, la imagen sale en escalera, 32 píxeles más
por cada bloque).

Las rayitas "del color de la franja de arriba" indican que llegan datos de un bloque
mientras el teclado aún guarda el anterior: "recibido" no significa "guardado".

## Formato oficial encontrado en internet (17/10, madrugada)

[nurlanjalil/ajazz-ak820-config](https://github.com/nurlanjalil/ajazz-ak820-config)
documenta el formato del programa oficial (grabación USB + análisis, hecho sobre el
AKS075, hermano del AK820): EMPEZAR con byte 8 = `0x00`; aviso `04 72 03` + n.º de
bloques; 9 bloques de 4096 bytes esperando el "recibido" de cada uno; cabecera con
`[0]=1` fotograma y `[1]=0`; cierre con `04 02` y **sin** `F0`. Otro proyecto
([allshouldbeready/ak820-pro-macos](https://github.com/allshouldbeready/ak820-pro-macos))
llama "hueco" (slot) al byte `03`/`02` del aviso.

Resultado en nuestro teclado (PID 0x800A), probado con el formato oficial completo:

| Hueco | Resultado |
|---|---|
| `0x03` | Los 9 bloques confirmados; la pantalla "carga" y luego vuelve a las animaciones de Ajazz |
| `0x02` | Igual |

Es decir: **recibe la imagen entera y la rechaza al final**. Coincide con
[la incidencia #6 de gohv](https://github.com/gohv/EPOMAKER-Ajazz-AK820-Pro/issues/6):
en el modelo 0x800A las imágenes salen corruptas. Algo cambia en esta revisión
(cabecera, tamaño o comprobación final) y nadie lo ha documentado aún.

`ak820.py imagen` usa ahora la secuencia exacta del programa oficial (ver abajo),
aunque en el 0x800A todavía no se ve la imagen.

## Lo que hace el programa oficial (análisis del instalador v1.0.0.5)

Del instalador oficial "AJAZZ AK820 PRO … 0.85英寸彩屏 … V1.0.0.5" (Inno Setup; se
extrae sin ejecutarlo descomprimiendo sus bloques LZMA y deshaciendo el filtro de
llamadas x86 de Inno) salen:

- `config.xml`: **el 0x800A está declarado igual que el 0x8009**, con la misma pantalla
  (`width=128 height=128 gif_headlength=256 gif_maxframes=140`). Así que el programa
  oficial usa el mismo protocolo para los dos.
- La función que sube la imagen (`0x422980` en `DeviceDriver.exe`):
  1. Reserva `256 + fotogramas × 128 × 128 × 2` bytes, todo a `0xFF`.
     Cabecera: `[0]` = n.º de fotogramas, `[1+i]` = duración/2 **con mínimo 1**.
  2. `04 18` con el resto a cero (feature report).
  3. `04 72 HH 00 00 00 00 00 NN nn`: `HH` = **hueco = posición elegida en su lista
     (`LCDViewList::GetCurSel()`) + 1**; `NNnn` = n.º de bloques.
  4. Por cada bloque: `WriteFile` de `00` + 4096 bytes, y `ReadFile` del "recibido"
     con 300 ms de tiempo máximo. Sin pausas ni reintentos.
  5. `04 02` y nada más.
- En sus textos, el botón de subir dice **"Save data and upload boot animation"**: lo
  que se sube es la **animación de arranque**.

- El "hueco" (`GetCurSel() + 1`) es la posición de la animación elegida en la lista
  del programa del PC (cada una es una carpeta `led\<fecha>\` con sus GIF), no una
  zona del teclado. El paquete del reloj lleva ese mismo número en su byte 1
  (nosotros enviamos 1, como gohv); enviarlo con 2 no cambia lo que se ve.
- V1.0.0.5 es la versión más reciente del programa oficial para el modelo con pantalla.

Con esa secuencia exacta (hueco 1, duración 1) el teclado confirma los 9 bloques,
"carga" y vuelve a sus animaciones. Tras desenchufar y volver a enchufar, el arranque
sigue mostrando la animación de Ajazz. **Falta averiguar** qué hueco se muestra y
cuándo (o si hay otro comando que lo elige), y qué hace la función auxiliar que envía
los feature reports (`0x44eed0`).

## Próximos pasos

1. **Ejecutar el programa oficial con este teclado** (Windows en una máquina virtual con
   UTM, pasándole el USB). Si tampoco consigue cambiar la imagen, es un límite del
   firmware del 0x800A; si lo consigue, registrar sus llamadas (p. ej. con API Monitor)
   y compararlas con las nuestras.
2. Si hace falta afinar: una **cámara apuntando a la pantalla** que el programa pueda
   leer, para probar variantes sin depender de fotos hechas a mano.

Para probar: `python3 ak820.py imagen prueba` muestra 8 franjas numeradas (cada una es
un bloque) con una raya negra en el centro: con una foto se ve qué bloque falla y cuánto
se ha movido la imagen.
