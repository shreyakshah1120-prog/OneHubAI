"""Notification centre routes."""
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Notification

bp = Blueprint("notifications", __name__)

# Default seeded notifications shown to every new user
SEED_NOTIFICATIONS = [
    {
        "category": "general",
        "title": "Welcome to OneHubAI",
        "body": "Your all-in-one AI platform is ready. Explore Study Assistant, AI Interview, Debates, and more.",
    },
    {
        "category": "feature",
        "title": "New Feature: Voice Study Mode",
        "body": "You can now listen to your study notes read aloud using the built-in TTS engine in Study Assistant.",
    },
    {
        "category": "tool",
        "title": "AI Debate Tool Added",
        "body": "Challenge your critical thinking with real-time AI debates. Try it from the sidebar.",
    },
    {
        "category": "update",
        "title": "Platform Update v2.1",
        "body": "Faster response times, improved PDF parsing accuracy, and a refreshed dashboard UI.",
    },
    {
        "category": "study",
        "title": "Study Module Improvement",
        "body": "Summary Overview now loads instantly at the top of the page — no scrolling needed.",
    },
    {
        "category": "test",
        "title": "Test Generator Upgraded",
        "body": "Generate MCQ, True/False, Fill-in-the-Blank, Short Answer, and Essay questions from any document.",
    },
    {
        "category": "account",
        "title": "Profile Customisation Available",
        "body": "Upload a profile photo, set your preferred language and AI voice in Settings.",
    },
    {
        "category": "system",
        "title": "System Status: All Services Operational",
        "body": "All OneHubAI services are running normally. Uptime: 99.9%.",
    },
]


def _seed_if_empty(user_id: int) -> None:
    """Insert seed notifications for brand-new users (once)."""
    existing = Notification.query.filter_by(user_id=user_id).count()
    if existing == 0:
        for n in SEED_NOTIFICATIONS:
            db.session.add(Notification(user_id=user_id, **n))
        db.session.commit()


@bp.route("/", methods=["GET"])
@login_required
def list_notifications():
    _seed_if_empty(current_user.id)
    notes = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    unread = sum(1 for n in notes if not n.is_read)
    return jsonify({
        "ok": True,
        "unread": unread,
        "notifications": [
            {
                "id": n.id,
                "category": n.category,
                "title": n.title,
                "body": n.body,
                "is_read": n.is_read,
                "created_at": n.created_at.strftime("%b %d, %Y"),
            }
            for n in notes
        ],
    })


@bp.route("/<int:nid>/read", methods=["POST"])
@login_required
def mark_read(nid: int):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"ok": True})
