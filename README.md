<p align="center"><img src="docs/img/icono.png" width="96" alt=""></p>

# ak820-mac

**A macOS app for the Ajazz AK820 Pro keyboard** (the one with the little screen). The
official configuration software only exists for Windows; this one was made by
reverse-engineering it, and covers what you'd actually use it for: keys, macros, lights,
the screen and music mode.

*[Leer en español](README.es.md)*

![The Keys tab](docs/img/teclas.png)

## What it can do

- **Keys**: remap any key, on the normal layer or the Fn layer: another key, a shortcut
  (⌘C…), media keys, mouse clicks and wheel, text macros (once, N times, while held,
  toggle…) or several keys at once. The keyboard stores it, so it works on any computer.
- **Lights**: all 19 built-in effects with color, brightness, speed and direction;
  **per-key colors** (paint the keys on a drawing of the keyboard); and a **music mode**
  where the keys become an equalizer that follows whatever your Mac is playing.
- **Screen**: put any picture or **animated GIF** on the 0.85" screen (cropped to
  128×128, up to 140 frames), see what's on it, or go back to the clock.
- **Clock**: sets the time automatically when the keyboard is plugged in.
- **Settings**: Fn key mode, sleep timer, key response time. Send the setup saved on
  your Mac to the keyboard again, or reset everything to factory.
