# Imagen en la pantalla desde macOS: lo que sabemos

Estado (17 de octubre de 2026): **funciona a veces**. Hemos mostrado imágenes casi
perfectas en la pantalla desde el Mac, pero repetir exactamente el mismo envío no siempre
da el mismo resultado. Es un problema de **ritmo**, no de formato.

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

## Próximos pasos

1. **Analizar el programa oficial de Windows** (la función que sube la imagen) para ver
   el ritmo exacto, el tamaño real de cada bloque y cómo se cierra la subida.
2. Si hace falta afinar: una **cámara apuntando a la pantalla** que el programa pueda
   leer, para probar variantes sin depender de fotos hechas a mano.

Para probar: `python3 ak820.py imagen prueba` muestra 8 franjas numeradas (cada una es
un bloque) con una raya negra en el centro: con una foto se ve qué bloque falla y cuánto
se ha movido la imagen.
