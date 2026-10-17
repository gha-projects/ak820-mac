# Ajazz AK820 Pro — configuration protocol

Everything this project knows about talking to the AK820 Pro, worked out from the
official Windows driver (`DeviceDriver.exe` v1.0.0.5, analysed statically: the Inno
Setup installer's LZMA chunk was extracted and its call/jump filter undone, then the
binary was disassembled with Capstone) and checked on a real keyboard. Function
addresses refer to that binary. The implementation is `ak820.py`.

All multi-byte numbers are little-endian. "Packet" means 64 bytes unless said otherwise.

## Devices

| Connection | VID:PID | Interface used |
|---|---|---|
| USB cable | `0C45:8009` or `0C45:800A` | usage page `0xFF13`: 64-byte feature reports (configuration); usage page `0xFF68`: 4096-byte output reports (screen images) |
| 2.4 GHz receiver | `0C45:FDFD` | interface 3, usage page `0xFF60`: 32-byte input/output reports, no feature reports |
| Bluetooth | `0C45:FEFE` ("AK820 5.1-2") | no vendor interface: can't be configured |

Report ID is always `0`; hidapi wants it prepended (`b"\x00" + packet`).

## Wired protocol

### Commands and timing

A command is a packet `[0]=0x04 [1]=command [2]=argument [8]=count`, rest zero. The
keyboard replies through a feature-report read (`get_feature_report`). Data packets that
follow a command are sent without reading a reply.

**The official driver sleeps 35 ms before and after every command** (`cmd_delaytime` in
its `rgb-keyboard.xml`). Without the sleep *before* a command, the keyboard often ignores
it (that was the reason image uploads and key tables "silently failed").

| Command | Meaning |
|---|---|
| `04 18` | Begin (byte 8 = 0 or 1 depending on the operation) |
| `04 02` | Commit. The reply's bytes 5–6 are the 16-bit sum of the data bytes received since the announcing command, and byte 4 is `01` on success: use it to verify and retry |
| `04 F0` | Save to flash |
| `04 28` | Clock |
| `04 13` | Lighting effect |
| `04 11` / `04 27` | Key table, normal / Fn layer |
| `04 19` / `04 15` | Macros (erase / data) |
| `04 17` | System settings |
| `04 23` | Per-key colors (saved) |
| `04 20` | Per-key colors live (not saved; music mode) |
| `04 72` | Screen image |

### Clock — `04 18`, `04 28`, data, `04 02`

Data: `[1]=01 [2]=5A [3]=year-2000 [4]=month [5]=day [6]=hour [7]=minute [8]=second
[10]=04 [62..63]=AA 55` (plain numbers, not BCD). Setting the clock also switches the
screen back to the clock.

### Lighting — `04 18`, `04 13`, data, `04 F0`

Data: `[0]=effect [1..3]=R G B [8]=rainbow (0/1) [9]=brightness 0–5 [10]=speed 0–5
[11]=direction (0 left, 1 down, 2 up, 3 right) [14..15]=AA 55` (the official driver
writes `AA 55`; `55 AA` works too).

| Effect | Code | Effect | Code |
|---|---|---|---|
| single key on (press) | `02` | scrolling | `0A` |
| single key off | `03` | rolling (wave) | `0B` |
| glittering | `04` | rotating | `0C` |
| falling (rain) | `05` | explode | `0D` |
| colourful | `06` | launch | `0E` |
| breath | `07` | ripples | `0F` |
| spectrum | `08` | flowing | `10` |
| outward | `09` | pulsating | `11` |
| tilt | `12` | shuttle | `13` |
| per-key custom colors | `80` | | |

This project sends "static" as breath with speed 0, and "off" as brightness 0.

### Key positions

Each key has an index (`key_index` in the official `rgb-keyboard.xml`; its
`light_index` is the same number). ANSI layout:

