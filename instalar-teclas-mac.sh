#!/bin/sh
# Hace que teclas-mac.sh se aplique solo: al iniciar sesión y cada 10 segundos
# (así vuelve a funcionar en cuanto reconectas el teclado).
# Para desinstalar: ./instalar-teclas-mac.sh quitar
set -e
ETIQUETA=com.ak820-mac.teclas
AGENTE="$HOME/Library/LaunchAgents/$ETIQUETA.plist"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/teclas-mac.sh"

launchctl bootout "gui/$(id -u)/$ETIQUETA" 2>/dev/null || true
if [ "$1" = "quitar" ]; then
  rm -f "$AGENTE"
  /usr/bin/hidutil property --matching '{"VendorID":0x0C45}' --set '{"UserKeyMapping":[]}' >/dev/null
  echo "Quitado: las teclas del AK820 vuelven a ser las de siempre."
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$AGENTE" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$ETIQUETA</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>$SCRIPT</string></array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>10</integer>
</dict>
</plist>
PLIST
launchctl bootstrap "gui/$(id -u)" "$AGENTE"
echo "Instalado: Control derecho del AK820 = 🌐, también tras reiniciar o reconectar."
