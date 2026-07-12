from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.config import load_config
from app.llm import openrouter
from app.llm.router import complete, list_providers

providers_bp = Blueprint("providers", __name__, url_prefix="/api/providers")


@providers_bp.get("")
def providers():
    return jsonify(list_providers())


@providers_bp.get("/openrouter/models")
def openrouter_models():
    """Lista modelos OpenRouter para o seletor da UI."""
    cfg = load_config()
    llm = cfg.get("llm") or {}
    # Aceita key no query só se a salva estiver mascarada/vazia no client — preferimos a do server
    key = (llm.get("openrouter_api_key") or "").strip()
    body_key = (request.args.get("key") or "").strip()
    if body_key and body_key != "***":
        key = body_key
    if not key:
        return jsonify(
            {
                "success": False,
                "models": [],
                "message": "Cole a OpenRouter API Key e salve, ou passe ?key=",
            }
        ), 400
    q = request.args.get("q") or ""
    try:
        models = openrouter.list_models(key, q=q or None)
        return jsonify(
            {
                "success": True,
                "count": len(models),
                "models": models,
                "default": llm.get("openrouter_model") or "openai/gpt-4o-mini",
            }
        )
    except Exception as e:
        return jsonify({"success": False, "models": [], "message": str(e)}), 400


@providers_bp.post("/test")
def test_provider():
    data = request.json or {}
    provider = data.get("provider") or "openrouter"
    try:
        text = complete(
            provider,
            prompt=data.get("prompt") or "Responda só: ok",
            system="Resposta curta.",
            model=data.get("model"),
        )
        return jsonify({"success": True, "reply": text[:500]})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400
