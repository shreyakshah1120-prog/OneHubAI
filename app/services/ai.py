"""Unified AI service layer for OneHubAI.

Every helper returns a dict shaped like:
    {"ok": bool, "data": ..., "error": str | None, "provider": str}
so route handlers can treat all providers uniformly and degrade gracefully
when API keys are missing.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any
import requests
from dotenv import load_dotenv
load_dotenv()

def _key(name: str) -> str | None:
    val = os.getenv(name)
    return val.strip() if val and val.strip() else None


def _missing(provider: str, key: str) -> dict:
    return {
        "ok": False,
        "data": None,
        "provider": provider,
        "error": f"{provider} is not configured. Add {key} to your .env file to enable this feature.",
    }


# --------------------------------------------------------------------------
# Prompt enhancement — OneHubAI's signature feature
def enhance_prompt(original: str) -> dict:
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
    "Authorization": f"Bearer {_key('OPENROUTER_API_KEY')}",
    "Content-Type": "application/json"
}

        data = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert prompt engineer. "
                        "Rewrite the user's prompt to be more detailed, structured, "
                        "and effective. Preserve intent. Return ONLY the refined prompt."
                    )
                },
                {
                    "role": "user",
                    "content": original
                }
            ]
        }

        response = requests.post(url, headers=headers, json=data)
        result = response.json()

        refined = result["choices"][0]["message"]["content"]

        return {
            "ok": True,
            "data": refined,
            "provider": "openrouter",
            "error": None
        }

    except Exception as e:
        return {
            "ok": False,
            "data": original,
            "provider": "openrouter",
            "error": str(e)
        }

# Text generation — Gemini only

def chat_gemini(prompt: str, model: str = "gemini-1.5-flash") -> dict:
    if not _key("GEMINI_API_KEY"):
        return _missing("Gemini", "GEMINI_API_KEY")
    import google.generativeai as genai
    genai.configure(api_key=_key("GEMINI_API_KEY"))

    # Try a safe model chain — most free-tier keys support gemini-1.5-flash
    models_to_try = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
    # If a specific model was requested and it's not already in the list, try it first
    if model not in models_to_try:
        models_to_try.insert(0, model)

    last_error = "Unknown error"
    for m_name in models_to_try:
        try:
            m = genai.GenerativeModel(m_name)
            res = m.generate_content(prompt, request_options={"timeout": 25})
            return {
                "ok": True,
                "data": res.text,
                "provider": f"gemini/{m_name}",
                "error": None,
            }
        except Exception as e:
            last_error = str(e)
            continue

    return {"ok": False, "data": None, "provider": "gemini", "error": last_error}

def chat_pollinations(prompt: str) -> dict:
    try:
        resp = requests.post(
            "https://text.pollinations.ai/",
            json={
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=75,
        )

        if resp.status_code != 200:
            return {
                "ok": False,
                "data": None,
                "provider": "AI",
                "error": f"HTTP {resp.status_code}"
            }

        text = resp.text.strip()

        return {
            "ok": True,
            "data": text,
            "provider": "AI",
            "error": None,
        }

    except Exception as e:
        return {
            "ok": False,
            "data": None,
            "provider": "AI",
            "error": str(e),
        }
# Keep these stubs so any blueprint that imports them doesn't break,
# but they all route straight to Gemini now.
def chat_openai(prompt: str, model: str = "gpt-4o-mini") -> dict:

    result = chat_gemini(prompt)

    if result["ok"]:
        return result

    return chat_pollinations(prompt)


def chat_claude(prompt: str, model: str = "claude-3-5-sonnet-20240620") -> dict:

    result = chat_gemini(prompt)

    if result["ok"]:
        return result

    return chat_pollinations(prompt)
def generate_text(prompt):

    # STEP 1: Refine prompt
    enhanced = enhance_prompt(prompt)

    if enhanced["ok"]:
        prompt = enhanced["data"]

    print("\n========== REFINED PROMPT ==========")
    print(prompt)
    print("===================================\n")

    # STEP 2: Generate final answer
    providers = [
        chat_gemini,
        chat_pollinations
    ]

    for provider in providers:
        try:
            result = provider(prompt)

            if result["ok"]:
                result["provider"] = "ai"
                return result

        except Exception:
            pass

    return {
        "ok": False,
        "data": None,
        "provider": "ai",
        "error": "No text provider available."
    }
def chat_any(prompt: str, model_choice: str = "gemini") -> dict:

    # Try Gemini first
    result = chat_gemini(prompt)

    if result["ok"]:
        return result

    # Free fallback
    return chat_pollinations(prompt)


# --------------------------------------------------------------------------
# Multi-turn "Lets chat" support (AI Studio conversation mode)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def describe_uploaded_image(image_path: str, user_prompt: str = "") -> str:
    """Use Gemini vision to turn an uploaded image into text context that a
    text-only model call can then reason over."""
    if not _key("GEMINI_API_KEY"):
        return ("[Image uploaded, but Gemini Vision is not configured "
                 "(missing GEMINI_API_KEY), so its contents could not be read.]")
    try:
        import google.generativeai as genai
        genai.configure(api_key=_key("GEMINI_API_KEY"))
        image_file = genai.upload_file(image_path)
        model = genai.GenerativeModel("gemini-1.5-flash")
        instruction = (
            "Describe everything relevant in this image in detail (objects, text, "
            "charts, people, layout, colors, etc.) so another assistant without "
            "eyes can use your description as context to answer questions about it."
        )
        if user_prompt:
            instruction += f" The user's question/request about this image is: {user_prompt}"
        res = model.generate_content([instruction, image_file], request_options={"timeout": 45})
        return res.text
    except Exception as e:
        return f"[Image uploaded, but analysis failed: {e}]"


def extract_upload_context(file_path: str, user_prompt: str = "") -> str:
    """Turn an uploaded file (image or document) into plain-text context
    that can be dropped into an AI prompt. Images go through Gemini vision;
    documents go through the text-extraction service."""
    ext = Path(file_path).suffix.lower()
    if ext in IMAGE_EXTS:
        return describe_uploaded_image(file_path, user_prompt)
    from .files import extract_text
    text = extract_text(file_path)
    return text[:12000] if text else "[Uploaded file could not be read.]"


def chat_with_history(
    history: list[dict],
    latest_message: str,
    model_choice: str = "gemini",
    file_context: str = "",
    attachment_name: str = "",
) -> dict:
    """Continue a multi-turn conversation. `history` is a list of
    {"role": "user"|"assistant", "content": str} for prior turns (oldest
    first, NOT including the new message being sent now). Builds a single
    prompt (so it works with any provider behind chat_any) that includes the
    conversation so far plus any newly uploaded file's content. The prompt
    is NOT re-refined on these follow-up turns — only the very first message
    of a chat goes through enhance_prompt()."""
    lines = [
        "You are a helpful AI assistant having an ongoing conversation with a "
        "user. Use the conversation history below for context, and respond "
        "only to the user's latest message.",
        "",
        "--- Conversation so far ---",
    ]
    for turn in history:
        speaker = "User" if turn.get("role") == "user" else "Assistant"
        lines.append(f"{speaker}: {turn.get('content', '')}")
    lines.append("--- End of history ---")
    lines.append("")
    if file_context:
        lines.append(f"[User attached a file: {attachment_name or 'upload'}]")
        lines.append(file_context)
        lines.append("")
    lines.append(f"User: {latest_message}")
    lines.append("Assistant:")
    full_prompt = "\n".join(lines)
    return chat_any(full_prompt, model_choice)


def chat_json(prompt: str, model_choice: str = "gemini") -> dict:
    """Ask Gemini for JSON. Returns parsed dict in data, or raw text on parse failure."""
    res = chat_any(prompt, model_choice)
    if not res["ok"]:
        return res
    text = res["data"].strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return {
            "ok": True,
            "data": json.loads(text),
            "provider": res["provider"],
            "error": None,
        }
    except Exception:
        return {
            "ok": True,
            "data": {"raw": res["data"]},
            "provider": res["provider"],
            "error": "JSON parse failed",
        }


# --------------------------------------------------------------------------
# Health assistant helpers
# --------------------------------------------------------------------------
def _json_prompt(prompt: str, fallback: dict) -> dict:
    res = chat_json(prompt)
    if res.get("ok") and isinstance(res.get("data"), dict) and "raw" not in res["data"]:
        return res
    return {"ok": True, "data": fallback, "provider": "local-fallback", "error": res.get("error")}


def get_body_part_info(body_part: str, language: str = "English") -> dict:
    fallback = {
        "title": body_part,
        "what_it_does": f"{body_part} is an important part of the body. Its role depends on the tissue, organ, or system involved.",
        "common_problems": ["Pain", "Inflammation", "Injury", "Infection", "Functional changes"],
        "warning_signs": ["Severe or worsening pain", "Fever", "Weakness", "Numbness", "Breathing trouble", "Sudden swelling"],
        "fun_facts": [f"The {body_part.lower()} works with other body systems continuously."],
        "preventive_tips": ["Stay hydrated", "Eat balanced meals", "Sleep well", "Exercise safely", "Seek care for persistent symptoms"],
    }
    prompt = f"""
