# Configurar por el receptor 2.4G

Estado (17 de octubre de 2026): **funciona** con el receptor que trae el AK820 Pro
(VID 0x0C45, PID 0xFDFD). `ak820.py` usa el cable si está y, si no, el receptor.

| Por el receptor | Orden | Probado |
|---|---|---|
| Luces (efecto, color, brillo…) | `05` | ✅ |
| Teclas, capa normal / Fn | `10` / `12` | ✅ |
| Macros | `09` | ✅ |
| Reloj | `0C` | ✅ |
| Ajustes del sistema | `07` | (mismo formato; sin probar) |
| Colores tecla a tecla, imagen de la pantalla | — | ❌ solo por cable (el programa oficial tampoco lo hace) |

Si el teclado lleva un rato sin usarse, **se duerme** y el receptor no contesta: basta con
pulsar una tecla.

## De dónde sale

El `config.xml` del programa oficial declara el modo 2 ("2.4G TYPE-A") en `PID_FDFD&MI_03`.
Casi cada función de configuración tiene dos versiones: la del cable (feature reports de 64
bytes) y la del receptor, que manda por `WriteFile` a través de la función `0x44f5f0`
(luces `0x42b2a0`, ajustes `0x4142d0`, reloj `0x423a70`, teclas `0x418cc0`, una sola tecla
`0x419000`, macros `0x42dc70`, batería `0x435890`, espectro de música `0x432c20`).

## El formato

La interfaz 3 del receptor (usage page `0xFF60`) no tiene feature reports: se le escriben
mensajes de salida de 32 bytes (con el report id `00` delante):

```
[orden] [longitud] [n.º de trozo] [hasta 28 bytes de datos ...] [suma]
```

- `suma` (byte 31) = suma de los 31 bytes anteriores, módulo 256.
- El receptor contesta con un mensaje cuyos 3 primeros bytes repiten los del enviado; el
  programa oficial espera hasta 20 veces 10 ms y lo da por bueno si coinciden.
- No hay `04 18` / `04 02` / `04 F0`: cada orden va sola.
- Luces, ajustes y reloj: un trozo de 16 bytes = los 16 primeros bytes del paquete por
  cable, con `AA 55` en los bytes 14-15 (en el reloj, el byte 10 es el día de la semana,
  domingo = 0).
- Teclas: la misma tabla de 576 bytes en 21 trozos (20 de 28 y uno de 16).
- Macros: el mismo bloque, rellenado hasta un múltiplo de 28 (con `AA 55` al final); el
  último trozo lleva como longitud lo que sobra de 28 (como el programa oficial).
- Una sola tecla (no usado): orden `03` (capa normal) o `0D` (Fn), longitud 4, n.º de
  trozo = posición de la tecla, y sus 4 bytes.
