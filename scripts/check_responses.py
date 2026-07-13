#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.gmail_tracking import sync_gmail_replies


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "todos"
    print(json.dumps(sync_gmail_replies(target, on_progress=print), ensure_ascii=False, indent=2))
