"""Unified history panel."""
from flask import Blueprint, render_template, redirect, url_for, abort
from flask_login import login_required, current_user

from ..extensions import db
from ..models import (
    HistoryEvent, Chat, GeneratedImage, StudyMaterial,
    Interview, DebateSession, HealthReport, VoiceFile,
)

bp = Blueprint("history", __name__)

MODULE_ROUTES = {
    "chat": "ai_studio.index",
    "image": "image.index",
    "study": "study.show",
    "interview": "interview.session",
    "debate": "debate.session",
    "health": "health.index",
    "voice": "voice.index",
}


@bp.route("/")
@login_required
def index():
    events = (
        HistoryEvent.query.filter_by(user_id=current_user.id)
        .order_by(HistoryEvent.created_at.desc())
        .all()
    )
    return render_template("dashboard/history.html", events=events)


@bp.route("/open/<int:eid>")
@login_required
def open_event(eid: int):
    ev = HistoryEvent.query.filter_by(id=eid, user_id=current_user.id).first_or_404()
    target = MODULE_ROUTES.get(ev.module)
    if not target:
        return redirect(url_for("history.index"))
    try:
        if ev.module in {"study"}:
            return redirect(url_for(target, mid=ev.ref_id))
        if ev.module in {"interview", "debate"}:
            return redirect(url_for(target, sid=ev.ref_id))
        return redirect(url_for(target))
    except Exception:
        return redirect(url_for("history.index"))


@bp.route("/clear", methods=["POST"])
@login_required
def clear():
    HistoryEvent.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return redirect(url_for("history.index"))


@bp.route("/delete/<int:eid>", methods=["POST"])
@login_required
def delete_event(eid: int):
    ev = HistoryEvent.query.filter_by(id=eid, user_id=current_user.id).first_or_404()
    db.session.delete(ev)
    db.session.commit()
    return redirect(url_for("history.index"))
