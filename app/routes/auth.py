"""Signup / login / logout."""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not name or not email or len(password) < 6:
            flash("Please enter a name, valid email, and password (6+ chars).", "danger")
            return render_template("auth/signup.html")

        if password != confirm:
            flash("Passwords do not match. Please try again.", "danger")
            return render_template("auth/signup.html")

        if User.query.filter_by(email=email).first():
            flash("That email is already registered. Try logging in.", "danger")
            return render_template("auth/signup.html")

        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        flash(f"Welcome to OneHubAI, {name.split()[0]}! 🎉", "success")
        return redirect(url_for("dashboard.home"))

    return render_template("auth/signup.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")
        login_user(user, remember=True)
        return redirect(url_for("dashboard.home"))
    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("main.landing"))
