"""Discovery engine selector — Places primary, Apify fallback."""
from __future__ import annotations

from typing import Callable

from app.config import get_maps_keys, load_config
from app.discovery.apify_client import ApifyGoogleMapsService
from app.discovery.places import GooglePlacesService
from app.discovery.qualify_site import is_lead_gold, qualify_site
from app.db import _slugify, db


Progress = Callable[[str], None]


def engine_status() -> dict:
    google_key, apify_key = get_maps_keys()
    return {
        "google_places": {"configured": bool(google_key)},
        "apify": {"configured": bool(apify_key)},
        "default": "google_places" if google_key else ("apify" if apify_key else None),
    }


def resolve_engine(preferred: str | None = None) -> tuple[str, object]:
    cfg = load_config()
    maps = cfg.get("maps") or {}
    preferred = preferred or maps.get("engine") or "auto"
    google_key, apify_key = get_maps_keys()

    if preferred in ("google_places", "places") and google_key:
        return "google_places", GooglePlacesService(google_key)
    if preferred == "apify" and apify_key:
        return "apify", ApifyGoogleMapsService(apify_key)
    if preferred == "auto" or preferred in ("google_places", "places", "apify"):
        if google_key:
            return "google_places", GooglePlacesService(google_key)
        if apify_key:
            return "apify", ApifyGoogleMapsService(apify_key)
    raise RuntimeError(
        "Nenhum motor Maps configurado. Defina maps.google_maps_api_key ou maps.apify_api_key."
    )


def run_prospecting(
    nicho: str,
    cidade: str,
    meta: int = 10,
    nota_min: float = 4.7,
    aval_min: int = 40,
    raio_km: int = 15,
    engine: str | None = None,
    on_progress: Progress | None = None,
) -> dict:
    def log(msg: str):
        if on_progress:
            on_progress(msg)

    eng_name, service = resolve_engine(engine)
    log(f"Motor: {eng_name} · {nicho} em {cidade} · meta {meta}")

    if eng_name == "google_places":
        candidates = service.search(
            nicho, cidade, max_results=max(meta * 5, 40), radius_km=raio_km, on_progress=log
        )
    else:
        candidates = service.search_sync(
            nicho, cidade, max_results=max(meta * 5, 40), on_progress=log
        )

    log(f"{len(candidates)} candidatos brutos")
    qualified = []
    discarded = []

    for i, p in enumerate(candidates):
        if len(qualified) >= meta:
            break
        log(f"Qualificando {i+1}/{len(candidates)}: {p.get('nome')}")
        site = p.get("site") or ""
        site_info = qualify_site(site) if site else {"ok": False, "motivos": ["sem website"], "email": "", "whatsapp": ""}
        ok, motivo = is_lead_gold(p, site_info, nota_min, aval_min)
        slug = _slugify(f"{p.get('nome','')}-{cidade}")
        wa = site_info.get("whatsapp") or _phone_to_wa(p.get("telefone") or "")
        row = {
            "slug": slug,
            "nome": p.get("nome") or "",
            "nicho": nicho,
            "cidade": cidade,
            "nota": p.get("nota") or 0,
            "avaliacoes": p.get("avaliacoes") or 0,
            "email": site_info.get("email") or "",
            "telefone": p.get("telefone") or "",
            "whatsapp": wa,
            "siteAntigo": site,
            "motivo": motivo,
            "status": "novo" if ok else "descartado",
            "placeId": p.get("place_id") or "",
            "engine": eng_name,
            "obs": "" if ok else motivo,
        }
        if ok:
            qualified.append(row)
            _upsert_lead(row, protect_advanced=True)
            log(f"✓ Lead: {row['nome']}")
        else:
            discarded.append(row)
            _upsert_lead(row, protect_advanced=True)
            log(f"✗ {row['nome']}: {motivo}")

    return {
        "engine": eng_name,
        "qualified": qualified,
        "discarded_count": len(discarded),
        "candidates": len(candidates),
    }


def _upsert_lead(row: dict, protect_advanced: bool = True) -> None:
    advanced = {"redesenhado", "publicado", "proposta", "respondeu", "fechado"}
    with db() as conn:
        existing = conn.execute(
            "SELECT status FROM leads WHERE slug=?", (row["slug"],)
        ).fetchone()
        if existing and protect_advanced and existing["status"] in advanced:
            return
        conn.execute(
            """
            INSERT INTO leads (
              slug,nome,nicho,cidade,nota,avaliacoes,email,telefone,whatsapp,
              siteAntigo,motivo,status,placeId,engine,obs,atualizado
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))
            ON CONFLICT(slug) DO UPDATE SET
              nome=excluded.nome, nicho=excluded.nicho, cidade=excluded.cidade,
              nota=excluded.nota, avaliacoes=excluded.avaliacoes,
              email=CASE WHEN excluded.email!='' THEN excluded.email ELSE leads.email END,
              telefone=excluded.telefone, whatsapp=excluded.whatsapp,
              siteAntigo=excluded.siteAntigo, motivo=excluded.motivo,
              status=CASE WHEN leads.status IN ('redesenhado','publicado','proposta','respondeu','fechado')
                     THEN leads.status ELSE excluded.status END,
              placeId=excluded.placeId, engine=excluded.engine,
              obs=excluded.obs, atualizado=datetime('now','localtime')
            """,
            (
                row["slug"],
                row["nome"],
                row["nicho"],
                row["cidade"],
                row["nota"],
                row["avaliacoes"],
                row["email"],
                row["telefone"],
                row["whatsapp"],
                row["siteAntigo"],
                row["motivo"],
                row["status"],
                row.get("placeId", ""),
                row.get("engine", ""),
                row.get("obs", ""),
            ),
        )


def _phone_to_wa(phone: str) -> str:
    digits = re_digits(phone)
    if not digits:
        return ""
    if digits.startswith("55"):
        return digits
    if len(digits) >= 10:
        return "55" + digits
    return digits


def re_digits(s: str) -> str:
    import re

    return re.sub(r"\D", "", s or "")
