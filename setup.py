"""Receta de py2app para crear AK820.app. Se usa con ./crear-app.sh."""
from setuptools import setup

setup(
    name="AK820",
    app=["ak820_app.py"],
    options={"py2app": {
        "iconfile": "app/AK820.icns",
        "resources": ["editor", "idiomas", "docs/teclas.md", "musica/espectro", "app/en.lproj", "app/es.lproj"],   # espectro: lo compila crear-app.sh
        "includes": ["ak820", "ak820_editor", "ak820_ventana", "idioma"],
        "plist": {
            "CFBundleName": "AK820",
            "CFBundleDisplayName": "AK820",
            "CFBundleIdentifier": "com.ak820-mac.app",
            "CFBundleShortVersionString": "1.0",
            "CFBundleVersion": "1",
            "LSUIElement": True,              # solo en la barra de menús, sin icono en el Dock
            "NSHumanReadableCopyright": "Configurador del Ajazz AK820 Pro para Mac",
            # El permiso de "grabar el audio del sistema" para el modo música lo pide la app.
            "NSAudioCaptureUsageDescription": "AK820 listens to the Mac's sound so the keyboard lights can follow the music.",
            # Idiomas: el texto de arriba y el nombre van traducidos en app/<idioma>.lproj/InfoPlist.strings.
            "CFBundleDevelopmentRegion": "en",
            "CFBundleLocalizations": ["en", "es"],
        },
    }},
)
