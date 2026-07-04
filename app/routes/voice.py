"""Voice Studio — Browser STT (Web Speech API) + Free gTTS Text-to-Speech."""
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, current_app, url_for
from flask_login import login_required, current_user

from ..extensions import db
from ..models import VoiceFile, log_history
from ..services.ai import text_to_speech

bp = Blueprint("voice", __name__)


@bp.route("/")
@login_required
def index():
    voices = (
        VoiceFile.query.filter_by(user_id=current_user.id)
        .order_by(VoiceFile.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template("dashboard/voice.html", voices=voices)


@bp.route("/stt", methods=["POST"])
@login_required
def stt():
    """STT is now handled client-side via the browser Web Speech API."""
    return jsonify({
        "ok": False,
        "error": "Speech-to-text is handled in the browser. No server upload needed.",
    }), 400


@bp.route("/tts", methods=["POST"])
@login_required
def tts():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    voice = (data.get("voice") or "professional").lower()
    if not text:
        return jsonify({"ok": False, "error": "Text is empty."}), 400
    if len(text) > 5000:
        return jsonify({"ok": False, "error": "Text is too long (max 5000 characters)."}), 400

    res = text_to_speech(text, voice, current_app.config["GENERATED_FOLDER"])
    if res["ok"]:
        vf = VoiceFile(
            user_id=current_user.id, kind="tts", text=text,
            voice=voice, file_path=res["data"],
        )
        db.session.add(vf)
        db.session.commit()
        log_history(current_user.id, "voice", text[:60], vf.id)
        res["url"] = url_for("static", filename=f"generated/{res['data']}")
    return jsonify(res)
