"""Study Assistant — Production-level: summaries, multi-type tests, interactive scoring."""
import json
import os
import re
from pathlib import Path

import requests
from werkzeug.utils import secure_filename
from flask import (
    Blueprint, render_template, request, jsonify,
    current_app, redirect, url_for, flash,
)
from flask_login import login_required, current_user
from dotenv import load_dotenv

load_dotenv()

from ..extensions import db
from ..models import StudyMaterial, MCQ, log_history
from ..services.files import extract_text

bp = Blueprint("study", __name__)

ALLOWED_DOCS = {".pdf", ".docx", ".pptx", ".ppt", ".txt", ".md"}
MAX_FILE_BYTES = 64 * 1024 * 1024  
MAX_COMBINED_CHARS = 8000
MAX_SOURCE_CHARS   = 6000

# ─── AI helpers ───────────────────────────────────────────────────────────────

def _clean_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _call_openai_text(prompt: str, system: str = None) -> dict:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return {"ok": False, "data": None, "error": "No key"}
    try:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": msgs, "temperature": 0.4, "max_tokens": 4000},
            timeout=120,
        )
        resp.raise_for_status()
        return {"ok": True, "data": resp.json()["choices"][0]["message"]["content"].strip(), "error": None, "provider": "openai"}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _call_openrouter_text(prompt: str, system: str = None) -> dict:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return {"ok": False, "data": None, "error": "No key"}
    try:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "openai/gpt-4o-mini", "messages": msgs, "max_tokens": 4000},
            timeout=120,
        )
        resp.raise_for_status()
        return {"ok": True, "data": resp.json()["choices"][0]["message"]["content"].strip(), "error": None, "provider": "openrouter"}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _call_gemini_text(prompt: str, system: str = None) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "data": None, "error": "GEMINI_API_KEY not set"}
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        for model_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]:
            try:
                model = genai.GenerativeModel(model_name)
                res = model.generate_content(full_prompt)
                return {"ok": True, "data": res.text, "error": None, "provider": f"gemini/{model_name}"}
            except Exception:
                continue
        return {"ok": False, "data": None, "error": "All Gemini models failed"}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _call_pollinations_text(prompt: str, system: str = None) -> dict:
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            "https://text.pollinations.ai/",
            json={"messages": messages},
            timeout=120,
        )
        if resp.status_code != 200:
            return {"ok": False, "data": None, "error": f"HTTP {resp.status_code}"}
        return {"ok": True, "data": resp.text.strip(), "error": None, "provider": "pollinations"}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def ask_ai_text(prompt: str, system: str = None) -> dict:
    for fn in (_call_openai_text, _call_openrouter_text, _call_gemini_text, _call_pollinations_text):
        result = fn(prompt, system)
        if result.get("ok") and result.get("data"):
            return result
    return {"ok": False, "data": None, "error": "All AI providers failed"}


def ask_ai_json(prompt: str, system: str = None) -> dict:
    res = ask_ai_text(prompt, system)
    if not res["ok"]:
        return res
    raw = _clean_json(res["data"])
    try:
        parsed = json.loads(raw)
        return {"ok": True, "data": parsed, "error": None, "provider": res.get("provider")}
    except json.JSONDecodeError:
        match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', raw)
        if match:
            try:
                parsed = json.loads(match.group(1))
                return {"ok": True, "data": parsed, "error": None, "provider": res.get("provider")}
            except Exception:
                pass
        return {"ok": False, "data": None, "error": f"JSON parse failed. Raw: {raw[:300]}"}


# ─── Routes ───────────────────────────────────────────────────────────────────

@bp.route("/")
@login_required
def index():
    materials = (
        StudyMaterial.query.filter_by(user_id=current_user.id)
        .order_by(StudyMaterial.created_at.desc())
        .all()
    )
    return render_template("dashboard/study.html", materials=materials)


