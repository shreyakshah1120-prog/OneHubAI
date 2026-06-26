"""AI Interview Coach — conversational voice-based interview."""
import json
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, flash
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Interview, InterviewReport, log_history
from ..services.ai import chat_any, chat_json, text_to_speech
from ..services.files import extract_text

bp = Blueprint("interview", __name__)

INTERVIEW_TYPES = {
    "standard": "a friendly, structured HR interview",
    "tough":    "a very challenging, high-pressure interview that probes weaknesses",
    "shark":    "a Shark Tank-style investor pitch interview — skeptical, business-focused",
}

# 5 topics, 2 questions per topic = 10 questions total
TOPIC_TEMPLATES = {
    "standard": [
        "Introduction & Background",
        "Technical Skills & Projects",
        "Problem Solving & Challenges",
        "Teamwork & Leadership",
        "Goals & Motivation",
    ],
    "tough": [
        "Handling Failure & Criticism",
        "Technical Depth & Gaps",
        "Pressure Situations",
        "Conflicting Priorities",
        "Weaknesses & Blind Spots",
    ],
    "shark": [
        "Product & Market Fit",
        "Revenue & Business Model",
        "Competition & Differentiation",
        "Team & Execution",
        "Funding & Scale",
    ],
}


@bp.route("/")
@login_required
def index():
    sessions = (
        Interview.query.filter_by(user_id=current_user.id)
        .order_by(Interview.created_at.desc())
        .all()
    )
    return render_template("dashboard/interview.html", sessions=sessions, types=INTERVIEW_TYPES)


@bp.route("/start", methods=["POST"])
@login_required
def start():
    itype = (request.form.get("type") or "standard").lower()
    role = (request.form.get("role") or "Software Engineer").strip()
    background = (request.form.get("background") or "").strip()
    school = (request.form.get("school") or "").strip()
    grad_year = (request.form.get("grad_year") or "").strip()
    skills = (request.form.get("skills") or "").strip()
    resume_file = request.files.get("resume")

    resume_text = ""
    if resume_file and resume_file.filename:
        safe = secure_filename(resume_file.filename)
        p = Path(current_app.config["UPLOAD_FOLDER"]) / f"resume_{current_user.id}_{safe}"
        resume_file.save(p)
        resume_text = extract_text(str(p))[:6000]

    style = INTERVIEW_TYPES.get(itype, INTERVIEW_TYPES["standard"])
    topics = TOPIC_TEMPLATES.get(itype, TOPIC_TEMPLATES["standard"])

    candidate_context = f"""
Role: {role}
Interview Style: {style}
Background/Degree: {background or 'Not specified'}
School/College: {school or 'Not specified'}
Graduation Year: {grad_year or 'Not specified'}
Skills: {skills or 'Not specified'}
Resume: {resume_text[:3000] if resume_text else '[No resume provided]'}
""".strip()

    prompt = (
        f"You are conducting {style} for the role of '{role}'.\n"
        f"Generate exactly 10 interview questions — 2 questions for each of these 5 topics:\n"
        + "\n".join(f"  {i+1}. {t}" for i, t in enumerate(topics))
        + f"\n\nReturn STRICT JSON: {{\"questions\":[\"q1\",\"q2\",...,\"q10\"], \"topics\":{json.dumps(topics)}}}\n"
        "No prose, no explanation. Just the JSON.\n\n"
        f"CANDIDATE CONTEXT:\n{candidate_context}"
    )
    res = chat_json(prompt, "gpt")

    questions = None
    if res["ok"] and isinstance(res["data"], dict):
        questions = res["data"].get("questions")

    if not questions or len(questions) < 5:
        questions = [
            f"Walk me through your background in {background or 'your field'} and why you're applying for {role}.",
            "Tell me about a key project or achievement you're proud of.",
            f"What {skills.split(',')[0].strip() if skills else 'technical'} skills do you bring to this role?",
            "Describe a challenging technical problem you solved. How did you approach it?",
            "Tell me about a time you disagreed with a teammate. How was it resolved?",
            "How do you handle tight deadlines and multiple priorities at once?",
            "Where do you see yourself in 3 years?",
            "Why are you interested in this specific role and company?",
            "What is your biggest professional weakness and how are you working on it?",
            "Do you have any questions for us?",
        ]

    # Build opening greeting TTS
    opening = (
        f"Hello! Welcome to your {itype} interview for the role of {role}. "
        f"I'm your AI interviewer. We'll go through 10 questions across 5 topics today. "
        f"After each answer, I'll give you a brief feedback and then move to the next question. "
        f"Take your time, speak clearly, and let's begin. Here is your first question: {questions[0]}"
    )

    session = Interview(
        user_id=current_user.id, interview_type=itype, role=role,
        resume_text=f"Background: {background}\nSchool: {school}\nYear: {grad_year}\nSkills: {skills}\n\n{resume_text}",
        questions_json=json.dumps(questions),
        answers_json=json.dumps([]),
    )
    db.session.add(session)
    db.session.commit()
    log_history(current_user.id, "interview", f"{itype.title()} interview — {role}", session.id)

    # Pre-generate opening TTS
    try:
        tts_res = text_to_speech(opening, "professional", current_app.config["GENERATED_FOLDER"])
        if tts_res["ok"]:
            session.answers_json = json.dumps([{"opening_audio": tts_res["data"]}])
            db.session.commit()
    except Exception:
        pass

    return redirect(url_for("interview.session", sid=session.id))


