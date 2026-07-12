from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.config import get_maps_keys, mask_config, merge_config
from app.discovery import engine_status
from app.discovery.apify_client import ApifyGoogleMapsService
from app.discovery.places import GooglePlacesService

config_bp = Blueprint("config_api", __name__, url_prefix="/api/config")


@config_bp.get("")
def get_config():
    return jsonify(mask_config())


@config_bp.post("")
def save_config():
    data = request.json or {}
    merge_config(data)
    return jsonify({"success": True, "config": mask_config()})


@config_bp.get("/engines")
def engines():
    return jsonify(engine_status())


@config_bp.post("/engines/test")
def test_engine():
    data = request.json or {}
    which = data.get("engine") or "google_places"
    google_key, apify_key = get_maps_keys()
    if which in ("google_places", "places"):
        if not google_key:
            return jsonify({"success": False, "message": "google_maps_api_key vazia"})
        return jsonify(GooglePlacesService(google_key).test_connection())
    if which == "apify":
        if not apify_key:
            return jsonify({"success": False, "message": "apify_api_key vazia"})
        return jsonify(ApifyGoogleMapsService(apify_key).test_connection())
    return jsonify({"success": False, "message": "engine inválido"}), 400


@config_bp.get("/integrations")
def integrations_status():
    """Status claro de cada integração do funil."""
    from app.config import load_config

    cfg = load_config()
    maps = cfg.get("maps") or {}
    cf = cfg.get("cloudflare") or {}
    aa = cfg.get("aapanel") or {}
    composio = cfg.get("composio") or {}
    llm = cfg.get("llm") or {}
    envio = cfg.get("envio") or {}
    return jsonify(
        {
            "funnel": [
                {
                    "id": "maps",
                    "label": "1. Google Maps",
                    "ready": bool(maps.get("google_maps_api_key") or maps.get("apify_api_key")),
                    "detail": f"Engine: {maps.get('engine') or 'auto'}",
                },
                {
                    "id": "redesign",
                    "label": "2. Redesign (LLM)",
                    "ready": bool(llm.get("openrouter_api_key")) or True,
                    "detail": f"Provider: {llm.get('default_provider') or 'openrouter'}",
                },
                {
                    "id": "aapanel",
                    "label": "3. Publicar aaPanel",
                    "ready": bool(aa.get("dominio_base")),
                    "detail": aa.get("dominio_base") or "domínio base não definido",
                },
                {
                    "id": "cloudflare",
                    "label": "4. DNS Cloudflare",
                    "ready": bool(cf.get("api_key") or cf.get("api_token")),
                    "detail": f"Zona: {cf.get('zone') or '—'}",
                },
                {
                    "id": "gmail",
                    "label": "5. Gmail (Composio)",
                    "ready": bool(composio.get("api_key")),
                    "detail": (
                        f"Modo envio: {envio.get('modo') or 'rascunho'}"
                        + (
                            " · Composio conectado"
                            if composio.get("api_key")
                            else " · sem Composio → draft local em drafts/"
                        )
                    ),
                },
            ]
        }
    )


@config_bp.post("/cloudflare/test")
def test_cloudflare():
    from app.config import load_config
    import sys
    from pathlib import Path

    cfg = load_config().get("cloudflare") or {}
    if not (cfg.get("api_key") or cfg.get("api_token")):
        return jsonify({"success": False, "message": "Cloudflare sem api_key/api_token"})
    ref = Path(__file__).resolve().parents[2] / "skills" / "deploy-aapanel" / "references"
    sys.path.insert(0, str(ref))
    try:
        from cloudflare_client import CloudflareClient

        if cfg.get("api_token"):
            client = CloudflareClient(
                api_token=cfg["api_token"],
                zone_name=cfg.get("zone") or "iabotz.online",
            )
        else:
            client = CloudflareClient(
                api_key=cfg["api_key"],
                api_email=cfg.get("email") or "",
                zone_name=cfg.get("zone") or "iabotz.online",
            )
        records = client.list_records()
        return jsonify(
            {
                "success": True,
                "message": f"OK — zona {cfg.get('zone')} com {len(records)} CNAMEs",
                "count": len(records),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
