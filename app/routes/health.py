"""Health Assistant — anatomy explorer + report analysis."""
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user

from ..extensions import db
from ..models import HealthReport, log_history
from ..services.ai import chat_any
from ..services.files import extract_text

bp = Blueprint("health", __name__)

ANATOMY_PARTS = [
    "Brain", "Heart", "Lungs", "Liver", "Kidneys", "Stomach", "Intestines",
    "Skeleton", "Spine", "Muscles", "Nervous System", "Digestive System",
    "Skin", "Eyes", "Ears", "Reproductive System",
]


@bp.route("/")
@login_required
def index():
    reports = (
        HealthReport.query.filter_by(user_id=current_user.id)
        .order_by(HealthReport.created_at.desc())
        .all()
    )
    return render_template("dashboard/health.html", reports=reports, parts=ANATOMY_PARTS)


@bp.route("/part", methods=["POST"])
@login_required
def part():
    data = request.get_json(silent=True) or {}
    part = (data.get("part") or "").strip()

    return jsonify({
        "ok": True,
        "selected": part
    })


@bp.route("/analyze", methods=["POST"])
@login_required
def analyze():
    age = request.form.get("age", type=int)
    gender = request.form.get("gender")
    weight = request.form.get("weight", type=float)
    height = request.form.get("height", type=float)
    symptoms = (request.form.get("symptoms") or "").strip()
    file = request.files.get("report")

    file_text = ""
    saved_name = None
    if file and file.filename:
        safe = secure_filename(file.filename)
        p = Path(current_app.config["UPLOAD_FOLDER"]) / f"health_{current_user.id}_{safe}"
        file.save(p)
        saved_name = safe
        ext = Path(safe).suffix.lower()
        if ext in {".pdf", ".docx", ".txt"}:
            file_text = extract_text(str(p))[:6000]
        else:
            file_text = "[Image/scan uploaded — visual analysis not performed in this version.]"

    prompt = (
        "You are a careful medical assistant. Provide a SIMPLIFIED explanation of the "
        "patient profile and any attached report. Output markdown with: Overview, "
        "Key Findings, Possible Concerns, Lifestyle Advice, When to See a Doctor. "
        "Always remind the user this is informational, not a diagnosis.\n\n"
        f"PATIENT — age: {age}, gender: {gender}, weight: {weight} kg, height: {height} cm.\n"
        f"SYMPTOMS: {symptoms or 'none reported'}\n\n"
        f"REPORT EXCERPT:\n{file_text or '[no report uploaded]'}"
    )
    res = chat_any(prompt, "gpt")
    analysis = res["data"] if res["ok"] else (res.get("error") or "Analysis unavailable.")

    h = HealthReport(
        user_id=current_user.id, age=age, gender=gender,
        weight=weight, height=height, symptoms=symptoms,
        uploaded_file=saved_name, analysis=analysis,
    )
    db.session.add(h)
    db.session.commit()
    log_history(current_user.id, "health", f"Health check — {symptoms[:40] or 'general'}", h.id)
    return jsonify({"ok": True, "analysis": analysis, "id": h.id})
