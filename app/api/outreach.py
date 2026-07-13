"""Outreach history for email and WhatsApp."""
from __future__ import annotations

from flask import Blueprint, jsonify

from app.db import db

outreach_bp = Blueprint("outreach", __name__, url_prefix="/api/outreach")


@outreach_bp.get("")
def list_outreach():
    with db() as conn:
        rows = conn.execute(
            """SELECT o.*, l.nome
               FROM outreach_log o
               JOIN leads l ON l.slug=o.lead_slug
               ORDER BY o.created_at DESC, o.id DESC
               LIMIT 200"""
        ).fetchall()
    return jsonify([dict(row) for row in rows])
