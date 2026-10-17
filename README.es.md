<p align="center"><img src="docs/img/icono.png" width="96" alt=""></p>

# ak820-mac

**Una app de Mac para el teclado Ajazz AK820 Pro** (el de la pantallita). El programa
oficial solo existe para Windows; este se ha hecho analizándolo, y cubre lo que de verdad
se usa: teclas, macros, luces, la pantalla y el modo música.

*[Read in English](README.md)*

![La pestaña Teclas](docs/img/teclas.png)

## Qué hace

- **Teclas**: cambiar lo que hace cualquier tecla, en la capa normal o en la de Fn: otra
  tecla, un atajo (⌘C…), multimedia, clics y rueda del ratón, macros de texto (una vez,
  N veces, mientras se mantiene, hasta volver a pulsar…) o varias teclas a la vez. Se
  guarda en el teclado, así que vale en cualquier ordenador.
- **Luces**: los 19 efectos del teclado con color, brillo, velocidad y dirección;
  **colores tecla a tecla** (pintando las teclas en un dibujo del teclado); y un **modo
  música** en el que las teclas son un ecualizador que sigue lo que suena en el Mac.
- **Pantalla**: poner una foto o un **GIF animado** en la pantalla de 0,85" (se recorta a
  128×128, hasta 140 fotogramas), ver cuál tiene, o volver al reloj.
- **Reloj**: se pone en hora solo al conectar el teclado.
- **Ajustes**: modo de la tecla Fn, reposo y tiempo de respuesta de las teclas. Volver
  a mandar al teclado lo que tiene guardado el Mac, o dejarlo todo de fábrica.
