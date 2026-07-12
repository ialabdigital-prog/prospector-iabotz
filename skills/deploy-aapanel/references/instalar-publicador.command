#!/bin/bash
# Instalar publicador automático aapanel - macOS (launchd)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PUBLISHER_SCRIPT="$BASE_DIR/skills/deploy-aapanel/references/publicar-aapanel.py"
PLIST_NAME="com.prospector.publicador"
PLIST_FILE="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

echo "🔧 Instalando publicador automático aapanel (macOS launchd)..."

# Verificar script
if [ ! -f "$PUBLISHER_SCRIPT" ]; then
    echo "❌ Script não encontrado: $PUBLISHER_SCRIPT"
    exit 1
fi

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado. Instale: brew install python3"
    exit 1
fi

# Criar plist
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$PUBLISHER_SCRIPT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$BASE_DIR</string>
    <key>StartInterval</key>
    <integer>60</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$BASE_DIR/publicador-log.txt</string>
    <key>StandardErrorPath</key>
    <string>$BASE_DIR/publicador-log.txt</string>
</dict>
</plist>
EOF

# Carregar
launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"

echo "✅ LaunchAgent instalado e carregado!"
echo "   Roda a cada 60 segundos verificando fila-publicacao.txt"
echo ""
echo "   Ver logs: tail -f $BASE_DIR/publicador-log.txt"
echo "   Status: launchctl list | grep $PLIST_NAME"
echo "   Parar: launchctl unload $PLIST_FILE"
echo "   Desinstalar: launchctl unload $PLIST_FILE && rm $PLIST_FILE"

# Se macOS bloquear na primeira execução
echo ""
echo "⚠️  Se o macOS bloquear 'python3' não identificado:"
echo "   Vá em Configurações → Privacidade e Segurança → Geral"
echo "   Clique 'Abrir mesmo assim' ao lado da mensagem do python3"