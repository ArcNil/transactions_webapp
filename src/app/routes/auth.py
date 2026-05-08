from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.models.user import User
from app.forms.auth import LoginForm
from app.utils.monitor import record_action

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pos.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            record_action(user.id, user.username, "auth.login.success", f"ip={request.remote_addr}")
            return redirect(url_for("pos.index"))
        failed_user = form.username.data
        record_action(None, failed_user, "auth.login.failure", f"ip={request.remote_addr}")
        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    record_action(current_user.id, current_user.username, "auth.logout")
    logout_user()
    return redirect(url_for("auth.login"))
