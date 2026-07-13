"""Selection utilities for the locally imported design-style catalog."""
from __future__ import annotations

import json
import re
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CATALOG_FILE = ROOT / "skills" / "redesign-premium" / "references" / "design-catalog" / "catalog.json"

# These are renderer compositions, not color-only variants. Each style can add
# more renderers over time without changing stored creative briefs.
COMPOSITIONS = {
    "academia": ["authority-ledger", "methodology-timeline", "heritage-profile"],
    "art-deco": ["sunburst-ceremony", "symmetric-salon", "ziggurat-offer"],
    "bauhaus": ["constructivist-poster", "color-block-story", "geometric-services"],
    "bold-typography": ["statement-scroll", "proof-poster", "typographic-manifesto"],
    "cyberpunk": ["neon-hud", "glitch-command", "signal-grid"],
    "kinetic": ["results-performance", "motion-manifesto", "metric-marquee"],
    "luxury": ["offset-editorial", "gallery-narrative", "quiet-authority"],
    "newsprint": ["front-page", "evidence-report", "column-story"],
    "playful-geometric": ["friendly-shapes", "sticker-services", "colorful-journey"],
    "saas": ["bento-product", "workflow-proof", "conversion-dashboard"],
    "terminal": ["command-center", "tmux-grid", "system-status"],
    "web3": ["network-orbit", "protocol-proof", "chain-timeline"],
}

NICHE_STYLE_ORDER = {
    "fitness": ["kinetic", "bauhaus", "bold-typography", "neo-brutalism"],
    "health": ["luxury", "academia", "monochrome", "professional"],
    "legal": ["academia", "newsprint", "professional", "luxury"],
    "food": ["bauhaus", "newsprint", "playful-geometric", "retro"],
    "technology": ["saas", "modern-dark", "enterprise", "terminal"],
    "creative": ["bauhaus", "luxury", "art-deco", "swiss-minimalist"],
    "family": ["playful-geometric", "material-design", "claymorphism", "botanical"],
}


def load_catalog() -> dict:
    if not CATALOG_FILE.exists():
        return {"styles": []}
    return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))


def style_ids() -> set[str]:
    return {item["id"] for item in load_catalog().get("styles", [])}


def niche_group(niche: str) -> str:
    value = (niche or "").lower()
    rules = {
        "fitness": ("personal trainer", "academia", "fitness", "treino", "crossfit", "pilates"),
        "health": ("odont", "dent", "clinica", "clínica", "medic", "estet", "psico", "nutri"),
        "legal": ("advog", "jurid", "contab", "consult"),
        "food": ("restaurante", "cafe", "café", "bar", "pizz", "hamburg", "food"),
        "technology": ("software", "tecnologia", "ia", "autom", "saas", "agencia digital"),
        "creative": ("arquitet", "fotograf", "design", "arte", "interior"),
        "family": ("infantil", "escola", "pet", "veter", "educa"),
    }
    return next((group for group, terms in rules.items() if any(term in value for term in terms)), "creative")


def fallback_brief(lead: dict, previous: list[dict] | None = None) -> dict:
    """Pick a compatible style and a non-repeating composition without an LLM."""
    available = style_ids()
    group = niche_group(str(lead.get("nicho") or ""))
    candidates = [style for style in NICHE_STYLE_ORDER[group] if style in available]
    if not candidates:
        candidates = sorted(available)
    seed = int(hashlib.sha1(f"{lead.get('nome','')}|{lead.get('nicho','')}".encode()).hexdigest()[:8], 16)
    if candidates:
        offset = seed % len(candidates)
        candidates = candidates[offset:] + candidates[:offset]
    previous_pairs = {
        (item.get("style_id"), item.get("layout_id"))
        for item in (previous or [])
        if isinstance(item, dict)
    }
    for style in candidates:
        layouts = COMPOSITIONS.get(style, ["editorial-story", "conversion-split", "proof-rail"])
        layout_offset = (seed // 7) % len(layouts)
        layouts = layouts[layout_offset:] + layouts[:layout_offset]
        for layout in layouts:
            if (style, layout) not in previous_pairs:
                return {
                    "style_id": style,
                    "layout_id": layout,
                    "confidence": 0.65,
                    "selection_method": "rules",
                    "reason": f"Direção {style} adequada para {group}.",
                    "section_plan": ["hero", "proof", "about", "services", "contact"],
                    "image_plan": ["hero", "support", "detail"],
                    "variation": {
                        "palette_direction": "brand-informed",
                        "image_mood": ("editorial-natural-light", "cinematic-contrast", "warm-documentary")[seed % 3],
                        "density": ("compact", "balanced", "spacious")[seed % 3],
                        "section_emphasis": ("proof", "services", "story")[seed % 3],
                        "hero_treatment": ("layout-led", "full-bleed", "statement-led")[seed % 3],
                        "surface_tone": ("brand-adaptive", "light", "dark")[seed % 3],
                        "section_rhythm": ("asymmetric", "alternating", "stacked")[seed % 3],
                    },
                }
    return {
        "style_id": candidates[0], "layout_id": COMPOSITIONS.get(candidates[0], ["editorial-story"])[0],
        "confidence": 0.5, "selection_method": "rules", "reason": "Catálogo sem composição inédita.",
        "section_plan": ["hero", "about", "services", "contact"], "image_plan": ["hero", "support"],
        "variation": {"palette_direction": "brand-informed", "image_mood": "editorial-natural-light", "density": "balanced", "section_emphasis": "proof", "hero_treatment": "layout-led", "surface_tone": "brand-adaptive", "section_rhythm": "asymmetric"},
    }


def normalize_llm_brief(value: dict, lead: dict, previous: list[dict] | None = None) -> dict:
    fallback = fallback_brief(lead, previous)
    style = str(value.get("style_id") or "")
    if style not in style_ids():
        return fallback
    layouts = COMPOSITIONS.get(style, ["editorial-story", "conversion-split", "proof-rail"])
    layout = str(value.get("layout_id") or "")
    if layout not in layouts:
        layout = layouts[0]
    previous_pairs = {
        (item.get("style_id"), item.get("layout_id"))
        for item in (previous or []) if isinstance(item, dict)
    }
    if (style, layout) in previous_pairs:
        return fallback
    variation = value.get("variation") if isinstance(value.get("variation"), dict) else {}
    return {
        **fallback,
        "style_id": style,
        "layout_id": layout,
        "confidence": min(1, max(0, float(value.get("confidence") or 0.8))),
        "selection_method": "llm",
        "reason": str(value.get("reason") or fallback["reason"])[:500],
        "section_plan": value.get("section_plan") if isinstance(value.get("section_plan"), list) else fallback["section_plan"],
        "image_plan": value.get("image_plan") if isinstance(value.get("image_plan"), list) else fallback["image_plan"],
        "variation": {
            "palette_direction": str(variation.get("palette_direction") or fallback["variation"]["palette_direction"])[:80],
            "image_mood": str(variation.get("image_mood") or fallback["variation"]["image_mood"])[:120],
            "density": str(variation.get("density") or fallback["variation"]["density"])[:40],
            "section_emphasis": str(variation.get("section_emphasis") or fallback["variation"]["section_emphasis"])[:60],
            "hero_treatment": str(variation.get("hero_treatment") or fallback["variation"]["hero_treatment"])[:60],
            "surface_tone": str(variation.get("surface_tone") or fallback["variation"]["surface_tone"])[:40],
            "section_rhythm": str(variation.get("section_rhythm") or fallback["variation"]["section_rhythm"])[:40],
        },
    }
