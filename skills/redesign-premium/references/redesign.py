#!/usr/bin/env python3
"""
Redesign Premium - Gera site premium, editor visual e comparador antes/depois
"""
import sys
import os
import json
import asyncio
import shutil
import re
import random
from html import escape
from collections import Counter
from urllib.parse import urljoin
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
from app.design_catalog import COMPOSITIONS, fallback_brief, load_catalog, normalize_llm_brief


def _public_url(slug: str) -> str:
    """Return the configured public URL for a generated lead site."""
    cfg = {}
    cf = BASE_DIR / "prospector-config.json"
    if cf.exists():
        try:
            cfg = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    base = (cfg.get("aapanel") or {}).get("dominio_base") or "example.com"
    return f"https://{slug}.{base}/"


# Load config directly from JSON
config_file = BASE_DIR / "skills" / "redesign-premium" / "references" / "redesign-config.json"
config = json.loads(config_file.read_text(encoding='utf-8'))
SECTIONS = config["sections"]
CSS_VARIABLES = config["css_variables"]
BREAKPOINTS = config["breakpoints"]
EDITOR_SNIPPETS = config["editor_snippets"]


@dataclass
class Lead:
    slug: str
    nome: str
    nicho: str
    cidade: str
    nota: str = ""
    avaliacoes: str = ""
    email: str = ""
    telefone: str = ""
    whatsapp: str = ""
    site_atual: str = ""
    motivo: str = ""
    status: str = ""
    url_nova: str = ""
    endereco: str = ""


def load_lead(slug: str) -> Optional[Lead]:
    """Carrega lead do SQLite (fonte da verdade) com fallback leads.md."""
    db_file = BASE_DIR / "prospector.db"
    if db_file.exists():
        import sqlite3
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM leads WHERE slug=?", (slug,)).fetchone()
        conn.close()
        if row:
            return Lead(
                slug=row["slug"],
                nome=row["nome"] or slug,
                nicho=row["nicho"] or "",
                cidade=row["cidade"] or "",
                nota=str(row["nota"] or ""),
                avaliacoes=str(row["avaliacoes"] or ""),
                email=row["email"] or "",
                telefone=row["telefone"] or "",
                whatsapp=row["whatsapp"] or "",
                site_atual=row["siteAntigo"] or "",
                motivo=row["motivo"] or "",
                status=row["status"] or "",
                url_nova=row["urlNova"] or "",
            )

    leads_file = BASE_DIR / "leads.md"
    if not leads_file.exists():
        return None

    content = leads_file.read_text(encoding="utf-8")
    for line in content.split("\n"):
        if "|" not in line or line.startswith("| #") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        # # | Nome | Nota | Aval | Email | Tel | WA | Site | Motivo | Status | URL
        if len(parts) < 10:
            continue
        nome = parts[1] if parts[0].replace(".", "").isdigit() else parts[0]
        lead_slug = "".join(
            c for c in __import__("unicodedata").normalize("NFKD", nome.lower())
            if not __import__("unicodedata").combining(c)
        )
        import re
        lead_slug = re.sub(r"[^a-z0-9]+", "-", lead_slug).strip("-")
        if lead_slug == slug or nome.lower().replace(" ", "-") == slug:
            idx = 1 if parts[0].replace(".", "").isdigit() else 0
            return Lead(
                slug=slug,
                nome=parts[idx],
                nota=parts[idx + 1] if len(parts) > idx + 1 else "",
                avaliacoes=parts[idx + 2] if len(parts) > idx + 2 else "",
                email=parts[idx + 3] if len(parts) > idx + 3 else "",
                telefone=parts[idx + 4] if len(parts) > idx + 4 else "",
                whatsapp=parts[idx + 5] if len(parts) > idx + 5 else "",
                site_atual=parts[idx + 6] if len(parts) > idx + 6 else "",
                motivo=parts[idx + 7] if len(parts) > idx + 7 else "",
                status=parts[idx + 8] if len(parts) > idx + 8 else "",
                url_nova=parts[idx + 9] if len(parts) > idx + 9 else "",
                cidade="",
                nicho="",
            )
    return None


def mark_redesigned(slug: str) -> None:
    db_file = BASE_DIR / "prospector.db"
    if not db_file.exists():
        return
    import sqlite3
    conn = sqlite3.connect(db_file)
    conn.execute(
        """UPDATE leads SET status='redesenhado', atualizado=datetime('now','localtime')
           WHERE slug=? AND status IN ('novo','descartado','redesenhado')""",
        (slug,),
    )
    conn.commit()
    conn.close()


def list_slugs_for_redesign(target: str) -> List[str]:
    db_file = BASE_DIR / "prospector.db"
    if db_file.exists():
        import sqlite3
        conn = sqlite3.connect(db_file)
        if target == "todos":
            rows = conn.execute(
                "SELECT slug FROM leads WHERE status='novo' ORDER BY atualizado DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT slug FROM leads WHERE slug=?", (target,)
            ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    return [target] if target != "todos" else []


def extract_content_from_site(url: str) -> Dict:
    """Extrai o que for possível via HTTP (meta/OG) — útil para SPAs com body vazio."""
    out = {
        "titulo": "",
        "sobre": "",
        "hero_headline": "",
        "hero_subheadline": "",
        "hero_tagline": "",
        "sobre_detalhado": "",
        "servicos": [],
        "depoimentos": [],
        "equipe": [],
        "faq": [],
        "artigos": [],
        "diferenciais": [],
        "navegacao": [],
        "source_profile": {},
        "contato": {},
        "cores": {"primary": "#0d9488", "secondary": "#0f172a", "accent": "#0f766e", "bg": "#f8fafc"},
        "logo_url": "",
        "imagens": [],
        "endereco": "",
    }
    if not url or not url.startswith("http"):
        return out
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }
        r = requests.get(
            url,
            timeout=20,
            headers=headers,
            allow_redirects=True,
        )
        r.encoding = r.apparent_encoding or r.encoding
        if r.status_code >= 400:
            return out
        soup = BeautifulSoup(r.text, "lxml")

        def meta(*attrs_list):
            for attrs in attrs_list:
                t = soup.find("meta", attrs=attrs)
                if t and t.get("content"):
                    return t["content"].strip()
            return ""

        title = (soup.title.string or "").strip() if soup.title else ""
        desc = meta({"name": "description"}, {"property": "og:description"})
        keywords = meta({"name": "keywords"})
        og_img = meta({"property": "og:image"})
        street = meta({"name": "business:contact_data:street_address"})
        city = meta({"name": "business:contact_data:locality"})
        phone = meta({"name": "business:contact_data:phone_number"})

        out["titulo"] = title
        out["sobre"] = desc
        out["hero_headline"] = title.split("|")[0].strip() if title else ""
        out["hero_subheadline"] = desc[:180] if desc else ""
        # Builder/placeholder OG assets are not business photography. Never reuse them.
        blocked_image_hosts = ("lovable.dev", "vercel.app", "webflow.io", "wixstatic.com")
        if og_img and not any(host in og_img.lower() for host in blocked_image_hosts):
            out["imagens"] = [og_img]
            out["hero_image"] = og_img
            out["sobre_imagem"] = og_img

        palette_sources = [r.text]
        stylesheet_palette = None
        # Modern sites often keep their brand colors only in a bundled stylesheet.
        for stylesheet in soup.select('link[rel="stylesheet"][href]')[:4]:
            css_url = urljoin(r.url, stylesheet.get("href", ""))
            if "fonts.googleapis" in css_url:
                continue
            try:
                css_response = requests.get(css_url, timeout=10, headers=headers)
                if css_response.ok:
                    palette_sources.append(css_response.text)
                    stylesheet_palette = extract_palette(css_response.text) or stylesheet_palette
            except requests.RequestException:
                continue
        palette = stylesheet_palette or extract_palette("\n".join(palette_sources))
        if palette:
            out["cores"] = palette
        if street or city:
            out["endereco"] = ", ".join(x for x in (street, city) if x)
        if phone:
            out["contato"]["telefone"] = phone

        page_h1 = soup.find("h1")
        if page_h1:
            out["hero_headline"] = page_h1.get_text(" ", strip=True) or out["hero_headline"]
            hero_section = page_h1.find_parent("section")
            hero_paragraph = hero_section.find("p") if hero_section else None
            if hero_paragraph:
                out["hero_tagline"] = hero_paragraph.get_text(" ", strip=True)

        # Recover public contact and brand data from real DOM, not just meta tags.
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            label = link.get_text(" ", strip=True)
            if href.startswith("mailto:") and not out["contato"].get("email"):
                out["contato"]["email"] = href.split(":", 1)[1].split("?", 1)[0]
            if href.startswith("tel:") and not out["contato"].get("telefone"):
                out["contato"]["telefone"] = href.split(":", 1)[1]
            if ("maps" in href or "g.co/" in href) and len(label) > 12 and not out["endereco"]:
                out["endereco"] = label
            wa_match = re.search(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\d+)", href, re.I)
            if wa_match and not out["contato"].get("whatsapp"):
                out["contato"]["whatsapp"] = wa_match.group(1)
            if not out["logo_url"] and ("logo" in " ".join(link.get("class", [])).lower() or "logo" in (link.get("aria-label") or "").lower()):
                image = link.find("img", src=True)
                if image:
                    out["logo_url"] = urljoin(r.url, image["src"])

        if not out["logo_url"]:
            logo = soup.select_one('img[alt*="logo" i], img[src*="logo" i], .hfe-site-logo-img, [class*="site-logo"] img, header img[src]')
            if logo and logo.get("src"):
                out["logo_url"] = urljoin(r.url, logo["src"])

        public_images = []
        for image in soup.select("img[src]"):
            image_url = urljoin(r.url, image["src"])
            alt = (image.get("alt") or "").lower()
            source_l = image_url.lower()
            if source_l.startswith("data:") or any(blocked in source_l for blocked in blocked_image_hosts):
                continue
            if any(token in f"{alt} {source_l}" for token in ("logo", "icon", "favicon", "sprite")):
                continue
            if image_url not in public_images:
                public_images.append(image_url)
        out["imagens"] = (out.get("imagens") or []) + public_images[:8]
        if not out.get("hero_image") and public_images:
            out["hero_image"] = public_images[0]
            out["sobre_imagem"] = public_images[min(1, len(public_images) - 1)]

        # Headings and nearby paragraphs supply real service/FAQ text.
        headings = [h.get_text(" ", strip=True) for h in soup.select("h1,h2,h3") if h.get_text(" ", strip=True)]
        text_blocks = [p.get_text(" ", strip=True) for p in soup.select("p") if len(p.get_text(" ", strip=True)) > 35]
        nav_items = []
        for link in soup.select("nav a[href], [class*='menu'] a[href]"):
            label = link.get_text(" ", strip=True)
            if 1 < len(label) < 40 and label not in nav_items:
                nav_items.append(label)
        out["navegacao"] = nav_items[:8]
        if text_blocks:
            out["sobre"] = max(text_blocks, key=len)[:700] if not out["sobre"] else out["sobre"]
        for heading in soup.select("h2,h3"):
            if heading.get_text(" ", strip=True).lower() in {"sobre nós", "sobre nos", "ronaldo abreu", "quem somos"}:
                section = heading.find_parent("section")
                paragraphs = [p.get_text(" ", strip=True) for p in section.select("p")] if section else []
                detailed = max(paragraphs, key=len) if paragraphs else ""
                if len(detailed) > len(out["sobre_detalhado"]):
                    out["sobre_detalhado"] = detailed[:1800]
        service_markers = ("serviço", "especialidade", "tratamento", "procedimento", "o que fazemos")
        service_keywords = (
            "direito ", "advocacia", "consulta", "terapia", "tratamento", "procedimento",
            "odont", "implante", "ortodont", "nutri", "fisioterapia", "cirurgia", "estética",
        )
        semantic_services = []
        for element in soup.select('[class*="service"], [class*="servico"], [class*="area"], .elementor-icon-list-text'):
            label = element.get_text(" ", strip=True)
            lowered = label.lower()
            if 3 < len(label) < 80 and any(keyword in lowered for keyword in service_keywords) and label not in semantic_services:
                semantic_services.append(label)
        heading_services = [
            node.get_text(" ", strip=True) for node in soup.select("h2,h3")
            if 3 < len(node.get_text(" ", strip=True)) < 80
            and any(keyword in node.get_text(" ", strip=True).lower() for keyword in service_keywords)
        ]
        combined_services = []
        source_labels = heading_services if len(heading_services) >= 3 else [*heading_services, *semantic_services]
        for label in source_labels:
            if label not in combined_services:
                combined_services.append(label)
        if combined_services:
            service_records = []
            for label in combined_services[:8]:
                heading_node = next((node for node in soup.select("h1,h2,h3") if node.get_text(" ", strip=True) == label), None)
                paragraph = heading_node.find_next("p") if heading_node else None
                service_records.append({"titulo": label, "descricao": paragraph.get_text(" ", strip=True)[:240] if paragraph else ""})
            out["servicos"] = service_records
        generic_headings = ("quem somos", "áreas de atuação", "areas de atuacao", "blog", "fale conosco", "contato", "nos siga")
        service_headings = [
            h for h in headings
            if not any(marker in h.lower() for marker in service_markers)
            and not any(generic in h.lower() for generic in generic_headings)
        ]
        if not out["servicos"]:
            out["servicos"] = [{"titulo": h, "descricao": ""} for h in service_headings[:6] if 3 < len(h) < 80]
        for detail in soup.select("details"):
            question = detail.find("summary")
            answer = detail.get_text(" ", strip=True)
            if question and answer:
                out["faq"].append((question.get_text(" ", strip=True), answer.replace(question.get_text(" ", strip=True), "", 1).strip()))
        for title in soup.select(".elementor-tab-title, [class*='accordion'] [class*='title']"):
            question = title.get_text(" ", strip=True)
            answer_node = title.find_next_sibling() or title.find_next(class_=re.compile("tab-content|accordion.*content", re.I))
            answer = answer_node.get_text(" ", strip=True) if answer_node else ""
            if question and answer and (question, answer) not in out["faq"]:
                out["faq"].append((question, answer))
        if not out["faq"]:
            for heading in headings:
                if "?" in heading:
                    out["faq"].append((heading, "Entre em contato para receber orientação personalizada."))
        out["faq"] = out["faq"][:6]

        for article in soup.select("article")[:6]:
            title_node = article.select_one("h2,h3,h4,h5,h6")
            link = title_node.find("a", href=True) if title_node else article.find("a", href=True)
            image = article.find("img", src=True)
            title_text = title_node.get_text(" ", strip=True) if title_node else ""
            if title_text and link:
                out["artigos"].append({
                    "titulo": title_text,
                    "url": urljoin(r.url, link["href"]),
                    "imagem": urljoin(r.url, image["src"]) if image else "",
                })

        for item in soup.select("li"):
            label = item.get_text(" ", strip=True)
            if 20 < len(label) < 150 and label not in out["diferenciais"]:
                out["diferenciais"].append(label)
        out["diferenciais"] = out["diferenciais"][:6]
        page_text = soup.get_text(" ", strip=True)
        if not out["contato"].get("email"):
            email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", page_text, re.I)
            if email_match:
                out["contato"]["email"] = email_match.group(0)
        out["source_profile"] = {
            "word_count": len(page_text.split()),
            "heading_count": len(headings),
            "section_count": len(soup.select("section")),
            "article_count": len(out["artigos"]),
            "image_count": len(public_images),
            "has_form": bool(soup.select_one("form")),
            "has_cta": bool(soup.select_one('a[href*="contato"], a[href*="agend"], a[href*="wa.me"], button')),
        }
        profile = out["source_profile"]
        out["source_strategy"] = "source-led" if (
            profile["word_count"] >= 500 and profile["heading_count"] >= 6
            and (profile["image_count"] >= 2 or profile["article_count"] >= 2)
            and profile["has_cta"]
        ) else "transformative"

        # Serviços a partir de keywords
        if keywords and not out["servicos"]:
            parts = [p.strip() for p in keywords.split(",") if p.strip()]
            # filtra termos genéricos
            skip = {"dentista", "clínica", "clinica", "rj", "rio", "odontológica", "odontologica"}
            nice = [p for p in parts if p.lower() not in skip and len(p) > 3][:6]
            out["servicos"] = [
                {
                    "titulo": p.title() if p.islower() else p,
                    "descricao": f"Atendimento especializado em {p.lower()}.",
                    "icone": "",
                }
                for p in nice
            ]
    except Exception:
        pass
    return out