@bp.route("/<int:sid>")
@login_required
def session(sid: int):
    s = Interview.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    raw_answers = json.loads(s.answers_json or "[]")
    # Filter out internal meta entries
    answers = [a for a in raw_answers if "q_index" in a]
    opening_audio = next((a.get("opening_audio") for a in raw_answers if "opening_audio" in a), None)
    return render_template(
        "dashboard/interview_session.html",
        s=s,
        questions=json.loads(s.questions_json or "[]"),
        answers=answers,
        opening_audio=opening_audio,
    )


@bp.route("/<int:sid>/answer", methods=["POST"])
@login_required
def answer(sid: int):
    s = Interview.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    raw_answers = json.loads(s.answers_json or "[]")
    raw_answers.append({
        "q_index": data.get("q_index"),
        "text": (data.get("text") or "").strip(),
    })
    s.answers_json = json.dumps(raw_answers)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/<int:sid>/feedback", methods=["POST"])
@login_required
def feedback(sid: int):
    """After each answer, AI speaks a short feedback and the next question."""
    s = Interview.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    q_index = int(data.get("q_index", 0))
    user_answer = (data.get("answer") or "").strip()
    questions = json.loads(s.questions_json or "[]")
    current_q = questions[q_index] if q_index < len(questions) else ""
    next_q = questions[q_index + 1] if (q_index + 1) < len(questions) else None

    # Build feedback prompt
    prompt = (
        f"You are an HR interviewer. The candidate just answered a question.\n"
        f"Question: {current_q}\n"
        f"Candidate's Answer: {user_answer or '[No answer given]'}\n\n"
        f"Give a BRIEF spoken feedback (2-3 sentences max) on their answer — what was good, "
        f"what could be better. Speak naturally as if in a real interview. No markdown.\n"
    )
    if next_q:
        prompt += f'\nThen say: "Now, here is your next question: {next_q}"\n'
    else:
        prompt += '\nThen say: "That was your last question. Great effort! Click Generate Report to see your evaluation."\n'

    res = chat_any(prompt, "gpt")
    feedback_text = res["data"] if res["ok"] else (
        f"Thank you for your answer. " +
        (f"Here is your next question: {next_q}" if next_q else "That was the last question. Please generate your report.")
    )

    # Generate TTS
    tts_res = text_to_speech(feedback_text, "professional", current_app.config["GENERATED_FOLDER"])
    audio_url = None
    if tts_res["ok"]:
        audio_url = url_for("static", filename=f"generated/{tts_res['data']}")

    return jsonify({
        "ok": True,
        "feedback_text": feedback_text,
        "audio_url": audio_url,
        "has_next": next_q is not None,
        "next_index": q_index + 1 if next_q else None,
    })


