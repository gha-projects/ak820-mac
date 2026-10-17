#!/bin/bash
# Crea AK820.app (con py2app) y la instala en Aplicaciones. Vale también con doble clic.
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Falta el entorno de Python del proyecto. Sigue el paso 3 de 'Cómo ejecutarlo' del README."
  exit 1
fi
echo "Instalando lo necesario..."
.venv/bin/pip install -q -r requirements-app.txt "py2app==0.28.8"
echo "Creando AK820.app (tarda un minuto)..."
rm -rf build dist
if ! .venv/bin/python setup.py py2app > build.log 2>&1; then
  echo "No se ha podido crear la app; los detalles están en build.log"
  exit 1
fi
destino=/Applications
[ -w "$destino" ] || { destino="$HOME/Applications"; mkdir -p "$destino"; }
# Se cierra la versión que esté abierta (la app o la del .command) para abrir la nueva.
pkill -f "AK820.app/Contents/MacOS/AK820" 2>/dev/null || true
pkill -f "ak820_app.py" 2>/dev/null || true
rm -rf "$destino/AK820.app"
cp -R dist/AK820.app "$destino/"
rm -rf build dist build.log
open "$destino/AK820.app"
echo "Listo: $destino/AK820.app (el icono ⌨︎ está en la barra de menús)."
