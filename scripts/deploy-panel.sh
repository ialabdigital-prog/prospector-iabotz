#!/usr/bin/env bash
# Deploy / refresh prospector.iabotz.online reverse proxy + systemd units
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="prospector.iabotz.online"
PORT="${PROSPECTOR_PORT:-8765}"
VENV="$ROOT/venv"

echo "==> Install deps"
"$VENV/bin/pip" install -q -r "$ROOT/requirements.txt"

echo "==> systemd units"
sudo tee /etc/systemd/system/prospector-web.service >/dev/null <<EOF
[Unit]
Description=Prospector IA Botz Web
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$ROOT
Environment=PYTHONUNBUFFERED=1
Environment=PROSPECTOR_ADMIN_USER=${PROSPECTOR_ADMIN_USER:-admin}
Environment=PROSPECTOR_ADMIN_PASS=${PROSPECTOR_ADMIN_PASS:-prospector2026}
ExecStart=$VENV/bin/gunicorn -b 127.0.0.1:${PORT} -w 2 --timeout 120 wsgi:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/prospector-worker.service >/dev/null <<EOF
[Unit]
Description=Prospector IA Botz Worker
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$ROOT
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV/bin/python worker.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now prospector-web prospector-worker
sudo systemctl restart prospector-web prospector-worker

NGINX_AVAIL="/www/server/panel/vhost/nginx"
NGINX_SITE="/www/server/panel/vhost/nginx/${DOMAIN}.conf"
if [[ -d "$NGINX_AVAIL" ]]; then
  echo "==> nginx vhost $DOMAIN"
  sudo tee "$NGINX_SITE" >/dev/null <<EOF
server {
    listen 80;
    listen 443 ssl http2;
    server_name ${DOMAIN};

    # SSL paths managed by aaPanel / Let's Encrypt when available
    # ssl_certificate /www/server/panel/vhost/cert/${DOMAIN}/fullchain.pem;
    # ssl_certificate_key /www/server/panel/vhost/cert/${DOMAIN}/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_read_timeout 3600;
    }
}
EOF
  if command -v nginx >/dev/null; then
    sudo nginx -t && sudo nginx -s reload || true
  fi
else
  echo "aaPanel nginx path not found — configure reverse proxy manually to 127.0.0.1:${PORT}"
fi

echo "==> health"
sleep 1
curl -sS "http://127.0.0.1:${PORT}/health" || true
echo
echo "Done. Login: https://${DOMAIN}/  (user admin / pass from PROSPECTOR_ADMIN_PASS)"
