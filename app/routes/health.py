"""Health Assistant routes for anatomy, consultation, reports, and history."""
from __future__ import annotations

import io
import json
import textwrap
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request, send_file, session
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import HealthReport, log_history
from ..services.ai import (
    analyze_medical_image,
    detect_emergency,
    generate_followup_questions,
    generate_health_report,
    get_body_part_info,
)
from ..services.files import extract_text

bp = Blueprint("health", __name__)

LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "gu": "Gujarati",
}

INTERNAL_PARTS = [
    "Brain", "Heart", "Lungs", "Liver", "Kidney", "Stomach", "Pancreas",
    "Intestine", "Spine", "Thyroid", "Bladder", "Blood Vessels",
]

EXTERNAL_PARTS = [
    "Skin", "Eye", "Ear", "Head", "Neck", "Shoulder", "Chest", "Abdomen",
    "Back", "Arm", "Hand", "Hip", "Leg", "Knee", "Foot",
]


def _language_code() -> str:
    code = (current_user.language or "en").strip().lower()
    return code if code in LANGUAGES else "en"


def _language_name() -> str:
    return LANGUAGES.get(_language_code(), "English")


def _json_loads(raw: str | None, fallback):
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _consultations() -> dict:
    data = session.get("health_consultations")
    if not isinstance(data, dict):
        data = {}
        session["health_consultations"] = data
    return data


def _report_to_cards(report: HealthReport) -> dict:
    analysis = _json_loads(report.analysis, {})
    symptoms = _json_loads(report.symptoms, {})
    return {
        "id": report.id,
        "organ": symptoms.get("organ") or analysis.get("selected_organ") or "General",
        "summary": symptoms.get("chief_complaint") or symptoms.get("summary") or "Health consultation",
        "urgency": analysis.get("urgency", "Routine"),
        "confidence": analysis.get("confidence", "Moderate"),
        "created_at": report.created_at.strftime("%b %d, %Y %I:%M %p"),
        "has_upload": bool(report.uploaded_file),
    }


@bp.route("/")
@login_required
def index():
    reports = (
        HealthReport.query.filter_by(user_id=current_user.id)
        .order_by(HealthReport.created_at.desc())
        .all()
    )
    return render_template(
        "dashboard/health.html",
        reports=[_report_to_cards(r) for r in reports],
        internal_parts=INTERNAL_PARTS,
        external_parts=EXTERNAL_PARTS,
        language_code=_language_code(),
        language_name=_language_name(),
        language_missing=not session.get("health_language_confirmed"),
    )


@bp.route("/language", methods=["POST"])
@login_required
def save_language():
    data = request.get_json(silent=True) or {}
    code = (data.get("language") or "").strip().lower()
    if code not in LANGUAGES:
        return jsonify({"ok": False, "error": "Choose English, Hindi, or Gujarati."}), 400
    current_user.language = code
    session["health_language_confirmed"] = True
    db.session.commit()
    return jsonify({"ok": True, "language": code, "label": LANGUAGES[code]})


@bp.route("/profile", methods=["POST"])
@login_required
def profile_metrics():
    data = request.get_json(silent=True) or {}
    weight = _safe_float(data.get("weight"))
    height = _safe_float(data.get("height"))
    bmi = None
    category = "Not available"
    healthy_weight = "Add height and weight"
    water = "Add weight"
    calories = "Add age, gender, height, and weight"

    if weight and height:
        meters = height / 100
        bmi = round(weight / (meters * meters), 1)
        if bmi < 18.5:
            category = "Underweight"
        elif bmi < 25:
            category = "Healthy range"
        elif bmi < 30:
            category = "Overweight"
        else:
            category = "High BMI"
        healthy_weight = f"{round(18.5 * meters * meters, 1)}-{round(24.9 * meters * meters, 1)} kg"
        water = f"{round(weight * 0.035, 1)} L/day"

    age = _safe_float(data.get("age"))
    gender = (data.get("gender") or "").lower()
    if age and weight and height:
        base = 10 * weight + 6.25 * height - 5 * age
        bmr = base + (5 if gender == "male" else -161)
        calories = f"{round(bmr * 1.35)} kcal/day"

    return jsonify({
        "ok": True,
        "metrics": {
            "bmi": bmi or "--",
            "category": category,
            "healthy_weight": healthy_weight,
            "water": water,
            "calories": calories,
        },
    })


