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
    def log(msg: str, level: str = "info"):
        if on_progress:
            # runners pass only msg; level via prefix for UI
            if level != "info":
                on_progress(f"[{level}] {msg}")
            else:
                on_progress(msg)

    def step(key: str, label: str):
        log(f"STEP:{key}|{label}")

    eng_name, service = resolve_engine(engine)
    step("start", f"Iniciando · {nicho} em {cidade} · meta {meta} leads · motor {eng_name}")
    log(
        f"Critérios: nota ≥ {nota_min}, avaliações ≥ {aval_min}, "
        f"site ativo ruim (≥2 problemas) + e-mail público"
    )

    step("search", "1/4 Buscando negócios no Google Maps (API Places/Apify)…")
    if eng_name == "google_places":
        candidates = service.search(
            nicho, cidade, max_results=max(meta * 5, 40), radius_km=raio_km, on_progress=log
        )
    else:
        candidates = service.search_sync(
            nicho, cidade, max_results=max(meta * 5, 40), on_progress=log
        )

    log(f"COUNT:candidates={len(candidates)}")
    step("filter", f"2/4 {len(candidates)} lugares encontrados — filtrando potencial e website…")

    # Pre-filter: score / reviews / has site (cheap, before HTTP qualify)
    to_qualify = []
    skipped_potential = 0
    skipped_no_site = 0
    for p in candidates:
        nota = p.get("nota")
        aval = p.get("avaliacoes") or 0
        if nota is None or nota < nota_min or aval < aval_min:
            skipped_potential += 1
            continue
        if not (p.get("site") or "").strip():
            skipped_no_site += 1
            continue
        to_qualify.append(p)

    log(
        f"Após filtro Maps: {len(to_qualify)} para analisar site "
        f"(↓{skipped_potential} nota/aval · ↓{skipped_no_site} sem website)"
    )
    log(f"COUNT:to_qualify={len(to_qualify)}")

    step("qualify", f"3/4 Analisando sites um a um (até meta {meta})…")
    qualified = []
    discarded = []
    discard_reasons: dict[str, int] = {}

    for i, p in enumerate(to_qualify):
        if len(qualified) >= meta:
            log(f"Meta de {meta} leads atingida — parando análise.")
            break
        log(f"  · ({i+1}/{len(to_qualify)}) {p.get('nome')} — abrindo site…")
        site = p.get("site") or ""
        site_info = (
            qualify_site(site)
            if site
            else {"ok": False, "motivos": ["sem website"], "email": "", "whatsapp": ""}
        )
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
            log(f"  ✓ LEAD #{len(qualified)}: {row['nome']} — {motivo}")
            log(f"COUNT:qualified={len(qualified)}")
        else:
            discarded.append(row)
            _upsert_lead(row, protect_advanced=True)
            key = (motivo or "outro").split(";")[0].strip()[:60]
            discard_reasons[key] = discard_reasons.get(key, 0) + 1
            log(f"  ✗ descartado: {row['nome']} — {motivo}")
            log(f"COUNT:discarded={len(discarded)}")

    step("save", "4/4 Resumo da prospecção")
    log(
        f"RESULTADO: {len(candidates)} no Maps → {len(to_qualify)} analisados → "
        f"{len(qualified)} leads ouro · {len(discarded)} descartados"
    )
    if discard_reasons:
        top = sorted(discard_reasons.items(), key=lambda x: -x[1])[:5]
        log("Principais motivos de descarte: " + " · ".join(f"{k} ({v})" for k, v in top))
    if qualified:
        log("Leads salvos: " + ", ".join(q["nome"] for q in qualified))
    else:
        log("Nenhum lead ouro nesta rodada — tente outro nicho/cidade ou afrouxar nota/avaliações.")
    step("done", "Concluído")

    return {
        "engine": eng_name,
        "nicho": nicho,
        "cidade": cidade,
        "meta": meta,
        "qualified": [{"slug": q["slug"], "nome": q["nome"], "motivo": q["motivo"]} for q in qualified],
        "qualified_count": len(qualified),
        "discarded_count": len(discarded),
        "candidates": len(candidates),
        "to_qualify": len(to_qualify),
        "skipped_potential": skipped_potential,
        "skipped_no_site": skipped_no_site,
        "discard_reasons": discard_reasons,
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
