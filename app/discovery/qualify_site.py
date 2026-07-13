"""Qualify lead website — HTTP + HTML heuristics (Playwright optional later).

Importante: sites SPA/JS (React, Lovable, Next) chegam com body quase vazio.
Não tratar isso como "site fraco" — meta description rica = site provavelmente bom.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

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

HARD_MOTIVOS = {
    "layout datado",
    "domínio/plataforma alheia",
    "diretório/rede social terceiro",
    "sem website",
}

# Sinais que só valem se o HTML estático for avaliável (não SPA vazio)
SOFT_MOTIVOS = {
    "sem CTA claro de agendamento/contato",
    "sem prova social no site",
    "conteúdo desorganizado/escasso",
    "não responsivo (sem viewport)",
}


def _meta_content(soup: BeautifulSoup, *selectors: tuple) -> str:
    parts = []
    for attrs in selectors:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            parts.append(tag["content"].strip())
    if soup.title and soup.title.string:
        parts.append(soup.title.string.strip())
    return " ".join(parts)


def qualify_site(url: str, timeout: int = 20) -> dict[str, Any]:
    """Heuristic site quality check (HTTP + HTML)."""
    result = {
        "ok": False,
        "email": "",
        "whatsapp": "",
        "motivos": [],
        "status_code": 0,
        "final_url": url,
        "spa": False,
        "evaluable": True,
        "text_len": 0,
        "meta_len": 0,
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
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }
        r = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        result["status_code"] = r.status_code
        result["final_url"] = r.url
        if r.status_code >= 400:
            result["motivos"].append(f"site inacessível HTTP {r.status_code}")
            return result

        html = r.text
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)
        text_l = text.lower()
        result["text_len"] = len(text)

        meta_blob = _meta_content(
            soup,
            {"name": "description"},
            {"property": "og:description"},
            {"name": "keywords"},
        )
        result["meta_len"] = len(meta_blob)
        meta_l = meta_blob.lower()

        # e-mails
        emails = [
            e
            for e in EMAIL_RE.findall(html)
            if not e.lower().endswith((".png", ".jpg", ".webp", ".gif"))
        ]
        if emails:
            result["email"] = emails[0]
        for a in soup.select('a[href^="mailto:"]'):
            m = EMAIL_RE.search(a.get("href", ""))
            if m:
                result["email"] = m.group(0)
                break
        # e-mail em meta / business tags
        if not result["email"]:
            m = EMAIL_RE.search(meta_blob + " " + html[:8000])
            if m and not m.group(0).lower().endswith((".png", ".jpg")):
                result["email"] = m.group(0)

        for a in soup.find_all("a", href=True):
            m = WA_RE.search(a["href"])
            if m:
                result["whatsapp"] = m.group(1)
                break

        # Detecção SPA / shell JS
        script_count = len(soup.find_all("script"))
        has_app_root = bool(
            soup.find(id="root")
            or soup.find(id="app")
            or soup.find(id="__next")
            or soup.find("div", attrs={"data-reactroot": True})
        )
        spa_markers = any(
            x in html.lower()
            for x in (
                "lovable.dev",
                "__NEXT_DATA__",
                "react-dom",
                "vue.runtime",
                "ng-version",
                "cdn.shopify.com/s/files",
            )
        )
        is_spa = (len(text) < 350 and (script_count >= 2 or has_app_root or spa_markers)) or (
            len(text) < 200 and result["meta_len"] > 60
        )
        result["spa"] = is_spa

        motivos: list[str] = []

        # Site SPA com meta profissional → NÃO é lead de redesign
        if is_spa and result["meta_len"] >= 80:
            result["evaluable"] = False
            result["motivos"] = [
                "site SPA/JS moderno com SEO — HTML estático insuficiente (provavelmente já bom)"
            ]
            result["ok"] = True
            return result

        if is_spa and result["meta_len"] < 80:
            result["evaluable"] = False
            result["motivos"] = ["site SPA/JS sem conteúdo estático — avaliação inconclusiva"]
            result["ok"] = True
            return result

        # Abaixo: HTML estático avaliável
        cta_words = ("whatsapp", "wa.me", "agendar", "agenda", "contato", "marcar", "consulta")
        has_cta = bool(
            soup.select(
                'a[href*="whatsapp"], a[href*="wa.me"], a[href*="agendar"], '
                'a[href*="contato"], button, .btn, .cta, [class*="cta"], [class*="btn"]'
            )
        ) or any(w in text_l or w in meta_l for w in cta_words)
        if not has_cta:
            motivos.append("sem CTA claro de agendamento/contato")

        if soup.find("table", {"width": True}) or 'font face="' in html.lower():
            motivos.append("layout datado")

        final_host = urlparse(r.url).netloc.lower()
        if any(
            x in final_host
            for x in ("wixsite.com", "squarespace.com", "webnode.", "lojavirtual.", "wordpress.com")
        ):
            motivos.append("domínio/plataforma alheia")

        vp = soup.find("meta", attrs={"name": "viewport"})
        if not vp:
            motivos.append("não responsivo (sem viewport)")

        proof = ("depoimento", "avaliação", "avaliacao", "review", "clientes", "estrelas", "nota")
        if not any(p in text_l or p in meta_l for p in proof):
            # só conta se há texto suficiente para esperar prova social
            if len(text) > 600:
                motivos.append("sem prova social no site")

        if len(text) < 400 and result["meta_len"] < 40:
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
    canais: list[str] | None = None,
    quality_mode: str = "balanced",
) -> tuple[bool, str]:
    """Lead ouro = potencial Maps alto + site fraco + contato do canal ativo."""
    nota = prospect.get("nota")
    aval = prospect.get("avaliacoes") or 0
    if nota is None or nota < nota_min or aval < aval_min:
        return False, "abaixo do potencial (nota/avaliações)"
    canais = canais or ["email"]
    has_email = bool(site_info.get("email"))
    has_whatsapp = bool(site_info.get("whatsapp") or prospect.get("telefone"))
    has_contact = ("email" in canais and has_email) or ("whatsapp" in canais and has_whatsapp)
    if not prospect.get("site"):
        # A business with strong Maps proof and a reachable contact is an ideal
        # "new site" offer, not a discarded redesign candidate.
        return (True, "sem site — oportunidade de criar presença digital") if has_contact else (False, "sem site e sem contato do canal")
    if not site_info.get("ok"):
        reason = (site_info.get("motivos") or ["site inválido"])[0]
        # A dead or malformed business website is a stronger commercial
        # opportunity than a merely dated one, provided there is a reachable
        # owner. Do not discard it before the contact-aware decision.
        broken_signals = ("inacess", "erro ao abrir", "vazio", "sem conteúdo", "inválido")
        if has_contact and any(signal in reason.lower() for signal in broken_signals):
            return True, f"{reason} — oportunidade de reconstrução"
        return False, reason

    motivos = site_info.get("motivos") or []

    # SPA moderno / avaliação inconclusiva → NÃO é lead
    if not site_info.get("evaluable", True):
        return False, motivos[0] if motivos else "site não avaliável estaticamente"

    if site_info.get("spa") and site_info.get("meta_len", 0) >= 80:
        return False, "site moderno (SPA) — não precisa redesign"

    if canais == ["email"] and not has_email:
        return False, "sem e-mail público"
    if canais == ["whatsapp"] and not has_whatsapp:
        return False, "sem WhatsApp/telefone público"
    if "email" in canais and "whatsapp" in canais and not (has_email or has_whatsapp):
        return False, "sem e-mail ou WhatsApp/telefone público"

    hard = [m for m in motivos if m in HARD_MOTIVOS or m.startswith("site inacessível")]
    soft = [m for m in motivos if m in SOFT_MOTIVOS or m not in hard]

    # Threshold explícito para a campanha, sem transformar qualquer site em lead.
    if len(hard) >= 2:
        return True, "; ".join(motivos[:4])
    if len(hard) >= 1 and len(soft) >= 1:
        return True, "; ".join(motivos[:4])
    if quality_mode in ("balanced", "broad") and len(soft) >= 2:
        return True, "; ".join(motivos[:4])
    if quality_mode == "broad" and len(hard) >= 1:
        return True, "; ".join(motivos[:4])
    if len(soft) >= 3:
        return True, "; ".join(motivos[:4])
    if len(motivos) < 2:
        return False, "site bom o suficiente (<2 problemas)"
    # 2 soft fracos sem hard → ainda não é ouro (evita falso positivo)
    return False, "sinais fracos para o critério " + quality_mode + " (" + "; ".join(motivos[:3]) + ")"
