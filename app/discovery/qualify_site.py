"""Qualify lead website with Playwright — NOT Google Maps."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
WA_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\d+)", re.I)

THIRD_PARTY = (
    "facebook.com",
    "instagram.com",
    "linktr.ee",
    "bit.ly",
    "sites.google.com",
)


def qualify_site(url: str, timeout: int = 20) -> dict[str, Any]:
    """Heuristic site quality check (HTTP + HTML). Optional Playwright later."""
    result = {
        "ok": False,
        "email": "",
        "whatsapp": "",
        "motivos": [],
        "status_code": 0,
        "final_url": url,
    }
    if not url or not url.startswith("http"):
        result["motivos"].append("sem website")
        return result

    host = urlparse(url).netloc.lower()
    if any(t in host for t in THIRD_PARTY):
        result["motivos"].append("diretório/rede social terceiro")
        return result

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ProspectorIABotz/1.0)"
        }
        r = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        result["status_code"] = r.status_code
        result["final_url"] = r.url
        if r.status_code >= 400:
            result["motivos"].append(f"site inacessível HTTP {r.status_code}")
            return result
        html = r.text
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True).lower()

        # emails
        emails = EMAIL_RE.findall(html)
        emails = [e for e in emails if not e.endswith((".png", ".jpg", ".webp"))]
        if emails:
            result["email"] = emails[0]

        # mailto
        for a in soup.select('a[href^="mailto:"]'):
            href = a.get("href", "")
            m = EMAIL_RE.search(href)
            if m:
                result["email"] = m.group(0)
                break

        # whatsapp
        for a in soup.find_all("a", href=True):
            m = WA_RE.search(a["href"])
            if m:
                result["whatsapp"] = m.group(1)
                break

        motivos = []
        # CTA heuristics
        has_cta = bool(
            soup.select(
                'a[href*="whatsapp"], a[href*="wa.me"], a[href*="agendar"], '
                'button, .btn, .cta'
            )
        )
        if not has_cta:
            motivos.append("sem CTA claro de agendamento/contato")

        # dated layout signals
        if soup.find("table", {"width": True}) or "font face" in html.lower():
            motivos.append("layout datado")

        # free platforms
        final_host = urlparse(r.url).netloc.lower()
        if any(
            x in final_host
            for x in ("wixsite.com", "squarespace.com", "webnode.", "lojavirtual.")
        ):
            motivos.append("domínio/plataforma alheia")

        # viewport / mobile
        vp = soup.find("meta", attrs={"name": "viewport"})
        if not vp:
            motivos.append("não responsivo (sem viewport)")

        # social proof on site
        if "depoimento" not in text and "avaliação" not in text and "review" not in text:
            motivos.append("sem prova social no site")

        if len(text) < 400:
            motivos.append("conteúdo desorganizado/escasso")

        result["motivos"] = motivos
        result["ok"] = True
        return result
    except Exception as e:
        result["motivos"].append(f"erro ao abrir site: {e}")
        return result


def is_lead_gold(
    prospect: dict,
    site_info: dict,
    nota_min: float = 4.7,
    aval_min: int = 40,
) -> tuple[bool, str]:
    nota = prospect.get("nota")
    aval = prospect.get("avaliacoes") or 0
    if nota is None or nota < nota_min or aval < aval_min:
        return False, "abaixo do potencial (nota/avaliações)"
    if not prospect.get("site"):
        return False, "sem website"
    if not site_info.get("ok"):
        return False, site_info.get("motivos", ["site inválido"])[0]
    if not site_info.get("email"):
        return False, "sem e-mail público"
    motivos = site_info.get("motivos") or []
    if len(motivos) < 2:
        return False, "site bom o suficiente (<2 problemas)"
    return True, "; ".join(motivos[:4])
