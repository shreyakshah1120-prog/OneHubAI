"""AI Studio — prompt enhancement + multi-model chat."""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Chat, log_history
from ..services.ai import enhance_prompt, chat_any

bp = Blueprint("ai_studio", __name__)


@bp.route("/")
@login_required
def index():
    chats = (
        Chat.query.filter_by(user_id=current_user.id)
        .order_by(Chat.created_at.desc())
        .limit(20)
        .all()
    )
    from ..models import GeneratedImage  # add this import at top if not already there

    images = (
        GeneratedImage.query.filter_by(user_id=current_user.id)
        .order_by(GeneratedImage.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template("dashboard/ai_studio.html", chats=chats, images=images)


@bp.route("/enhance", methods=["POST"])
@login_required
def enhance():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    res = enhance_prompt(prompt)
    return jsonify(res)


@bp.route("/generate", methods=["POST"])
@login_required
def generate():
    data = request.get_json(silent=True) or {}
    enhanced = (data.get("prompt") or "").strip()
    original = (data.get("original") or enhanced).strip()
    model = (data.get("model") or "gpt").lower()
    if not enhanced:
        return jsonify({"ok": False, "error": "Prompt is empty."}), 400

    res = chat_any(enhanced, model)
    if res["ok"]:
        chat = Chat(
            user_id=current_user.id,
            title=original[:80] or "Untitled Chat",
            model=model,
            original_prompt=original,
            enhanced_prompt=enhanced,
            response=res["data"],
        )
        db.session.add(chat)
        db.session.commit()
        log_history(current_user.id, "chat", chat.title, chat.id)
    return jsonify(res)


@bp.route("/compare", methods=["POST"])
@login_required
def compare():
    data = request.get_json(silent=True) or {}
    enhanced = (data.get("prompt") or "").strip()
    if not enhanced:
        return jsonify({"ok": False, "error": "Prompt is empty."}), 400
    return jsonify({
        "ok": True,
        "results": {
            "gpt": chat_any(enhanced, "gpt"),
            "claude": chat_any(enhanced, "claude"),
            "gemini": chat_any(enhanced, "gemini"),
        },
    })
