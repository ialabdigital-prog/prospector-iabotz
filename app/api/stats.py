from __future__ import annotations

from flask import Blueprint, jsonify

from app.db import db

stats_bp = Blueprint("stats", __name__, url_prefix="/api/stats")


@stats_bp.get("")
def stats():
    with db() as conn:
        c = conn.cursor()
        out = {
            "total": c.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
            "novo": c.execute("SELECT COUNT(*) FROM leads WHERE status='novo'").fetchone()[0],
            "redesenhado": c.execute(
                "SELECT COUNT(*) FROM leads WHERE status='redesenhado'"
            ).fetchone()[0],
            "publicado": c.execute(
                "SELECT COUNT(*) FROM leads WHERE status='publicado'"
            ).fetchone()[0],
            "proposta": c.execute(
                "SELECT COUNT(*) FROM leads WHERE status='proposta'"
            ).fetchone()[0],
            "fechado": c.execute(
                "SELECT COUNT(*) FROM leads WHERE status='fechado'"
            ).fetchone()[0],
            "descartado": c.execute(
                "SELECT COUNT(*) FROM leads WHERE status='descartado'"
            ).fetchone()[0],
            "receita": c.execute(
                "SELECT COALESCE(SUM(valor),0) FROM leads WHERE status='fechado'"
            ).fetchone()[0],
            "mrr": c.execute(
                "SELECT COALESCE(SUM(manutencao),0) FROM leads WHERE status='fechado'"
            ).fetchone()[0],
            "jobs_running": c.execute(
                "SELECT COUNT(*) FROM jobs WHERE status='running'"
            ).fetchone()[0],
            "jobs_queued": c.execute(
                "SELECT COUNT(*) FROM jobs WHERE status='queued'"
            ).fetchone()[0],
        }
    return jsonify(out)
