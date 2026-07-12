"""Prospector IA Botz — painel admin Flask."""
from __future__ import annotations

from flask import Flask

from app.config import BASE_DIR, load_config
from app.db import init_db


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "app" / "templates"),
        static_folder=str(BASE_DIR / "app" / "static"),
        static_url_path="/static",
    )
    cfg = load_config()
    secret = cfg.get("auth", {}).get("secret_key") or "prospector-dev-change-me"
    app.secret_key = secret
    app.config["PROSPECTOR_CONFIG"] = cfg

    init_db()

    from app.auth import auth_bp, login_required
    from app.api.leads import leads_bp
    from app.api.jobs import jobs_bp
    from app.api.config_api import config_bp
    from app.api.providers import providers_bp
    from app.api.stats import stats_bp
    from app.api.ui import ui_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(providers_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(ui_bp)

    @app.get("/health")
    def health():
        return {"ok": True, "service": "prospector-iabotz"}

    # Protect API by default (auth_bp and health exempt via decorators/routes)
    @app.before_request
    def require_login():
        from flask import request, session, redirect, url_for

        path = request.path
        public = (
            path.startswith("/login")
            or path.startswith("/logout")
            or path.startswith("/health")
            or path.startswith("/static/")
        )
        if public:
            return None
        if session.get("user_id"):
            return None
        if path.startswith("/api/"):
            return {"error": "unauthorized"}, 401
        return redirect(url_for("auth.login", next=path))

    return app
