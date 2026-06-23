"""Public marketing routes."""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

bp = Blueprint("main", __name__)


@bp.route("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    return render_template("landing.html")


@bp.route("/pricing")
def pricing():
    return render_template("landing.html", anchor="pricing")
