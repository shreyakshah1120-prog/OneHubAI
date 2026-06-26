"""User settings."""
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from ..extensions import db

bp = Blueprint("settings", __name__)


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        section = request.form.get("section")
        if section == "profile":
            current_user.name = (request.form.get("name") or current_user.name).strip()
            avatar = request.files.get("avatar")
            if avatar and avatar.filename:
                safe = secure_filename(avatar.filename)
                fname = f"avatar_{current_user.id}_{safe}"
                avatar.save(Path(current_app.config["UPLOAD_FOLDER"]) / fname)
                current_user.avatar = fname
        elif section == "preferences":
            current_user.theme = request.form.get("theme", "dark")
            current_user.language = request.form.get("language", "en")
            current_user.voice_pref = request.form.get("voice_pref", "professional")
            current_user.notifications = request.form.get("notifications") == "on"
        elif section == "password":
            current = request.form.get("current") or ""
            new = request.form.get("new") or ""
            confirm_new = request.form.get("confirm_new") or ""
            if not current_user.check_password(current):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("settings.index"))
            if len(new) < 6:
                flash("New password must be 6+ characters.", "danger")
                return redirect(url_for("settings.index"))
            if new != confirm_new:
                flash("New passwords do not match.", "danger")
                return redirect(url_for("settings.index"))
            current_user.set_password(new)
        db.session.commit()
        flash("Settings updated.", "success")
        return redirect(url_for("settings.index"))
    return render_template("dashboard/settings.html")


@bp.route("/theme", methods=["POST"])
@login_required
def set_theme():
    from flask import request, jsonify
    data = request.get_json(silent=True) or {}
    theme = data.get("theme", "dark")
    if theme in ("dark", "light"):
        current_user.theme = theme
        db.session.commit()
    return jsonify({"ok": True})
