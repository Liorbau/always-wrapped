"""HTML shells. Every byte of data these pages show arrives over the JSON API."""

from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def dashboard():
    return render_template("index.html")


@pages_bp.route("/agents")
def observatory():
    return render_template("agents.html")
