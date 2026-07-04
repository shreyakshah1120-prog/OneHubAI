"""Image generation routes."""
from flask import Blueprint, render_template, request, jsonify, current_app, url_for
from flask_login import login_required, current_user

from ..extensions import db
from ..models import GeneratedImage, log_history
from ..services.ai import enhance_prompt, generate_image

bp = Blueprint("image", __name__)


@bp.route("/")
@login_required
def index():
    images = (
        GeneratedImage.query.filter_by(user_id=current_user.id)
        .order_by(GeneratedImage.created_at.desc())
        .all()
    )
    return render_template("dashboard/image.html", images=images)


@bp.route("/generate", methods=["POST"])
@login_required
def generate():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    provider = (data.get("provider") or "openai").lower()
    use_enhanced = data.get("use_enhanced", True)
    if not prompt:
        return jsonify({"ok": False, "error": "Prompt is empty."}), 400

    enhanced = prompt
    if use_enhanced:
        eh = enhance_prompt(prompt)
        if eh["ok"]:
            enhanced = eh["data"]

    res = generate_image(enhanced, provider, current_app.config["GENERATED_FOLDER"])
    if res["ok"]:
        img = GeneratedImage(
            user_id=current_user.id,
            prompt=prompt,
            enhanced_prompt=enhanced,
            provider=provider,
            file_path=res["data"],
        )
        db.session.add(img)
        db.session.commit()
        log_history(current_user.id, "image", prompt[:80], img.id)
        res["url"] = url_for("static", filename=f"generated/{res['data']}")
        res["enhanced_prompt"] = enhanced
        res["id"] = img.id
    return jsonify(res)
