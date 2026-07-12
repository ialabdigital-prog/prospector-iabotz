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