Respond completely in {language}.
You are NOT diagnosing. You are explaining anatomy for initial medical triage.
Return ONLY valid JSON with keys:
title, what_it_does, common_problems, warning_signs, fun_facts, preventive_tips.
Keep every section concise and patient friendly.
Body part: {body_part}
"""
    return _json_prompt(prompt, fallback)


def detect_emergency(body_part: str, transcript: list[dict], language: str = "English") -> dict:
    text = " ".join(str(item.get("answer", "")) for item in transcript).lower()
    danger_groups = [
        ["chest", "pain", "sweat"],
        ["chest", "pain", "breath"],
        ["left arm", "chest"],
        ["faint", "breath"],
        ["stroke", "face", "speech"],
        ["suicide"],
        ["seizure"],
        ["unconscious"],
        ["severe bleeding"],
        ["blood vomiting"],
    ]
    is_emergency = any(all(word in text for word in group) for group in danger_groups)
    if not is_emergency:
        return {"is_emergency": False, "level": "none", "message": ""}
    message = {
        "English": "These symptoms may indicate a serious medical emergency. Seek emergency medical care immediately. Do not rely on AI.",
        "Hindi": "ये लक्षण गंभीर मेडिकल इमरजेंसी का संकेत हो सकते हैं। तुरंत आपातकालीन चिकित्सा सहायता लें। AI पर निर्भर न रहें।",
        "Gujarati": "આ લક્ષણો ગંભીર તબીબી ઇમરજન્સી દર્શાવી શકે છે. તરત જ ઇમરજન્સી સારવાર લો. AI પર આધાર રાખશો નહીં.",
    }.get(language, "These symptoms may indicate a serious medical emergency. Seek emergency medical care immediately. Do not rely on AI.")
    return {"is_emergency": True, "level": "red", "message": message}


def generate_followup_questions(
    body_part: str,
    profile: dict,
    transcript: list[dict],
    asked: list[str],
    language: str = "English",
) -> dict:
    fallback_questions = [
        f"When did the {body_part.lower()} problem begin?",
        "How severe is it from 1 to 10?",
        "Is it constant, or does it come and go?",
        "Does anything make it better or worse?",
        "Do you have fever, swelling, numbness, vomiting, sweating, or trouble breathing?",
    ]
    for q in fallback_questions:
        if q not in asked:
            fallback = q
            break
    else:
        fallback = "Is there any medical condition, allergy, injury, or report finding I should consider?"

    prompt = f"""