- **Ayuda**: qué hace cada tecla de fábrica (los atajos con Fn; F1–F12, que en modo Mac
  funcionan como la fila de arriba de un Mac; la rueda, los interruptores y las luces
  **C** y **W**: Bloq Mayús y bloqueo de Win), sacado del
  [manual oficial](https://epomaker.com/cdn/shop/files/AK820_PRO_manual.pdf). La pestaña
  Teclas también enseña la función de fábrica de cada tecla.
- **Sin cable**: luces, teclas, macros, ajustes y la hora funcionan también con el
  **receptor 2.4G**. El menú también enseña la batería si el receptor la da (el de las
  pruebas siempre contesta «no lo sé»; la pantalla del teclado sí la enseña).

Es una app de la barra de menús con su propia ventana, y también un programa de terminal.

| Colores tecla a tecla | Modo música |
|---|---|
| ![](docs/img/luces-tecla-a-tecla.png) | ![](docs/img/musica.png) |

## Con qué funciona

Lo que cuenta es el identificador USB del teclado y sus interfaces, no la caja: el AK820
Pro lo venden Ajazz, Epomaker y **Ajazz × Nacodex**. `python3 ak820.py buscar` enseña lo
que ve tu Mac.

| Teclado | Estado |
|---|---|
| Cable, `0C45:800A` con la interfaz `0xFF13` | ✅ Todo, probado en un teclado de verdad |
| Cable, `0C45:8009` con la interfaz `0xFF13` | 🟡 Debería ir (el programa oficial usa el mismo protocolo), sin probar todavía |
| Receptor 2.4G, `0C45:FDFD` | ✅ Teclas, macros, luces, ajustes, hora y modo música. Los colores tecla a tecla y la pantalla, solo por cable (como en el programa oficial). La batería no sale: el receptor de las pruebas siempre contesta «no lo sé» |
| Bluetooth, `0C45:FEFE` | ❌ No tiene interfaz de configuración |
| Firmware más nuevo, con la interfaz `0xFF67` | ❌ Otro protocolo |
| `1A2C:9605` (visto en un Nacodex) | ❌ Otro hardware |

¿Tu teclado no está aquí, o algo falla?
[Abre una incidencia](../../issues/new/choose) y pega lo que sale con `buscar`.

- **Distribución**: el dibujo de las teclas es el ANSI (EE. UU.) del programa oficial. En
  un teclado ISO alguna tecla puede estar en otro sitio.
- **Mac**: probado en Apple Silicon con macOS 26. Cada uno se la compila en su Mac, así
  que en Intel también debería ir. El modo música necesita **macOS 14.2** o posterior; lo
  demás debería funcionar también en versiones anteriores.
- **Idioma**: español o inglés, según el idioma del Mac (Ajustes del Sistema → General →
  Idioma y región). Para añadir otro, mira [CONTRIBUTING.md](CONTRIBUTING.md) (en
  inglés).

## Instalación

Hacen falta las **herramientas de línea de comandos de Xcode** (traen Python 3 y el
compilador de Swift). Si no las tienes, al escribir `python3` en la Terminal macOS ofrece
instalarlas.

```sh
git clone https://github.com/gha-projects/ak820-mac.git
cd ak820-mac
/usr/bin/python3 -m venv .venv
.venv/bin/pip install -r requirements-app.txt
./crear-app.sh
```

`/usr/bin/python3` es el Python que traen las herramientas de línea de comandos: usa ese
aunque tengas otro (el de Homebrew, por ejemplo), que es con el que se crea y se prueba la
app.

`crear-app.sh` crea **AK820.app**, la copia a Aplicaciones y la abre. A partir de ahí se
abre como cualquier app. Para que arranque al encender el Mac: Ajustes del Sistema →
General → Ítems de inicio. Si cambias el código, vuelve a ejecutar `./crear-app.sh`.

La primera vez que uses el modo música, macOS pide permiso para **grabar el audio del
sistema** (solo el audio, no la pantalla).

## Cómo se usa

- **La app**: al abrir AK820 sale su ventana, con cinco pestañas: **Teclas**, **Luces**,
  **Pantalla**, **Ajustes** y **Ayuda**. El icono ⌨︎ de la barra de menús tiene accesos
  rápidos (luces, modo música, reloj, reposo…). Mientras trabaja, el icono pasa a `⌨︎…`,
  `⌨︎ 45 %` o `⌨︎ ♪`, y lo que hace queda en `~/Library/Logs/ak820-app.log`.
- **La terminal** (desde la carpeta del proyecto):

  ```sh
  source .venv/bin/activate
  python3 ak820.py buscar                              # ¿ve el teclado?
  python3 ak820.py reloj                               # poner la hora
  python3 ak820.py luces respirar --color 8000FF       # un efecto (ver: luces --help)
  python3 ak820.py colores esc=FF0000 --fondo 102040    # colores tecla a tecla
  python3 ak820.py musica --modo arcoiris               # modo música, hasta Ctrl+C
  python3 ak820.py imagen ~/Escritorio/anim.gif         # foto o GIF en la pantalla
  python3 ak820.py teclas avpag=cmd+a repag=texto:Hola  # cambiar teclas (ver: teclas lista)
  python3 ak820.py teclas restaurar todo               # todas las teclas de fábrica
  python3 ak820.py sistema --fn-modo alternar          # ajustes (ver: sistema --help)
  python3 ak820.py bateria                             # batería, si el receptor la da
  python3 ak820.py reenviar                            # volver a mandar lo guardado
  python3 ak820.py fabrica --si                        # todo de fábrica
  ```

  Por 2.4G el receptor contesta aunque el teclado no le escuche (por ejemplo, nada más
  pasarlo a 2.4G), así que comprueba que el cambio se ve en el teclado.

El teclado no deja leer su configuración, así que el programa recuerda lo último que le
ha mandado en `~/Library/Application Support/ak820-mac/` (teclas, colores, luces, ajustes
y una copia de la imagen de la pantalla). Si el teclado se resetea o lo configuras en
otro ordenador, **Volver a mandar mi configuración** (o `reenviar`) lo deja como estaba.
Antes de dejarlo de fábrica guarda una copia de lo que tenías, para poder deshacerlo (en
Ajustes, o con `fabrica --deshacer`).

### Extra: la tecla 🌐 de Mac

El AK820 no tiene la tecla 🌐 (Fn/Globo) y no puede enviarla. `extras/teclas-mac.sh` le
dice a macOS que el **Control derecho** del AK820 haga de 🌐, y que **Inicio** sea F13
(para asignarle la captura de pantalla en Ajustes del Sistema → Teclado → Atajos). Solo
afecta al AK820.

```sh
./extras/instalar-teclas-mac.sh          # aplicarlo para siempre (también tras reiniciar)
./extras/instalar-teclas-mac.sh quitar   # dejarlo como estaba
```

## Cómo funciona

Todo sale del programa oficial de Windows (`DeviceDriver.exe` v1.0.0.5), analizado sin
ejecutarlo, y de muchas pruebas con el teclado. Se configura con "feature reports" HID de
64 bytes (las imágenes van por otra interfaz en bloques de 4 KB); el receptor 2.4G usa
mensajes de 32 bytes. Todos los formatos están en **[docs/PROTOCOL.md](docs/PROTOCOL.md)**
(en inglés). Las notas de cómo se descubrió cada cosa, en español:
[teclas](docs/teclas.md), [pantalla](docs/pantalla.md),
[receptor 2.4G](docs/receptor-24g.md) y [pruebas en el teclado](docs/pruebas.md).

| Archivo | Qué es |
|---|---|
| `ak820.py` | El protocolo y el programa de terminal |
| `ak820_app.py` | La app de la barra de menús ([rumps](https://github.com/jaredks/rumps)) |
| `ak820_ventana.py`, `ak820_editor.py`, `editor/` | La ventana: una página web local en un WKWebView, servida en `127.0.0.1` con una clave aleatoria |
| `musica/espectro.swift` | Escucha el audio del sistema (tap de Core Audio) y escribe el espectro en 21 bandas |
| `setup.py`, `crear-app.sh`, `app/` | Crear `AK820.app` con py2app |
| `tests/` | Pruebas con un teclado falso: `.venv/bin/python -m unittest discover -s tests` |
| `extras/` | La tecla 🌐 en macOS y un lanzador para probar cambios sin crear la app |

## Otros proyectos

Si prefieres cambiar el firmware del teclado,
[fpb/ajazz-ak820-pro](https://github.com/fpb/ajazz-ak820-pro) ha portado **QMK** al
AK820 Pro. Es otro camino: esta app habla con el firmware original y no funciona con QMK,
y hay varias revisiones del hardware, así que conviene leer sus notas antes de grabar
nada.

## Créditos

Es un programa nuevo y no copia código de otros proyectos, pero mucho de lo que sabe del
teclado lo descubrió antes la comunidad:

- [gohv/EPOMAKER-Ajazz-AK820-Pro](https://github.com/gohv/EPOMAKER-Ajazz-AK820-Pro): luces, reposo y
  reloj en Linux. Su incidencia #6 (imágenes rotas en el modelo `800A`) señaló el
  problema de la pantalla.
- [TaxMachine/ajazz-keyboard-software-linux](https://github.com/TaxMachine/ajazz-keyboard-software-linux):
  la primera referencia abierta de la interfaz de configuración y de la subida de
  imágenes.
- [KyleBoyer/TFTTimeSync-node](https://github.com/KyleBoyer/TFTTimeSync-node): el paquete del reloj.
- [Aiacos/ajazz-control-center](https://github.com/Aiacos/ajazz-control-center): notas del protocolo de
  varios teclados Ajazz, y el Nacodex con otro identificador USB.
- [gusleig/ajazz-ak820-pro-mac](https://github.com/gusleig/ajazz-ak820-pro-mac): la primera herramienta
  de Mac para este mismo modelo. Sus pruebas de remapeo mostraron qué formatos no
  funcionan.
- [nurlanjalil/ajazz-ak820-config](https://github.com/nurlanjalil/ajazz-ak820-config) y
  [aar-rafi/aks075-linux](https://github.com/aar-rafi/aks075-linux): el formato de imagen de la pantalla
  del programa oficial (en el AKS075, un modelo hermano).
- [allshouldbeready/ak820-pro-macos](https://github.com/allshouldbeready/ak820-pro-macos) y
  [wsclx/ak820pro-modder](https://github.com/wsclx/ak820pro-modder): el byte del hueco de imagen, la
  pregunta de la batería al receptor y los problemas con los que se encuentra la gente
  (sus incidencias).

Cada proyecto tiene su licencia (MIT, GPL o ninguna indicada): mira sus páginas.

Licencia MIT (ver [LICENSE](LICENSE)). Proyecto no oficial, sin relación con Ajazz ni Epomaker. Úsalo bajo tu responsabilidad:
escribe en la memoria del teclado (todo se puede dejar de fábrica desde la app, o en el
propio teclado manteniendo Fn + Espacio de 3 a 5 segundos).