@bp.route("/upload", methods=["POST"])
@login_required
def upload():
    # Support both multipart/form-data and application/x-www-form-urlencoded
    topic = (request.form.get("topic") or "").strip()
    files = request.files.getlist("docs")
    files = [f for f in files if f and f.filename]

    combined_text = ""
    filenames = []

    # Handle file uploads — read and extract text from each file
    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_DOCS:
            continue
        # Reject files over 5MB before saving
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        if file_size > MAX_FILE_BYTES:
            return jsonify({"ok": False, "error": f"File '{file.filename}' is too large. Max 64MB."}), 400

        safe = secure_filename(file.filename)
        p = Path(current_app.config["UPLOAD_FOLDER"]) / f"study_{current_user.id}_{safe}"
        file.save(p)
        try:
            text = extract_text(str(p))
        except Exception:
            text = ""
        finally:
            try:
                p.unlink(missing_ok=True)  # delete file after reading
            except Exception:
                pass
        combined_text += f"\n\n--- File: {safe} ---\n{text}"
        filenames.append(safe)

    # Determine display name and build content
    if topic and not filenames:
        combined_text = f"Topic: {topic}"
        display_name = topic[:120]
    elif topic and filenames:
        combined_text = f"Topic: {topic}\n\n" + combined_text
        display_name = f"{topic} ({filenames[0]})"
    elif filenames:
        display_name = filenames[0] if len(filenames) == 1 else f"{filenames[0]} (+{len(filenames) - 1} more)"
    else:
        return jsonify({"ok": False, "error": "Please enter a topic or upload at least one file."}), 400

    combined_text = combined_text[:MAX_COMBINED_CHARS]

    system_prompt = "You are an expert academic tutor and study guide creator. Return ONLY valid JSON — no markdown fences, no extra text. For all content fields, use rich HTML formatting: use <table> for comparisons, <h4> for section headers, <ul><li> for bullet lists, <strong> for key terms, <em> for definitions, <div class='example-box'> for examples, <span class='formula'> for formulas. Make content visually rich and student-friendly."
    prompt = f"""Analyze the study content below and create a comprehensive, professional, visually rich study guide using HTML formatting.

Return ONLY a valid JSON object with this EXACT structure. ALL values must be HTML strings — use tables, headers, lists, highlights:

{{
    "summary": "Write a detailed HTML overview. Start with a <h4>What is this topic?</h4> definition block. Then add a <table> comparing the main concepts with columns: Concept | Definition | Example. Then write 2-3 paragraphs of explanation with <strong>key terms</strong> highlighted. End with a <h4>Why it matters</h4> section.",

    "subtopics": "Return an HTML <table> with columns: Subtopic | What it covers | Importance (High/Medium/Low). List every section from the content.",

    "key_points": "Return an HTML <ul> list. Each <li> must have: <strong>Term/Concept:</strong> followed by its definition and one example. Minimum 12 points.",

    "examples": "Return numbered HTML sections. For each example: <h4>Example N: Title</h4> then <p>Problem or scenario</p> then <div class='example-box'>Step-by-step solution or explanation</div>. Minimum 5 examples.",

    "diagrams_text": "Describe key diagrams as HTML tables showing relationships, flows, or structures. Use arrows (→) and labels inside table cells to simulate a diagram.",

    "formulas": "Return an HTML <table> with columns: Formula Name | Formula | What each symbol means | When to use it. Leave empty string if no formulas.",

    "real_world": "Return an HTML <table> with columns: Application | Industry/Field | How this concept is used | Real example. Minimum 5 rows.",

    "exam_tips": "Return an HTML <ol> numbered list. Each item: <strong>Tip N:</strong> followed by the tip and a <em>Common mistake to avoid</em> note.",

    "common_mistakes": "Return an HTML <table> with columns: Mistake | Why students make it | How to avoid it | Correct approach. Minimum 6 rows.",

    "revision_notes": "Return a quick-read HTML revision card. Use <h4> section headers, <ul> bullet points with <strong>bold</strong> key facts. Max 300 words. Fast to read before an exam.",

    "chapter_summary": "Return an HTML <table> with columns: Section/Chapter | Key Concepts | Key Takeaway | Exam Weightage (High/Medium/Low).",

    "long_notes": "Write a full comprehensive HTML explanation minimum 800 words. Structure: <h4>Introduction</h4> paragraph, then for each major concept: <h4>Concept Name</h4> with definition, explanation, analogy, example, and a mini <table> summarising it. End with <h4>Summary Table</h4> covering all concepts."
}}

STUDY CONTENT:
{combined_text}
"""

    res = ask_ai_json(prompt, system_prompt)
    del combined_text, prompt  # free RAM before DB write
    payload = res.get("data") or {}
    if isinstance(payload, list):
        payload = {}

    sm = StudyMaterial(
        user_id=current_user.id,
        filename=display_name,
        summary=payload.get("summary", ""),
        chapter_summary=json.dumps({
            "subtopics": payload.get("subtopics", ""),
            "key_points": payload.get("key_points", ""),
            "examples": payload.get("examples", ""),
            "diagrams_text": payload.get("diagrams_text", ""),
            "formulas": payload.get("formulas", ""),
            "real_world": payload.get("real_world", ""),
            "exam_tips": payload.get("exam_tips", ""),
            "common_mistakes": payload.get("common_mistakes", ""),
            "chapter_summary": payload.get("chapter_summary", ""),
        }),
        short_notes=payload.get("revision_notes", ""),
        long_notes=payload.get("long_notes", ""),
        revision_notes=payload.get("revision_notes", ""),
    )
    db.session.add(sm)
    db.session.commit()
    log_history(current_user.id, "study", display_name, sm.id)

    # Return JSON with redirect URL so the JS can navigate
    return jsonify({"ok": True, "redirect": url_for("study.show", mid=sm.id)})


