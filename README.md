# ak820-mac

Configurador casero del teclado **Ajazz AK820 Pro** para macOS. El programa oficial
solo existe para Windows.

## Qué hace ahora

- `buscar`: comprueba que el Mac ve el teclado. No cambia nada.
- `reloj`: pone en hora la pantalla del teclado.
- `luces`: cambia las luces RGB (efecto, color, brillo, velocidad y dirección). Se guarda en el teclado.
- `reposo`: tiempo sin usar el teclado hasta que se apagan las luces (1, 5, 30 min o nunca). Solo actúa con batería (Bluetooth o 2.4G sin cable).
- `teclas`: cambia lo que escribe cada tecla **dentro del propio teclado** (vale en cualquier ordenador). Ver [docs/teclas.md](docs/teclas.md).
- `imagen`: pone una foto o dibujo en la pantalla del teclado. Ver [docs/pantalla.md](docs/pantalla.md).

## Cómo ejecutarlo en tu Mac

1. Conecta el teclado **por cable USB-C** (ni Bluetooth ni el receptor 2.4G sirven para configurar).
2. Abre la app **Terminal** y entra en la carpeta del proyecto:
   ```
   cd ~/Proyectos/ak820-mac
   ```
3. La primera vez, prepara Python e instala la librería para hablar con dispositivos USB:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   (Las siguientes veces solo necesitas `source .venv/bin/activate`.)
4. Comprueba que ve el teclado:
   ```
   python3 ak820.py buscar
   ```
5. Pon el reloj en hora:
   ```
   python3 ak820.py reloj
   ```
   Para comprobar que de verdad funciona, prueba con una hora rara y mira la pantalla:
   ```
   python3 ak820.py reloj --hora "2026-01-01 12:34"
   ```
6. Cambia las luces. Algunos ejemplos:
   ```
   python3 ak820.py luces fijo --color FF0000          # todo rojo fijo
   python3 ak820.py luces fijo --color 00AAFF --brillo 2   # azul claro, más tenue
   python3 ak820.py luces respirar --color 8000FF --velocidad 2   # morado que "respira"
   python3 ak820.py luces rodar --arcoiris --direccion derecha    # ola de colores
   python3 ak820.py luces apagado                      # apagar las luces
   ```
   - El color va en hexadecimal (`RRGGBB`); cualquier "selector de color" de internet te lo da.
   - Brillo y velocidad van de 0 a 5. Direcciones: `izquierda`, `derecha`, `arriba`, `abajo`
     (solo algunos efectos, como `rodar`, `desplazar` o `fluir`, las usan).
   - Para ver todos los efectos: `python3 ak820.py luces --help`

