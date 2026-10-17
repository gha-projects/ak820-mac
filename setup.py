"""Receta de py2app para crear AK820.app. Se usa con ./crear-app.sh."""
from setuptools import setup

setup(
    name="AK820",
    app=["ak820_app.py"],
    options={"py2app": {
        "iconfile": "app/AK820.icns",
        "resources": ["editor", "docs/teclas.md"],
        "includes": ["ak820", "ak820_editor", "ak820_ventana"],
        "plist": {
            "CFBundleName": "AK820",
            "CFBundleDisplayName": "AK820",
            "CFBundleIdentifier": "com.ak820-mac.app",
            "CFBundleShortVersionString": "1.0",
            "CFBundleVersion": "1",
            "LSUIElement": True,              # solo en la barra de menús, sin icono en el Dock
            "NSHumanReadableCopyright": "Configurador del Ajazz AK820 Pro para Mac",
        },
    }},
)
