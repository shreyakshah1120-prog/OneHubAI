# OneHubAI

> **One hub. Every AI.** A premium Flask SaaS that unifies GPT, Claude, Gemini, Stability AI, Replicate, Whisper, and ElevenLabs into a single beautiful workspace.

![tech](https://img.shields.io/badge/python-3.11+-blue) ![tech](https://img.shields.io/badge/flask-3.0-black) ![tech](https://img.shields.io/badge/bootstrap-5.3-7952b3)

## ✨ Features

| Module | What it does |
| --- | --- |
| 🎯 **AI Studio** | Auto-enhances your prompt, then runs it against GPT / Claude / Gemini — compare them side by side. |
| 🖼️ **Image Generator** | Stability AI, Replicate FLUX, OpenAI Images. Gallery, download, regenerate. |
| 🎙️ **Voice Studio** | Whisper transcription (MP3/WAV/M4A) + 5 ElevenLabs voices (male, female, professional, narrator, motivational). |
| 🎤 **Interview Coach** | Standard / Tough / Shark Tank modes. Resume upload. Voice questions. Scorecard with radar chart. |
| 🧠 **Debate Partner** | Pick or type a topic. Voice debates (browser SpeechRecognition + ElevenLabs). 8-dimension radar score. |
| 📚 **Study Assistant** | Upload PDF/DOCX/PPTX. Auto-generate summary, chapter notes, short/long/revision notes, and 5–50 MCQs with scoring. |
| 🏥 **Health Assistant** | Interactive anatomy figure, click-to-explain organs, upload reports for plain-English analysis. |
| 📜 **History** | Every chat, image, debate, interview, voice file in one searchable timeline. |
| ⚙️ **Settings** | Theme, language, voice preferences, password, profile photo. |

Premium UI: glassmorphism, neon gradients, animated aurora background, floating particles, full dark/light mode.

## 🛠️ Tech Stack

- **Backend**: Python 3, Flask 3, SQLAlchemy, Flask-Login, Flask-WTF (CSRF), Flask-Limiter (rate limiting)
- **Database**: SQLite (zero-config) — swap `DATABASE_URL` for Postgres in production
- **Frontend**: HTML5, Bootstrap 5.3, custom design system in `app/static/css/app.css`, vanilla JS + Chart.js
- **AI providers**: OpenAI · Anthropic · Google Gemini · Stability AI · Replicate · ElevenLabs

## 🚀 Quick start

```bash
# 1) clone / unzip
cd onehubai

# 2) virtualenv
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 3) install
pip install -r requirements.txt

# 4) configure
cp .env.example .env          # then edit .env and add your API keys

# 5) run
python run.py                 # serves on http://localhost:3000
```

You can open the site immediately — every module is reachable without keys, and shows a friendly "configure API key" notice where it needs one.

## 🔐 Environment variables

See `.env.example`. The only **required** value is `SECRET_KEY`. All AI providers are optional — add whichever you want to enable.

```env
SECRET_KEY=change-me
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
STABILITY_API_KEY=sk-...
REPLICATE_API_TOKEN=r8_...
ELEVENLABS_API_KEY=...
```

## 📁 Project structure

```
onehubai/
├── run.py                  # entry-point
├── requirements.txt
├── .env.example
├── instance/               # SQLite DB lives here at runtime
└── app/
    ├── __init__.py         # app factory
    ├── extensions.py
    ├── models.py           # 13 SQLAlchemy tables
    ├── routes/
    │   ├── main.py         # landing
    │   ├── auth.py         # signup / login / logout
    │   ├── dashboard.py
    │   ├── ai_studio.py    # enhance + chat + compare
    │   ├── image.py
    │   ├── voice.py        # Whisper STT + ElevenLabs TTS
    │   ├── interview.py
    │   ├── debate.py
    │   ├── study.py
    │   ├── health.py
    │   ├── history.py
    │   └── settings.py
    ├── services/
    │   ├── ai.py           # unified AI service layer
    │   └── files.py        # PDF/DOCX/PPTX text extraction
    ├── static/
    │   ├── css/app.css     # design system
    │   ├── js/app.js
    │   ├── img/logo.svg    # ← replace with your uploaded logo
    │   ├── img/favicon.svg
    │   ├── uploads/        # user uploads
    │   └── generated/      # AI-generated images & audio
    └── templates/
        ├── _base.html
        ├── _base_public.html      # landing/auth shell
        ├── _base_app.html         # dashboard shell (sidebar + navbar)
        ├── landing.html
        ├── auth/{login,signup}.html
        └── dashboard/{home,ai_studio,image,voice,interview,
                       interview_session,interview_report,
                       debate,debate_session,study,study_detail,
                       health,history,settings}.html
```

## 🔄 Replacing the logo

Drop your file at `app/static/img/logo.svg` (or `logo.png` — then update the references in `_base_public.html`, `_base_app.html`, `auth/login.html`, `auth/signup.html`). The favicon is `app/static/img/favicon.svg`.

## 🛡️ Security

- Werkzeug password hashing (pbkdf2)
- Flask-Login session management with HttpOnly + SameSite=Lax cookies
- Flask-WTF CSRF protection on every form and AJAX POST (token in `<meta name="csrf-token">`)
- Flask-Limiter rate-limit (600/hour default)
- File upload validation (extension whitelist) + 64 MB cap
- Secrets read from `.env` — never committed

## ☁️ Deployment

```bash
# Render / Railway / VPS
gunicorn -w 4 -b 0.0.0.0:$PORT run:app
```

Set the same env vars in your platform dashboard. SQLite works for small deployments; for production scale, point `DATABASE_URL` at Postgres (SQLAlchemy will do the rest).

## 📄 License

MIT — do whatever you want, just don't sell it as-is to compete with us. 😉

---

Built with ❤️ — **OneHubAI**