@bp.route("/<int:sid>/speak", methods=["POST"])
@login_required
def speak(sid: int):
    Interview.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Empty text"}), 400
    res = text_to_speech(text, "professional", current_app.config["GENERATED_FOLDER"])
    if res["ok"]:
        res["url"] = url_for("static", filename=f"generated/{res['data']}")
    return jsonify(res)


@bp.route("/<int:sid>/report", methods=["POST"])
@login_required
def report(sid: int):
    s = Interview.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    questions = json.loads(s.questions_json or "[]")
    raw_answers = json.loads(s.answers_json or "[]")
    answers = [a for a in raw_answers if "q_index" in a]
    qa_text = "\n".join(
        f"Q{i+1}: {questions[i] if i < len(questions) else '?'}\nA: {a.get('text','[no answer]')}"
        for i, a in enumerate(answers)
    ) or "[no answers recorded]"

    prompt = (
        "You are a senior hiring manager. Score the candidate out of 10 on each dimension "
        "and provide qualitative feedback. Return STRICT JSON with keys:\n"
        "communication (0-10), english_fluency (0-10), knowledge_domain (0-10), "
        "preparation (0-10), confidence (0-10), overall (0-10), "
        "feedback (string 3-4 sentences), weak_points (string), missing_skills (string), "
        "ats_suggestions (string).\n\n"
        f"ROLE: {s.role}\nINTERVIEW TYPE: {s.interview_type}\n\n"
        f"RESUME:\n{(s.resume_text or '')[:1500]}\n\nTRANSCRIPT:\n{qa_text}"
    )
    res = chat_json(prompt, "gpt")
    payload = res["data"] if isinstance(res["data"], dict) else {}

    rep = s.report or InterviewReport(interview_id=s.id)
    # Map new 0-10 scores to 0-100 for model compatibility
    for k, model_k in [
        ("communication", "communication"),
        ("english_fluency", "body_language"),
        ("knowledge_domain", "technical"),
        ("preparation", "resume_quality"),
        ("confidence", "confidence"),
        ("overall", "overall"),
    ]:
        try:
            val = int(payload.get(k, 7))
            # Store raw /10 * 10 to keep percentage scale
            setattr(rep, model_k, val * 10)
        except (TypeError, ValueError):
            setattr(rep, model_k, 70)
    # Fill remaining fields
    rep.leadership = rep.confidence
    rep.problem_solving = rep.technical
    rep.feedback = payload.get("feedback", "Good effort. Keep practising.")
    rep.weak_points = payload.get("weak_points", "")
    rep.missing_skills = payload.get("missing_skills", "")
    rep.ats_suggestions = payload.get("ats_suggestions", "")

    # Store raw /10 payload for display
    rep.feedback = json.dumps({
        "communication": payload.get("communication", 7),
        "english_fluency": payload.get("english_fluency", 7),
        "knowledge_domain": payload.get("knowledge_domain", 7),
        "preparation": payload.get("preparation", 7),
        "confidence": payload.get("confidence", 7),
        "overall": payload.get("overall", 7),
        "feedback": payload.get("feedback", "Good effort. Keep practising."),
        "weak_points": payload.get("weak_points", ""),
        "missing_skills": payload.get("missing_skills", ""),
        "ats_suggestions": payload.get("ats_suggestions", ""),
    })

    db.session.add(rep)
    db.session.commit()
    return jsonify({"ok": True, "redirect": url_for("interview.show_report", sid=s.id)})


@bp.route("/<int:sid>/report")
@login_required
def show_report(sid: int):
    s = Interview.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    if not s.report:
        flash("No report generated yet.", "warning")
        return redirect(url_for("interview.session", sid=sid))
    # Parse JSON feedback if stored that way
    try:
        report_data = json.loads(s.report.feedback or "{}")
    except Exception:
        report_data = {}
    return render_template("dashboard/interview_report.html", s=s, r=s.report, rd=report_data)