Respond completely in {language}.
You are Dr. AI, a warm, attentive, experienced doctor speaking directly to your patient.
You are NOT diagnosing. You are performing initial medical triage.
Ask exactly ONE follow-up question, related only to {body_part}.
Before the question, add one short warm sentence acknowledging what the patient told you (like a real doctor would),
then ask your question clearly. Keep it natural and caring, not robotic or clinical.
Use the previous answers to choose the next most useful question.
Never ask the same question twice. Avoid irrelevant questions.

Patient profile JSON: {json.dumps(profile)}
Previous answers JSON: {json.dumps(transcript)}
Already asked JSON: {json.dumps(asked)}

Return ONLY valid JSON:
{{"question": "..." }}
"""
    res = _json_prompt(prompt, {"question": fallback})
    data = res.get("data") or {}
    return {"ok": True, "data": data.get("question") or fallback, "provider": res.get("provider"), "error": res.get("error")}


def generate_health_report(
    body_part: str,
    profile: dict,
    transcript: list[dict],
    report_text: str = "",
    language: str = "English",
    emergency: dict | None = None,
) -> dict:
    emergency = emergency or {}
    fallback = {
        "selected_organ": body_part,
        "overview": "This is an initial triage summary based on your answers. It is not a diagnosis.",
        "what_is_happening": "Based on what you described, your body may be responding to irritation, strain, infection, or inflammation in this area. A qualified doctor can confirm the exact cause after an examination.",
        "possible_causes": [
            "This is NOT a diagnosis.",
            "Minor strain or irritation — common and usually resolves with rest and care.",
            "Infection or inflammation — possible if symptoms include redness, warmth, fever, or discharge.",
            "An underlying condition that needs a doctor's examination to rule in or out.",
        ],
        "severity_reasoning": "This urgency level is based on the symptoms you described and how long they've lasted. It may change if new symptoms appear.",
        "home_remedies": ["Hydration", "Rest", "Balanced diet", "Gentle movement if comfortable", "Stress reduction"],
        "lifestyle_advice": ["Track symptoms daily", "Avoid known triggers", "Sleep 7-8 hours", "Avoid unsafe self-medication"],
        "when_to_see_doctor": ["See a doctor within 24-48 hours if symptoms persist or worsen.", "See a doctor immediately if new severe symptoms appear."],
        "emergency_warning_signs": ["Severe pain", "Breathing trouble", "Fainting", "Weakness", "Confusion", "Heavy bleeding"],
        "follow_up_plan": "Recheck in 2-3 days. If there is no improvement, or symptoms worsen, book a doctor's appointment.",
        "questions_to_ask_doctor": [
            "What is the most likely cause of my symptoms?",
            "Do I need any tests to confirm this?",
            "What treatment do you recommend, and how soon should I expect improvement?",
        ],
        "uploaded_report_cross_check": "No uploaded report was available to cross-check.",
        "urgency": "Routine",
        "confidence": "Moderate",
        "disclaimer": "This is informational medical triage, not a diagnosis. Consult a qualified doctor before taking medication.",
    }
    if emergency.get("is_emergency"):
        fallback["urgency"] = "Emergency"
        fallback["emergency_warning_signs"].insert(0, emergency.get("message", "Seek emergency medical care immediately."))

    prompt = f"""
