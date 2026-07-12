"""List and preview proposal email drafts."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

from app.config import BASE_DIR
from app.db import db

emails_bp = Blueprint("emails", __name__, url_prefix="/api/emails")

DRAFTS_DIR = BASE_DIR / "drafts"


def _parse_draft(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    # Meta header we write in proposta.py
    to_m = re.search(r"<strong>Para:</strong>\s*([^<]+)", text, re.I)
    sub_m = re.search(r"<strong>Assunto:</strong>\s*([^<]+)", text, re.I)
    if not sub_m:
        sub_m = re.search(r"<title>([^<]+)</title>", text, re.I)
    modo_m = re.search(r"<strong>Modo:</strong>\s*([^<]+)", text, re.I)

    # Filename: draft_YYYYMMDD_HHMMSS_{slug}.html
    slug = ""
    m = re.match(r"draft_(\d{8})_(\d{6})_(.+)\.html$", path.name)
    created = None
    if m:
        slug = m.group(3)
        try:
            created = datetime.strptime(f"{m.group(1)}{m.group(2)}", "%Y%m%d%H%M%S").isoformat(
                sep=" "
            )
        except ValueError:
            created = None
    else:
        # fallback: {slug}-proposta.txt
        if path.name.endswith("-proposta.txt"):
            slug = path.name.replace("-proposta.txt", "")

    # Body after <hr> if present
    body = text
    if "<hr>" in text:
        body = text.split("<hr>", 1)[1].strip()
    elif "<hr/>" in text.lower():
        body = re.split(r"<hr\s*/?>", text, maxsplit=1, flags=re.I)[-1].strip()

    return {
        "id": path.name,
        "filename": path.name,
        "slug": slug,
        "to": (to_m.group(1).strip() if to_m else ""),
        "subject": (sub_m.group(1).strip() if sub_m else path.stem),
        "channel": (modo_m.group(1).strip() if modo_m else "local"),
        "created": created or datetime.fromtimestamp(path.stat().st_mtime).isoformat(sep=" "),
        "size": path.stat().st_size,
        "kind": "html" if path.suffix.lower() in (".html", ".htm") else "text",
    }


@emails_bp.get("")
def list_emails():
    """Drafts locais + leads em status proposta/publicado."""
    drafts = []
    if DRAFTS_DIR.exists():
        files = sorted(
            [p for p in DRAFTS_DIR.iterdir() if p.is_file() and p.suffix.lower() in (".html", ".htm", ".txt")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        drafts = [_parse_draft(p) for p in files[:100]]

    with db() as conn:
        leads = [
            dict(r)
            for r in conn.execute(
                """SELECT slug, nome, email, status, urlNova, dataProposta, atualizado
                   FROM leads
                   WHERE status IN ('proposta','publicado') AND COALESCE(email,'') != ''
                   ORDER BY atualizado DESC
                   LIMIT 100"""
            ).fetchall()
        ]

    return jsonify({"drafts": drafts, "leads": leads, "count": len(drafts)})


@emails_bp.get("/<path:filename>")
def get_email(filename: str):
    # Prevent path traversal
    safe = Path(filename).name
    path = DRAFTS_DIR / safe
    if not path.exists() or not path.is_file():
        return jsonify({"error": "not found"}), 404
    meta = _parse_draft(path)
    content = path.read_text(encoding="utf-8", errors="replace")
    meta["content"] = content
    return jsonify(meta)


@emails_bp.get("/<path:filename>/preview")
def preview_email(filename: str):
    safe = Path(filename).name
    path = DRAFTS_DIR / safe
    if not path.exists() or not path.is_file():
        return "Not found", 404
    content = path.read_text(encoding="utf-8", errors="replace")
    # Serve as HTML iframe-friendly
    if path.suffix.lower() in (".html", ".htm"):
        return Response(content, mimetype="text/html; charset=utf-8")
    html = f"""<!DOCTYPE html><html><head><meta charset=utf-8>
    <style>body{{font-family:system-ui;padding:24px;white-space:pre-wrap;background:#fff;color:#111}}</style>
    </head><body>{content.replace("&", "&amp;").replace("<", "&lt;")}</body></html>"""
    return Response(html, mimetype="text/html; charset=utf-8")


@emails_bp.delete("/<path:filename>")
def delete_email(filename: str):
    safe = Path(filename).name
    path = DRAFTS_DIR / safe
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    path.unlink()
    return jsonify({"success": True})