Si `python3` no existe, macOS te ofrecerá instalar las "herramientas de línea de comandos"; acepta.
Si `pip install` falla, instala [Homebrew](https://brew.sh) y ejecuta `brew install hidapi`.

## App de la barra de menús

Para usarlo sin la terminal: un icono ⌨︎ arriba a la derecha con el reloj, las luces
(efecto, color y brillo), la imagen o GIF de la pantalla, el reposo, los ajustes del
sistema y el **editor de teclas**.

**Instalarla como una app más** (con su icono, en Aplicaciones):
```
./crear-app.sh
```
Crea `AK820.app` con [py2app](https://py2app.readthedocs.io), la copia a Aplicaciones y la
abre. Después se abre como cualquier app (Launchpad, Spotlight: "AK820"). Para que se
abra sola al encender el Mac: Ajustes del Sistema → General → Ítems de inicio → añadir
AK820. Si cambias el código, vuelve a ejecutar `./crear-app.sh`.

**Sin instalarla** (para probar cambios): doble clic en `Abrir AK820.command`, o
`python3 ak820_app.py` con el entorno activado (la primera vez:
`pip install -r requirements-app.txt`).

Al conectar el teclado por cable, la app **pone la hora sola** (se puede quitar en
Reloj → Ponerla sola al conectar el teclado). Como poner la hora vuelve a enseñar el
reloj en la pantalla, no lo hace si lo último que mandaste a la pantalla fue una imagen.

Mientras trabaja, el icono pasa a **⌨︎…** (o al % enviado, con las imágenes). Cuando
acaba bien sale **⌨︎ ✓** unos segundos; si algo falla, una ventana explica qué pasa. Lo
que va haciendo se guarda en `~/Library/Logs/ak820-app.log`. Como siempre, el teclado
tiene que estar **por cable** (y en modo cable, no en Bluetooth ni 2.4G).

### La ventana de AK820

**Abrir AK820…** abre la ventana de la app, con cuatro pestañas:

- **Teclas**: un dibujo del teclado; pinchas una tecla, eliges qué hace (otra tecla o un
  atajo, multimedia, ratón, escribir un texto o varias teclas a la vez), en la capa
  normal o en la de Fn, y pulsas **Enviar al teclado**.
- **Luces**: efecto, color, brillo, velocidad y dirección; se aplican al momento. Con
  **🎨 Tecla a tecla** sale el dibujo del teclado para pintar cada tecla de un color.
- **Pantalla**: elegir (o arrastrar) una imagen o GIF y enviarlo, con el progreso; o
  volver al reloj.
- **Ajustes**: tecla Fn, reposo, tiempo de respuesta y bloqueos.

Mientras la ventana está abierta, AK820 sale en el Dock y en Cmd+Tab. Sin la app, la
misma página se abre en el navegador con `python3 ak820_editor.py`.

La página solo funciona en este Mac (`127.0.0.1`) y con la clave que pone la app en la
dirección, así que ninguna otra web puede tocar el teclado.

## Teclas de Mac (la 🌐)

El AK820 no tiene la tecla 🌐 (Fn/Globo de Mac) y no puede enviarla. Lo resolvemos en macOS:
`teclas-mac.sh` le dice al Mac que el **Control derecho** del AK820 haga de 🌐, y que **Home** sea F13
(en *Ajustes del Sistema → Teclado → Atajos de teclado → Capturas de pantalla* se le asigna la captura).
Solo afecta al AK820 (el teclado del portátil queda igual) y funciona por cable, Bluetooth y 2.4G.

```
./instalar-teclas-mac.sh          # aplicarlo para siempre (también tras reiniciar)
./instalar-teclas-mac.sh quitar   # volver a como estaba
```

## Reposo y otros ajustes del sistema

```
python3 ak820.py reposo 5                      # 1, 5, 30 o nunca
python3 ak820.py sistema --fn-modo alternar    # Fn activa/desactiva la capa Fn (de fábrica: mantener)
python3 ak820.py sistema --respuesta 3         # antirrebote, nivel 1 (rápido) a 5; de fábrica 2
python3 ak820.py sistema --bloquear win        # también altf4, alttab (solo en modo Windows)
python3 ak820.py sistema                       # ver los últimos ajustes enviados
python3 ak820.py sistema --fabrica             # volver a los de fábrica
```

El reposo se configura por cable, pero solo se nota con batería: enchufado por USB las
luces no se apagan. Todos estos ajustes viajan en el mismo paquete y el teclado no deja
leerlos, así que el programa recuerda los últimos enviados (en
`~/Library/Application Support/ak820-mac/sistema.json`) para no pisar unos al cambiar otros.

## Cambiar teclas dentro del teclado

```
python3 ak820.py teclas avpag=b                  # PgDn escribe "b"
python3 ak820.py teclas repag=cmd+a avpag=volumen+  # combinaciones y multimedia
python3 ak820.py teclas supr=clic_der              # ratón (también clic_medio, doble_clic, rueda_abajo...)
python3 ak820.py teclas --fn avpag=play            # capa con Fn (Fn + PgDn)
python3 ak820.py teclas avpag=texto:Hola           # macro: el teclado escribe "Hola"
python3 ak820.py teclas avpag=texto:hola --modo mantener  # se repite mientras se mantiene
                                                   # (también alternar y paso)
python3 ak820.py teclas avpag=multi:a+s            # "Multi-Key": hasta 3 teclas a la vez
python3 ak820.py teclas avpag=defecto              # esa tecla vuelve a ser la de fábrica
python3 ak820.py teclas                            # ver las teclas cambiadas
python3 ak820.py teclas restaurar                  # la capa normal de fábrica (--fn: la de Fn)
python3 ak820.py teclas restaurar todo             # las dos capas de fábrica
python3 ak820.py teclas lista                      # todos los nombres
```

Los cambios se suman a los que ya había: el programa recuerda lo que tiene el teclado
(en `~/Library/Application Support/ak820-mac/teclas.json`, porque el teclado no deja
leerlo) y cada vez manda las dos capas y todas las macros. Es lo mismo que usa el editor,
así que se puede mezclar uno y otro. Si el teclado se resetea por otro lado,
`python3 ak820.py teclas reenviar` le vuelve a mandar lo guardado. Detalles en
[docs/teclas.md](docs/teclas.md).

## Colores tecla a tecla

```
python3 ak820.py colores avpag=FF0000 esc=FFD000 fn=FF00FF   # cada tecla de un color
python3 ak820.py colores --fondo 102040                       # el resto de teclas (000000 = apagadas)
python3 ak820.py colores avpag=defecto --brillo 3             # esa tecla vuelve al fondo; brillo 1-5
python3 ak820.py colores                                      # ver los colores guardados
python3 ak820.py colores restaurar                            # todas al fondo apagado
python3 ak820.py luces fijo --color 0000FF                    # volver a un efecto normal
```

Pone el efecto "personal" (0x80) y manda una tabla de 576 bytes con `[n.º, R, G, B]` en el
hueco de cada tecla, igual que la de teclas (función `0x44ba10` del programa oficial,
orden `04 23`). Como las teclas, el teclado no deja leerlos: se recuerdan en
`colores.json` y los cambios se suman. `luces personal` vuelve a los colores guardados.

## Imagen en la pantalla

```
python3 ak820.py imagen ~/Desktop/foto.jpg   # cualquier JPG/PNG; se recorta al centro a 128x128
python3 ak820.py imagen ~/Desktop/anim.gif   # GIF animado (hasta 140 fotogramas, 30-500 ms cada uno)
python3 ak820.py imagen prueba               # franjas de prueba para diagnosticar
python3 ak820.py reloj                       # volver al reloj (o salir de "loading")
```

Cómo se descubrió (y todo lo que no funcionó por el camino) en [docs/pantalla.md](docs/pantalla.md).

## Sin cable: el receptor 2.4G

Si el teclado está en modo 2.4G con su receptor, `ak820.py` (y la app) lo usan solos
cuando no hay cable: luces, teclas, macros, ajustes y la hora. Los colores tecla a tecla
y la imagen de la pantalla solo van por cable. Si no contesta, el teclado se habrá
dormido: pulsa una tecla. Por Bluetooth no se puede configurar. Detalles en
[docs/receptor-24g.md](docs/receptor-24g.md).

## Pruebas automáticas

```
.venv/bin/python -m unittest discover -s tests
```

Comprueban los formatos y las secuencias de envío con un **teclado falso** (responde con
la suma de lo recibido, como el de verdad), así que no hace falta tener el AK820
conectado ni se toca nada. Las pruebas hechas con el teclado de verdad están en
[docs/pruebas.md](docs/pruebas.md).

## Próximos pasos

Todo lo previsto funciona. Queda como idea el modo música (luces al ritmo del sonido;
el receptor tiene su orden, `0B`, pero en Mac hay que capturar el audio del sistema).

## Créditos

El protocolo lo descifró la comunidad, en proyectos con licencia MIT:
[gohv/EPOMAKER-Ajazz-AK820-Pro](https://github.com/gohv/EPOMAKER-Ajazz-AK820-Pro),
[TaxMachine/ajazz-keyboard-software-linux](https://github.com/TaxMachine/ajazz-keyboard-software-linux),
[Aiacos/ajazz-control-center](https://github.com/Aiacos/ajazz-control-center) y
[gusleig/ajazz-ak820-pro-mac](https://github.com/gusleig/ajazz-ak820-pro-mac).

Proyecto no oficial, sin relación con Ajazz ni Epomaker. Úsalo bajo tu responsabilidad.