@bp.route("/<int:mid>")
@login_required
def show(mid: int):
    m = StudyMaterial.query.filter_by(id=mid, user_id=current_user.id).first_or_404()
    extra = {}
    try:
        if m.chapter_summary and m.chapter_summary.strip().startswith("{"):
            extra = json.loads(m.chapter_summary)
    except Exception:
        pass
    return render_template("dashboard/study_detail.html", m=m, extra=extra)


@bp.route("/<int:mid>/generate-questions", methods=["POST"])
@login_required
def generate_questions(mid: int):
    m = StudyMaterial.query.filter_by(id=mid, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    q_type = data.get("type", "mcq")
    n = max(1, min(50, int(data.get("count", 10))))

    extra = {}
    try:
        if m.chapter_summary and m.chapter_summary.strip().startswith("{"):
            extra = json.loads(m.chapter_summary)
    except Exception:
        pass

    source_parts = [m.summary or "", m.long_notes or ""]
    for v in extra.values():
        if isinstance(v, str):
            source_parts.append(v)
    source = " ".join(filter(None, source_parts))[:MAX_SOURCE_CHARS]

    if not source.strip():
        return jsonify({"ok": False, "error": "No study content available."}), 400

    system_prompt = "You are an expert exam question creator. Return ONLY valid JSON — no markdown, no extra text."

    if q_type == "mcq":
        prompt = f"""Generate exactly {n} multiple-choice questions from the study material below.

Return ONLY this JSON structure:
{{"questions":[{{"q":"question text","options":["A option","B option","C option","D option"],"correct":0,"explanation":"why this answer is correct"}}]}}

Rules:
- Each question has EXACTLY 4 options (A B C D)
- "correct" is 0-based index (0=A, 1=B, 2=C, 3=D)
- Mix factual, conceptual, and application questions
- Include clear explanations

STUDY MATERIAL:
{source}"""

    elif q_type == "truefalse":
        prompt = f"""Generate exactly {n} True/False questions from the study material below.

Return ONLY this JSON structure:
{{"questions":[{{"q":"statement text","correct":true,"explanation":"why it's true or false"}}]}}

STUDY MATERIAL:
{source}"""

    elif q_type == "fillblank":
        prompt = f"""Generate exactly {n} fill-in-the-blank questions from the study material below.

Return ONLY this JSON structure:
{{"questions":[{{"q":"sentence with ___ blank","answer":"the correct word/phrase","hint":"optional hint","explanation":"why this is correct"}}]}}

STUDY MATERIAL:
{source}"""

    elif q_type == "short":
        prompt = f"""Generate exactly {n} short answer questions from the study material below.

Return ONLY this JSON structure:
{{"questions":[{{"q":"question text","answer":"ideal answer (2-4 sentences)","key_points":["point1","point2","point3"],"explanation":"detailed explanation"}}]}}

STUDY MATERIAL:
{source}"""

    elif q_type == "long":
        prompt = f"""Generate exactly {n} long answer / essay questions from the study material below.

Return ONLY this JSON structure:
{{"questions":[{{"q":"essay question","answer":"model answer (full paragraph)","key_points":["major point 1","major point 2","major point 3","major point 4"],"marks":10,"explanation":"what a perfect answer includes"}}]}}

STUDY MATERIAL:
{source}"""
    else:
        return jsonify({"ok": False, "error": "Invalid question type"}), 400

    res = ask_ai_json(prompt, system_prompt)
    raw_data = res.get("data")

    items = []
    if isinstance(raw_data, dict):
        items = raw_data.get("questions", [])
    elif isinstance(raw_data, list):
        items = raw_data

    if not items:
        return jsonify({"ok": False, "error": f"AI failed to generate questions. {res.get('error', '')}"}), 500

    if q_type == "mcq":
        MCQ.query.filter_by(study_id=m.id).delete()
        saved = []
        for q in items:
            if not isinstance(q, dict):
                continue
            question_text = q.get("q") or q.get("question", "")
            options = q.get("options", [])
            correct = q.get("correct", 0)
            explanation = q.get("explanation", "")
            if not question_text or len(options) < 2:
                continue
            obj = MCQ(
                study_id=m.id,
                question=question_text,
                options_json=json.dumps(options),
                correct_index=int(correct),
                explanation=explanation,
            )
            db.session.add(obj)
            saved.append(obj)
        db.session.commit()
        all_mcqs = MCQ.query.filter_by(study_id=m.id).all()
        return jsonify({
            "ok": True, "type": "mcq", "count": len(all_mcqs),
            "questions": [{"id": q.id, "q": q.question, "options": json.loads(q.options_json or "[]")} for q in all_mcqs],
        })

    return jsonify({"ok": True, "type": q_type, "count": len(items), "questions": items})


@bp.route("/<int:mid>/mcq/score", methods=["POST"])
@login_required
def mcq_score(mid: int):
    m = StudyMaterial.query.filter_by(id=mid, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    answers = data.get("answers", {})
    questions = MCQ.query.filter_by(study_id=m.id).all()

    correct_count = 0
    wrong_topics = []
    breakdown = []
    for q in questions:
        chosen = int(answers.get(str(q.id), -1))
        is_correct = chosen == q.correct_index
        if is_correct:
            correct_count += 1
        else:
            wrong_topics.append(q.question[:60])
        breakdown.append({
            "question": q.question, "chosen": chosen,
            "correct": q.correct_index, "is_correct": is_correct,
            "options": json.loads(q.options_json or "[]"),
            "explanation": q.explanation,
        })

    total = len(questions) or 1
    pct = round(correct_count * 100 / total, 1)

    revision_notes = ""
    if wrong_topics and pct < 80:
        weak_str = "\n".join(wrong_topics[:10])
        rev_res = ask_ai_text(
            f"The student got these questions wrong:\n{weak_str}\n\n"
            "Write 3-5 bullet points of targeted revision tips to help them improve on these specific weak areas. Be concise and actionable.",
            "You are a helpful study coach."
        )
        if rev_res.get("ok"):
            revision_notes = rev_res["data"]

    return jsonify({
        "ok": True, "score": correct_count, "total": total,
        "percent": pct, "breakdown": breakdown,
        "revision_notes": revision_notes,
        "weak_count": len(wrong_topics),
    })


@bp.route("/<int:mid>/score-open", methods=["POST"])
@login_required
def score_open(mid: int):
    data = request.get_json(silent=True) or {}
    q_type = data.get("type", "short")
    questions = data.get("questions", [])
    user_answers = data.get("answers", {})

    if not questions:
        return jsonify({"ok": False, "error": "No questions provided"}), 400

    eval_items = []
    for i, q in enumerate(questions):
        q_key = str(i)
        user_ans = user_answers.get(q_key, "").strip()
        eval_items.append({
            "question": q.get("q", ""),
            "user_answer": user_ans,
            "model_answer": q.get("answer", ""),
            "key_points": q.get("key_points", []),
        })

    prompt = f"""You are a strict but fair academic examiner. Evaluate the student's answers below.

For each answer, return:
- score: 0-10
- is_correct: true if score >= 6
- feedback: specific feedback on what was right/wrong
- correct_answer: the ideal answer

Return ONLY this JSON:
{{"results":[{{"score":8,"is_correct":true,"feedback":"Good answer, but missed X","correct_answer":"Full model answer"}}]}}

ANSWERS TO EVALUATE:
{json.dumps(eval_items, indent=2)}
"""

    res = ask_ai_json(prompt, "You are an academic examiner. Return only JSON.")
    if not res.get("ok"):
        return jsonify({"ok": False, "error": "AI evaluation failed"}), 500

    raw = res["data"]
    results = raw.get("results", []) if isinstance(raw, dict) else []

    total = len(results)
    correct = sum(1 for r in results if r.get("is_correct"))
    total_score = sum(r.get("score", 0) for r in results)
    max_score = total * 10

    return jsonify({
        "ok": True,
        "results": results,
        "score": correct,
        "total": total,
        "total_score": total_score,
        "max_score": max_score,
        "percent": round(total_score * 100 / max_score, 1) if max_score else 0,
    })


@bp.route("/<int:mid>/mcq", methods=["POST"])
@login_required
def mcq(mid: int):
    return generate_questions(mid)
