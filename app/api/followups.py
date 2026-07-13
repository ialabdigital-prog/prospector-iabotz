from __future__ import annotations

from flask import Blueprint, jsonify

from app.followups import followup_candidates

followups_bp = Blueprint("followups", __name__, url_prefix="/api/followups")


@followups_bp.get("")
def list_due_followups():
    leads = followup_candidates()
    return jsonify({"count": len(leads), "leads": leads})
