"""Todas las frases que se traducen, sacadas del código.

    .venv/bin/python idiomas/frases.py en     # las que le faltan a idiomas/en.json

Las pruebas (tests/) lo usan para comprobar que cada idioma las tiene todas, con los
mismos {huecos}.
"""
import ast
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = ["ak820.py", "ak820_app.py", "ak820_editor.py", "ak820_ventana.py"]

# Frases que llegan a tr() en una variable (no se pueden sacar del código).
DINAMICAS = {
    # NOMBRE_CAPA, sin_respuesta_24g(que) y los títulos de las ventanas de la app
    "capa normal", "capa con Fn", "la hora", "las luces", "los ajustes", "las teclas",
    "Teclado", "Reloj", "Luces", "Sistema", "Reposo", "Pantalla", "Teclas", "Música",
    # menús de la app (COLORES, EFECTOS_CON_COLOR, REPOSOS, MODOS_FN) y el estado del teclado
    "Rojo", "Verde", "Azul", "Blanco", "Morado", "Naranja", "Cian", "Fijo", "Respirar",
    "1 minuto", "5 minutos", "30 minutos", "Nunca",
    "Solo mientras se mantiene (de fábrica)", "Pulsar para activar/desactivar",
    "Teclado: conectado por cable ✓", "Teclado: con el receptor 2.4G ✓", "Teclado: sin conectar",
    # menús de la ventana (ak820_ventana.menu_principal)
    "Cerrar ventana", "Salir de AK820", "Deshacer", "Rehacer", "Cortar", "Copiar", "Pegar", "Seleccionar todo",
    # trozos que la app y el servidor buscan en lo que imprime ak820.py
    "No encuentro el teclado", "No veo ningún", "No aparece la interfaz", "Para volver", "repitiendo",
    # etiquetas del dibujo del teclado (editor/distribucion.json) que cambian de un idioma a otro
    "Supr", "Inicio", "RePág", "AvPág", "Bloq Mayús", "Espacio",
}


def de_python():
    frases = set()
    for nombre in PYTHON:
        with open(os.path.join(RAIZ, nombre), encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "tr"
                    and nodo.args and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[0].value, str)):
                frases.add(nodo.args[0].value)
    return frases


def de_la_pagina():
    with open(os.path.join(RAIZ, "editor", "index.html"), encoding="utf-8") as f:
        pagina = f.read()
    html, script = pagina[:pagina.index("<script>")], pagina[pagina.index("<script>"):]
    frases = {json.loads(f'"{m}"') for m in re.findall(r'tr\("((?:[^"\\]|\\.)*)"', script)}
    frases |= {" ".join(m.split()) for m in re.findall(r"data-t>([^<]*)<", html)}
    frases |= set(re.findall(r'(?:title|aria-label)="([^"]+)"', html[html.index("<body>"):]))
    return frases


def todas():
    return de_python() | de_la_pagina() | DINAMICAS


def huecos(frase):
    return sorted(re.findall(r"\{(\w+)", frase))


if __name__ == "__main__":
    idioma = sys.argv[1] if len(sys.argv) > 1 else "en"
    with open(os.path.join(RAIZ, "idiomas", idioma + ".json"), encoding="utf-8") as f:
        catalogo = json.load(f)
    faltan = sorted(todas() - set(catalogo))
    sobran = sorted(set(catalogo) - todas())
    print(json.dumps({"faltan": faltan, "sobran": sobran}, ensure_ascii=False, indent=1))
