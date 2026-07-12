"""Session auth — username/password."""
from __future__ import annotations

import os
from functools import wraps

from flask import Blueprint, redirect, render_template, request, session, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import db, row_to_dict

auth_bp = Blueprint("auth", __name__)


def ensure_admin_user() -> None:
    """Create admin from env or defaults if no users exist."""
    with db() as conn:
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if n > 0:
            return
        username = os.environ.get("PROSPECTOR_ADMIN_USER", "admin")
        password = os.environ.get("PROSPECTOR_ADMIN_PASS", "prospector2026")
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return {"error": "unauthorized"}, 401
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    ensure_admin_user()
    if session.get("user_id"):
        return redirect(url_for("ui.home"))
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        with db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            nxt = request.args.get("next") or url_for("ui.home")
            return redirect(nxt)
        error = "Usuário ou senha inválidos"
    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


def current_user() -> dict | None:
    uid = session.get("user_id")
    if not uid:
        return None
    with db() as conn:
        return row_to_dict(
            conn.execute("SELECT id, username, created_at FROM users WHERE id=?", (uid,)).fetchone()
        )