@bp.route("/part", methods=["POST"])
@login_required
def part():
    data = request.get_json(silent=True) or {}
    organ = (data.get("part") or "").strip()
    if not organ:
        return jsonify({"ok": False, "error": "Select a body part first."}), 400
    res = get_body_part_info(organ, _language_name())
    return jsonify({"ok": True, "selected": organ, "data": res["data"], "provider": res.get("provider")})


@bp.route("/consult/start", methods=["POST"])
@login_required
def consult_start():
    data = request.get_json(silent=True) or {}
    organ = (data.get("organ") or "General").strip()
    profile = data.get("profile") or {}
    cid = uuid.uuid4().hex
    _consultations()[cid] = {
        "organ": organ,
        "profile": profile,
        "language": _language_name(),
        "transcript": [],
        "asked": [],
        "report_text_path": "",
        "uploaded_file": None,
        "created_at": datetime.utcnow().isoformat(),
    }
    session.modified = True
    return jsonify({
        "ok": True,
        "consultation_id": cid,
        "question": f"Describe your problem with your {organ}. Include when it started and what you feel.",
    })


@bp.route("/consult/message", methods=["POST"])
@login_required
def consult_message():
    cid = request.form.get("consultation_id") or ""
    answer = (request.form.get("answer") or "").strip()
    force_report = request.form.get("force_report") == "1"
    consultations = _consultations()
    consult = consultations.get(cid)
    if not consult:
        return jsonify({"ok": False, "error": "Consultation expired. Please select the body part again."}), 400
    if not answer and not request.files.get("report"):
        return jsonify({"ok": False, "error": "Please describe what you are feeling."}), 400

    uploaded = _handle_upload(request.files.get("report"), consult)
    if answer:
        consult["transcript"].append({"answer": answer, "time": datetime.utcnow().isoformat()})

    emergency = detect_emergency(consult["organ"], consult["transcript"], _language_name())
    enough = force_report or emergency.get("is_emergency") or len(consult["transcript"]) >= 5

    if not enough:
        q_res = generate_followup_questions(
            consult["organ"],
            consult["profile"],
            consult["transcript"],
            consult["asked"],
            _language_name(),
        )
        question = q_res["data"]
        consult["asked"].append(question)
        session.modified = True
        return jsonify({
            "ok": True,
            "done": False,
            "question": question,
            "emergency": emergency,
            "uploaded": uploaded,
        })

    report_res = generate_health_report(
        consult["organ"],
        consult["profile"],
        consult["transcript"],
        _read_report_text(consult),
        _language_name(),
        emergency,
    )
    report = report_res["data"]
    saved = _save_report(consult, report)
    consultations.pop(cid, None)
    session.modified = True
    return jsonify({
        "ok": True,
        "done": True,
        "report": report,
        "report_id": saved.id,
        "emergency": emergency,
        "uploaded": uploaded,
    })


@bp.route("/report/<int:report_id>")
@login_required
def report_detail(report_id: int):
    report = HealthReport.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()
    return jsonify({
        "ok": True,
        "report": _json_loads(report.analysis, {}),
        "meta": _report_to_cards(report),
        "transcript": _json_loads(report.symptoms, {}).get("transcript", []),
    })


@bp.route("/report/<int:report_id>/delete", methods=["POST"])
@login_required
def report_delete(report_id: int):
    report = HealthReport.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()
    db.session.delete(report)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/report/<int:report_id>/pdf")