- **Help**: what each key does out of the box (Fn shortcuts; F1–F12, which in Mac mode
  work like a Mac's top row; the knob, the switches, and the **C** and **W** lights: Caps
  Lock and Win lock), from the
  [official manual](https://epomaker.com/cdn/shop/files/AK820_PRO_manual.pdf). The Keys
  tab also shows each key's factory function.
- **Without the cable**: lights, keys, macros, settings and the clock also work through
  the **2.4 GHz receiver**. The menu also shows the battery if the receiver reports it
  (the one it was tested with always answers "unknown"; the keyboard's screen shows it).

It comes as a menu-bar app with its own window, and as a command-line tool.

| Per-key colors | Music mode |
|---|---|
| ![](docs/img/luces-tecla-a-tecla.png) | ![](docs/img/musica.png) |

## Compatibility

- **Keyboard**: Ajazz AK820 Pro, wired USB IDs `0C45:8009` / `0C45:800A` with the vendor
  interface `0xFF13` (run `python3 ak820.py buscar` to check), and its 2.4 GHz receiver
  (`0C45:FDFD`). Some newer AK820 Pro firmwares use a different protocol and won't be
  detected. Bluetooth can't be used to configure anything. Boxes that say **Ajazz ×
  Nacodex** are the same keyboard: what matters is the USB ID (at least one Nacodex unit
  reports `1A2C:9605`, and that one isn't detected).
- **Layout**: the key drawing is the ANSI (US) one from the official software. ISO
  keyboards may have one or two keys in different places.
- **Mac**: tested on Apple Silicon with macOS 26. You build it on your own Mac, so Intel
  should work too. Music mode needs **macOS 14.2** or later; the rest should also work
  on older versions.
- **Language**: English or Spanish, following the Mac's language (System Settings →
  General → Language & Region). To add a language, translate `idiomas/en.json` into
  `idiomas/<code>.json` (`idiomas/frases.py` lists the phrases).

## Installation

You need the Xcode **Command Line Tools** (they bring Python 3 and the Swift compiler). If
you don't have them, `python3` in the Terminal will offer to install them.

```sh
git clone https://github.com/gha-projects/ak820-mac.git
cd ak820-mac
/usr/bin/python3 -m venv .venv
.venv/bin/pip install -r requirements-app.txt
./crear-app.sh
```

`/usr/bin/python3` is the Python that comes with the Command Line Tools: use that one even
if you have another (Homebrew's, for example), since the app is built and tested with it.

`crear-app.sh` builds **AK820.app**, copies it to Applications and opens it. Open it
like any other app from then on. To start it at login: System Settings → General →
Login Items. After changing the code, run `./crear-app.sh` again.

The first time you use music mode, macOS asks for permission to **record system audio**
(audio only, not the screen).

## Using it

- **The app**: the window opens when you start AK820, with five tabs: **Keys**,
  **Lights**, **Screen**, **Settings** and **Help**. The ⌨︎ icon in the menu bar has quick
  actions too (lights, music mode, clock, sleep…). While it's busy the icon shows `⌨︎…`,
  `⌨︎ 45 %` or `⌨︎ ♪`.
- **The command line** (from the project folder):

  ```sh
  source .venv/bin/activate
  python3 ak820.py buscar                              # is the keyboard there?
  python3 ak820.py reloj                               # set the clock
  python3 ak820.py luces respirar --color 8000FF       # an effect (see: luces --help)
  python3 ak820.py colores esc=FF0000 --fondo 102040    # per-key colors
  python3 ak820.py musica --modo arcoiris               # music mode, until Ctrl+C
  python3 ak820.py imagen ~/Desktop/anim.gif            # picture or GIF on the screen
  python3 ak820.py teclas avpag=cmd+a repag=texto:Hi    # remap keys (see: teclas lista)
  python3 ak820.py teclas restaurar todo               # all keys back to factory
  python3 ak820.py sistema --fn-modo alternar          # settings (see: sistema --help)
  python3 ak820.py bateria                             # battery, if the receiver reports it
  python3 ak820.py reenviar                            # send the saved setup again
  python3 ak820.py fabrica --si                        # everything back to factory
  ```

  Over 2.4 GHz the receiver answers even when the keyboard isn't listening (for example,
  right after switching it to 2.4G), so check that the change shows on the keyboard.

The keyboard doesn't let you read its configuration back, so the program remembers
what it last sent in `~/Library/Application Support/ak820-mac/` (keys, colors, lights,
settings and a copy of the screen image). If the keyboard gets reset or you set it up
on another computer, **Send my configuration again** (or `reenviar`) puts it back. Before
a factory reset it keeps a copy of what you had, so you can undo it (in Settings, or
`fabrica --deshacer`).

## How it works

Everything was worked out from the official Windows driver (`DeviceDriver.exe`
v1.0.0.5), statically, without running it, plus a lot of trial and error with the
keyboard. The keyboard is configured with 64-byte HID feature reports (images go
through a second interface in 4 KB blocks); the 2.4 GHz receiver uses 32-byte reports.
Every format is documented in **[docs/PROTOCOL.md](docs/PROTOCOL.md)**.

The project is a few Python files with no framework:

| File | What it is |
|---|---|
| `ak820.py` | The protocol and the command-line tool |
| `ak820_app.py` | The menu-bar app ([rumps](https://github.com/jaredks/rumps)) |
| `ak820_ventana.py`, `ak820_editor.py`, `editor/` | The window: a local web page in a WKWebView, served on `127.0.0.1` with a random key |
| `musica/espectro.swift` | Listens to system audio (Core Audio tap) and prints a 21-band spectrum |
| `setup.py`, `crear-app.sh`, `app/` | Building `AK820.app` with py2app |
| `tests/` | Tests against a fake keyboard: `.venv/bin/python -m unittest discover -s tests` |
| `extras/` | Optional macOS remaps (Right Ctrl → 🌐 Globe, Home → F13) and a launcher for development |

## Other projects

If you'd rather replace the keyboard's firmware,
[fpb/ajazz-ak820-pro](https://github.com/fpb/ajazz-ak820-pro) ports **QMK** to it. It's
a different approach: this app talks to the stock firmware and doesn't work with QMK, and
there are several hardware revisions of the keyboard, so read their notes before
flashing anything.

## Credits

This is a new implementation and copies no code from other projects, but a lot of what
it knows about the keyboard was first worked out by the community:

- [gohv/EPOMAKER-Ajazz-AK820-Pro](https://github.com/gohv/EPOMAKER-Ajazz-AK820-Pro): lighting, sleep
  timer and clock on Linux. Its issue #6 (garbled images on the `800A` model) pointed to
  the screen problem.
- [TaxMachine/ajazz-keyboard-software-linux](https://github.com/TaxMachine/ajazz-keyboard-software-linux):
  the first open reference for the configuration interface and image upload.
- [KyleBoyer/TFTTimeSync-node](https://github.com/KyleBoyer/TFTTimeSync-node): the clock packet.
- [Aiacos/ajazz-control-center](https://github.com/Aiacos/ajazz-control-center): protocol notes for
  several Ajazz keyboards, and the Nacodex unit with another USB ID.
- [gusleig/ajazz-ak820-pro-mac](https://github.com/gusleig/ajazz-ak820-pro-mac): the first macOS tool
  for this same model. Its key-remapping experiments showed which formats don't work.
- [nurlanjalil/ajazz-ak820-config](https://github.com/nurlanjalil/ajazz-ak820-config) and
  [aar-rafi/aks075-linux](https://github.com/aar-rafi/aks075-linux): the official software's screen
  image format (on the AKS075, a sibling model).
- [allshouldbeready/ak820-pro-macos](https://github.com/allshouldbeready/ak820-pro-macos) and
  [wsclx/ak820pro-modder](https://github.com/wsclx/ak820pro-modder): the image slot byte, the receiver's
  battery query, and the problems people run into (their issues).

Each project has its own license (MIT, GPL or none stated): see their pages.

MIT license (see [LICENSE](LICENSE)). Unofficial project, not affiliated with Ajazz or Epomaker. Use at your own risk: it
writes to the keyboard's memory (everything can be reset to factory from the app, or on
the keyboard by holding Fn + Space for 3–5 seconds).
