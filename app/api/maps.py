"""Location lookup for the prospecting map."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.config import get_maps_keys
from app.discovery.places import GEOCODING_URL

import requests

maps_bp = Blueprint("maps_api", __name__, url_prefix="/api/maps")


@maps_bp.get("/locations")
def locations():
    query = (request.args.get("q") or "").strip()
    if len(query) < 3:
        return jsonify([])
    key, _ = get_maps_keys()
    if not key:
        return jsonify({"error": "Google Maps API não configurada"}), 400
    try:
        response = requests.get(
            GEOCODING_URL,
            params={"address": query, "key": key, "language": "pt-BR", "region": "br"},
            timeout=12,
        )
        data = response.json()
        results = []
        for item in (data.get("results") or [])[:6]:
            loc = (item.get("geometry") or {}).get("location") or {}
            if "lat" in loc and "lng" in loc:
                results.append({
                    "label": item.get("formatted_address") or query,
                    "lat": float(loc["lat"]),
                    "lng": float(loc["lng"]),
                    "types": item.get("types") or [],
                })
        return jsonify(results)
    except Exception as exc:
        return jsonify({"error": f"Falha ao buscar local: {exc}"}), 502
