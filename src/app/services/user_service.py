from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.models.user import User


class UserError(ValueError):
    """Raised when a user management operation cannot be completed."""


def change_credentials(user: User, current_password: str, new_username: str, new_password: str) -> None:
    """
    Update the username and password for *user*.

    Raises UserError if the current password is wrong.
    """
    if not check_password_hash(user.password_hash, current_password):
        raise UserError("Current password is incorrect.")
    if len(new_password) < 6:
        raise UserError("Password must be at least 6 characters.")
    user.username = new_username
    user.password_hash = generate_password_hash(new_password)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def create_user(username: str, password: str, role: str = User.ROLE_ADMIN) -> User:
    """
    Create and persist a new user.

    Raises UserError if the username is already taken or role is invalid.
    """
    if role not in (User.ROLE_ADMIN, User.ROLE_SUPERADMIN):
        raise UserError(f'Invalid role "{role}".')
    if len(password) < 6:
        raise UserError("Password must be at least 6 characters.")
    if User.query.filter_by(username=username).first():
        raise UserError(f'Username "{username}" already taken.')
    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
    )
    db.session.add(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return user


def delete_user(user: User, current_user_id: int) -> None:
    """
    Delete *user* from the database.

    Raises UserError if the user is trying to delete their own account.
    """
    if user.id == current_user_id:
        raise UserError("You cannot delete your own account.")
    db.session.delete(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def edit_user(user: User, new_username: str, new_password: str | None = None) -> None:
    """
    Update username and optionally password for *user*.

    Raises UserError if new_username is empty or already taken by another user.
    """
    if not new_username:
        raise UserError("Username cannot be empty.")
    if User.query.filter(User.username == new_username, User.id != user.id).first():
        raise UserError(f'Username "{new_username}" already taken.')
    user.username = new_username
    if new_password:
        if len(new_password) < 6:
            raise UserError("Password must be at least 6 characters.")
        user.password_hash = generate_password_hash(new_password)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