```
Esc 1 · F1 2 · F2 3 · F3 4 · F4 5 · F5 6 · F6 7 · F7 8 · F8 9 · F9 10 · F10 11 · F11 12 · F12 13 · Del 119
` 19 · 1 20 · 2 21 · 3 22 · 4 23 · 5 24 · 6 25 · 7 26 · 8 27 · 9 28 · 0 29 · - 30 · = 31 · Backspace 103 · Home 117
Tab 37 · Q 38 · W 39 · E 40 · R 41 · T 42 · Y 43 · U 44 · I 45 · O 46 · P 47 · [ 48 · ] 49 · \ 67 · PgUp 118
Caps 55 · A 56 · S 57 · D 58 · F 59 · G 60 · H 61 · J 62 · K 63 · L 64 · ; 65 · ' 66 · Enter 85 · PgDn 121
Shift 73 · Z 74 · X 75 · C 76 · V 77 · B 78 · N 79 · M 80 · , 81 · . 82 · / 83 · RShift 84 · ↑ 101
Ctrl 91 · Win 92 · Alt 93 · Space 94 · RAlt 95 · Fn 96 · RCtrl 98 · ← 99 · ↓ 100 · → 102
```

The drawing coordinates are in `editor/distribucion.json`. In Mac mode the keyboard
swaps Win and Alt by itself; a remapped key sends exactly what it's told.

### Key table — `04 18` (byte 8 = 0), `04 11`/`04 27` (byte 8 = 9), 9 packets, `04 02`, `04 F0`

Function `0x418420`. 576 bytes = 144 slots × 4, ending in `AA 55`. Slot `key_index`
holds four bytes:

| Bytes | Meaning |
|---|---|
| `00 00 00 00` | factory behaviour |
| `02 mods key 00` | key or shortcut. `mods` = HID modifier bits (Ctrl `01`, Shift `02`, Alt/Option `04`, GUI/Cmd `08`; right-hand `10 20 40 80`); `key` = HID usage |
| `03 lo hi 00` | consumer usage (play `CD`, next `B5`, previous `B6`, stop `B7`, mute `E2`, volume up `E9`, down `EA`, brightness up `6F`, down `70`) |
| `01 01 buttons 00` | mouse buttons: left `01`, right `02`, middle `04`. The official "double click" `03` presses left and right together; buttons 4/5 (`08`/`10`) don't work because the keyboard's mouse HID descriptor only declares 3 buttons |
| `01 03 wheel 00` | wheel: `01` up, `FF` down. Always one notch per press (other values act the same) |
| `06 macro mode count` | play macro number `macro`. Modes: 0 once, 1 `count` times, 2 toggle (until pressed again), 3 while held, 4 one keystroke per press |
| `07 k1 k2 k3` | "Multi-Key": up to 3 normal keys at once (HID usages, `00` = empty). Modifiers here (`E0`–`E7`) are ignored by macOS: use type `02` for shortcuts |

Not usable on the Fn layer: Esc, Backspace, Home, `\`, Win (`fnlayer_disable` in the
XML) and Delete (the keyboard ignores it). The keyboard can't be read back, so to
change one key the whole table has to be sent again.

### Macros — `04 19` (byte 8 = 0), `04 15` (byte 8 = packet count), block, `04 02`

Function `0x42d6f0`. Sent before the key table. No `04 18`. The block (at most 3584
bytes) holds all macros of both layers (sending one layer's macros wipes the other's):

- bytes 0–399: index of 100 entries × 4 bytes; bytes 0–1 of entry *i* = offset of macro *i*
- from byte 400, each macro: event count (2 bytes), 6 zero bytes, then 4-byte events:
  - `00 00 key B0` key down, `00 00 key 30` key up (HID usages; Shift = `E1`)
  - `lo hi 00 50` delay in ms (the driver puts ≥ 10 ms after each action)
  - `00 00 button 90` / `00 00 button 10` mouse button down / up (a double click is two
    left clicks)
- padded to a multiple of 64 (`len // 64 + 1` packets if `len % 64 == 0`, else `+ 2`)
  with `AA 55` in the last two bytes.

The first upload after a while is sometimes lost: check the commit checksum and retry.

