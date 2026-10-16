# ak820-mac

Configurador casero del teclado **Ajazz AK820 Pro** para macOS. El programa oficial
solo existe para Windows.

## Qué hace ahora (paso 1)

- `buscar`: comprueba que el Mac ve el teclado. No cambia nada.
- `reloj`: pone en hora la pantalla del teclado.

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

Si `python3` no existe, macOS te ofrecerá instalar las "herramientas de línea de comandos"; acepta.
Si `pip install` falla, instala [Homebrew](https://brew.sh) y ejecuta `brew install hidapi`.

## Próximos pasos

1. Luces RGB, brillo y temporizador de reposo.
2. Remapeo de teclas y macros.
3. Imágenes en la pantalla (en macOS es lo más difícil).

## Créditos

El protocolo lo descifró la comunidad, en proyectos con licencia MIT:
[gohv/EPOMAKER-Ajazz-AK820-Pro](https://github.com/gohv/EPOMAKER-Ajazz-AK820-Pro),
[TaxMachine/ajazz-keyboard-software-linux](https://github.com/TaxMachine/ajazz-keyboard-software-linux),
[Aiacos/ajazz-control-center](https://github.com/Aiacos/ajazz-control-center) y
[gusleig/ajazz-ak820-pro-mac](https://github.com/gusleig/ajazz-ak820-pro-mac).

Proyecto no oficial, sin relación con Ajazz ni Epomaker. Úsalo bajo tu responsabilidad.
