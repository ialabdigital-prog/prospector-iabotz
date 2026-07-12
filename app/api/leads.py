from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.db import db, row_to_dict

leads_bp = Blueprint("leads", __name__, url_prefix="/api/leads")

ALLOWED = [
    "nome",
    "nicho",
    "cidade",
    "nota",
    "avaliacoes",
    "email",
    "telefone",
    "whatsapp",
    "siteAntigo",
    "motivo",
    "status",
    "urlNova",
    "dataProposta",
    "valor",
    "obs",
    "contratoStatus",
    "contratoEm",
    "manutencao",
    "pago",
    "docCliente",
    "endCliente",
    "placeId",
    "engine",
]


@leads_bp.get("")
def list_leads():
    status = request.args.get("status")
    q = (request.args.get("q") or "").strip()
    with db() as conn:
        sql = "SELECT * FROM leads WHERE 1=1"
        params = []
        if status:
            sql += " AND status=?"
            params.append(status)
        if q:
            sql += " AND (nome LIKE ? OR email LIKE ? OR cidade LIKE ? OR nicho LIKE ?)"
            like = f"%{q}%"
            params.extend([like, like, like, like])
        sql += " ORDER BY atualizado DESC"
        rows = conn.execute(sql, params).fetchall()
    return jsonify([dict(r) for r in rows])


@leads_bp.post("")
def upsert_lead():
    data = request.json or {}
    nome = data.get("nome") or ""
    slug = data.get("slug") or nome.lower().replace(" ", "-")
    if not slug:
        return jsonify({"error": "slug/nome obrigatório"}), 400
    cols = ["slug"] + [f for f in ALLOWED if f in data]
    placeholders = ",".join("?" for _ in cols)
    values = [slug] + [data.get(f) for f in cols if f != "slug"]
    updates = ", ".join(f"{f}=excluded.{f}" for f in cols if f != "slug")
    with db() as conn:
        conn.execute(
            f"""INSERT INTO leads ({','.join(cols)}, atualizado)
                VALUES ({placeholders}, datetime('now','localtime'))
                ON CONFLICT(slug) DO UPDATE SET {updates}, atualizado=datetime('now','localtime')""",
            values,
        )
    return jsonify({"success": True, "slug": slug})


@leads_bp.put("/<slug>")
def update_lead(slug: str):
    data = request.json or {}
    sets, vals = [], []
    for f in ALLOWED:
        if f in data:
            sets.append(f"{f}=?")
            vals.append(data[f])
    if not sets:
        return jsonify({"success": True})
    sets.append("atualizado=datetime('now','localtime')")
    vals.append(slug)
    with db() as conn:
        conn.execute(f"UPDATE leads SET {','.join(sets)} WHERE slug=?", vals)
    return jsonify({"success": True})


@leads_bp.delete("/<slug>")
def delete_lead(slug: str):
    with db() as conn:
        conn.execute("DELETE FROM leads WHERE slug=?", (slug,))
    return jsonify({"success": True})


@leads_bp.post("/bulk")
def bulk():
    data = request.json or {}
    with db() as conn:
        for item in data.get("updates") or []:
            slug = item.pop("slug", None)
            if not slug:
                continue
            sets, vals = [], []
            for k, v in item.items():
                if k in ALLOWED:
                    sets.append(f"{k}=?")
                    vals.append(v)
            if sets:
                sets.append("atualizado=datetime('now','localtime')")
                vals.append(slug)
                conn.execute(f"UPDATE leads SET {','.join(sets)} WHERE slug=?", vals)
    return jsonify({"success": True})


@leads_bp.get("/<slug>")
def get_lead(slug: str):
    with db() as conn:
        row = row_to_dict(conn.execute("SELECT * FROM leads WHERE slug=?", (slug,)).fetchone())
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(row)
