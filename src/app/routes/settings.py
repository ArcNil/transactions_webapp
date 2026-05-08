from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.forms.settings import ChangeCredentialsForm, AddUserForm
from app.services.user_service import (
    change_credentials as svc_change_credentials,
    create_user as svc_create_user,
    delete_user as svc_delete_user,
    edit_user as svc_edit_user,
    UserError,
)
from app.utils.decorators import superadmin_required
from app.utils.monitor import record_action

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/")
@login_required
def index():
    users = User.query.order_by(User.username).all()
    creds_form = ChangeCredentialsForm()
    add_form = AddUserForm()
    return render_template(
        "settings/index.html",
        users=users,
        creds_form=creds_form,
        add_form=add_form,
    )


@bp.route("/change-credentials", methods=["POST"])
@login_required
def change_credentials():
    form = ChangeCredentialsForm()
    if form.validate_on_submit():
        try:
            svc_change_credentials(
                user=current_user,
                current_password=form.current_password.data,
                new_username=form.new_username.data,
                new_password=form.new_password.data,
            )
            record_action(current_user.id, current_user.username, "settings.credentials_changed")
            flash("Credentials updated successfully.", "success")
        except UserError as e:
            flash(str(e), "danger")
    else:
        for errors in form.errors.values():
            for error in errors:
                flash(error, "danger")
    return redirect(url_for("settings.index"))


@bp.route("/users/add", methods=["POST"])
@login_required
@superadmin_required
def add_user():
    form = AddUserForm()
    if form.validate_on_submit():
        try:
            user = svc_create_user(form.username.data, form.password.data, form.role.data)
            record_action(current_user.id, current_user.username, "settings.user_added", user.username)
            flash(f'User "{user.username}" created.', "success")
        except UserError as e:
            flash(str(e), "danger")
    else:
        for errors in form.errors.values():
            for error in errors:
                flash(error, "danger")
    return redirect(url_for("settings.index"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@superadmin_required
def delete_user(user_id):
    user = db.get_or_404(User, user_id)
    try:
        svc_delete_user(user, current_user.id)
        record_action(current_user.id, current_user.username, "settings.user_deleted", user.username)
        flash(f'User "{user.username}" deleted.', "success")
    except UserError as e:
        flash(str(e), "danger")
    return redirect(url_for("settings.index"))


@bp.route("/users/<int:user_id>/edit", methods=["POST"])
@login_required
@superadmin_required
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    new_username = request.form.get("username", "").strip()
    new_password = request.form.get("password", "").strip() or None
    try:
        svc_edit_user(user, new_username, new_password)
        record_action(current_user.id, current_user.username, "settings.user_edited", user.username)
        flash(f'User "{user.username}" updated.', "success")
    except UserError as e:
        flash(str(e), "danger")
    return redirect(url_for("settings.index"))
