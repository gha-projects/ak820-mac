#!/usr/bin/env python3
"""Dibuja el icono de AK820.app y lo guarda como app/AK820.icns (con iconutil de macOS).

    .venv/bin/python app/crear_icono.py
"""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw

CARPETA = os.path.dirname(os.path.abspath(__file__))
TAM = 1024


def degradado(tam, arriba, abajo):
    """Imagen tam×tam con un degradado vertical entre dos colores RGB."""
    franja = Image.new("RGB", (1, tam))
    for y in range(tam):
        t = y / (tam - 1)
        franja.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(arriba, abajo)))
    return franja.resize((tam, tam))


def icono():
    # Fondo: cuadrado redondeado como los iconos de macOS (con margen alrededor).
    margen, radio = 100, 185
    fondo = degradado(TAM, (52, 58, 84), (18, 20, 32))
    mascara = Image.new("L", (TAM, TAM), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((margen, margen, TAM - margen, TAM - margen), radio, fill=255)
    lienzo = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
    lienzo.paste(fondo, (0, 0), mascara)
    d = ImageDraw.Draw(lienzo)

    # Cuerpo del teclado.
    cx0, cy0, cx1, cy1 = 190, 422, 834, 742
    d.rounded_rectangle((cx0, cy0 + 14, cx1, cy1 + 14), 46, fill=(8, 9, 14))          # sombra
    d.rounded_rectangle((cx0, cy0, cx1, cy1), 46, fill=(236, 237, 242))

    # Teclas: 4 filas; la de abajo con barra espaciadora. Colores de las luces RGB.
    colores = [(255, 94, 87), (255, 176, 59), (90, 200, 120), (64, 156, 255), (175, 110, 255)]
    paso, lado, x0, y0 = 66, 54, cx0 + 34, cy0 + 34
    for fila in range(4):
        y = y0 + fila * paso
        teclas = [(x0 + i * paso, 1) for i in range(9)] if fila < 3 else \
                 [(x0, 1), (x0 + paso, 1), (x0 + 2 * paso, 5), (x0 + 7 * paso, 1), (x0 + 8 * paso, 1)]
        for n, (x, ancho) in enumerate(teclas):
            color = colores[(n + fila) % len(colores)]
            d.rounded_rectangle((x, y, x + lado + (ancho - 1) * paso, y + lado), 12, fill=color)

    # La pantalla del AK820, arriba a la derecha, con la hora.
    px0, py0, px1, py1 = 610, 272, 834, 392
    d.rounded_rectangle((px0, py0, px1, py1), 24, fill=(236, 237, 242))
    d.rounded_rectangle((px0 + 16, py0 + 16, px1 - 16, py1 - 16), 12, fill=(18, 20, 32))
    # "12:34" con segmentos sencillos
    trazo, alto, ancho = 9, 52, 26
    xs = [px0 + 38, px0 + 74, px0 + 128, px0 + 164]
    ys = py0 + 34
    segmentos = {"1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc"}
    for x, digito in zip(xs, "1234"):
        for s in segmentos[digito]:
            caja = {"a": (x, ys, x + ancho, ys + trazo),
                    "b": (x + ancho - trazo, ys, x + ancho, ys + alto // 2),
                    "c": (x + ancho - trazo, ys + alto // 2, x + ancho, ys + alto),
                    "d": (x, ys + alto - trazo, x + ancho, ys + alto),
                    "e": (x, ys + alto // 2, x + trazo, ys + alto),
                    "f": (x, ys, x + trazo, ys + alto // 2),
                    "g": (x, ys + alto // 2 - trazo // 2, x + ancho, ys + alto // 2 + trazo // 2)}[s]
            d.rectangle(caja, fill=(120, 220, 255))
    for y in (ys + 14, ys + 34):                                   # los dos puntos
        d.rectangle((px0 + 110, y, px0 + 110 + trazo, y + trazo), fill=(120, 220, 255))
    return lienzo


def main():
    imagen = icono()
    with tempfile.TemporaryDirectory() as carpeta:
        iconset = os.path.join(carpeta, "AK820.iconset")
        os.mkdir(iconset)
        for lado in (16, 32, 128, 256, 512):
            imagen.resize((lado, lado), Image.LANCZOS).save(os.path.join(iconset, f"icon_{lado}x{lado}.png"))
            imagen.resize((lado * 2, lado * 2), Image.LANCZOS).save(os.path.join(iconset, f"icon_{lado}x{lado}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(CARPETA, "AK820.icns")], check=True)
    imagen.save(os.path.join(CARPETA, "icono.png"))
    print("Hecho: app/AK820.icns (y app/icono.png para verlo)")


if __name__ == "__main__":
    main()