def localize_brand_assets(content: Dict, site_dir: Path) -> Dict:
    """Keep the original public logo stable instead of hotlinking it."""
    logo_url = content.get("logo_url") or ""
    assets = site_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    def download(url: str, stem: str) -> str:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        suffix = ".svg" if "svg" in content_type else ".webp" if "webp" in content_type else ".png" if "png" in content_type else ".jpg"
        target = assets / f"{stem}{suffix}"
        target.write_bytes(response.content)
        return f"assets/{target.name}"

    if logo_url and logo_url.startswith("http"):
        try:
            content["source_logo_url"] = logo_url
            content["logo_url"] = download(logo_url, "source-logo")
        except requests.RequestException:
            pass

    source_images = []
    image_map = {}
    for index, url in enumerate(dict.fromkeys(content.get("imagens") or []), 1):
        if not str(url).startswith("http") or url == logo_url:
            continue
        try:
            local = download(url, f"source-{index}")
            source_images.append(local)
            image_map[url] = local
        except requests.RequestException:
            continue
        if len(source_images) >= 6:
            break
    content["source_images"] = source_images
    for article in content.get("artigos") or []:
        if article.get("imagem") in image_map:
            article["imagem"] = image_map[article["imagem"]]
    return content


def extract_palette(html: str) -> Dict | None:
    """Derive a restrained brand palette from real CSS, avoiding neutral colors."""
    colors = Counter(re.findall(r"#[0-9a-fA-F]{6}\b", html))
    candidates = []
    for color, count in colors.items():
        value = color.lower()
        rgb = tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
        maximum, minimum = max(rgb), min(rgb)
        saturation = maximum - minimum
        # Ignore whites, almost blacks and neutral grays.
        if maximum > 242 or maximum < 38 or saturation < 35:
            continue
        candidates.append((count, value, rgb))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, primary, primary_rgb = candidates[0]
    distinct = [item for item in candidates[1:] if sum((a - b) ** 2 for a, b in zip(item[2], primary_rgb)) > 4200]
    accent = distinct[0][1] if distinct else _mix_hex(primary, "#ffffff", 0.28)
    secondary = _mix_hex(primary, "#080b12", 0.68)
    bg = _mix_hex(primary, "#ffffff", 0.94)
    return {"primary": primary, "secondary": secondary, "accent": accent, "bg": bg}


def _mix_hex(first: str, second: str, second_weight: float) -> str:
    def rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))

    try:
        a, b = rgb(first), rgb(second)
    except (ValueError, TypeError):
        return first
    weight = max(0.0, min(1.0, second_weight))
    mixed = tuple(round(x * (1 - weight) + y * weight) for x, y in zip(a, b))
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


