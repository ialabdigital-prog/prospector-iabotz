#!/bin/bash
# Instalar publicador automático aapanel como systemd service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PUBLISHER_SCRIPT="$BASE_DIR/skills/deploy-aapanel/references/publicar-aapanel.py"
SERVICE_NAME="prospector-publicador"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

echo "🔧 Instalando publicador automático aapanel..."

# Verificar script
if [ ! -f "$PUBLISHER_SCRIPT" ]; then
    echo "❌ Script não encontrado: $PUBLISHER_SCRIPT"
    exit 1
fi

# Verificar se é root (para systemd)
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Precisa rodar como root (sudo) para instalar systemd service"
    echo "   Tentando instalar user service em ~/.config/systemd/user/..."
    
    USER_SERVICE_DIR="$HOME/.config/systemd/user"
    mkdir -p "$USER_SERVICE_DIR"
    USER_SERVICE_FILE="$USER_SERVICE_DIR/$SERVICE_NAME.service"
    
    cat > "$USER_SERVICE_FILE" <<EOF
[Unit]
Description=Prospector aapanel Auto-Publisher
After=network.target

[Service]
Type=simple
WorkingDirectory=$BASE_DIR
ExecStart=/usr/bin/python3 $PUBLISHER_SCRIPT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
    
    systemctl --user daemon-reload
    systemctl --user enable --now "$SERVICE_NAME"
    
    echo "✅ User service instalado!"
    echo "   Ver logs: journalctl --user -u $SERVICE_NAME -f"
    echo "   Parar: systemctl --user stop $SERVICE_NAME"
    exit 0
fi

# Instalar system service (root)
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Prospector aapanel Auto-Publisher
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$BASE_DIR
ExecStart=/usr/bin/python3 $PUBLISHER_SCRIPT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

echo "✅ System service instalado e iniciado!"
echo "   Ver logs: journalctl -u $SERVICE_NAME -f"
echo "   Status: systemctl status $SERVICE_NAME"
echo "   Parar: systemctl stop $SERVICE_NAME"