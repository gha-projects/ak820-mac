"""El idioma de los textos: el del Mac.

Los textos se escriben en español en el código, dentro de tr("..."), y cada otro idioma
tiene un archivo idiomas/<idioma>.json que traduce cada frase española (con los mismos
{huecos}). Se usa el primer idioma de la lista del Mac (Ajustes del Sistema → General →
Idioma y región) que tengamos; si no hay ninguno, inglés, como hacen las apps de Mac.

AK820_IDIOMA=en (o es) lo fuerza, para probar.
"""
import json
import os
import subprocess

# Dentro de AK820.app los archivos van en Contents/Resources (RESOURCEPATH).
CARPETA = os.path.join(os.environ.get("RESOURCEPATH") or os.path.dirname(os.path.abspath(__file__)), "idiomas")
BASE = "es"                 # el idioma en el que está escrito el código
SI_NO_HAY = "en"            # el que se usa si el Mac no está en ninguno de los que tenemos


def disponibles():
    return {BASE} | {n[:-5] for n in os.listdir(CARPETA) if n.endswith(".json")} if os.path.isdir(CARPETA) else {BASE}


def preferidos():
    """Los idiomas del Mac, por orden de preferencia ("es-ES", "en-GB"…)."""
    try:
        from Foundation import NSLocale
        return [str(i) for i in NSLocale.preferredLanguages()]
    except Exception:                                  # sin PyObjC (solo la terminal)
        try:
            salida = subprocess.run(["defaults", "read", "-g", "AppleLanguages"],
                                    capture_output=True, text=True, timeout=5).stdout
            return [l.strip(' ",()') for l in salida.splitlines() if l.strip(' ",()')]
        except Exception:
            return []


def detectar():
    forzado = os.environ.get("AK820_IDIOMA", "")
    hay = disponibles()
    if forzado in hay:
        return forzado
    for idioma in preferidos():
        codigo = idioma.split("-")[0].split("_")[0].lower()
        if codigo in hay:
            return codigo
    return SI_NO_HAY


IDIOMA = detectar()
TEXTOS = {}
if IDIOMA != BASE:
    try:
        with open(os.path.join(CARPETA, IDIOMA + ".json"), encoding="utf-8") as f:
            TEXTOS = json.load(f)
    except (OSError, ValueError):
        IDIOMA = BASE


def tr(_frase, **datos):
    """La frase en el idioma del Mac, con los {huecos} rellenos (cualquier nombre de hueco vale)."""
    frase = TEXTOS.get(_frase, _frase)
    return frase.format(**datos) if datos else frase
