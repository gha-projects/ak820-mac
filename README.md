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

## Teclas de Mac (la 🌐)

El AK820 no tiene la tecla 🌐 (Fn/Globo de Mac) y no puede enviarla. Lo resolvemos en macOS:
`teclas-mac.sh` le dice al Mac que el **Control derecho** del AK820 haga de 🌐, y que **Home** sea F13
(en *Ajustes del Sistema → Teclado → Atajos de teclado → Capturas de pantalla* se le asigna la captura).
Solo afecta al AK820 (el teclado del portátil queda igual) y funciona por cable, Bluetooth y 2.4G.

```
./instalar-teclas-mac.sh          # aplicarlo para siempre (también tras reiniciar)
./instalar-teclas-mac.sh quitar   # volver a como estaba
```

## Reposo

```
python3 ak820.py reposo 5        # 1, 5, 30 o nunca
```

Se configura por cable, pero solo se nota con batería: enchufado por USB las luces no
se apagan. El paquete lleva también otros ajustes del sistema (tecla Fn, tiempo de
respuesta de las teclas, desactivar Win/Alt+F4/Alt+Tab); se envían con los valores por
defecto del programa oficial.

## Cambiar teclas dentro del teclado

```
python3 ak820.py teclas avpag=b                  # PgDn escribe "b"
python3 ak820.py teclas repag=cmd+a avpag=volumen+  # combinaciones y multimedia
python3 ak820.py teclas supr=clic_der              # ratón
python3 ak820.py teclas --fn avpag=play            # capa con Fn (Fn + PgDn)
python3 ak820.py teclas avpag=texto:Hola           # macro: el teclado escribe "Hola"
python3 ak820.py teclas restaurar                  # todas de fábrica (añade --fn para esa capa)
python3 ak820.py teclas lista                      # todos los nombres
```

Cada vez se manda la tabla entera de la capa, así que pon todos los cambios en la misma
orden. Detalles en [docs/teclas.md](docs/teclas.md).

## Imagen en la pantalla

```
python3 ak820.py imagen ~/Desktop/foto.jpg   # cualquier JPG/PNG; se recorta al centro a 128x128
python3 ak820.py imagen ~/Desktop/anim.gif   # GIF animado (hasta 140 fotogramas, 30-500 ms cada uno)
python3 ak820.py imagen prueba               # franjas de prueba para diagnosticar
python3 ak820.py reloj                       # volver al reloj (o salir de "loading")
```

Cómo se descubrió (y todo lo que no funcionó por el camino) en [docs/pantalla.md](docs/pantalla.md).

## Próximos pasos

Todo lo previsto funciona. Ideas que quedan: el tipo "Multi-Key" (hasta 3 teclas a la
vez), los otros modos de repetición de las macros y exponer el resto de ajustes del
sistema (tecla Fn, tiempo de respuesta).

## Créditos

El protocolo lo descifró la comunidad, en proyectos con licencia MIT:
[gohv/EPOMAKER-Ajazz-AK820-Pro](https://github.com/gohv/EPOMAKER-Ajazz-AK820-Pro),
[TaxMachine/ajazz-keyboard-software-linux](https://github.com/TaxMachine/ajazz-keyboard-software-linux),
[Aiacos/ajazz-control-center](https://github.com/Aiacos/ajazz-control-center) y
[gusleig/ajazz-ak820-pro-mac](https://github.com/gusleig/ajazz-ak820-pro-mac).

Proyecto no oficial, sin relación con Ajazz ni Epomaker. Úsalo bajo tu responsabilidad.