def _luminance(value: str) -> float:
    try:
        channels = [int(value.lstrip("#")[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    except (ValueError, TypeError):
        return 0.5
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def resolve_brand_palette(conteudo: Dict, family: str, style: str, variation: Dict) -> Dict:
    source = conteudo.get("cores") or {}
    primary = source.get("primary") or "#315f78"
    secondary = source.get("secondary") or _mix_hex(primary, "#070a10", 0.7)
    accent = source.get("accent") or _mix_hex(primary, "#ffffff", 0.25)
    background = source.get("bg") or _mix_hex(primary, "#ffffff", 0.94)
    tone = str(variation.get("surface_tone") or "brand-adaptive").lower()

    if style == "monochrome":
        return {"bg": "#f7f7f5", "ink": "#111111", "accent": "#111111", "secondary": "#242424", "surface": "#ffffff"}
    if style == "newsprint":
        return {"bg": "#f5f1e8", "ink": "#171512", "accent": primary, "secondary": secondary, "surface": "#fffdf7"}
    if family in {"technical", "kinetic"} or "dark" in tone:
        return {"bg": secondary, "ink": "#f7f8fa", "accent": accent, "secondary": primary, "surface": _mix_hex(secondary, "#ffffff", 0.08)}
    if family == "geometric":
        return {"bg": background, "ink": secondary, "accent": primary, "secondary": accent, "surface": _mix_hex(background, "#ffffff", 0.5)}
    if family == "soft":
        return {"bg": _mix_hex(background, "#ffffff", 0.35), "ink": secondary, "accent": primary, "secondary": accent, "surface": "#ffffff"}
    return {"bg": background, "ink": secondary, "accent": primary, "secondary": accent, "surface": _mix_hex(background, "#ffffff", 0.72)}


def niche_palette(nicho: str) -> Dict:
    n = (nicho or "").lower()
    if any(x in n for x in ("odont", "dent", "invisalign", "implante")):
        return {"primary": "#0d9488", "secondary": "#134e4a", "accent": "#14b8a6", "bg": "#f0fdfa"}
    if any(x in n for x in ("nutri", "diet")):
        return {"primary": "#16a34a", "secondary": "#14532d", "accent": "#22c55e", "bg": "#f0fdf4"}
    if any(x in n for x in ("psico", "terap")):
        return {"primary": "#7c3aed", "secondary": "#1e1b4b", "accent": "#a78bfa", "bg": "#faf5ff"}
    if any(x in n for x in ("advog", "jurid")):
        return {"primary": "#1e3a5f", "secondary": "#0f172a", "accent": "#c4a574", "bg": "#f8fafc"}
    return {"primary": "#0d9488", "secondary": "#0f172a", "accent": "#14b8a6", "bg": "#f8fafc"}


def niche_services(nicho: str) -> List[Dict]:
    n = (nicho or "").lower()
    if any(x in n for x in ("odont", "dent", "invisalign")):
        return [
            {
                "titulo": "Implantes dentários",
                "descricao": "Reabilitação com tecnologia atual e planejamento digital.",
            },
            {
                "titulo": "Alinhadores invisíveis",
                "descricao": "Ortodontia discreta com acompanhamento próximo.",
            },
            {
                "titulo": "Lentes e estética",
                "descricao": "Harmonia do sorriso com acabamento natural.",
            },
            {
                "titulo": "Clareamento",
                "descricao": "Protocolos seguros para um sorriso mais luminoso.",
            },
        ]
    if "nutri" in n:
        return [
            {"titulo": "Consulta nutricional", "descricao": "Plano alimentar sob medida para sua rotina."},
            {"titulo": "Emagrecimento", "descricao": "Estratégia sustentável, sem fórmulas milagre."},
            {"titulo": "Performance", "descricao": "Nutrição para treino, energia e recuperação."},
        ]
    if "psico" in n:
        return [
            {"titulo": "Terapia individual", "descricao": "Espaço seguro para ansiedade, humor e autoconhecimento."},
            {"titulo": "Online ou presencial", "descricao": "Flexibilidade sem perder profundidade no cuidado."},
            {"titulo": "Acompanhamento contínuo", "descricao": "Processo terapêutico com presença e clareza."},
        ]
    return [
        {"titulo": "Atendimento personalizado", "descricao": "Cuidado próximo, do primeiro contato ao acompanhamento."},
        {"titulo": "Especialidade", "descricao": f"Referência em {nicho or 'sua área'} na região."},
        {"titulo": "Agendamento fácil", "descricao": "WhatsApp e formulário direto no site."},
    ]


def visual_direction(lead: Lead) -> str:
    """Choose a composition, not just a different palette."""
    cfg_file = BASE_DIR / "prospector-config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else {}
    selected = ((cfg.get("redesign") or {}).get("direction") or "auto").lower()
    if selected != "auto":
        return selected
    niche = (lead.nicho or "").lower()
    if any(term in niche for term in ("advog", "arquitet", "estética", "estetica")):
        return "editorial"
    if any(term in niche for term in ("odont", "dent", "clínica", "clinica", "medic")):
        return "cinematic"
    return "minimal"


def llm_redesign_content(lead: Lead, source: Dict) -> Dict:
    """Use distinct orchestration and redesign models when configured.

    Both calls are optional: an unavailable provider never blocks a demo site.
    """
    cfg_file = BASE_DIR / "prospector-config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else {}
    llm_cfg = cfg.get("llm") or {}
    if not llm_cfg.get("redesign_llm_enabled"):
        return {}
    try:
        from app.llm.router import complete

        redesign_provider = llm_cfg.get("redesign_provider") or llm_cfg.get("default_provider")
        copy = complete(
            redesign_provider,
            system="Você cria copy de site premium em pt-BR. Preserve fatos; não invente credenciais, preços ou depoimentos.",
            prompt=(
                f"Crie copy para {lead.nome}, {lead.nicho} em {lead.cidade}. "
                f"Dados públicos: título={source.get('titulo','')}; descrição={source.get('sobre','')}; "
                f"serviços={source.get('servicos',[])}. Responda SOMENTE JSON com hero_headline, hero_subheadline, sobre."
            ),
            model=llm_cfg.get("redesign_model") or None,
        )
        match = re.search(r"\{.*\}", copy, re.S)
        data = json.loads(match.group(0)) if match else {}
        return {key: value for key, value in data.items() if key in {"hero_headline", "hero_subheadline", "sobre"} and isinstance(value, str)}
    except Exception as exc:
        print(f"   ⚠️ LLM redesign indisponível: {exc}")
        return {}


def select_creative_brief(lead: Lead, source: Dict, previous: List[Dict]) -> Dict:
    """Select one coherent catalog direction before copy or visual generation."""
    lead_data = {"nome": lead.nome, "nicho": lead.nicho, "cidade": lead.cidade}
    fallback = fallback_brief(lead_data, previous)
    cfg_file = BASE_DIR / "prospector-config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else {}
    llm_cfg = cfg.get("llm") or {}
    if not llm_cfg.get("redesign_llm_enabled"):
        return fallback
    try:
        from app.llm.router import complete

        catalog = load_catalog().get("styles", [])
        # Give the model a small, auditable decision matrix rather than thirty
        # conflicting raw prompts. Detailed rules are consumed by renderers.
        options = [
            {"id": item["id"], "name": item["name"], "tags": item.get("tags", []), "best_for": item.get("best_for", [])}
            for item in catalog
        ]
        provider = llm_cfg.get("orchestrator_provider") or llm_cfg.get("default_provider")
        response = complete(
            provider,
            system=(
                "Você é diretor criativo. Escolha UMA direção visual coerente para um site local. "
                "Não misture estilos e não escolha cyberpunk, terminal ou web3 para saúde, jurídico ou negócios tradicionais. "
                "Responda somente JSON válido."
            ),
            prompt=(
                f"Negócio: {lead.nome}; nicho: {lead.nicho}; cidade: {lead.cidade}; "
                f"reputação: {lead.nota} ({lead.avaliacoes} avaliações); conteúdo: {source.get('sobre', '')[:900]}. "
                f"Identidade extraída: cores={source.get('cores', {})}; logo={'sim' if source.get('logo_url') else 'não'}. "
                f"Direção única recomendada para evitar sites genéricos no nicho: {fallback['style_id']} / {fallback['layout_id']}. "
                f"Opções: {json.dumps(options, ensure_ascii=False)}. "
                "JSON: style_id, layout_id, confidence (0-1), reason, section_plan (lista), image_plan (lista), "
                "variation {palette_direction, image_mood, density, section_emphasis, hero_treatment, surface_tone, section_rhythm}. "
                "Cada campo deve variar a composição, não apenas adjetivos. Respeite logo e cores corporativas extraídas."
            ),
            model=llm_cfg.get("orchestrator_model") or None,
        )
        match = re.search(r"\{.*\}", response, re.S)
        return normalize_llm_brief(json.loads(match.group(0)) if match else {}, lead_data, previous)
    except Exception as exc:
        print(f"   ⚠️ seletor criativo indisponível: {exc}")
        return fallback


def generate_css_variables(cores: Dict, direction: str = "minimal") -> str:
    """Gera CSS custom properties com tipografia e composição por direção visual."""
    heading = '"DM Serif Display", Georgia, serif' if direction == "editorial" else '"Playfair Display", Georgia, serif' if direction == "cinematic" else '"Fraunces", Georgia, serif'
    body = '"DM Sans", system-ui, sans-serif' if direction == "editorial" else '"Plus Jakarta Sans", system-ui, sans-serif' if direction == "cinematic" else '"Manrope", system-ui, sans-serif'
    return f"""
:root {{
    --color-primary: {cores.get('primary', '#0d9488')};
    --color-secondary: {cores.get('secondary', '#0f172a')};
    --color-accent: {cores.get('accent', '#14b8a6')};
    --color-bg: {cores.get('bg', '#f8fafc')};
    --color-card: #ffffff;
    --color-border: rgba(15,23,42,.08);
    --color-text: #0f172a;
    --color-muted: #64748b;
    --font-heading: {heading};
    --font-body: {body};
    --radius-sm: 10px;
    --radius-md: 14px;
    --radius-lg: 22px;
    --shadow-sm: 0 1px 2px rgba(15,23,42,.04);
    --shadow-md: 0 8px 24px rgba(15,23,42,.06);
    --shadow-lg: 0 24px 48px rgba(15,23,42,.1);
}}"""


def generate_hero(lead: Lead, conteudo: Dict, direction: str) -> str:
    brand = brand_name(lead.nome)
    headline = conteudo.get("hero_headline") or default_hero_headline(lead.nicho)
    subheadline = (
        conteudo.get("hero_subheadline")
        or f"{brand} · atendimento em {lead.cidade}."
    )
    wa = lead.whatsapp or (conteudo.get("contato") or {}).get("whatsapp") or ""
    whatsapp_link = f"https://wa.me/{wa}" if wa else "#contato"
    prova = ""
    if lead.nota and lead.avaliacoes:
        prova = f'<p class="hero-proof">Google · {lead.nota} ★ · {lead.avaliacoes} avaliações</p>'

    hero_image = str(conteudo.get("hero_image") or "").replace("'", "%27")
    hero_media = f'<div class="hero-media" style="background-image:url(\'{hero_image}\')"></div>' if hero_image else ""

    return f'''
<section class="hero hero--{direction}" id="main" data-parallax>
    <div class="hero-overlay"></div>
    {hero_media}
    <div class="container hero-inner">
        <p class="hero-eyebrow">{brand} · {lead.cidade}</p>
        <h1>{headline}</h1>
        <p class="hero-sub">{subheadline}</p>
        {prova}
        <div class="cta-group">
            <a href="{whatsapp_link}" class="btn btn-primary" target="_blank" rel="noopener">Falar no WhatsApp</a>
        </div>
    </div>
</section>'''


def brand_name(name: str) -> str:
    """Keep the visual mark short even when Maps returns SEO-stuffed names."""
    clean = re.split(r"[|/—-]", name or "")[0].strip()
    doctor = re.search(r"\b(?:dr\.?|dra\.?)\s+[A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+){0,1}", clean, re.I)
    if doctor:
        return doctor.group(0).title().replace("Dr.", "Dr.").replace("Dra.", "Dra.")
    clean = re.split(
        r"\b(?:sociedade individual|sociedade de advocacia|advogados associados|advocacia|cl[ií]nica|especialista|personal trainer)\b",
        clean,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" ,-–—")
    words = clean.split()
    return " ".join(words[:4]) or "Sua marca"


def default_hero_headline(nicho: str) -> str:
    niche = (nicho or "").lower()
    if any(term in niche for term in ("odont", "dent")):
        return "Seu sorriso em boas mãos."
    if any(term in niche for term in ("estet", "beleza")):
        return "Beleza com intenção."
    if any(term in niche for term in ("nutri", "saúde", "saude")):
        return "Cuidado que acompanha sua rotina."
    return "Uma experiência feita para você."


def generate_nav(lead: Lead, conteudo: Dict) -> str:
    logo = conteudo.get("logo_url") or ""
    brand = f'<img src="{logo}" alt="{lead.nome}" class="brand-logo">' if logo else f'<span class="brand-wordmark">{brand_name(lead.nome)}</span>'
    wa = lead.whatsapp or (conteudo.get("contato") or {}).get("whatsapp") or ""
    cta = f'<a class="nav-cta" href="https://wa.me/{wa}" target="_blank" rel="noopener">Agendar agora</a>' if wa else '<a class="nav-cta" href="#contato">Agendar agora</a>'
    return f'''<header class="site-nav">
  <div class="container nav-inner">
    <a href="#main" class="brand-link">{brand}</a>
    <nav class="nav-links" aria-label="Navegação principal"><a href="#sobre">Sobre</a><a href="#servicos">Especialidades</a><a href="#depoimentos">Avaliações</a></nav>
    {cta}
  </div>
</header>'''


def generate_sobre(lead: Lead, conteudo: Dict) -> str:
    sobre = conteudo.get("sobre") or (
        f"{lead.nome} é referência em {lead.nicho} em {lead.cidade}. "
        "Atendimento personalizado e foco em resultado."
    )
    credenciais = conteudo.get("credenciais") or []
    cred_html = ""
    if credenciais:
        cred_html = "<ul class='credenciais'>" + "".join(f"<li>{c}</li>" for c in credenciais) + "</ul>"
    img = conteudo.get("sobre_imagem") or ""
    img_block = (
        f'<div class="sobre-imagem"><img src="{img}" alt="{lead.nome}" loading="lazy"></div>'
        if img
        else '<div class="sobre-imagem" aria-hidden="true"></div>'
    )

    return f'''
<section class="sobre" id="sobre">
    <div class="container">
        <div class="sobre-grid">
            <div class="sobre-texto">
                <p class="section-eyebrow">Sobre</p>
                <h2>{lead.nome}</h2>
                <p>{sobre}</p>
                {cred_html}
            </div>
            {img_block}
        </div>
    </div>
</section>'''


def generate_servicos(lead: Lead, conteudo: Dict) -> str:
    servicos = conteudo.get("servicos") or []
    if not servicos:
        servicos = niche_services(lead.nicho)

    cards = ""
    for i, s in enumerate(servicos[:6], 1):
        cards += f"""
        <article class="servico-card">
            <span class="servico-num">{i:02d}</span>
            <h3>{s['titulo']}</h3>
            <p>{s.get('descricao', '')}</p>
            <a href="#contato" class="servico-cta">Quero saber mais</a>
        </article>"""

    return f'''
<section class="servicos" id="servicos">
    <div class="container">
        <p class="section-eyebrow">Especialidades</p>
        <h2>Como podemos cuidar de você</h2>
        <div class="servicos-grid">
            {cards}
        </div>
    </div>
</section>'''


def generate_depoimentos(lead: Lead, conteudo: Dict) -> str:
    depoimentos = conteudo.get("depoimentos") or []
    if depoimentos:
        cards = ""
        for d in depoimentos:
            cards += f"""
        <article class="depoimento-card">
            <div class="depoimento-stars">{"★" * int(d.get("avaliacao", 5))}</div>
            <p class="depoimento-texto">"{d.get("texto", "")}"</p>
            <div class="depoimento-autor"><strong>{d.get("nome", "")}</strong></div>
        </article>"""
        return f'''
<section class="depoimentos" id="depoimentos">
    <div class="container">
        <p class="section-eyebrow">Prova social</p>
        <h2>O que dizem os pacientes</h2>
        <div class="depoimentos-carousel">{cards}</div>
    </div>
</section>'''

    if lead.nota and lead.avaliacoes:
        return f'''
<section class="depoimentos" id="depoimentos">
    <div class="container">
        <p class="section-eyebrow">Google</p>
        <h2>Reputação comprovada</h2>
        <article class="depoimento-card" style="max-width:520px">
            <div class="depoimento-stars">{"★" * min(5, int(float(lead.nota or 5)))}</div>
            <p class="depoimento-texto">Nota {lead.nota} com base em {lead.avaliacoes} avaliações no Google Maps.</p>
            <a href="{lead.site_atual or "#"}" target="_blank" rel="noopener" class="servico-cta">Ver perfil</a>
        </article>
    </div>
</section>'''
    return ""


def generate_faq(lead: Lead, conteudo: Dict) -> str:
    faqs = conteudo.get('faq', [])
    if not faqs:
        faqs_padrao = {
            'nutricionistas': [
                ('Preciso fazer dieta restritiva?', 'Não! Trabalhamos com reeducação alimentar flexível, adaptada à sua rotina e preferências.'),
                ('Atende convênio?', 'Atendemos particular e alguns convênios. Entre em contato para verificar o seu.'),
                ('Como é a primeira consulta?', 'Avaliação completa: histórico, exames, rotina, preferências. Montamos o plano juntos.'),
            ],
            'psicologos': [
                ('Como funciona a terapia?', 'Encontros semanais de 50min, espaço seguro e sigiloso para você se expressar.'),
                ('Quantas sessões vou precisar?', 'Varia conforme sua demanda. Avaliamos juntos a cada sessão.'),
                ('O sigilo é garantido?', 'Sim, sigilo profissional absoluto conforme código de ética.'),
            ],
        }
        faqs = faqs_padrao.get(lead.nicho.lower(), [
            ('Dúvida 1', 'Resposta 1'),
            ('Dúvida 2', 'Resposta 2'),
        ])
    
    items = ""
    for i, (pergunta, resposta) in enumerate(faqs):
        items += f"""
        <details class="faq-item">
            <summary>{pergunta}</summary>
            <p>{resposta}</p>
        </details>"""
    
    return f'''
<section class="faq" id="faq">
    <div class="container">
        <h2>Perguntas Frequentes</h2>
        <div class="faq-list">{items}</div>
    </div>
</section>'''


def generate_contato(lead: Lead, conteudo: Dict) -> str:
    endereco = lead.endereco or conteudo.get("endereco") or ""
    horario = conteudo.get("horario") or "Seg a Sex · 8h–18h"
    tel = lead.telefone or (conteudo.get("contato") or {}).get("telefone") or ""
    wa = lead.whatsapp or ""
    email = lead.email or ""

    return f'''
<section class="contato" id="contato">
    <div class="container">
        <p class="section-eyebrow">Contato</p>
        <h2>Vamos conversar</h2>
        <div class="contato-grid">
            <div class="contato-info">
                <h3>{lead.nome}</h3>
                {f"<p><strong>Endereço:</strong> {endereco}</p>" if endereco else ""}
                {f"<p><strong>Telefone:</strong> <a href='tel:{tel}'>{tel}</a></p>" if tel else ""}
                {f"<p><strong>WhatsApp:</strong> <a href='https://wa.me/{wa}' target='_blank' rel='noopener'>{wa}</a></p>" if wa else ""}
                {f"<p><strong>E-mail:</strong> <a href='mailto:{email}'>{email}</a></p>" if email else ""}
                <p><strong>Horário:</strong> {horario}</p>
            </div>
            <form class="contato-form" action="#" method="POST">
                <input type="hidden" name="_next" value="{_public_url(lead.slug)}obrigado.html">
                <div class="form-row">
                    <input type="text" name="nome" placeholder="Seu nome" required>
                    <input type="tel" name="telefone" placeholder="WhatsApp" required>
                </div>
                <input type="email" name="email" placeholder="E-mail" required>
                <textarea name="mensagem" placeholder="Como podemos ajudar?" rows="4" required></textarea>
                <button type="submit" class="btn btn-primary">Enviar mensagem</button>
            </form>
        </div>
    </div>
</section>'''


def generate_footer(lead: Lead) -> str:
    return f'''
<footer class="footer">
    <div class="container">
        <div class="footer-grid">
            <div class="footer-brand">
                <h3>{lead.nome}</h3>
                <p>Excellence em {lead.nicho} na região de {lead.cidade}.</p>
            </div>
            <nav class="footer-links">
                <h4>Links Rápidos</h4>
                <ul>
                    <li><a href="#sobre">Sobre</a></li>
                    <li><a href="#servicos">Serviços</a></li>
                    <li><a href="#depoimentos">Depoimentos</a></li>
                    <li><a href="#contato">Contato</a></li>
                </ul>
            </nav>
            <div class="footer-social">
                <h4>Conecte-se</h4>
                <a href="https://wa.me/{lead.whatsapp}" target="_blank" class="social-link">WhatsApp</a>
                <a href="mailto:{lead.email}" class="social-link">E-mail</a>
            </div>
        </div>
        <div class="footer-bottom">
            <p>&copy; {datetime.now().year} {lead.nome}. Todos os direitos reservados.</p>
        </div>
    </div>
</footer>'''


def generate_catalog_page(lead: Lead, conteudo: Dict) -> str:
    """Render a style-led proposal from a persisted creative brief.

    The markup changes by composition family; style tokens then enforce the
    selected catalog direction. This deliberately avoids a single template with
    a different accent color.
    """
    brief = conteudo["creative_brief"]
    style = brief["style_id"]
    layout = brief["layout_id"]
    variation = brief.get("variation") or {}
    brand = brand_name(lead.nome)
    hero = str(conteudo.get("hero_image") or "").replace("'", "%27")
    support = str(conteudo.get("support_image") or conteudo.get("sobre_imagem") or hero).replace("'", "%27")
    detail = str(conteudo.get("detail_image") or support).replace("'", "%27")
    headline = conteudo.get("hero_headline") or default_hero_headline(lead.nicho)
    subtitle = conteudo.get("hero_subheadline") or (conteudo.get("sobre") or f"{brand} em {lead.cidade}.")[:180]
    about = conteudo.get("sobre") or f"Atendimento em {lead.nicho} com uma experiência desenhada para você."
    wa = lead.whatsapp or (conteudo.get("contato") or {}).get("whatsapp") or ""
    contact = f"https://wa.me/{wa}" if wa else "#contato"
    services = conteudo.get("servicos") or niche_services(lead.nicho)
    cards = "".join(
        f'<article class="service-card"><span class="service-index">{i + 1:02d}</span><h3>{item.get("titulo", "Especialidade")}</h3><p>{item.get("descricao") or "Atendimento personalizado para suas necessidades."}</p></article>'
        for i, item in enumerate(services[:6])
    )
    family = (
        "kinetic" if style in {"kinetic", "bold-typography", "neo-brutalism"}
        else "geometric" if style in {"bauhaus", "flat-design", "playful-geometric", "retro", "maximalism"}
        else "technical" if style in {"saas", "enterprise", "terminal", "cyberpunk", "web3", "modern-dark", "industrial"}
        else "soft" if style in {"material-design", "claymorphism", "neumorphism", "botanical", "organic", "aurora-mesh", "glassmorphism"}
        else "editorial"
    )
    font_by_family = {
        "kinetic": "Space Grotesk,Arial,sans-serif", "geometric": "Outfit,Arial,sans-serif",
        "technical": "Inter,Arial,sans-serif", "soft": "Roboto,Arial,sans-serif",
        "editorial": "Playfair Display,Georgia,serif",
    }
    palette = resolve_brand_palette(conteudo, family, style, variation)
    bg, ink, accent, secondary, surface = (
        palette["bg"], palette["ink"], palette["accent"], palette["secondary"], palette["surface"]
    )
    heading_font = font_by_family[family]
    layouts = COMPOSITIONS.get(style, [layout])
    layout_index = layouts.index(layout) if layout in layouts else 0
    composition = ("split", "immersive", "statement")[layout_index % 3]
    hero_treatment = str(variation.get("hero_treatment") or "").lower()
    if "full" in hero_treatment or "cinematic" in hero_treatment:
        composition = "immersive"
    elif "statement" in hero_treatment or "text" in hero_treatment:
        composition = "statement"
    logo = conteudo.get("logo_url") or ""
    brand_markup = f'<img class="brand-logo" src="{logo}" alt="{brand}">' if logo else brand
    eyebrow = f"{lead.nicho} · {lead.cidade}"
    cta_label = "Falar no WhatsApp ↗"
    ornament = (
        f'<div class="giant" aria-hidden="true">{brand[:1].upper()}</div>' if family == "kinetic"
        else '<div class="shape circle" aria-hidden="true"></div><div class="shape square" aria-hidden="true"></div>' if family == "geometric"
        else '<div class="grid-overlay" aria-hidden="true"></div>' if family == "technical"
        else '<div class="blob one" aria-hidden="true"></div><div class="blob two" aria-hidden="true"></div>' if family == "soft"
        else ""
    )
    if composition == "immersive":
        hero_markup = f'''<section class="hero hero-immersive" style="--hero:url('{hero}')">{ornament}<div class="hero-shade"></div><div class="container hero-copy"><p class="label">{eyebrow}</p><h1>{headline}</h1><p>{subtitle}</p><a class="button" href="{contact}">{cta_label}</a></div></section>'''
    elif composition == "statement":
        hero_markup = f'''<section class="hero hero-statement">{ornament}<div class="container statement-grid"><div class="hero-copy"><p class="label">{eyebrow}</p><h1>{headline}</h1><a class="button" href="{contact}">{cta_label}</a></div><div><p class="statement-intro">{subtitle}</p><img class="statement-image" src="{hero}" alt="{brand}"></div></div></section>'''
    else:
        hero_markup = f'''<section class="hero hero-split">{ornament}<div class="container hero-grid"><div class="hero-copy"><p class="label">{eyebrow}</p><h1>{headline}</h1><p>{subtitle}</p><a class="button" href="{contact}">{cta_label}</a></div><figure class="hero-figure"><img src="{hero}" alt="{brand}"><figcaption>{lead.cidade}</figcaption></figure></div></section>'''
    hero_fx = '''<svg class="hero-fx" viewBox="0 0 800 800" aria-hidden="true"><circle cx="400" cy="400" r="300" fill="none" stroke="currentColor" stroke-width="1" stroke-dasharray="8 18"/><circle cx="400" cy="400" r="210" fill="none" stroke="currentColor" stroke-width="1" opacity=".45"/><path d="M100 400h600M400 100v600" fill="none" stroke="currentColor" opacity=".2"/><circle cx="700" cy="400" r="7" fill="currentColor"/></svg>'''
    hero_markup = hero_markup.replace("</section>", hero_fx + "</section>", 1)
    about_section = f'''<section class="content about"><div class="container split"><div><p class="label">Nossa abordagem</p><h2>{brand}, com intenção em cada detalhe.</h2><p>{about}</p></div><img class="support" src="{support}" alt="Ambiente de {brand}"></div></section>'''
    services_section = f'''<section class="content expertise"><div class="container"><p class="label">Especialidades</p><h2>O que podemos fazer por você.</h2><div class="services">{cards}</div><img class="detail-media" src="{detail}" alt="Detalhe de {brand}"></div></section>'''
    emphasis = str(variation.get("section_emphasis") or "").lower()
    content_sections = services_section + about_section if any(word in emphasis for word in ("serv", "especial", "oferta")) else about_section + services_section
    rhythm = str(variation.get("section_rhythm") or "asymmetric").lower()
    density = str(variation.get("density") or "balanced").lower()
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{brand} — {lead.cidade}</title><link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700&family=Outfit:wght@400;600;700;900&family=Playfair+Display:ital,wght@0,500;0,700;1,500&family=Roboto:wght@400;500;700&family=Space+Grotesk:wght@400;600;700&display=swap" rel="stylesheet"><style>
:root{{--bg:{bg};--ink:{ink};--accent:{accent};--secondary:{secondary};--surface:{surface};--heading:{heading_font}}}
.hero-fx{{position:absolute;width:min(70vw,760px);height:min(70vw,760px);right:-18%;top:5%;opacity:.18;pointer-events:none;animation:fxSpin 28s linear infinite}}@keyframes fxSpin{{to{{transform:rotate(360deg)}}}}@media(max-width:760px){{.editorial-grid figure{{display:block!important}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,Arial,sans-serif;line-height:1.6}}.container{{width:min(1160px,calc(100% - 40px));margin:auto}}.top{{position:absolute;inset:0 0 auto;padding:20px 0;z-index:2;color:#fff}}.top .container{{display:flex;justify-content:space-between}}a{{color:inherit}}.brand{{font:700 1.1rem var(--heading);text-decoration:none}}.hero{{min-height:86svh;display:flex;align-items:center;position:relative;overflow:hidden}}.hero-grid,.editorial-grid,.split{{display:grid;grid-template-columns:1fr 1fr;gap:7vw;align-items:center}}h1,h2,h3{{font-family:var(--heading);line-height:.94;letter-spacing:-.05em}}h1{{font-size:clamp(3rem,7vw,7.6rem)}}h2{{font-size:clamp(2.5rem,5vw,5rem)}}.button{{display:inline-flex;padding:15px 22px;background:var(--ink);color:var(--bg);font-weight:700;text-decoration:none}}.proof{{padding:28px 0;background:var(--ink);color:var(--bg)}}.proof .container{{display:flex;gap:24px;flex-wrap:wrap}}.content{{padding:10vw 0}}.support,.detail-media,.hero-photo,.editorial-grid img{{width:100%;object-fit:cover}}.support,.hero-photo,.editorial-grid img{{aspect-ratio:4/5}}.detail-media{{height:min(40vw,460px);margin-top:20px}}.services{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#9994;margin-top:35px}}.service-card{{background:var(--bg);padding:28px}}.kinetic-hero,.technical-hero{{background:#09090b;color:#fafafa}}.giant{{position:absolute;right:2%;bottom:-16%;font-size:40vw;color:#27272a}}.marquee{{padding:16px;background:var(--accent);overflow:hidden;white-space:nowrap}}.geometric-hero{{background:#f0f0f0}}.shape{{position:absolute;border:4px solid #121212}}.circle{{width:34vw;height:34vw;border-radius:50%;background:var(--accent);right:-8vw;top:8vh}}.square{{width:17vw;height:17vw;background:#1040c0;left:45%;bottom:-7vw}}.hero-image{{min-height:65vh;background:center/cover;border:4px solid #121212}}.grid-overlay{{position:absolute;inset:0;background-image:linear-gradient(#5e6ad222 1px,transparent 1px),linear-gradient(90deg,#5e6ad222 1px,transparent 1px);background-size:48px 48px}}.status-panel{{position:relative;padding:30px;border:1px solid #fff4}}.soft-hero{{background:#fffafe}}.blob{{position:absolute;border-radius:50%;filter:blur(60px);opacity:.3}}.one{{width:40vw;height:40vw;background:var(--accent);top:-15vw;right:-8vw}}.two{{width:28vw;height:28vw;background:#db2777;bottom:-12vw;left:30%}}.contact{{padding:11vw 0;text-align:center}}@media(max-width:760px){{.hero{{padding:100px 0 60px}}.hero-grid,.editorial-grid,.split,.services{{grid-template-columns:1fr}}.editorial-grid figure,.status-panel{{display:none}}}}
.top{{color:var(--ink)}}.top .container{{align-items:center}}.brand-logo{{display:block;max-width:190px;max-height:58px;object-fit:contain}}.hero{{background:var(--bg)}}.hero-copy{{position:relative;z-index:1}}.hero-copy p{{max-width:580px}}.hero-split .hero-grid{{min-height:88svh;padding:110px 0 70px;grid-template-columns:minmax(0,.9fr) minmax(380px,1.1fr)}}.hero-figure{{margin:0;position:relative;height:min(76vh,780px)}}.hero-figure img{{width:100%;height:100%;object-fit:cover}}.hero-figure figcaption{{position:absolute;right:14px;bottom:12px;padding:6px 9px;background:var(--surface);color:var(--ink);font-size:.7rem}}.hero-immersive{{min-height:100svh;align-items:flex-end;background-image:var(--hero);background-size:cover;background-position:center;color:#fff}}.hero-immersive .hero-copy{{padding:30vh 0 10vh;max-width:850px}}.hero-immersive h1{{color:#fff}}.hero-shade{{position:absolute;inset:0;background:linear-gradient(90deg,color-mix(in srgb,var(--ink) 88%,transparent),color-mix(in srgb,var(--secondary) 42%,transparent),transparent)}}.mode-immersive .top{{color:#fff}}.mode-immersive .brand-logo{{filter:brightness(0) invert(1)}}.hero-statement{{padding:150px 0 80px;min-height:92svh}}.statement-grid{{display:grid;grid-template-columns:1.35fr .65fr;gap:6vw;align-items:end}}.statement-grid h1{{font-size:clamp(4rem,9vw,10rem);margin:.15em 0 .35em}}.statement-intro{{font-size:1.1rem;margin-bottom:25px}}.statement-image{{width:100%;height:min(48vh,520px);object-fit:cover}}.content{{background:var(--bg)}}.expertise{{background:var(--surface)}}.service-card{{background:var(--surface)}}.expertise .service-card{{background:var(--bg)}}.detail-media{{width:100%;object-fit:cover}}.rhythm-alternating .about .split>img{{order:-1}}.density-compact .content{{padding:6vw 0}}.density-spacious .content{{padding:14vw 0}}footer{{padding:32px 0;background:var(--ink);color:var(--bg)}}@media(max-width:760px){{.top{{padding:14px 0}}.brand-logo{{max-width:135px;max-height:44px}}.hero-split .hero-grid,.statement-grid{{grid-template-columns:1fr}}.hero-split .hero-grid{{padding-top:130px}}.hero-figure{{height:64svh}}.hero-statement{{padding-top:130px}}.statement-grid h1{{font-size:clamp(3.4rem,16vw,6rem)}}.statement-image{{height:55svh}}.hero-immersive .hero-copy{{padding-top:42vh}}}}
.shape{{border-color:var(--ink)}}.square{{background:var(--secondary)}}.two{{background:var(--secondary)}}.giant{{color:color-mix(in srgb,var(--accent) 18%,transparent)}}.grid-overlay{{background-image:linear-gradient(color-mix(in srgb,var(--accent) 18%,transparent) 1px,transparent 1px),linear-gradient(90deg,color-mix(in srgb,var(--accent) 18%,transparent) 1px,transparent 1px)}}
</style></head><body class="mode-{composition} density-{density} rhythm-{rhythm}"><header class="top"><div class="container"><a class="brand" href="#main">{brand_markup}</a><a href="{contact}">WhatsApp ↗</a></div></header><main id="main">{hero_markup}<section class="proof"><div class="container"><span><b>{lead.nota or '5.0'} ★</b> reputação Google</span><span>{lead.avaliacoes or 'Atendimento'} avaliações</span><span>{lead.cidade}</span></div></section>{content_sections}<section class="contact" id="contato"><div class="container"><p class="label">Próximo passo</p><h2>Vamos conversar sobre o que você precisa.</h2><a class="button" href="{contact}">Falar no WhatsApp ↗</a></div></section></main><footer><div class="container">{brand} · {lead.cidade} · Todos os direitos reservados</div></footer></body></html>'''


def generate_source_led_page(lead: Lead, content: Dict) -> str:
    """Modernize a mature source site without discarding its information architecture."""
    brand = brand_name(lead.nome)
    colors = content.get("cores") or niche_palette(lead.nicho)
    primary = colors.get("primary") or "#b3262d"
    secondary = colors.get("secondary") or _mix_hex(primary, "#111827", 0.72)
    accent = colors.get("accent") or _mix_hex(primary, "#ffffff", 0.3)
    background = _mix_hex(primary, "#ffffff", 0.96)
    logo = content.get("logo_url") or ""
    logo_markup = f'<img src="{escape(logo)}" alt="{escape(brand)}">' if logo else escape(brand)
    source_images = content.get("source_images") or content.get("imagens") or []
    hero_image = source_images[0] if source_images else content.get("hero_image") or ""
    about_image = hero_image
    headline = content.get("hero_headline") or "Advocacia trabalhista"
    if " - " in headline or " | " in headline:
        headline = "Advocacia trabalhista"
    subtitle = content.get("hero_tagline") or content.get("hero_subheadline") or content.get("sobre") or ""
    about = content.get("sobre_detalhado") or content.get("sobre") or ""
    services = content.get("servicos") or []
    articles = content.get("artigos") or []
    faqs = content.get("faq") or []
    differentials = content.get("diferenciais") or []
    contact_data = content.get("contato") or {}
    phone = lead.whatsapp or lead.telefone or contact_data.get("whatsapp") or contact_data.get("telefone") or ""
    digits = "".join(character for character in phone if character.isdigit())
    if digits and not digits.startswith("55"):
        digits = "55" + digits
    contact_url = f"https://wa.me/{digits}" if digits else "#contato"

    service_parts = []
    for index, item in enumerate(services[:6], 1):
        description = item.get("descricao") or item.get("descrição") or ""
        description_html = f"<p>{escape(description)}</p>" if description else ""
        service_parts.append(
            f'<article><span>{index:02d}</span><h3>{escape(item.get("titulo") or "Área de atuação")}</h3>'
            f'{description_html}</article>'
        )
    service_cards = "".join(service_parts)
    article_parts = []
    for item in articles[:4]:
        title = item.get("titulo") or "Artigo"
        image_html = f'<img src="{escape(item["imagem"])}" alt="{escape(title)}">' if item.get("imagem") else ""
        article_parts.append(
            f'<a class="article" href="{escape(item.get("url") or "#")}" target="_blank" rel="noopener">'
            f'{image_html}<div><span>Conteúdo jurídico</span><h3>{escape(title)}</h3></div></a>'
        )
    article_cards = "".join(article_parts)
    faq_items = "".join(
        f'<details><summary>{escape(str(question))}</summary><p>{escape(str(answer))}</p></details>'
        for question, answer in faqs[:5]
    )
    differential_items = "".join(f"<li>{escape(item)}</li>" for item in differentials[:5])
    nav = "".join(
        f'<a href="#{target}">{label}</a>' for target, label in (
            ("atuacao", "Atuação"), ("sobre", "Sobre"), ("conteudo", "Conteúdo"), ("contato", "Contato")
        )
    )
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(brand)} — {escape(lead.cidade)}</title><meta name="description" content="{escape(subtitle[:160])}"><link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Libre+Caslon+Display&display=swap" rel="stylesheet"><style>
:root{{--primary:{primary};--secondary:{secondary};--accent:{accent};--bg:{background};--surface:#fff;--ink:#17191f;--muted:#626873}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 'DM Sans',sans-serif}}img{{display:block;max-width:100%}}a{{color:inherit;text-decoration:none}}.wrap{{width:min(1180px,calc(100% - 40px));margin:auto}}header{{position:absolute;z-index:5;inset:0 0 auto;padding:24px 0;color:#fff}}header .wrap{{display:flex;align-items:center;justify-content:space-between;gap:25px}}.logo img{{width:auto;max-width:180px;max-height:64px;filter:brightness(0) invert(1)}}nav{{display:flex;gap:25px;font-size:.85rem}}.header-cta,.cta{{display:inline-flex;padding:13px 19px;border-radius:999px;background:var(--primary);color:#fff;font-weight:700}}.hero{{position:relative;min-height:96svh;display:flex;align-items:flex-end;color:#fff;overflow:hidden;background:var(--secondary)}}.hero-bg{{position:absolute;inset:0;background:url('{escape(str(hero_image))}') center/cover}}.hero:after{{content:'';position:absolute;inset:0;background:linear-gradient(90deg,color-mix(in srgb,var(--secondary) 94%,transparent) 0%,color-mix(in srgb,var(--secondary) 72%,transparent) 48%,color-mix(in srgb,var(--secondary) 18%,transparent) 100%)}}.hero-copy{{position:relative;z-index:1;max-width:760px;padding:190px 0 11vh}}.eyebrow{{font-size:.72rem;text-transform:uppercase;letter-spacing:.18em;color:var(--accent);font-weight:700}}h1,h2,h3{{font-family:'Libre Caslon Display',Georgia,serif;font-weight:400;line-height:1.02}}h1{{font-size:clamp(4rem,8.5vw,9rem);margin:.18em 0 .22em;letter-spacing:-.045em}}h2{{font-size:clamp(2.7rem,5vw,5.2rem);margin:.15em 0 .35em;letter-spacing:-.035em}}.hero p{{font-size:1.05rem;max-width:620px;margin:0 0 28px}}.proof{{background:var(--primary);color:#fff;padding:22px 0}}.proof .wrap{{display:flex;justify-content:space-between;gap:25px;flex-wrap:wrap}}section{{padding:110px 0}}.section-head{{max-width:760px;margin-bottom:45px}}.services{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#ddd}}.services article{{min-height:250px;padding:34px;background:var(--surface)}}.services article span{{color:var(--primary);font-weight:700;font-size:.75rem}}.services h3{{font-size:2rem;margin:45px 0 10px}}.about{{background:var(--secondary);color:#fff}}.about-grid{{display:grid;grid-template-columns:1fr 1fr;gap:7vw;align-items:center}}.about h2{{color:#fff}}.about img{{width:100%;height:650px;object-fit:cover}}.about p{{color:#e5e7eb}}.values{{margin-top:28px;padding:0;list-style:none;display:grid;gap:10px}}.values li{{padding-left:22px;position:relative}}.values li:before{{content:'•';position:absolute;left:0;color:var(--accent)}}.insights{{background:#fff}}.articles{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}}.article{{display:grid;grid-template-columns:180px 1fr;min-height:180px;border:1px solid #e5e7eb;background:var(--surface)}}.article img{{width:180px;height:100%;object-fit:cover}}.article div{{padding:25px}}.article span{{color:var(--primary);font-size:.7rem;text-transform:uppercase;letter-spacing:.12em}}.article h3{{font-size:1.55rem;margin:12px 0}}.faq-grid{{display:grid;grid-template-columns:.65fr 1.35fr;gap:7vw}}details{{border-top:1px solid #d8dce2;padding:20px 0}}summary{{cursor:pointer;font-weight:700}}details p{{color:var(--muted)}}.contact{{text-align:center;background:color-mix(in srgb,var(--primary) 8%,white)}}.contact p{{color:var(--muted)}}.contact-links{{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-top:28px}}.contact-links a:not(.cta){{padding:13px 19px;border:1px solid #ccd1d8;border-radius:999px}}footer{{background:#11151b;color:#b8bec8;padding:42px 0}}footer .wrap{{display:flex;justify-content:space-between;gap:25px;flex-wrap:wrap}}@media(max-width:800px){{nav{{display:none}}header .header-cta{{display:none}}.hero-copy{{padding-top:170px}}h1{{font-size:clamp(3.6rem,17vw,6rem)}}.services,.about-grid,.articles,.faq-grid{{grid-template-columns:1fr}}.about img{{height:75vw;max-height:560px}}.article{{grid-template-columns:120px 1fr}}.article img{{width:120px}}section{{padding:80px 0}}}}
</style></head><body><header><div class="wrap"><a class="logo" href="#inicio">{logo_markup}</a><nav>{nav}</nav><a class="header-cta" href="{contact_url}">Agendar reunião</a></div></header><main><section class="hero" id="inicio"><div class="hero-bg"></div><div class="wrap hero-copy"><span class="eyebrow">{escape(lead.nicho)} · {escape(lead.cidade)}</span><h1>{escape(headline)}</h1><p>{escape(subtitle[:320])}</p><a class="cta" href="{contact_url}">Conversar sobre o seu caso</a></div></section><div class="proof"><div class="wrap"><span><b>{lead.nota} ★</b> no Google</span><span>{lead.avaliacoes} avaliações</span><span>Atendimento em {escape(lead.cidade)}</span></div></div><section id="atuacao"><div class="wrap"><div class="section-head"><span class="eyebrow">Áreas de atuação</span><h2>Experiência jurídica para decisões importantes.</h2></div><div class="services">{service_cards}</div></div></section><section class="about" id="sobre"><div class="wrap about-grid"><div><span class="eyebrow">Sobre o escritório</span><h2>Atendimento próximo, análise cuidadosa.</h2><p>{escape(about)}</p>{f'<ul class="values">{differential_items}</ul>' if differential_items else ''}</div>{f'<img src="{escape(str(about_image))}" alt="{escape(brand)}">' if about_image else ''}</div></section>{f'<section class="insights" id="conteudo"><div class="wrap"><div class="section-head"><span class="eyebrow">Informação jurídica</span><h2>Conteúdo para orientar escolhas.</h2></div><div class="articles">{article_cards}</div></div></section>' if article_cards else ''}{f'<section id="faq"><div class="wrap faq-grid"><div><span class="eyebrow">Perguntas frequentes</span><h2>Informação clara antes da conversa.</h2></div><div>{faq_items}</div></div></section>' if faq_items else ''}<section class="contact" id="contato"><div class="wrap"><span class="eyebrow">Contato</span><h2>Agende uma reunião.</h2><p>{escape(content.get("endereco") or lead.cidade)}</p><div class="contact-links"><a class="cta" href="{contact_url}">WhatsApp</a>{f'<a href="mailto:{escape(contact_data.get("email"))}">{escape(contact_data.get("email"))}</a>' if contact_data.get("email") else ''}</div></div></section></main><footer><div class="wrap"><strong>{escape(brand)}</strong><span>{escape(lead.cidade)} · Todos os direitos reservados</span></div></footer></body></html>'''


def generate_page_html(lead: Lead, conteudo: Dict) -> str:
    if conteudo.get("source_strategy") == "source-led":
        return add_whatsapp_widget(generate_source_led_page(lead, conteudo), lead, conteudo)
    if (conteudo.get("creative_brief") or {}).get("style_id"):
        return add_whatsapp_widget(generate_catalog_page(lead, conteudo), lead, conteudo)
    variant = conteudo.get("layout_variant") or "classic"
    if variant in ("orbit", "poster"):
        return add_whatsapp_widget(generate_immersive_page(lead, conteudo, variant), lead, conteudo)
    cores = {**niche_palette(lead.nicho), **(conteudo.get("cores") or {})}
    conteudo = {**conteudo, "cores": cores}
    if not conteudo.get("sobre"):
        conteudo["sobre"] = (
            f"{lead.nome} atua em {lead.nicho} em {lead.cidade}. "
            f"Atendimento com foco em resultado e experiência do paciente."
        )
    direction = conteudo.get("visual_direction") or visual_direction(lead)
    css_vars = generate_css_variables(cores, direction)
    primary = cores.get("primary", "#0d9488")
    nicho = lead.nicho or "Serviços"
    cidade = lead.cidade or ""
    meta_desc = (
        conteudo.get("sobre")
        or f"{lead.nome} — {nicho} em {cidade}. Agende sua consulta."
    ).replace('"', "'")[:160]

    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{lead.nome} — {nicho} {("em " + cidade) if cidade else ""}</title>
<meta name="description" content="{meta_desc}">
<meta name="theme-color" content="{primary}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display:ital@0;1&family=Manrope:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{css_vars}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--font-body);background:var(--color-bg);color:var(--color-text);line-height:1.65;-webkit-font-smoothing:antialiased}}
.container{{max-width:1120px;margin:0 auto;padding:0 24px}}
a{{color:var(--color-primary);text-decoration:none}}
img{{max-width:100%;height:auto;display:block}}
.btn{{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:14px 26px;border-radius:999px;font-weight:600;font-size:.95rem;transition:transform .15s,box-shadow .15s,background .15s;border:none;cursor:pointer;text-decoration:none!important}}
.btn-primary{{background:var(--color-primary);color:#fff;box-shadow:0 12px 28px color-mix(in srgb,var(--color-primary) 32%,transparent)}}
.btn-primary:hover{{transform:translateY(-1px);filter:brightness(1.05)}}
.btn-secondary{{background:rgba(255,255,255,.12);color:#fff;border:1px solid rgba(255,255,255,.35);backdrop-filter:blur(8px)}}
.btn-secondary:hover{{background:rgba(255,255,255,.2)}}
h1,h2,h3{{font-family:var(--font-heading);letter-spacing:-.02em;font-weight:700;color:var(--color-secondary)}}
h2{{font-size:clamp(1.7rem,3.5vw,2.4rem);margin-bottom:12px}}
h3{{font-size:1.15rem}}
.section-eyebrow{{font-size:.75rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--color-primary);margin-bottom:10px}}
.site-nav{{position:absolute;z-index:5;top:0;left:0;right:0;padding:22px 0;color:#fff}}
.nav-inner{{display:flex;align-items:center;justify-content:space-between;gap:22px}}
.brand-link{{display:flex;align-items:center;color:#fff;font-weight:700;max-width:280px}}
.brand-logo{{max-width:190px;max-height:48px;object-fit:contain;filter:brightness(0) invert(1)}}
.brand-wordmark{{font-family:var(--font-heading);font-size:1.15rem;line-height:1.1}}
.nav-links{{display:flex;gap:22px}}.nav-links a{{color:rgba(255,255,255,.8);font-size:.88rem}}
.nav-cta{{padding:10px 16px;border:1px solid rgba(255,255,255,.45);border-radius:999px;color:#fff;font-size:.85rem;font-weight:700;background:rgba(255,255,255,.1);backdrop-filter:blur(10px)}}

/* Hero */
.hero{{position:relative;isolation:isolate;overflow:hidden;min-height:88vh;display:flex;align-items:flex-end;padding:72px 0 80px;color:#fff;background:
  radial-gradient(900px 500px at 10% 0%, rgba(20,184,166,.35), transparent 55%),
  linear-gradient(145deg, var(--color-secondary) 0%, var(--color-primary) 100%)}}
.hero-media{{position:absolute;z-index:-2;inset:-8%;background-position:center;background-size:cover;filter:saturate(.82) contrast(1.08);transform:scale(1.06);will-change:transform}}
.hero-overlay{{position:absolute;z-index:-1;inset:0;background:linear-gradient(90deg,rgba(3,12,20,.82) 0%,rgba(3,12,20,.5) 52%,rgba(3,12,20,.18) 100%);pointer-events:none}}
.hero-inner{{position:relative;z-index:1;max-width:720px}}
.hero-eyebrow{{font-size:.8rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;opacity:.75;margin-bottom:14px;font-family:var(--font-body)}}
.hero h1{{color:#fff;font-size:clamp(2.2rem,5vw,3.6rem);line-height:1.08;margin-bottom:18px}}
.hero-sub{{font-size:1.05rem;opacity:.9;margin-bottom:16px;max-width:540px;font-family:var(--font-body);font-weight:400}}
.hero-proof{{display:inline-block;padding:8px 14px;border-radius:999px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);font-size:.85rem;margin-bottom:28px}}
.cta-group{{display:flex;gap:12px;flex-wrap:wrap}}
.hero--editorial{{min-height:82vh;align-items:center;text-align:left}}
.hero--editorial .hero-inner{{max-width:650px;padding:34px;border-left:1px solid rgba(255,255,255,.45)}}
.hero--cinematic{{min-height:100vh;padding-bottom:12vh}}
.hero--cinematic h1{{font-size:clamp(3rem,7vw,6.8rem);max-width:880px}}
.hero--cinematic~.servicos{{background:var(--color-secondary);color:#fff;overflow:hidden}}
.hero--cinematic~.servicos h2{{color:#fff;max-width:580px}}
.hero--cinematic~.servicos .servicos-grid{{display:flex;overflow-x:auto;gap:22px;padding:8px 24px 24px 0;scroll-snap-type:x mandatory;scrollbar-width:thin}}
.hero--cinematic~.servicos .servico-card{{flex:0 0 min(78vw,360px);scroll-snap-align:start;background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.16);color:#fff;backdrop-filter:blur(14px)}}
.hero--cinematic~.servicos .servico-card h3{{color:#fff}}
.hero--cinematic~.servicos .servico-card p{{color:rgba(255,255,255,.72)}}
.hero--editorial~.sobre{{background:#f5f0e8}}
.hero--editorial~.servicos .servico-card{{border-radius:0;border-width:0 0 1px;padding:28px 0;box-shadow:none;background:transparent}}
.hero--minimal~.servicos .servico-card:nth-child(odd){{transform:translateY(24px)}}
.hero--minimal{{min-height:76vh}}
.js .sobre,.js .servicos,.js .depoimentos,.js .faq,.js .contato{{opacity:0;transform:translateY(26px);transition:opacity .7s ease,transform .7s cubic-bezier(.2,.7,.2,1)}}
.js .is-visible{{opacity:1;transform:none}}

/* Sections */
.sobre,.servicos,.depoimentos,.faq,.contato{{padding:88px 0}}
.sobre-grid{{display:grid;grid-template-columns:1.2fr .8fr;gap:40px;align-items:center}}
.sobre-texto p{{color:var(--color-muted);font-size:1.05rem}}
.sobre-imagem{{border-radius:var(--radius-lg);overflow:hidden;box-shadow:var(--shadow-lg);min-height:280px;background:linear-gradient(135deg,var(--color-primary),var(--color-secondary))}}
.sobre-imagem img{{width:100%;height:100%;object-fit:cover;min-height:280px}}
.credenciais{{margin-top:20px;padding-left:18px;color:var(--color-muted)}}

.servicos-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin-top:36px}}
.servico-card{{background:var(--color-card);border:1px solid var(--color-border);border-radius:var(--radius-lg);padding:28px 24px;box-shadow:var(--shadow-sm);transition:transform .15s,box-shadow .15s}}
.servico-card:hover{{transform:translateY(-3px);box-shadow:var(--shadow-md)}}
.servico-num{{display:block;font-family:var(--font-heading);font-size:1.4rem;color:var(--color-primary);margin-bottom:12px;opacity:.7}}
.servico-card h3{{margin-bottom:10px}}
.servico-card p{{color:var(--color-muted);margin-bottom:18px;font-size:.95rem}}
.servico-cta{{font-weight:600;font-size:.88rem;color:var(--color-primary)}}

.depoimentos-carousel{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin-top:32px}}
.depoimento-card{{background:var(--color-card);border:1px solid var(--color-border);border-radius:var(--radius-lg);padding:28px}}
.depoimento-stars{{color:var(--color-primary);letter-spacing:2px;margin-bottom:12px;font-size:.9rem}}
.depoimento-texto{{font-family:var(--font-heading);font-style:italic;font-size:1.05rem;margin-bottom:16px}}

.faq-list{{max-width:720px;margin:32px auto 0}}
.faq-item{{background:var(--color-card);border:1px solid var(--color-border);border-radius:var(--radius-md);margin-bottom:10px;overflow:hidden}}
.faq-item summary{{padding:18px 22px;font-weight:600;cursor:pointer;list-style:none}}
.faq-item summary::-webkit-details-marker{{display:none}}
.faq-item p{{padding:0 22px 18px;color:var(--color-muted)}}

.contato-grid{{display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:start;margin-top:28px}}
.contato-info p{{margin-bottom:10px;color:var(--color-muted)}}
.contato-form{{background:var(--color-card);border:1px solid var(--color-border);border-radius:var(--radius-lg);padding:28px;box-shadow:var(--shadow-md)}}
.form-row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.contato-form input,.contato-form textarea{{width:100%;padding:13px 14px;border:1px solid var(--color-border);border-radius:12px;font:inherit;margin-bottom:12px;background:#fff}}
.contato-form input:focus,.contato-form textarea:focus{{outline:none;border-color:var(--color-primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--color-primary) 18%,transparent)}}
.contato-form button{{width:100%}}

.footer{{background:var(--color-secondary);color:#fff;padding:56px 0 24px}}
.footer-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:32px;margin-bottom:32px}}
.footer-brand h3,.footer-links h4{{color:#fff;margin-bottom:12px;font-family:var(--font-heading)}}
.footer-brand p,.footer-links a{{color:#94a3b8}}
.footer-links ul{{list-style:none}}
.footer-links li{{margin-bottom:8px}}
.footer-bottom{{border-top:1px solid rgba(255,255,255,.1);padding-top:20px;text-align:center;color:#64748b;font-size:.85rem}}

@media(max-width:860px){{
  .hero{{min-height:auto;padding:56px 0 64px;align-items:center}}
  .sobre-grid,.contato-grid{{grid-template-columns:1fr}}
  .form-row{{grid-template-columns:1fr}}
  .cta-group{{flex-direction:column;align-items:stretch}}
  .nav-links{{display:none}}.site-nav{{padding:16px 0}}.brand-logo{{max-width:145px}}.nav-cta{{padding:8px 12px}}
}}
.skip-link{{position:absolute;top:-40px;left:0;background:var(--color-primary);color:#fff;padding:8px 16px;z-index:100}}
.skip-link:focus{{top:0}}
</style>
</head>
<body>
<a href="#main" class="skip-link">Pular para o conteúdo</a>

{generate_nav(lead, conteudo)}
{generate_hero(lead, conteudo, direction)}
{generate_sobre(lead, conteudo)}
{generate_servicos(lead, conteudo)}
{generate_depoimentos(lead, conteudo)}
{generate_faq(lead, conteudo)}
{generate_contato(lead, conteudo)}
{generate_footer(lead)}

<script>
document.documentElement.classList.add('js');
document.querySelectorAll('a[href^="#"]').forEach(a=>{{
  a.addEventListener('click',e=>{{
    const id=a.getAttribute('href');
    if(id==='#')return;
    const el=document.querySelector(id);
    if(el){{e.preventDefault();el.scrollIntoView({{behavior:'smooth'}});}}
  }});
}});
const heroMedia=document.querySelector('[data-parallax] .hero-media');
if(heroMedia && !matchMedia('(prefers-reduced-motion: reduce)').matches){{
  addEventListener('scroll',()=>{{heroMedia.style.transform=`translateY(${{scrollY*.16}}px) scale(1.06)`;}},{{passive:true}});
}}
if('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches){{
  const observer=new IntersectionObserver((entries)=>entries.forEach(entry=>{{if(entry.isIntersecting){{entry.target.classList.add('is-visible');observer.unobserve(entry.target);}}}}),{{threshold:.14}});
  document.querySelectorAll('.sobre,.servicos,.depoimentos,.faq,.contato').forEach(section=>observer.observe(section));
}}
</script>
</body>
</html>'''
    return add_whatsapp_widget(html, lead, conteudo)


def evaluate_redesign_preservation(source: Dict, generated_html: str) -> Dict:
    """Reject source-led redesigns that discard the original site's useful structure."""
    if source.get("source_strategy") != "source-led":
        return {"passed": True, "strategy": "transformative", "checks": {}}
    generated = BeautifulSoup(generated_html, "lxml")
    generated_text = generated.get_text(" ", strip=True).lower()
    services = [item.get("titulo", "") for item in source.get("servicos") or [] if item.get("titulo")]
    articles = [item.get("titulo", "") for item in source.get("artigos") or [] if item.get("titulo")]
    questions = [str(item[0]) for item in source.get("faq") or [] if item]

    def coverage(items: List[str]) -> float:
        if not items:
            return 1.0
        found = sum(1 for item in items if item.lower() in generated_text)
        return found / len(items)

    source_words = int((source.get("source_profile") or {}).get("word_count") or 0)
    generated_words = len(generated_text.split())
    checks = {
        "service_coverage": coverage(services),
        "article_coverage": coverage(articles),
        "faq_coverage": coverage(questions),
        "content_ratio": generated_words / source_words if source_words else 1.0,
        "section_count": len(generated.select("section")),
        "logo_preserved": bool(not source.get("logo_url") or generated.select_one(".logo img, .brand-logo")),
    }
    passed = (
        checks["service_coverage"] >= 0.7
        and checks["article_coverage"] >= 0.7
        and checks["faq_coverage"] >= 0.5
        and checks["content_ratio"] >= 0.22
        and checks["section_count"] >= 5
        and checks["logo_preserved"]
    )
    return {"passed": bool(passed), "strategy": "source-led", "checks": checks}


def add_whatsapp_widget(html: str, lead: Lead, conteudo: Dict) -> str:
    """Add the same accessible conversion widget to every generated layout."""
    wa = lead.whatsapp or (conteudo.get("contato") or {}).get("whatsapp") or ""
    digits = re.sub(r"\D", "", wa)
    if not digits or "data-whatsapp-widget" in html:
        return html
    message = requests.utils.quote(f"Olá, vi o site de {brand_name(lead.nome)} e gostaria de conversar.")
    widget = f'''<style>
.wa-float{{position:fixed;right:22px;bottom:22px;z-index:9999;display:flex;align-items:center;gap:10px;padding:12px 16px 12px 13px;border-radius:999px;background:#25d366;color:#071b0e!important;text-decoration:none!important;font:700 14px/1 Inter,Arial,sans-serif;box-shadow:0 14px 40px rgba(0,0,0,.24);transition:transform .2s,box-shadow .2s}}
.wa-float:hover{{transform:translateY(-3px);box-shadow:0 18px 48px rgba(0,0,0,.3)}}.wa-float svg{{width:25px;height:25px;fill:currentColor}}.wa-pulse{{position:absolute;inset:-5px;border:1px solid #25d366;border-radius:999px;animation:waPulse 2s infinite;pointer-events:none}}@keyframes waPulse{{70%,100%{{transform:scale(1.12);opacity:0}}}}@media(max-width:560px){{.wa-float{{width:56px;height:56px;padding:0;justify-content:center}}.wa-float span{{display:none}}}}@media(prefers-reduced-motion:reduce){{.wa-pulse{{display:none}}}}
</style><a data-whatsapp-widget class="wa-float" href="https://wa.me/{digits}?text={message}" target="_blank" rel="noopener" aria-label="Conversar pelo WhatsApp"><i class="wa-pulse"></i><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 3.5A11 11 0 0 0 3.6 17.7L2 22l4.4-1.6A11 11 0 1 0 20.5 3.5Zm-8.5 17a9 9 0 0 1-4.6-1.3l-.3-.2-2.6 1 .9-2.6-.2-.3A9 9 0 1 1 12 20.5Zm5.2-6.4c-.3-.2-1.7-.8-1.9-.9-.3-.1-.5-.2-.7.2-.2.3-.7.9-.9 1.1-.2.2-.3.2-.6 0-.3-.2-1.2-.5-2.3-1.4-.9-.7-1.4-1.7-1.6-2-.2-.3 0-.5.1-.7.1-.1.3-.3.4-.5.1-.2.2-.3.3-.5.1-.2 0-.4 0-.5l-.7-1.8c-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.5.1-.7.4-.2.3-.9.9-.9 2.2 0 1.3.9 2.5 1 2.7.1.2 1.8 2.8 4.5 3.9.6.3 1.1.5 1.5.6.6.2 1.1.2 1.5.1.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.1-1.2 0-.1-.2-.2-.5-.3Z"/></svg><span>Falar no WhatsApp</span></a>'''
    return html.replace("</body>", widget + "</body>")


def generate_immersive_page(lead: Lead, conteudo: Dict, variant: str) -> str:
    """A deliberately different, image-led layout used for alternate proposals."""
    colors = {**niche_palette(lead.nicho), **(conteudo.get("cores") or {})}
    brand = brand_name(lead.nome)
    hero = str(conteudo.get("hero_image") or "").replace("'", "%27")
    support = str(conteudo.get("support_image") or conteudo.get("sobre_imagem") or hero).replace("'", "%27")
    headline = conteudo.get("hero_headline") or default_hero_headline(lead.nicho)
    subtitle = conteudo.get("hero_subheadline") or f"{brand} · {lead.cidade}"
    wa = lead.whatsapp or (conteudo.get("contato") or {}).get("whatsapp") or ""
    wa_link = f"https://wa.me/{wa}" if wa else "#contato"
    services = conteudo.get("servicos") or niche_services(lead.nicho)
    cards = "".join(f'<article class="service"><span>0{i + 1}</span><h3>{item.get("titulo", "Especialidade")}</h3><p>{item.get("descricao") or "Atendimento planejado para você."}</p></article>' for i, item in enumerate(services[:6]))
    poster = "poster" if variant == "poster" else "orbit"
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{brand} — {lead.cidade}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Outfit:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--p:{colors['primary']};--s:{colors['secondary']};--a:{colors['accent']};--bg:{colors['bg']};--ink:#11131a}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:Outfit,system-ui}}.wrap{{max-width:1320px;margin:auto;padding:0 28px}}.top{{position:absolute;z-index:3;inset:0 0 auto;padding:25px 0;color:#fff}}.top .wrap{{display:flex;justify-content:space-between;align-items:center}}.brand{{font-family:'Playfair Display';font-size:1.2rem}}.top a{{color:#fff;text-decoration:none}}.navcta{{border:1px solid #ffffff70;padding:10px 16px;border-radius:999px;background:#ffffff18;backdrop-filter:blur(12px);font-size:.8rem}}
.hero{{min-height:100svh;display:grid;grid-template-columns:1.05fr .95fr;position:relative;overflow:hidden;background:var(--s);color:#fff}}.hero-copy{{align-self:end;padding:18vh 8vw 11vh;position:relative;z-index:1}}.eyebrow{{font:500 .7rem 'DM Mono';letter-spacing:.16em;text-transform:uppercase;color:#ffffffaa}}h1{{font:600 clamp(3.5rem,7vw,8rem)/.88 'Playfair Display';letter-spacing:-.06em;margin:24px 0}}.sub{{max-width:390px;font-size:1rem;color:#ffffffb8}}.hero-image{{background:linear-gradient(120deg,#0005,#0000),url('{hero}') center/cover;min-height:100%}}.hero-orbit{{position:absolute;width:32vw;height:32vw;border:1px solid #ffffff30;border-radius:50%;right:42%;top:18%;animation:spin 22s linear infinite}}.hero-orbit:before,.hero-orbit:after{{content:'';position:absolute;border-radius:50%;background:var(--a)}}.hero-orbit:before{{width:12px;height:12px;top:-6px;left:50%}}.hero-orbit:after{{width:7px;height:7px;bottom:7%;right:4%}}@keyframes spin{{to{{transform:rotate(360deg)}}}}.cta{{display:inline-flex;margin-top:30px;padding:15px 22px;border-radius:999px;background:#fff;color:var(--s);font-weight:700;text-decoration:none}}
.ticker{{overflow:hidden;white-space:nowrap;padding:19px 0;background:var(--p);color:#fff;font:500 .75rem 'DM Mono';letter-spacing:.13em;text-transform:uppercase}}.ticker span{{display:inline-block;animation:marquee 22s linear infinite}}@keyframes marquee{{to{{transform:translateX(-30%)}}}}.intro{{padding:12vw 0 8vw;display:grid;grid-template-columns:1fr .8fr;gap:8vw;align-items:end}}.intro h2{{font:600 clamp(2.4rem,5vw,5.3rem)/.95 'Playfair Display';letter-spacing:-.05em;margin:0}}.intro p{{font-size:1.1rem;line-height:1.7;color:#525865}}.support{{width:100%;height:min(650px,64vw);object-fit:cover;display:block;clip-path:polygon(9% 0,100% 0,91% 100%,0 100%)}}
.services{{padding:7vw 0;background:#11131a;color:#fff;overflow:hidden}}.services-head{{display:flex;justify-content:space-between;align-items:end;margin-bottom:40px}}.services h2{{font:600 clamp(2.5rem,5vw,5.5rem)/.9 'Playfair Display';margin:0}}.rail{{display:flex;overflow:auto;gap:18px;padding-bottom:22px;scroll-snap-type:x mandatory}}.service{{scroll-snap-align:start;flex:0 0 min(76vw,360px);min-height:310px;padding:28px;border:1px solid #ffffff25;background:linear-gradient(145deg,#ffffff12,#ffffff04);border-radius:22px;display:flex;flex-direction:column;justify-content:end}}.service span{{font:500 .7rem 'DM Mono';color:var(--a)}}.service h3{{font:500 1.55rem 'Playfair Display';margin:20px 0 8px}}.service p{{color:#ffffffa8;line-height:1.55}}
.closing{{padding:10vw 0;text-align:center;background:linear-gradient(135deg,var(--bg),#fff)}}.closing h2{{font:600 clamp(3rem,7vw,7rem)/.86 'Playfair Display';letter-spacing:-.06em;max-width:900px;margin:0 auto 30px}}.facts{{display:flex;justify-content:center;gap:35px;flex-wrap:wrap;font:500 .75rem 'DM Mono';color:#555}}.facts b{{color:var(--p)}}footer{{padding:30px 0;background:#11131a;color:#fff8;font-size:.8rem}}@media(max-width:760px){{.hero{{grid-template-columns:1fr;min-height:860px}}.hero-copy{{padding:25vh 28px 70px}}.hero-image{{position:absolute;inset:0;opacity:.58}}.hero:after{{content:'';position:absolute;inset:0;background:linear-gradient(180deg,#0002,#000a)}}.hero-copy{{z-index:1}}.hero-orbit{{width:70vw;height:70vw;right:-14%;top:12%}}.intro{{grid-template-columns:1fr;padding:22vw 0 16vw;gap:35px}}.support{{height:110vw}}.wrap{{padding:0 20px}}}}
</style></head><body class="{poster}"><header class="top"><div class="wrap"><span class="brand">{brand}</span><a class="navcta" href="{wa_link}">Agendar avaliação</a></div></header><main><section class="hero"><div class="hero-copy"><p class="eyebrow">{lead.nicho} · {lead.cidade}</p><h1>{headline}</h1><p class="sub">{subtitle}</p><a class="cta" href="{wa_link}">Falar no WhatsApp ↗</a></div><div class="hero-image"></div><div class="hero-orbit"></div></section><div class="ticker"><span>EXPERIÊNCIA · TECNOLOGIA · ATENDIMENTO PRÓXIMO · {brand.upper()} · EXPERIÊNCIA · TECNOLOGIA · ATENDIMENTO PRÓXIMO · </span></div><section class="wrap intro"><h2>Detalhes pensados para uma experiência mais leve.</h2><div><p>{conteudo.get('sobre') or 'Um espaço criado para unir cuidado, precisão e conforto em cada etapa do atendimento.'}</p><img class="support" src="{support}" alt="Ambiente da clínica"></div></section><section class="services"><div class="wrap"><div class="services-head"><p class="eyebrow">Especialidades</p><h2>O que fazemos<br>com excelência.</h2></div><div class="rail">{cards}</div></div></section><section class="closing wrap" id="contato"><h2>Vamos construir o seu melhor sorriso.</h2><div class="facts"><span><b>Google</b> {lead.nota} ★</span><span>{lead.avaliacoes} avaliações</span><span>{lead.cidade}</span></div><a class="cta" href="{wa_link}">Agendar agora</a></section></main><footer><div class="wrap">{brand} · Todos os direitos reservados</div></footer><script>const h=document.querySelector('.hero-image');addEventListener('scroll',()=>{{h.style.transform=`translateY(${{scrollY*.12}}px) scale(1.06)`}},{{passive:true}})</script></body></html>'''


async def redesign_lead(lead: Lead, conteudo_extra: Dict = None) -> Dict:
    """Executa redesign completo de um lead"""
    print(f"🎨 Redesenhando: {lead.nome}")
    
    site_dir = BASE_DIR / "sites" / lead.slug
    site_dir.mkdir(parents=True, exist_ok=True)
    overrides_file = site_dir / "design-overrides.json"
    brief_file = site_dir / "creative-brief.json"
    history_file = site_dir / "design-history.json"
    overrides = {}
    if overrides_file.exists():
        try:
            overrides = json.loads(overrides_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("   ⚠️ design-overrides.json inválido; ignorando overrides")

    # Extrai conteúdo público; assets gerados aprovados têm prioridade.
    conteudo = localize_brand_assets(extract_content_from_site(lead.site_atual), site_dir)
    history = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []
    if brief_file.exists():
        try:
            history.append(json.loads(brief_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    brief = select_creative_brief(lead, conteudo, history[-8:])
    brief["generated_at"] = datetime.now().isoformat()
    brief["catalog_version"] = 1
    brief_file.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    history.append(brief)
    history_file.write_text(json.dumps(history[-12:], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    conteudo["creative_brief"] = brief
    conteudo.update(llm_redesign_content(lead, conteudo))
    generated = generate_missing_visual_assets(lead, conteudo, site_dir, overrides)
    if generated:
        overrides.update(generated)
        overrides_file.write_text(json.dumps(overrides, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        brief["assets"] = generated.get("asset_manifest", [])
        brief_file.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        history[-1] = brief
        history_file.write_text(json.dumps(history[-12:], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    conteudo.update(overrides)
    if conteudo_extra:
        conteudo.update(conteudo_extra)
    
    # Gera HTML
    html = generate_page_html(lead, conteudo)
    quality = evaluate_redesign_preservation(conteudo, html)
    (site_dir / "quality-report.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not quality["passed"]:
        raise RuntimeError(f"Redesign bloqueado por perda de conteúdo/estrutura: {quality['checks']}")
    
    # Salva arquivos
    # index.html
    (site_dir / "index.html").write_text(html, encoding='utf-8')

    await capture_comparison_screenshots(lead, site_dir)
    
    # proposta.html (capa para e-mail)
    proposta_html = generate_proposta_html(lead, conteudo)
    (site_dir / "proposta.html").write_text(proposta_html, encoding='utf-8')
    
    # editor.html
    editor_html = generate_editor_html(lead, conteudo)
    (site_dir / "editor.html").write_text(editor_html, encoding='utf-8')
    
    # comparador.html
    comparador_html = generate_comparador_html(lead, conteudo)
    (site_dir / "comparador.html").write_text(comparador_html, encoding='utf-8')
    
    # assets (copiar se existirem)
    assets_src = BASE_DIR / "skills" / "redesign-premium" / "references" / "assets"
    if assets_src.exists():
        assets_dst = site_dir / "assets"
        assets_dst.mkdir(exist_ok=True)
        for asset in assets_src.iterdir():
            if asset.is_file():
                shutil.copy2(asset, assets_dst / asset.name)
    
    print(f"   ✅ Site gerado em: {site_dir}")
    return {
        'slug': lead.slug,
        'site_dir': str(site_dir),
        'url': _public_url(lead.slug),
        'proposta_url': _public_url(lead.slug) + 'proposta.html'
    }


def generate_missing_visual_assets(lead: Lead, conteudo: Dict, site_dir: Path, overrides: Dict) -> Dict:
    """Generate a KIE image set from the selected style and LLM variation plan."""
    cfg_file = BASE_DIR / "prospector-config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else {}
    redesign_cfg = cfg.get("redesign") or {}
    if conteudo.get("source_strategy") == "source-led" and len(conteudo.get("source_images") or []) >= 2:
        print("   ℹ️ Site fonte rico: preservando fotografia original, sem gerar imagens KIE")
        return {}
    if redesign_cfg.get("image_provider") != "kie_mcp":
        return {}
    key = (redesign_cfg.get("kie_api_key") or "").strip()
    model = (redesign_cfg.get("image_model") or "").strip()
    if not key or not model:
        return {}
    try:
        from app.api.config_api import _kie_call, _kie_payload

        palette = conteudo.get("cores") or niche_palette(lead.nicho)
        brief = conteudo.get("creative_brief") or {}
        variation = brief.get("variation") or {}
        style_id = brief.get("style_id") or "editorial"
        style_meta = next((item for item in load_catalog().get("styles", []) if item.get("id") == style_id), {})
        requested = brief.get("image_plan") if isinstance(brief.get("image_plan"), list) else ["hero", "support", "detail"]
        recipes = {
            "hero": ("hero_image", "16:9", "wide establishing hero image"),
            "hero-action": ("hero_image", "16:9", "dynamic hero image with a clear sense of action"),
            "support": ("support_image", "4:5", "editorial supporting portrait or environmental detail"),
            "support-image": ("support_image", "4:5", "editorial supporting portrait or environmental detail"),
            "detail": ("detail_image", "1:1", "close editorial detail for a service or brand moment"),
            "coach-detail": ("detail_image", "1:1", "close authentic professional detail"),
            "training-environment": ("detail_image", "1:1", "atmospheric environment detail"),
        }
        jobs = []
        seen = set()
        for requested_asset in requested:
            field, ratio, framing = recipes.get(str(requested_asset).lower(), ("detail_image", "1:1", "editorial service detail"))
            if field in seen:
                continue
            seen.add(field)
            jobs.append((field, ratio, framing))
        # A premium landing always needs a complete visual sequence, even when
        # the selector produced a minimal image plan.
        for field, ratio, framing in (("hero_image", "16:9", "wide establishing hero image"), ("support_image", "4:5", "editorial supporting environmental detail"), ("detail_image", "1:1", "close editorial detail")):
            if field not in seen:
                jobs.append((field, ratio, framing))
                seen.add(field)
        generated = {}
        manifest = []
        import time
        version = datetime.now().strftime("%Y%m%d%H%M%S")
        for field, ratio, framing in jobs:
            filename = f"{field.replace('_image', '')}-{style_id}-{version}.jpg"
            prompt = (
                f"{framing} for {lead.nome}, a {lead.nicho} business in {lead.cidade}. "
                f"Visual direction: {style_meta.get('name', style_id)}. {style_meta.get('description', '')}. "
                f"Variation: {variation.get('image_mood', 'editorial natural light')}; "
                f"palette direction {variation.get('palette_direction', 'brand informed')}; corporate colors "
                f"{palette.get('primary')}, {palette.get('secondary')}, {palette.get('accent')}. "
                "Premium commercial photography, believable people and environment, composition with clean negative space for web copy; "
                "specific to this business and city, avoid generic stock-photo poses and obvious industry clichés; "
                "no readable text, no invented logo, no watermark, no collage, no distorted anatomy."
            )
            result = _kie_payload(_kie_call(key, model, {"prompt": prompt, "aspect_ratio": ratio, "resolution": "1K"}))
            task_id = ((result.get("response") or {}).get("data") or {}).get("taskId")
            if not task_id:
                continue
            for _ in range(30):
                time.sleep(4)
                status = _kie_payload(_kie_call(key, "get_task_status", {"task_id": task_id}))
                urls = status.get("result_urls") or []
                if status.get("status") == "success" and urls:
                    assets = site_dir / "assets"
                    assets.mkdir(parents=True, exist_ok=True)
                    target = assets / filename
                    image = requests.get(urls[0], timeout=60)
                    image.raise_for_status()
                    target.write_bytes(image.content)
                    generated[field] = f"assets/{filename}"
                    generated[f"{field}_task_id"] = task_id
                    manifest.append({"field": field, "path": generated[field], "task_id": task_id, "model": model, "prompt": prompt, "aspect_ratio": ratio})
                    print(f"   ✨ Asset KIE gerado: {filename}")
                    break
                if status.get("status") in ("failed", "error", "cancelled"):
                    break
        if manifest:
            generated["asset_manifest"] = manifest
        return generated
    except Exception as exc:
        print(f"   ⚠️ Hero KIE não gerado: {exc}")
    return {}


async def capture_comparison_screenshots(lead: Lead, site_dir: Path) -> None:
    """Capture the real old site and the generated redesign for the proposal page."""
    try:
        from playwright.async_api import async_playwright

        assets = site_dir / "assets"
        assets.mkdir(exist_ok=True)
        for screenshot in (assets / "before.png", assets / "after.png"):
            screenshot.unlink(missing_ok=True)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1440, "height": 980}, device_scale_factor=1)
            if lead.site_atual:
                try:
                    await page.goto(lead.site_atual, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(1800)
                    await page.screenshot(path=str(assets / "before.png"), full_page=False)
                except Exception as exc:
                    print(f"   ⚠️ Screenshot do site antigo falhou: {exc}")
            await page.goto((site_dir / "index.html").as_uri(), wait_until="load", timeout=30000)
            await page.wait_for_timeout(500)
            visual = await page.evaluate("""() => ({
                overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
                brokenImages: [...document.images].filter(img => !img.complete || img.naturalWidth === 0).length,
                hasHeading: !!document.querySelector('h1'),
                hasCta: !!document.querySelector('a[href*="wa.me"], a[href*="contato"], .cta, .button')
            })""")
            if visual["overflow"] or visual["brokenImages"] or not visual["hasHeading"] or not visual["hasCta"]:
                raise RuntimeError(f"QA visual do redesign falhou: {visual}")
            await page.screenshot(path=str(assets / "after.png"), full_page=False)
            await browser.close()
    except Exception as exc:
        raise RuntimeError(f"Screenshots/QA visual indisponíveis: {exc}") from exc


def generate_proposta_html(lead: Lead, conteudo: Dict) -> str:
    """Gera página-capa para proposta (antes/depois)"""
    cores = conteudo.get('cores', {'primary': '#1e40af'})
    css_vars = generate_css_variables(cores)
    
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nova versão do site - {lead.nome}</title>
<style>
{css_vars}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#f8fafc;color:#1e293b;line-height:1.6}}
.container{{max-width:1000px;margin:0 auto;padding:40px 20px}}
.header{{text-align:center;padding:40px 0;border-bottom:1px solid #e2e8f0;margin-bottom:40px}}
.header h1{{font-size:2rem;color:var(--color-secondary);margin-bottom:8px}}
.before-after{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:32px 0}}
@media(max-width:768px){{.before-after{{grid-template-columns:1fr}}}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}}
.card-header{{padding:16px;font-weight:600;text-align:center}}
.card-header.old{{background:#fef2f2;color:#dc2626;border-bottom:2px solid #fecaca}}
.card-header.new{{background:#f0fdf4;color:#059669;border-bottom:2px solid #bbf7d0}}
.card-img{{aspect-ratio:16/10;background:#f1f5f9;display:flex;align-items:center;justify-content:center;color:#64748b;font-size:.85rem;overflow:hidden;padding:14px;text-align:center}}
.card-img img{{width:100%;height:100%;object-fit:cover;object-position:top;border-radius:8px;box-shadow:0 12px 32px rgba(15,23,42,.14)}}
.features{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;margin:32px 0}}
.feature{{display:flex;align-items:flex-start;gap:12px;padding:16px;background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0}}
.feature-icon{{width:40px;height:40px;background:var(--color-primary);border-radius:10px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:1.25rem;flex-shrink:0}}
.feature-text h3{{font-size:.95rem;font-weight:600;margin-bottom:4px}}
.feature-text p{{font-size:.85rem;color:#64748b;margin:0}}
.cta{{text-align:center;margin-top:40px;padding-top:32px;border-top:1px solid #e2e8f0}}
.btn{{display:inline-block;background:var(--color-primary);color:#fff;padding:16px 32px;border-radius:10px;font-weight:600;text-decoration:none;transition:filter .2s}}
.btn:hover{{filter:brightness(.9)}}
.footer{{text-align:center;padding-top:32px;border-top:1px solid #e2e8f0;color:#64748b;font-size:.9rem}}
</style>
</head>
<body>
<div class="container">
<header class="header">
<h1>Uma nova presença digital para <strong>{lead.nome}</strong></h1>
<p>Antes & Depois — comparação lado a lado</p>
</header>

<div class="before-after">
<div class="card">
<div class="card-header old">🔴 Site Atual</div>
<div class="card-img">{f'<img src="assets/before.png" alt="Site atual de {lead.nome}">' if lead.site_atual else '<span>Este negócio ainda não tem site. A proposta é criar sua presença digital completa.</span>'}</div>
</div>
<div class="card">
<div class="card-header new">🟢 Nova Versão</div>
<div class="card-img"><img src="assets/after.png" alt="Nova versão proposta"></div>
</div>
</div>

<div class="features">
<div class="feature"><span class="feature-icon">01</span><div class="feature-text"><h3>Experiência responsiva</h3><p>Layout validado em telas de desktop e celular.</p></div></div>
<div class="feature"><span class="feature-icon">02</span><div class="feature-text"><h3>Identidade preservada</h3><p>Logo, cores e conteúdo público da marca aplicados ao redesign.</p></div></div>
<div class="feature"><span class="feature-icon">03</span><div class="feature-text"><h3>Conteúdo organizado</h3><p>Serviços e informações apresentados com hierarquia mais clara.</p></div></div>
<div class="feature"><span class="feature-icon">04</span><div class="feature-text"><h3>Contato direto</h3><p>Atalho visível para iniciar uma conversa pelo WhatsApp.</p></div></div>
</div>

<div class="cta">
<a class="btn" href="{_public_url(lead.slug)}" target="_blank">Explorar a nova versão →</a>
</div>

<div class="footer">
Feito para <strong>{lead.nome}</strong> pela IA Botz
</div>
</div>
</body>
</html>'''


def generate_editor_html(lead: Dict, conteudo: Dict) -> str:
    """Editor visual para ajustes manuais"""
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Editor Visual - {conteudo.get('nome', 'Cliente')}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#f1f5f9;height:100vh;display:flex}}
.toolbar{{width:320px;background:#fff;border-right:1px solid #e2e8f0;padding:20px;overflow-y:auto;position:fixed;height:100vh;left:0;top:0;z-index:100}}
.toolbar h2{{font-size:1.25rem;margin-bottom:20px;padding-bottom:12px;border-bottom:1px solid #e2e8f0}}
.toolbar-section{{margin-bottom:24px}}
.toolbar-section h3{{font-size:.85rem;text-transform:uppercase;color:#64748b;margin-bottom:12px;letter-spacing:.5px}}
.color-picker{{display:flex;gap:8px;margin-bottom:8px}}
.color-btn{{width:36px;height:36px;border-radius:8px;border:2px solid transparent;cursor:pointer;transition:border .2s}}
.color-btn.active{{border-color:#1e40af}}
.color-btn:hover{{transform:scale(1.1)}}
.btn{{width:100%;padding:10px 16px;border-radius:8px;font-weight:600;margin-top:8px;cursor:pointer;border:none;font-size:.9rem}}
.btn-primary{{background:#1e40af;color:#fff}}
.btn-primary:hover{{background:#1e3a8a}}
.btn-secondary{{background:#f1f5f9;color:#1e40af;border:1px solid #e2e8f0}}
iframe{{flex:1;border:none;background:#fff}}
@media(max-width:768px){{.toolbar{{position:fixed;bottom:0;left:0;right:0;width:auto;height:auto;max-height:60vh;border-top:1px solid #e2e8f0;border-right:none}}}}
</style>
</head>
<body>
<div class="toolbar">
<h2>✏️ Editor Visual</h2>
<div class="toolbar-section">
<h3>Cores da Marca</h3>
<div class="color-picker">
<button class="color-btn" style="background:#1e40af" data-var="--color-primary" onclick="setColor(this)"></button>
<button class="color-btn" style="background:#059669" data-var="--color-accent" onclick="setColor(this)"></button>
<button class="color-btn" style="background:#dc2626" data-var="--color-primary" onclick="setColor(this)"></button>
<button class="color-btn" style="background:#7c3aed" data-var="--color-primary" onclick="setColor(this)"></button>
<button class="color-btn" style="background:#ea580c" data-var="--color-primary" onclick="setColor(this)"></button>
<button class="color-btn" style="background:#0891b2" data-var="--color-primary" onclick="setColor(this)"></button>
</div>
<input type="color" id="color-primary" value="#1e40af" onchange="applyColor('--color-primary', this.value)">
<input type="color" id="color-accent" value="#059669" onchange="applyColor('--color-accent', this.value)">
</div>
<div class="toolbar-section">
<h3>Tipografia</h3>
<select onchange="applyFont('heading', this.value)"><option value="Inter,system-ui,sans-serif">Inter (padrão)</option><option value="Poppins,system-ui,sans-serif">Poppins</option><option value="Roboto,system-ui,sans-serif">Roboto</option><option value="Montserrat,system-ui,sans-serif">Montserrat</option></select>
<select onchange="applyFont('body', this.value)"><option value="Inter,system-ui,sans-serif">Inter (padrão)</option><option value="DM Sans,system-ui,sans-serif">DM Sans</option><option value="Open Sans,system-ui,sans-serif">Open Sans</option></select>
</div>
<div class="toolbar-section">
<h3>Ações</h3>
<button class="btn btn-primary" onclick="exportHTML()">💾 Exportar HTML</button>
<button class="btn btn-secondary" onclick="resetStyles()">🔄 Resetar</button>
</div>
</div>
<iframe id="preview" src="index.html"></iframe>
<script>
function setColor(btn){{
    document.querySelectorAll('.color-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    const varName=btn.dataset.var;
    const color=btn.style.backgroundColor;
    applyColor(varName, color);
}}
function applyColor(varName, color){{
    document.documentElement.style.setProperty(varName, color);
    document.getElementById('preview').contentDocument.documentElement.style.setProperty(varName, color);
}}
function applyFont(type, font){{
    const varName=type==='heading'?'--font-heading':'--font-body';
    applyColor(varName, font);
}}
function applyColor(varName, value){{
    document.documentElement.style.setProperty(varName, value);
    const iframe=document.getElementById('preview');
    iframe.contentDocument.documentElement.style.setProperty(varName, value);
}}
function exportHTML(){{
    const html=document.getElementById('preview').contentDocument.documentElement.outerHTML;
    const blob=new Blob([html],{{type:'text/html'}});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;a.download='index.html';a.click();
    URL.revokeObjectURL(url);
}}
function resetStyles(){{
    document.documentElement.style.cssText='';
    const iframe=document.getElementById('preview');
    iframe.contentDocument.documentElement.style.cssText='';
    iframe.src=iframe.src;
}}
</script>
</body>
</html>'''


def generate_comparador_html(lead: Dict, conteudo: Dict) -> str:
    """Slider antes/depois"""
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparador - {conteudo.get('nome', 'Cliente')}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#f8fafc;min-height:100vh}}
.container{{max-width:1200px;margin:0 auto;padding:20px}}
h1{{text-align:center;margin:32px 0;font-size:clamp(1.5rem,4vw,2.5rem);color:#1e293b}}
.tabs{{display:flex;justify-content:center;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
.tab{{padding:12px 24px;border:1px solid #e2e8f0;background:#fff;border-radius:8px;cursor:pointer;font-weight:500;transition:all .2s}}
.tab.active{{background:#1e40af;color:#fff;border-color:#1e40af}}
.comparison{{position:relative;height:600px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}}
@media(max-width:768px){{.comparison{{height:400px}}}}
.view{{position:absolute;top:0;left:0;width:100%;height:100%;overflow:hidden}}
.view.old{{z-index:1}}
.view.new{{z-index:2;clip-path:polygon(50% 0,100% 0,100% 100%,50% 100%)}}
.handle{{position:absolute;top:0;bottom:0;width:4px;background:#1e40af;left:50%;transform:translateX(-50%);z-index:10;cursor:ew-resize}}
.handle::before{{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:32px;height:32px;background:#1e40af;border-radius:50%;opacity:.8;display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px}}
.handle::after{{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:48px;height:48px;border:2px solid #1e40af;border-radius:50%;opacity:.3}}
iframe{{width:100%;height:100%;border:none}}
@media(max-width:768px){{.comparison{{height:350px}}h1{{font-size:1.5rem}}}}
</style>
</head>
<body>
<div class="container">
<h1>📊 Comparador: Antes vs Depois</h1>
<div class="tabs">
<button class="tab active" onclick="showTab('split')">📱 Slider</button>
<button class="tab" onclick="showTab('side')">📐 Lado a Lado</button>
<button class="tab" onclick="showTab('old')">🔴 Antigo</button>
<button class="tab" onclick="showTab('new')">🟢 Novo</button>
</div>
<div class="comparison" id="comparison">
<div class="view old"><iframe src="http://webcache.googleusercontent.com/search?q=cache:{conteudo.get('site_atual', '')}"></iframe></div>
<div class="view new"><iframe src="index.html"></iframe></div>
<div class="handle" id="handle"></div>
</div>
</div>
<script>
let isDragging=false;
const comparison=document.getElementById('comparison');
const handle=document.getElementById('handle');
const newView=comparison.querySelector('.view.new');
function showTab(tab){{
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    event.target.classList.add('active');
    const oldView=comparison.querySelector('.view.old');
    const newView=comparison.querySelector('.view.new');
    const handle=comparison.querySelector('.handle');
    if(tab==='split'){{oldView.style.display='block';newView.style.display='block';handle.style.display='block';newView.style.clipPath='polygon(50% 0,100% 0,100% 100%,50% 100%)';}}
    else if(tab==='side'){{oldView.style.display='block';newView.style.display='block';handle.style.display='none';oldView.style.width='50%';newView.style.width='50%';newView.style.clipPath='none';}}
    else if(tab==='old'){{oldView.style.display='block';newView.style.display='none';handle.style.display='none';}}
    else if(tab==='new'){{oldView.style.display='none';newView.style.display='block';handle.style.display='none';newView.style.clipPath='none';}}
}}
handle.addEventListener('mousedown',e=>{{isDragging=true;}});
document.addEventListener('mousemove',e=>{{if(!isDragging)return;const rect=comparison.getBoundingClientRect();let x=e.clientX-rect.left;x=Math.max(0,Math.min(x,rect.width));newView.style.clipPath=`polygon(${{x}}px 0,${{rect.width}}px 0,${{rect.width}}px ${{rect.height}}px,${{x}}px ${{rect.height}}px)`;handle.style.left=`${{x}}px`;}});
document.addEventListener('mouseup',()=>{{isDragging=false;}});
handle.addEventListener('touchstart',e=>{{isDragging=true;}},{{passive:true}});
document.addEventListener('touchmove',e=>{{if(!isDragging)return;const rect=comparison.getBoundingClientRect();let x=e.touches[0].clientX-rect.left;x=Math.max(0,Math.min(x,rect.width));newView.style.clipPath=`polygon(${{x}}px 0,${{rect.width}}px 0,${{rect.width}}px ${{rect.height}}px,${{x}}px ${{rect.height}}px)`;handle.style.left=`${{x}}px`;}},{{passive:true}});
document.addEventListener('touchend',()=>{{isDragging=false;}});
</script>
</body>
</html>'''


# ============================================================
# MAIN
# ============================================================

async def main():
    if len(sys.argv) < 2:
        print("Uso: python3 redesign.py <slug|todos>")
        sys.exit(1)

    target = sys.argv[1]
    render_only = "--render-only" in sys.argv[2:]
    slugs = list_slugs_for_redesign(target)

    if not slugs:
        print("⚠️  Nenhum lead elegível para redesign (status 'novo' ou slug inexistente)")
        sys.exit(1)

    print(f"\n🎨 Iniciando redesign de {len(slugs)} site(s)...\n")

    for slug in slugs:
        lead = load_lead(slug)
        if not lead:
            print(f"❌ Lead não encontrado: {slug}")
            continue

        if render_only:
            site_dir = BASE_DIR / "sites" / lead.slug
            brief_file = site_dir / "creative-brief.json"
            overrides_file = site_dir / "design-overrides.json"
            if not brief_file.exists():
                print(f"❌ Briefing inexistente para render-only: {slug}")
                continue
            content = localize_brand_assets(extract_content_from_site(lead.site_atual), site_dir)
            content["creative_brief"] = json.loads(brief_file.read_text(encoding="utf-8"))
            if overrides_file.exists():
                content.update(json.loads(overrides_file.read_text(encoding="utf-8")))
            rendered = generate_page_html(lead, content)
            quality = evaluate_redesign_preservation(content, rendered)
            (site_dir / "quality-report.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if not quality["passed"]:
                raise RuntimeError(f"Render bloqueado por perda de conteúdo/estrutura: {quality['checks']}")
            (site_dir / "index.html").write_text(rendered, encoding="utf-8")
            await capture_comparison_screenshots(lead, site_dir)
            (site_dir / "proposta.html").write_text(generate_proposta_html(lead, content), encoding="utf-8")
            print(f"   ✅ Render atualizado sem consumir KIE: {site_dir}")
        else:
            await redesign_lead(lead)
        mark_redesigned(slug)
        print(f"✅ Status → redesenhado: {slug}")

    print("\n🎉 Redesign concluído!")
    print("💡 Próximo: publicar no painel ou ./prospector publicar")


if __name__ == "__main__":
    asyncio.run(main())
