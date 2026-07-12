#!/usr/bin/env bash
cd "$(dirname "$0")"
systemctl --user is-active prospector-web >/dev/null 2>&1 || true
if systemctl is-active --quiet prospector-web 2>/dev/null; then
  echo "prospector-web já ativo (systemd)"
else
  ./venv/bin/gunicorn -b 127.0.0.1:8765 -w 2 --timeout 120 wsgi:app &
  ./venv/bin/python worker.py &
fi
echo "Painel: https://prospector.iabotz.online/  (local :8765)"
