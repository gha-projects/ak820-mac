# Pruebas pendientes en el teclado

Lo que está programado pero aún no se ha visto funcionar en el AK820 (PID 0x800A). Todo
se prueba **por cable**. Se usan teclas que no hacen falta en el día a día: **RePág
(PgUp)**, **AvPág (PgDn)** y **Supr (Delete)**, y las mismas con Fn. Inicio (Home) no
se toca porque hace la captura de pantalla.

Al final de cada ronda se vuelve a lo de fábrica (la última ronda lo hace con la app).

## Ronda 1: ratón y Multi-Key

```
python3 ak820.py teclas repag=multi:shift+a avpag=doble_clic supr=clic_medio
python3 ak820.py teclas --fn repag=atras avpag=adelante supr=rueda_abajo
```

| # | Pulsa | Debería | Resultado |
|---|---|---|---|
| 1 | RePág (en Notas) | escribir **A** mayúscula (`multi:shift+a` → combinación `shift+a`) | |
| 2 | AvPág con el ratón sobre una palabra | **seleccionar la palabra** (doble clic) | |
| 3 | Supr con el ratón sobre un enlace de Safari | abrir el enlace en **otra pestaña** (clic central) | |
| 4 | Fn + RePág en Safari, tras visitar dos páginas | **página anterior** | |
| 5 | Fn + AvPág | **página siguiente** | |
| 6 | Fn + Supr en una página larga | **bajar** un poco (rueda) | |

## Ronda 2: multimedia

```
python3 ak820.py teclas repag=anterior avpag=siguiente supr=silencio
python3 ak820.py teclas --fn repag=brillo- avpag=brillo+ supr=volumen-
```

| # | Pulsa | Debería | Resultado |
|---|---|---|---|
| 1 | RePág / AvPág con música sonando | **canción anterior / siguiente** | |
| 2 | Supr | **silenciar** (y otra vez, quitar el silencio) | |
| 3 | Fn + RePág / Fn + AvPág | **bajar / subir el brillo** de la pantalla del Mac | |
| 4 | Fn + Supr | **bajar el volumen** | |

## Ronda 3: macro en modo "clic"

```
python3 ak820.py teclas avpag=texto:hola --modo clic
```

El programa oficial lo llama "al hacer clic" (modo 4), sin más explicación. Se prueba
un toque corto y mantener: hay que ver qué hace.

## Ronda 4: ajustes del sistema

En modo Mac el teclado intercambia Win y Alt: la tecla rotulada **Alt** hace de **Cmd** y
la rotulada **Win** hace de **Option**. Hay que ver qué bloquea cada opción.

| # | Orden | Prueba | Resultado |
|---|---|---|---|
| 1 | `sistema --bloquear win` | ¿Cmd + A selecciona todo? ¿Win + 2 escribe "@"? | |
| 2 | `sistema --desbloquear win --bloquear alttab altf4` | ¿Cmd + Tab cambia de app? | |
| 3 | `sistema --desbloquear alttab altf4 --respuesta 5` | escribir rápido: ¿se nota algo? | |
| 4 | `sistema --respuesta 1` | escribir rápido: ¿se nota algo? | |
| 5 | `sistema --fabrica` | todo como de fábrica (el reposo vuelve a 5 min) | |

## Ronda 5: la app (lo que falta)

Con `Abrir AK820.command`:

| # | Menú | Debería | Resultado |
|---|---|---|---|
| 1 | Poner el reloj en hora | ✓ en el icono y la hora correcta en la pantalla | |
| 2 | Imagen o GIF… → `Art Spiderman GIF.gif` | el icono enseña el %, luego ✓ y el GIF en la pantalla | |
| 3 | Luces → Espectro / Ola de colores / Apagadas | lo que dice cada uno | |
| 4 | Luces → Brillo → 2 (con una luz puesta) | más tenue | |
| 5 | Reposo → 5 minutos | ventana con el ajuste | |
| 6 | Sistema → Tecla Fn → Pulsar para activar/desactivar, y luego volver | ventana con el ajuste | |
| 7 | Sistema → Ajustes de fábrica | ventana con los ajustes de fábrica | |
| 8 | Teclas → Restaurar teclas de fábrica | ✓; RePág, AvPág y Supr vuelven a ser normales | |
| 9 | Teclas → Abrir guía de teclas | se abre `docs/teclas.md` | |
