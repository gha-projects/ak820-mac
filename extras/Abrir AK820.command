#!/bin/bash
# Abre la app de la barra de menús del AK820. Pensado para doble clic en Finder.
cd "$(dirname "$0")/.." || exit 1

if [ ! -x .venv/bin/python ]; then
  echo "Falta el entorno de Python del proyecto. Sigue el paso 3 de 'Cómo ejecutarlo' del README."
  read -r -p "Pulsa Enter para cerrar"
  exit 1
fi

if ! .venv/bin/python -c "import rumps" 2>/dev/null; then
  echo "Instalando lo necesario para la app (solo la primera vez)..."
  if ! .venv/bin/pip install -r requirements-app.txt; then
    read -r -p "No se ha podido instalar. Pulsa Enter para cerrar"
    exit 1
  fi
fi

# Si ya estaba abierta, se cierra para abrir la versión actual.
pkill -f "ak820_app.py" 2>/dev/null
nohup .venv/bin/python ak820_app.py >>"$HOME/Library/Logs/ak820-app.log" 2>&1 &
disown
echo "La app está en la barra de menús (arriba a la derecha, icono ⌨︎)."
echo "Ya puedes cerrar esta ventana."
