from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.llm.router import complete, list_providers

providers_bp = Blueprint("providers", __name__, url_prefix="/api/providers")


@providers_bp.get("")
def providers():
    return jsonify(list_providers())


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
