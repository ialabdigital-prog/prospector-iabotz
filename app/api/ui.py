from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for

ui_bp = Blueprint("ui", __name__)


@ui_bp.get("/")
def home():
    return render_template("app.html")


@ui_bp.get("/app")
def app_page():
    return render_template("app.html")
