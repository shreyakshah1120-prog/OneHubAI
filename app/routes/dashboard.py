"""Dashboard home — real per-day chart data, zero-state for new users."""
from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func

from ..extensions import db
from ..models import (
    Chat, GeneratedImage, Interview, DebateSession,
    StudyMaterial, VoiceFile, HistoryEvent, HealthReport,
)

bp = Blueprint("dashboard", __name__)


def _daily_counts(model, user_id: int, days: int = 7) -> list:
    """Return list of `days` integers — count per day oldest→newest.
    Returns all zeros for brand-new users."""
    cutoff = datetime.utcnow() - timedelta(days=days - 1)
    rows = (
        db.session.query(
            func.date(model.created_at).label("day"),
            func.count().label("cnt"),
        )
        .filter(model.user_id == user_id, model.created_at >= cutoff)
        .group_by(func.date(model.created_at))
        .all()
    )
    bucket = {str(r.day): r.cnt for r in rows}
    result = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=days - 1 - i)).date()
        result.append(bucket.get(str(d), 0))
    return result


def _day_labels(days: int = 7) -> list:
    return [
        (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%a")
        for i in range(days)
    ]


@bp.route("/")
@login_required
def home():
    uid = current_user.id
    week_ago = datetime.utcnow() - timedelta(days=7)

    stats = {
        "chats":      Chat.query.filter_by(user_id=uid).count(),
        "images":     GeneratedImage.query.filter_by(user_id=uid).count(),
        "studies":    StudyMaterial.query.filter_by(user_id=uid).count(),
        "interviews": Interview.query.filter_by(user_id=uid).count(),
        "debates":    DebateSession.query.filter_by(user_id=uid).count(),
        "voices":     VoiceFile.query.filter_by(user_id=uid).count(),
        "healths":    HealthReport.query.filter_by(user_id=uid).count(),
        "this_week":  HistoryEvent.query.filter(
            HistoryEvent.user_id == uid,
            HistoryEvent.created_at >= week_ago,
        ).count(),
    }

    # Real per-day chart data (all zeros for new users)
    chart = {
        "labels":  _day_labels(7),
        "chats":   _daily_counts(Chat, uid),
        "images":  _daily_counts(GeneratedImage, uid),
        "studies": _daily_counts(StudyMaterial, uid),
    }

    recent = (
        HistoryEvent.query.filter_by(user_id=uid)
        .order_by(HistoryEvent.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "dashboard/home.html",
        stats=stats,
        chart=chart,
        recent=recent,
    )
