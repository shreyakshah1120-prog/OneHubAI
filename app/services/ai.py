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
            res = m.generate_content(prompt)
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
            timeout=120,
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
