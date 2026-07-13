#!/usr/bin/env python3
"""Import the public Design Prompts catalog into structured local references.

The site is a client-rendered application: its public JavaScript bundle contains
the canonical prompt content. This importer preserves the source URL and hash so
the catalog can be refreshed and audited without hand-maintained copies.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "skills" / "redesign-premium" / "references" / "design-catalog"
RAW_DIR = CATALOG_DIR / "raw"
STYLES_DIR = CATALOG_DIR / "styles"
SITE_URL = "https://designprompts.dev"


def decode_template(value: str) -> str:
    """Decode the JavaScript template literal without corrupting UTF-8 content."""
    return (
        value.replace("\\`", "`")
        .replace("\\n", "\n")
        .replace("\\\"", '"')
        .replace("\\\\", "\\")
    )


def classify(style_id: str, content: str) -> dict:
    text = f"{style_id} {content}".lower()
    tags = []
    for tag, terms in {
        "editorial": ("editorial", "newsprint", "serif", "typography"),
        "technical": ("terminal", "saas", "web3", "cyber", "industrial", "enterprise"),
        "playful": ("playful", "clay", "material", "maximal", "retro"),
        "luxury": ("luxury", "art deco", "academia", "monochrome"),
        "geometric": ("bauhaus", "swiss", "geometric", "brutal"),
        "dark": ("dark", "cyber", "terminal", "web3", "vaporwave"),
    }.items():
        if any(term in text for term in terms):
            tags.append(tag)

    recommendations = {
        "fitness": ["kinetic", "bauhaus", "bold-typography", "neo-brutalism"],
        "health": ["luxury", "academia", "monochrome", "professional"],
        "legal": ["academia", "newsprint", "professional", "luxury"],
        "food": ["bauhaus", "newsprint", "playful-geometric", "retro"],
        "technology": ["saas", "modern-dark", "terminal", "enterprise", "web3"],
        "creative": ["bauhaus", "luxury", "maximalism", "art-deco", "swiss-minimalist"],
        "family": ["playful-geometric", "material-design", "claymorphism", "botanical"],
    }
    best_for = [group for group, styles in recommendations.items() if style_id in styles]
    return {"tags": tags, "best_for": best_for}


def extract_bundle_url(html: str) -> str:
    match = re.search(r'<script type="module" crossorigin src="([^"]+\.js)">', html)
    if not match:
        raise RuntimeError("Design Prompts bundle was not found in the landing page")
    return SITE_URL + match.group(1)


def main() -> int:
    session = requests.Session()
    session.headers["User-Agent"] = "prospector-iabotz catalog importer/1.0"
    landing = session.get(SITE_URL, timeout=30)
    landing.raise_for_status()
    bundle_url = extract_bundle_url(landing.text)
    bundle = session.get(bundle_url, timeout=60)
    bundle.raise_for_status()
    source_hash = hashlib.sha256(bundle.content).hexdigest()
    source = bundle.text

    # Each bundled style has an id, metadata and a template literal named content.
    # Find each template first, then inspect its own nearby object header. Some
    # style ids are quoted JavaScript keys while others are bare identifiers.
    pattern = re.compile(r'''content:(?:`((?:\\.|[^`])*)`|'((?:\\.|[^'])*)'|"((?:\\.|[^"])*)")''', re.S)
    matches = list(pattern.finditer(source))
    if len(matches) < 20:
        raise RuntimeError(f"Expected a complete catalog, found only {len(matches)} styles")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    STYLES_DIR.mkdir(parents=True, exist_ok=True)
    styles = []
    imported_at = datetime.now(timezone.utc).isoformat()
    for match in matches:
        content = match.group(1) or match.group(2) or match.group(3)
        start = source.rfind('id:"', max(0, match.start() - 30000), match.start())
        identity = re.match(r'id:"([\w-]+)"', source[start:]) if start >= 0 else None
        if not identity:
            continue
        if match.start() - start > 10000:
            # This is a UI metadata `content` property, not a style prompt.
            continue
        style_id = identity.group(1)
        header = source[start:match.start()]
        key = style_id
        def field(name: str, fallback: str = "") -> str:
            value = re.search(rf'{name}:"([^"]*)"', header)
            return value.group(1) if value else fallback
        name = field("name", style_id.replace("-", " ").title())
        mode = field("mode", "light")
        font_type = field("fontType", "sans-serif")
        description = field("description")
        content = decode_template(content).strip()
        raw_file = RAW_DIR / f"{style_id}.md"
        raw_file.write_text(content + "\n", encoding="utf-8")
        details = classify(style_id, content)
        item = {
            "id": style_id,
            "name": name,
            "mode": mode,
            "font_type": font_type,
            "description": description,
            "source_url": f"{SITE_URL}/{style_id}",
            "raw_prompt": str(raw_file.relative_to(CATALOG_DIR)),
            "source_hash": source_hash,
            "imported_at": imported_at,
            "layouts": re.findall(r'([a-zA-Z]+):"([^"]+)"', header)[:12],
            **details,
        }
        (STYLES_DIR / f"{style_id}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        styles.append(item)

    catalog = {
        "schema_version": 1,
        "source": {"site": SITE_URL, "bundle": bundle_url, "hash": source_hash, "imported_at": imported_at},
        "license_note": "Source attribution is retained. Review upstream terms before redistributing raw prompt text.",
        "styles": styles,
    }
    (CATALOG_DIR / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Imported {len(styles)} design styles from {bundle_url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Catalog import failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
