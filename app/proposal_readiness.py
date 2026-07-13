from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import requests

from app.config import SITES_DIR


def check_proposal_readiness(slug: str, public_url: str = "", verify_public: bool = True) -> dict:
    site_dir = SITES_DIR / slug
    index = site_dir / "index.html"
    proposal = site_dir / "proposta.html"
    before = site_dir / "assets" / "before.png"
    after = site_dir / "assets" / "after.png"
    errors = []

    for path, label, minimum in ((index, "site gerado", 1_000), (proposal, "página de proposta", 1_000), (after, "print novo", 10_000)):
        if not path.exists() or path.stat().st_size < minimum:
            errors.append(f"{label} ausente ou inválido: {path.name}")

    html = proposal.read_text(encoding="utf-8", errors="replace") if proposal.exists() else ""
    requires_before = "assets/before.png" in html
    if requires_before and (not before.exists() or before.stat().st_size < 10_000):
        errors.append("print anterior ausente ou inválido: before.png")
    if "assets/after.png" not in html:
        errors.append("a proposta não referencia o print novo")
    if "inserir screenshot" in html.lower() or "card-img placeholder" in html.lower():
        errors.append("a proposta ainda contém placeholders")
    if index.exists():
        screenshots = [(after, "print novo")] + ([(before, "print anterior")] if requires_before else [])
        for screenshot, label in screenshots:
            if screenshot.exists() and screenshot.stat().st_mtime + 5 < index.stat().st_mtime:
                errors.append(f"{label} está desatualizado")

    base = (public_url or "").rstrip("/") + "/"
    if verify_public:
        if not base.startswith("https://"):
            errors.append("URL pública HTTPS não configurada")
        elif not errors:
            try:
                response = requests.get(urljoin(base, "proposta.html"), timeout=20)
                response.raise_for_status()
                public_html = response.text
                if "assets/after.png" not in public_html or (requires_before and "assets/before.png" not in public_html):
                    errors.append("proposta pública não contém os prints esperados")
                if "inserir screenshot" in public_html.lower() or "card-img placeholder" in public_html.lower():
                    errors.append("proposta pública ainda contém placeholders")
                assets = ["assets/after.png"] + (["assets/before.png"] if requires_before else [])
                for asset in assets:
                    image = requests.get(urljoin(base, asset), timeout=20)
                    if not image.ok or len(image.content) < 10_000 or "image" not in image.headers.get("content-type", ""):
                        errors.append(f"asset público inválido: {asset}")
            except requests.RequestException as exc:
                errors.append(f"proposta pública indisponível: {exc}")

    return {
        "ready": not errors,
        "errors": errors,
        "proposal_url": urljoin(base, "proposta.html") if base else "",
    }


def require_proposal_ready(slug: str, public_url: str = "", verify_public: bool = True) -> dict:
    result = check_proposal_readiness(slug, public_url, verify_public)
    if not result["ready"]:
        raise RuntimeError("Outreach bloqueado: " + "; ".join(result["errors"]))
    return result