Respond completely in {language}.
You are Dr. AI — an experienced, compassionate physician giving a patient a thorough
initial triage report after a consultation, the way a real doctor would explain things
in person: clear, specific, and reassuring, never vague or generic.

Ground every section in the patient's actual answers below — reference specific details
they mentioned (symptom, duration, severity, triggers) rather than generic statements.
You are NOT diagnosing. Always explain uncertainty. Never claim certainty.
Never prescribe medicines by name or dose. You may mention categories of commonly used
over-the-counter options (e.g. "a paracetamol-based pain reliever") but must always add
"consult your doctor or pharmacist before taking any medication."

Return ONLY valid JSON with exactly these keys:

- selected_organ: string
- overview: 2-3 sentences summarizing the consultation and the leading impression, in warm plain language.
- what_is_happening: a detailed (4-6 sentence) doctor-style explanation of what is likely going on physiologically, referencing the patient's specific symptoms.
- possible_causes: a list of 3-5 possible causes, ORDERED from most to least likely, each written as "Cause — why this fits what you described".
- severity_reasoning: 2-3 sentences explaining exactly why this urgency level was chosen, referencing specific red flags present or absent.
- home_remedies: a list of 4-6 specific, actionable self-care steps (not generic — tailored to {body_part} and the symptoms described).
- lifestyle_advice: a list of 3-5 tailored lifestyle recommendations.
- when_to_see_doctor: a list of 3-4 specific, timed triggers (e.g. "if pain exceeds 7/10", "if fever crosses 101°F for more than 2 days").
- emergency_warning_signs: a list of specific red-flag symptoms that mean "go to the ER now".
- follow_up_plan: 1-2 sentences giving a concrete recheck timeline (e.g. "Recheck in 48 hours; if X hasn't improved, book an in-person visit").
- questions_to_ask_doctor: a list of 3-4 smart, specific questions the patient should bring to their real doctor's appointment.
- uploaded_report_cross_check: if a report/image was uploaded, state clearly whether it supports or doesn't support the leading impression, and why. If none was uploaded, say so plainly.
- urgency: one of "Routine", "Soon", "Urgent", "Emergency".
- confidence: one of "Low", "Moderate", "High" — how confident this triage impression is given the information available.
- disclaimer: a clear one-sentence disclaimer that this is not a diagnosis.

