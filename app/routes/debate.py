"""AI Debate Partner — voice-based."""
import json
from flask import Blueprint, render_template, request, jsonify, current_app, url_for, redirect, flash
from flask_login import login_required, current_user

from ..extensions import db
from ..models import DebateSession, log_history
from ..services.ai import chat_any, chat_json, text_to_speech

bp = Blueprint("debate", __name__)


DEFAULT_TOPICS = [
    "AI vs Humans — will AI take over creative jobs?",
    "Online Learning is more effective than classroom learning.",
    "Climate Change is the most urgent global crisis.",
    "Business Ethics matter more than profit.",
    "Social media does more harm than good.",
    "Universal Basic Income should be implemented.",
]


@bp.route("/")
@login_required
def index():
    sessions = (
        DebateSession.query.filter_by(user_id=current_user.id)
        .order_by(DebateSession.created_at.desc())
        .all()
    )
    return render_template("dashboard/debate.html", sessions=sessions, topics=DEFAULT_TOPICS)


@bp.route("/start", methods=["POST"])
@login_required
def start():
    topic = (request.form.get("topic") or "").strip()
    if not topic:
        flash("Pick or enter a topic.", "warning")
        return redirect(url_for("debate.index"))
    opening_prompt = (
        f"You are a skilled debate champion. Open a 4-minute debate on the topic: '{topic}'.\n"
        "Take the OPPOSING position to the user (they will respond). Speak in clear, "
        "spoken-word English (no markdown). 220–280 words. Make 3 strong arguments."
    )
    res = chat_any(opening_prompt, "gpt")
    opening = res["data"] if res["ok"] else (
        f"Welcome. Today we debate: {topic}. I'll take the opposing view. "
        "Begin when you're ready."
    )
    transcript = [{"role": "ai", "text": opening}]
    s = DebateSession(
        user_id=current_user.id, topic=topic,
        transcript_json=json.dumps(transcript),
    )
    db.session.add(s)
    db.session.commit()
    log_history(current_user.id, "debate", topic[:80], s.id)
    return redirect(url_for("debate.session", sid=s.id))


@bp.route("/<int:sid>")
@login_required
def session(sid: int):
    s = DebateSession.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    return render_template(
        "dashboard/debate_session.html",
        s=s,
        transcript=json.loads(s.transcript_json or "[]"),
        scores=json.loads(s.scores_json) if s.scores_json else None,
    )


@bp.route("/<int:sid>/turn", methods=["POST"])
@login_required
def turn(sid: int):
    s = DebateSession.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "").strip()
    if not user_text:
        return jsonify({"ok": False, "error": "Empty input."}), 400

    transcript = json.loads(s.transcript_json or "[]")
    transcript.append({"role": "user", "text": user_text})

    history = "\n".join(f"{t['role'].upper()}: {t['text']}" for t in transcript)
    prompt = (
        f"You are debating the user on '{s.topic}'. Continue the debate.\n"
        "Counter their last point with logic, examples, and a question back. "
        "150–200 words, spoken-word English, no markdown.\n\n"
        f"TRANSCRIPT SO FAR:\n{history}"
    )
    res = chat_any(prompt, "gpt")
    ai_text = res["data"] if res["ok"] else "Interesting point — let me think about that."
    transcript.append({"role": "ai", "text": ai_text})
    s.transcript_json = json.dumps(transcript)
    db.session.commit()
    return jsonify({"ok": True, "ai_text": ai_text})


@bp.route("/<int:sid>/speak", methods=["POST"])
@login_required
def speak(sid: int):
    DebateSession.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Empty text."}), 400
    res = text_to_speech(text, "narrator", current_app.config["GENERATED_FOLDER"])
    if res["ok"]:
        res["url"] = url_for("static", filename=f"generated/{res['data']}")
    return jsonify(res)


@bp.route("/<int:sid>/analyze", methods=["POST"])
@login_required
def analyze(sid: int):
    s = DebateSession.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    transcript = json.loads(s.transcript_json or "[]")
    user_text = "\n".join(t["text"] for t in transcript if t["role"] == "user") or "[no user turns]"
    
    full_transcript = "\n".join(
    f"{t['role'].upper()}: {t['text']}" for t in transcript
    )
    prompt = (
    "You are a strict, impartial debate judge. Score the user's debate performance HONESTLY and CRITICALLY.\n"
    "Do NOT be generous. If the user said rubbish, irrelevant, incoherent, or very short statements, "
    "scores should be 0–35. If mediocre, 36–55. If decent, 56–74. Only give 75+ for genuinely strong arguments.\n\n"
    "SCORING RUBRIC:\n"
    "- public_speaking: clarity, pace, structure of spoken delivery\n"
    "- confidence: assertiveness, conviction in statements\n"
    "- logical_reasoning: use of logic, valid inferences, avoiding fallacies\n"
    "- communication: ability to express ideas clearly and concisely\n"
    "- persuasion: how convincingly they argued their position\n"
    "- vocabulary: range and appropriateness of words used\n"
    "- critical_thinking: ability to challenge, rebut, and analyse the opponent's points\n"
    "- fluency: smooth, natural flow of language without excessive repetition or filler\n\n"
    "STRICT RULES:\n"
    "- If user statements are fewer than 20 words total: all scores must be below 30\n"
    "- If statements are off-topic, nonsensical, or just filler words: all scores must be below 25\n"
    "- If statements show no counter-argument or rebuttal: logical_reasoning and critical_thinking must be below 30\n"
    "- Never give a score above 60 unless the argument is clearly structured with evidence or examples\n"
    "- Never give a score above 80 unless the argument is genuinely exceptional\n\n"
    f"DEBATE TOPIC: {s.topic}\n\n"
    f"FULL DEBATE TRANSCRIPT (for context only):\n{full_transcript}\n\n"
    f"USER STATEMENTS ONLY (score only these):\n{user_text}\n\n"
    "Return STRICT JSON only with these exact keys: "
    "public_speaking, confidence, logical_reasoning, communication, persuasion, vocabulary, "
    "critical_thinking, fluency, suggestions (a single string with 3-5 specific, harsh but constructive improvement tips based on what the user actually said)."
)
    res = chat_json(prompt, "gpt")
    scores = res["data"] if isinstance(res["data"], dict) else {}

    cleaned = {}
    for k in ("public_speaking", "confidence", "logical_reasoning", "communication",
          "persuasion", "vocabulary", "critical_thinking", "fluency"):
        try:
            cleaned[k] = max(0, min(100, int(scores.get(k, 0))))
        except (TypeError, ValueError):
            cleaned[k] = 0
    s.scores_json = json.dumps(cleaned)
    s.suggestions = scores.get("suggestions", "Practice structured arguments and use concrete examples.")
    db.session.commit()
    return jsonify({"ok": True, "scores": cleaned, "suggestions": s.suggestions})