### System settings — `04 18`, `04 17` (byte 2 = 1, byte 8 = 1), data, `04 02`

Function `0x414060`. Data: `[1]=01 [2]=block Win [3]=block Alt+F4 [4]=block Alt+Tab
[5]=Fn mode (0 while held, 1 toggle) [6]=sleep (0 never, 1 = 1 min, 2 = 5 min,
3 = 30 min) [8]=key response 1–5 [62..63]=AA 55`. Factory: Fn 0, sleep 2, response 2.
All settings go in one packet and can't be read, so keep the last ones sent. Sleep only
applies on battery. The three "block" options have no effect in Mac mode.

### Per-key colors — effect `80`, then `04 18`, `04 23` (byte 8 = 9), 9 packets, `04 02`, `04 F0`

Function `0x44ba10`. First set the lighting effect to `80` (with the brightness you
want). Then a 576-byte table like the key table, with `[key_index, R, G, B]` in each
key's slot (Fn included) and `AA 55` at the end.

### Live per-key colors — `04 20` (byte 8 = 8), 8 packets, `04 02`

Functions `0x4329e0` (music) and `0x427e10` (preview). 512 bytes holding
`[key_index, R, G, B]` for each key, one after another (not by slot). No `04 18`, no
save. The driver waits only 5 ms around the commands and 2 ms between packets, which
gives about 23 frames per second. When frames stop, the keyboard goes back to its saved
effect. Music mode over the cable is the host drawing an equalizer with this.

### Screen image — `04 18` (byte 8 = 0), `04 72`, blocks, `04 02`

`04 72` with byte 2 = slot `1` and bytes 8–9 = number of 4096-byte blocks. Then each
block goes as an output report on the `0xFF68` interface; wait for the input report
`01 5A 02` after each one. Finally `04 02` (no `04 F0`).

Content: a 256-byte header — `[0]` = frame count (max 140), `[1+i]` = frame *i*'s duration
in 2 ms units (minimum 1), the rest `FF` — followed by the frames, each 128×128 pixels
in RGB565 little-endian, padded with `FF` to whole blocks. A still image is 9 blocks.

## 2.4 GHz receiver

Each operation of the wired protocol has a receiver version in the driver, all going
through `0x44f5f0` (`WriteFile`). Messages are 32 bytes:

```
[order] [length] [chunk number] [up to 28 data bytes ...] [sum]
```

`sum` (byte 31) is the sum of bytes 0–30, modulo 256. The receiver answers with an input
report whose first 3 bytes repeat the message's; the driver waits up to 20 × 10 ms and
retries. There's no begin/commit/save: each order stands alone. If the keyboard is
asleep (battery sleep timer), nothing answers until a key is pressed.

| Order | Data |
|---|---|
| `05` lighting | 16 bytes: the first 16 bytes of the wired lighting packet (`AA 55` at 14–15) |
| `07` system settings | 16 bytes: the first 14 of the wired packet + `AA 55` |
| `0C` clock | 16 bytes: like the wired packet's first 14, with `[10]` = day of week (Sunday = 0), + `AA 55` |
| `10` / `12` key table, normal / Fn | the same 576 bytes in 21 chunks (20 × 28 and one of 16) |
| `03` / `0D` one key, normal / Fn | length 4, chunk number = key index, data = the 4-byte slot |
| `09` macros | the same block padded to a multiple of 28 (`AA 55` at the end); the last chunk's length is `len % 28` |
| `0B` music spectrum | `[mode, background, background brightness]` + 21 bar heights (rows lit per column, 0–6); the keyboard draws the bars |
| `20 01` battery | reply byte 3 = battery % (0 = unknown) |

Per-key colors and screen images can't go through the receiver (the driver doesn't
send them either).

Music modes (`0B`): 1 green/yellow/red, 2 rainbow, 3 reverse rainbow, 4 gradient,
5 spectrum cycle, 6 white, 7 red, 8 orange, 9 yellow, `0A` blue, `0B` green, `64`
"ambilight".