Patient profile JSON: {json.dumps(profile)}
Consultation transcript JSON: {json.dumps(transcript)}
Emergency detection JSON: {json.dumps(emergency)}
Uploaded report or image findings:
{report_text or "[no report uploaded]"}
Body part: {body_part}
"""
    return _json_prompt(prompt, fallback)


def analyze_health_case(*args, **kwargs) -> dict:
    return generate_health_report(*args, **kwargs)


def analyze_medical_image(image_path: str, body_part: str = "General", language: str = "English") -> dict:
    if not _key("GEMINI_API_KEY"):
        return {
            "ok": False,
            "data": "Image uploaded, but Gemini Vision is not configured. Add GEMINI_API_KEY to enable image report analysis.",
            "provider": "gemini-vision",
            "error": "Missing GEMINI_API_KEY",
        }
    try:
        import google.generativeai as genai
        genai.configure(api_key=_key("GEMINI_API_KEY"))
        image_file = genai.upload_file(image_path)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            f"Respond completely in {language}. You are not diagnosing. "
            f"Extract visible medical findings from this uploaded report/image related to {body_part}. "
            "Mention uncertainty and do not prescribe medicine."
        )
        res = model.generate_content([prompt, image_file], request_options={"timeout": 45})
        return {"ok": True, "data": res.text, "provider": "gemini-vision", "error": None}
    except Exception as e:
        return {"ok": False, "data": f"Image uploaded, but visual analysis failed: {e}", "provider": "gemini-vision", "error": str(e)}
# --------------------------------------------------------------------------
# Image generation
def generate_image(prompt: str, provider: str, out_dir: str) -> dict:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    fname = f"img_{int(time.time()*1000)}.png"
    out_path = Path(out_dir) / fname

    # --- Replicate (FLUX) ---
    if provider == "replicate":
        if not _key("REPLICATE_API_TOKEN"):
            return _missing("Replicate", "REPLICATE_API_TOKEN")
        try:
            import replicate
            client = replicate.Client(api_token=_key("REPLICATE_API_TOKEN"))
            output = client.run(
                "black-forest-labs/flux-schnell",
                input={"prompt": prompt, "num_outputs": 1, "aspect_ratio": "1:1"},
            )
            url = output[0] if isinstance(output, list) else output
            img = requests.get(url, timeout=120).content
            out_path.write_bytes(img)
            return {
                "ok": True,
                "data": str(out_path.name),
                "provider": "replicate",
                "error": None,
            }
        except Exception:
            pass  # Fall through to Pollinations

    # --- Pollinations (free, no key needed — also the fallback) ---
    try:
        import urllib.parse
        encoded = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded}"
        response = requests.get(image_url, timeout=120)
        if response.status_code != 200:
            return {
                "ok": False,
                "data": None,
                "provider": "pollinations",
                "error": f"HTTP {response.status_code}",
            }
        out_path.write_bytes(response.content)
        return {
            "ok": True,
            "data": str(out_path.name),
            "provider": "pollinations",
            "error": None,
        }
    except Exception as e:
        return {"ok": False, "data": None, "provider": "pollinations", "error": str(e)}


# --------------------------------------------------------------------------
# Speech-to-Text — disabled, handled client-side via Web Speech API
# --------------------------------------------------------------------------
def speech_to_text(audio_path: str = None) -> dict:
    return {
        "ok": False,
        "data": "",
        "provider": "browser",
        "error": "Speech recognition is handled client-side via Web Speech API. This endpoint is disabled.",
    }

# --------------------------------------------------------------------------
# Text-to-Speech — Microsoft Edge TTS (free, no API key, real male/female voices)
# --------------------------------------------------------------------------
EDGE_VOICE_MAP = {
    "male":         "en-US-GuyNeural",          # Deep American male
    "female":       "en-US-JennyNeural",         # Clear American female
    "professional": "en-GB-RyanNeural",          # British male, professional tone
    "narrator":     "en-US-ChristopherNeural",   # Rich male narrator
    "motivational": "en-US-TonyNeural",          # Energetic American male
}


def text_to_speech(text: str, voice_key: str, out_dir: str) -> dict:
    """TTS using edge-tts (Microsoft Edge voices). Free, no API key needed.
    Falls back to gTTS if edge-tts is unavailable."""
    import asyncio

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    fname = f"tts_{int(time.time()*1000)}.mp3"
    out_path = Path(out_dir) / fname
    voice = EDGE_VOICE_MAP.get(voice_key, EDGE_VOICE_MAP["professional"])

    # ── Try edge-tts first ──
    try:
        import edge_tts
    except ImportError:
        try:
            import subprocess
            subprocess.run(["pip", "install", "edge-tts", "--quiet"], check=True)
            import edge_tts
        except Exception:
            edge_tts = None

    if edge_tts is not None:
        async def _run_edge():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(out_path))

        try:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, _run_edge())
                        future.result(timeout=60)
                else:
                    loop.run_until_complete(_run_edge())
            except RuntimeError:
                asyncio.run(_run_edge())
            return {"ok": True, "data": fname, "provider": "edge-tts", "error": None}
        except Exception as e:
            pass  # Fall through to gTTS

    # ── Fallback: gTTS ──
    GTTS_STYLES = {
        "male":         {"lang": "en", "tld": "com.au", "slow": False},
        "female":       {"lang": "en", "tld": "co.uk",  "slow": False},
        "professional": {"lang": "en", "tld": "com",    "slow": False},
        "narrator":     {"lang": "en", "tld": "com",    "slow": True},
        "motivational": {"lang": "en", "tld": "ca",     "slow": False},
    }
    try:
        from gtts import gTTS
    except ImportError:
        try:
            import subprocess
            subprocess.run(["pip", "install", "gtts", "--quiet"], check=True)
            from gtts import gTTS
        except Exception as e:
            return {"ok": False, "data": None, "provider": "tts", "error": f"No TTS engine available: {e}"}

    try:
        style = GTTS_STYLES.get(voice_key, GTTS_STYLES["professional"])
        tts = gTTS(text=text, lang=style["lang"], tld=style["tld"], slow=style["slow"])
        tts.save(str(out_path))
        return {"ok": True, "data": fname, "provider": "gtts", "error": None}
    except Exception as e:
        return {"ok": False, "data": None, "provider": "gtts", "error": str(e)}
