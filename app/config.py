"""Config loader — prospector-config.json."""
from __future__ import annotations

import copy
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "prospector-config.json"
DB_FILE = BASE_DIR / "prospector.db"
LEADS_FILE = BASE_DIR / "leads.md"
SITES_DIR = BASE_DIR / "sites"

SECRET_KEYS = {
    ("aapanel", "api_token"),
    ("aapanel", "senha"),
    ("cloudflare", "api_key"),
    ("cloudflare", "api_token"),
    ("maps", "google_maps_api_key"),
    ("maps", "apify_api_key"),
    ("llm", "openrouter_api_key"),
    ("auth", "secret_key"),
    ("composio", "api_key"),
}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def save_config(config: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def mask_config(config: dict | None = None) -> dict:
    cfg = copy.deepcopy(config if config is not None else load_config())
    for section, key in SECRET_KEYS:
        block = cfg.get(section)
        if isinstance(block, dict) and block.get(key):
            block[key] = "***"
    # legacy cloudflare key at top if any
    return cfg


def merge_config(incoming: dict) -> dict:
    """Merge incoming config without overwriting secrets sent as ***."""
    current = load_config()
    for section, values in incoming.items():
        if not isinstance(values, dict):
            current[section] = values
            continue
        dest = current.setdefault(section, {})
        if not isinstance(dest, dict):
            current[section] = values
            continue
        for k, v in values.items():
            if v == "***":
                continue
            dest[k] = v
    save_config(current)
    return current


def get_maps_keys() -> tuple[str, str]:
    cfg = load_config()
    maps = cfg.get("maps") or {}
    return (
        (maps.get("google_maps_api_key") or "").strip(),
        (maps.get("apify_api_key") or "").strip(),
    )
