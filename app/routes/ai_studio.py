"""AI Studio — prompt enhancement + multi-model chat."""
import uuid
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Chat, ChatMessage, log_history
from ..services.ai import enhance_prompt, chat_any, chat_with_history, extract_upload_context

bp = Blueprint("ai_studio", __name__)


def _save_upload(file_storage):
    """Save an uploaded file (if any) and return (path, display_name) or (None, None)."""
    if not file_storage or not file_storage.filename:
        return None, None
    safe = secure_filename(file_storage.filename)
    fname = f"chat_{current_user.id}_{uuid.uuid4().hex}_{safe}"
    path = Path(current_app.config["UPLOAD_FOLDER"]) / fname
    file_storage.save(path)
    return str(path), safe


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


@bp.route("/chat/start", methods=["POST"])
@login_required
def chat_start():
    """First turn of a new conversation: refine the prompt (once), fold in
    any uploaded file's content, get a response, and create the Chat thread."""
    prompt = (request.form.get("prompt") or "").strip()
    model = (request.form.get("model") or "gemini").lower()
    upload = request.files.get("file")

    if not prompt and not upload:
        return jsonify({"ok": False, "error": "Please write a prompt or attach a file."}), 400

    # Step 1 — refine the prompt (only ever done on this first turn)
    enhance_res = enhance_prompt(prompt) if prompt else {"ok": False, "data": prompt}
    refined = enhance_res["data"] if enhance_res.get("data") else prompt

    # Step 2 — pull context out of the uploaded file, if any
    file_path, file_name = _save_upload(upload)
    file_context = extract_upload_context(file_path, prompt) if file_path else ""

    full_prompt = refined
    if file_context:
        full_prompt += f"\n\n[Attached file: {file_name}]\n{file_context}"

    # Step 3 — generate the first response
    res = chat_any(full_prompt, model)
    if not res["ok"]:
        return jsonify(res)

    chat = Chat(
        user_id=current_user.id,
        title=(prompt[:80] or file_name or "Untitled Chat"),
        model=model,
        original_prompt=prompt,
        enhanced_prompt=refined,
        response=res["data"],
    )
    db.session.add(chat)
    db.session.flush()  # get chat.id before adding messages
    db.session.add(ChatMessage(chat_id=chat.id, role="user", content=prompt, attachment_name=file_name))
    db.session.add(ChatMessage(chat_id=chat.id, role="assistant", content=res["data"]))
    db.session.commit()
    log_history(current_user.id, "chat", chat.title, chat.id)

    return jsonify({
        "ok": True,
        "chat_id": chat.id,
        "refined": refined,
        "data": res["data"],
        "provider": res.get("provider"),
    })


@bp.route("/chat/<int:chat_id>/message", methods=["POST"])
@login_required
def chat_message(chat_id):
    """Follow-up turn in an existing conversation. No prompt refinement here
    — just append to history and respond, optionally with a new file."""
    chat = Chat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({"ok": False, "error": "Chat not found."}), 404

    message = (request.form.get("message") or "").strip()
    upload = request.files.get("file")
    if not message and not upload:
        return jsonify({"ok": False, "error": "Please write a message or attach a file."}), 400

    file_path, file_name = _save_upload(upload)
    file_context = extract_upload_context(file_path, message) if file_path else ""

    history = [{"role": m.role, "content": m.content} for m in chat.messages]

    res = chat_with_history(
        history,
        message or f"(see attached file: {file_name})",
        model_choice=chat.model or "gemini",
        file_context=file_context,
        attachment_name=file_name,
    )
    if not res["ok"]:
        return jsonify(res)

    db.session.add(ChatMessage(chat_id=chat.id, role="user", content=message, attachment_name=file_name))
    db.session.add(ChatMessage(chat_id=chat.id, role="assistant", content=res["data"]))
    db.session.commit()

    return jsonify({"ok": True, "data": res["data"], "provider": res.get("provider")})


@bp.route("/chat/<int:chat_id>", methods=["GET"])
@login_required
def chat_get(chat_id):
    """Fetch the full message history for a chat (e.g. to reopen it)."""
    chat = Chat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({"ok": False, "error": "Chat not found."}), 404
    return jsonify({
        "ok": True,
        "chat_id": chat.id,
        "title": chat.title,
        "messages": [
            {"role": m.role, "content": m.content, "attachment_name": m.attachment_name}
            for m in chat.messages
        ],
    })


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