@login_required
def report_pdf(report_id: int):
    report = HealthReport.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()
    payload = _json_loads(report.analysis, {})
    meta = _report_to_cards(report)
    pdf = _simple_pdf_bytes(meta, payload)
    return send_file(
        io.BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"onehubai-health-report-{report.id}.pdf",
    )


def _save_report(consult: dict, report: dict) -> HealthReport:
    profile = consult.get("profile") or {}
    transcript = consult.get("transcript") or []
    chief = transcript[0]["answer"] if transcript else "General consultation"
    symptoms_payload = {
        "organ": consult.get("organ"),
        "chief_complaint": chief,
        "summary": chief[:160],
        "transcript": transcript,
        "questions": consult.get("asked", []),
    }
    item = HealthReport(
        user_id=current_user.id,
        age=_safe_int(profile.get("age")),
        gender=profile.get("gender"),
        weight=_safe_float(profile.get("weight")),
        height=_safe_float(profile.get("height")),
        symptoms=json.dumps(symptoms_payload),
        uploaded_file=consult.get("uploaded_file"),
        analysis=json.dumps(report),
    )
    db.session.add(item)
    db.session.commit()
    log_history(current_user.id, "health", f"Health consultation - {consult.get('organ', 'General')}", item.id)
    return item


def _handle_upload(file, consult: dict) -> dict | None:
    if not file or not file.filename:
        return None
    safe = secure_filename(file.filename)
    suffix = Path(safe).suffix.lower()
    allowed = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".txt", ".docx"}
    if suffix not in allowed:
        return {"ok": False, "message": "Unsupported file type."}
    path = Path(current_app.config["UPLOAD_FOLDER"]) / f"health_{current_user.id}_{uuid.uuid4().hex}_{safe}"
    file.save(path)
    consult["uploaded_file"] = path.name
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        res = analyze_medical_image(str(path), consult.get("organ", "General"), _language_name())
        report_text = res.get("data") or "Image uploaded, but visual analysis was unavailable."
    else:
        report_text = extract_text(str(path))[:8000]
    text_name = f"health_extract_{current_user.id}_{uuid.uuid4().hex}.txt"
    text_path = Path(current_app.config["UPLOAD_FOLDER"]) / text_name
    text_path.write_text(report_text[:8000], encoding="utf-8")
    consult["report_text_path"] = text_name
    return {"ok": True, "filename": safe}


def _read_report_text(consult: dict) -> str:
    name = consult.get("report_text_path")
    if not name:
        return ""
    path = Path(current_app.config["UPLOAD_FOLDER"]) / secure_filename(name)
    try:
        return path.read_text(encoding="utf-8")[:8000]
    except OSError:
        return ""


def _safe_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    try:
        return int(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _simple_pdf_bytes(meta: dict, payload: dict) -> bytes:
    lines = [
        "OneHubAI Health Report",
        f"Body part: {meta.get('organ', 'General')}",
        f"Date: {meta.get('created_at', '')}",
        f"Urgency: {payload.get('urgency', 'Not stated')}",
        f"Confidence: {payload.get('confidence', 'Not stated')}",
        "",
    ]
    for key in ["overview", "possible_causes", "home_remedies", "lifestyle_advice", "when_to_see_doctor", "emergency_warning_signs", "disclaimer"]:
        value = payload.get(key, "")
        if isinstance(value, list):
            value = "; ".join(str(v) for v in value)
        lines.append(key.replace("_", " ").title())
        lines.extend(textwrap.wrap(str(value), width=82) or [""])
        lines.append("")
    text = "\n".join(lines)
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream_lines = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
    for line in escaped.splitlines()[:58]:
        stream_lines.append(f"({line}) Tj")
        stream_lines.append("T*")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = [b"%PDF-1.4\n"]
    offsets = []
    for idx, obj in enumerate(objects, start=1):
        offsets.append(sum(len(p) for p in pdf))
        pdf.append(f"{idx} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = sum(len(p) for p in pdf)
    pdf.append(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        pdf.append(f"{off:010d} 00000 n \n".encode())
    pdf.append(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return b"".join(pdf)
