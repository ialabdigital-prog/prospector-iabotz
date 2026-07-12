#!/usr/bin/env python3
"""Compat: antigo dashboard-server.py agora sobe o painel Flask completo."""
from wsgi import app

if __name__ == "__main__":
    from app.config import load_config
    from app.auth import ensure_admin_user

    ensure_admin_user()
    cfg = load_config()
    port = int((cfg.get("dashboard") or {}).get("porta") or 8765)
    host = (cfg.get("dashboard") or {}).get("host") or "0.0.0.0"
    print(f"Prospector panel http://{host}:{port}")
    app.run(host=host, port=port, threaded=True)
