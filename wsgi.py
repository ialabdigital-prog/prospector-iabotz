#!/usr/bin/env python3
"""WSGI entrypoint for gunicorn."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.auth import ensure_admin_user

app = create_app()
ensure_admin_user()

if __name__ == "__main__":
    from app.config import load_config

    cfg = load_config()
    port = int((cfg.get("dashboard") or {}).get("porta") or 8765)
    host = (cfg.get("dashboard") or {}).get("host") or "0.0.0.0"
    app.run(host=host, port=port, threaded=True)
