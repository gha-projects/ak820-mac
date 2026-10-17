# Pruebas en el teclado

Sesión del 17 de octubre de 2026, AK820 con PID 0x800A, por cable. Se usaron RePág,
AvPág y Supr (y las mismas con Fn), y al final todo se dejó de fábrica. Los detalles
del formato de las teclas están en [teclas.md](teclas.md).

Para ver qué eventos de ratón llegan de verdad sirve una página web que los apunte
(`mousedown`, `dblclick`, `wheel`): en una nota corta la rueda no mueve nada y Safari no
usa los botones 4/5, así que a simple vista no se distingue "no llega" de "no hace nada".

## Ratón y Multi-Key

| Prueba | Resultado |
|---|---|
| `multi:shift+a` (se guarda como `shift+a`) | ✅ escribe "A" |
| `doble_clic` (macro: pulsar y soltar el izquierdo dos veces) | ✅ selecciona la palabra |
| `clic_medio`, también en la capa Fn | ✅ |
| `rueda_abajo` / `rueda_arriba`, también en la capa Fn | ✅ una muesca (4 px) por pulsación |
| Rueda con valor 5 (`01 03 05`) | ⚠️ igual que 1: el teclado solo mira el signo |
| `01 01 03` ("doble clic" del programa oficial) | ⚠️ pulsa izquierdo y derecho a la vez: en el Mac, clic derecho |
| Botones 4/5 (atrás/adelante) | ❌ el ratón del teclado solo declara 3 botones (su descriptor HID: `Usage Max 3`) |

## Multimedia

| Prueba | Resultado |
|---|---|
| `anterior`, `siguiente`, `silencio`, `volumen-` | ✅ |
| `brillo-`, `brillo+` (en la capa Fn) | ✅ brillo de la pantalla del Mac |
| Fn + Supr → cualquier cosa | ❌ el teclado no deja cambiarla (ahora `ak820.py` lo avisa) |

## Macros

| Prueba | Resultado |
|---|---|
| `--modo mantener` | ✅ se repite mientras se mantiene |
| `--modo alternar` | ✅ un toque empieza, otro para |
| `--modo paso` (modo 4, "al hacer clic" en el oficial) | ✅ cada pulsación escribe la siguiente letra |

## Ajustes del sistema

En modo Mac la tecla rotulada Alt hace de Cmd y la rotulada Win hace de Option.

| Prueba | Resultado |
|---|---|
| `--fn-modo alternar` | ✅ un toque a Fn activa la capa Fn, otro la quita |
| `--bloquear win` | Sin efecto en modo Mac: Cmd + A y Win (Option) + V siguen funcionando |
| `--bloquear alttab altf4` | Sin efecto en modo Mac: Cmd + Tab sigue funcionando |
| `--respuesta 5` | No se nota escribiendo normal ni golpeando rápido la misma tecla |
| `--fabrica` | ✅ |

## App de la barra de menús

| Prueba | Resultado |
|---|---|
| Comprobar teclado, Sistema → Ver ajustes actuales | ✅ ventana con la respuesta |
| Reloj | ✅ |
| Imagen o GIF… (GIF de 77 fotogramas) | ✅ el icono enseña el % y acaba en ✓ |
| Luces: Fijo, Respirar, Ola de colores, Apagadas, Brillo | ✅ |
| Reposo → 5 minutos | ✅ |
| Sistema → Tecla Fn (los dos modos) | ✅ |
