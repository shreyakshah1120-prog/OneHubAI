"""SQLAlchemy models for OneHubAI."""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from .extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(255))
    theme = db.Column(db.String(10), default="dark")
    language = db.Column(db.String(10), default="en")
    voice_pref = db.Column(db.String(40), default="professional")
    notifications = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chats = db.relationship("Chat", backref="user", cascade="all, delete-orphan")
    images = db.relationship("GeneratedImage", backref="user", cascade="all, delete-orphan")
    studies = db.relationship("StudyMaterial", backref="user", cascade="all, delete-orphan")
    interviews = db.relationship("Interview", backref="user", cascade="all, delete-orphan")
    debates = db.relationship("DebateSession", backref="user", cascade="all, delete-orphan")
    healths = db.relationship("HealthReport", backref="user", cascade="all, delete-orphan")
    voices = db.relationship("VoiceFile", backref="user", cascade="all, delete-orphan")
    history = db.relationship("HistoryEvent", backref="user", cascade="all, delete-orphan")

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


class Chat(db.Model):
    __tablename__ = "chats"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), default="Untitled Chat")
    model = db.Column(db.String(40))
    original_prompt = db.Column(db.Text)
    enhanced_prompt = db.Column(db.Text)
    response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GeneratedImage(db.Model):
    __tablename__ = "generated_images"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    prompt = db.Column(db.Text)
    enhanced_prompt = db.Column(db.Text)
    provider = db.Column(db.String(40))
    file_path = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudyMaterial(db.Model):
    __tablename__ = "study_materials"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename = db.Column(db.String(255))
    summary = db.Column(db.Text)
    short_notes = db.Column(db.Text)
    long_notes = db.Column(db.Text)
    revision_notes = db.Column(db.Text)
    chapter_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    mcqs = db.relationship("MCQ", backref="study", cascade="all, delete-orphan")


class MCQ(db.Model):
    __tablename__ = "mcqs"
    id = db.Column(db.Integer, primary_key=True)
    study_id = db.Column(db.Integer, db.ForeignKey("study_materials.id"))
    question = db.Column(db.Text)
    options_json = db.Column(db.Text)  # JSON list
    correct_index = db.Column(db.Integer)
    explanation = db.Column(db.Text)


class Interview(db.Model):
    __tablename__ = "interviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    interview_type = db.Column(db.String(40))  # standard / tough / shark
    role = db.Column(db.String(120))
    resume_text = db.Column(db.Text)
    questions_json = db.Column(db.Text)
    answers_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    report = db.relationship("InterviewReport", backref="interview", uselist=False, cascade="all, delete-orphan")


class InterviewReport(db.Model):
    __tablename__ = "interview_reports"
    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey("interviews.id"))
    communication = db.Column(db.Integer)
    confidence = db.Column(db.Integer)
    technical = db.Column(db.Integer)
    leadership = db.Column(db.Integer)
    problem_solving = db.Column(db.Integer)
    body_language = db.Column(db.Integer)
    resume_quality = db.Column(db.Integer)
    overall = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    weak_points = db.Column(db.Text)
    missing_skills = db.Column(db.Text)
    ats_suggestions = db.Column(db.Text)


class DebateSession(db.Model):
    __tablename__ = "debate_sessions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    topic = db.Column(db.String(255))
    transcript_json = db.Column(db.Text)
    scores_json = db.Column(db.Text)
    suggestions = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class HealthReport(db.Model):
    __tablename__ = "health_reports"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    weight = db.Column(db.Float)
    height = db.Column(db.Float)
    symptoms = db.Column(db.Text)
    uploaded_file = db.Column(db.String(400))
    analysis = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VoiceFile(db.Model):
    __tablename__ = "voice_files"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kind = db.Column(db.String(20))  # tts / stt
    text = db.Column(db.Text)
    voice = db.Column(db.String(40))
    file_path = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class HistoryEvent(db.Model):
    __tablename__ = "history_events"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    module = db.Column(db.String(40))  # chat / image / study / interview / debate / health / voice
    title = db.Column(db.String(255))
    ref_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def log_history(user_id: int, module: str, title: str, ref_id: int | None = None) -> None:
    db.session.add(HistoryEvent(user_id=user_id, module=module, title=title, ref_id=ref_id))
    db.session.commit()


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category = db.Column(db.String(40), default="general")   # feature / tool / update / study / test / account / system
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
