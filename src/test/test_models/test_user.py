import pytest
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app import db as _db
from app.models.user import User


def test_user_can_be_created(db_session):
    user = User(username="alice", password_hash=generate_password_hash("secret"))
    db_session.add(user)
    db_session.commit()

    saved = db_session.get(User, user.id)
    assert saved is not None
    assert saved.username == "alice"


def test_username_is_unique(db_session):
    u1 = User(username="dupname", password_hash=generate_password_hash("pass1"))
    u2 = User(username="dupname", password_hash=generate_password_hash("pass2"))
    db_session.add(u1)
    db_session.commit()

    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_password_not_stored_in_plain_text(db_session):
    plain = "mysecretpassword"
    user = User(username="bobtest", password_hash=generate_password_hash(plain))
    db_session.add(user)
    db_session.commit()

    assert user.password_hash != plain
    assert len(user.password_hash) > len(plain)


def test_username_cannot_be_null(db_session):
    user = User(username=None, password_hash=generate_password_hash("secret"))
    db_session.add(user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_password_hash_cannot_be_null(db_session):
    user = User(username="nullpwtest", password_hash=None)
    db_session.add(user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_role_defaults_to_admin(db_session):
    user = User(username="defaultrole", password_hash=generate_password_hash("pass"))
    db_session.add(user)
    db_session.commit()

    assert user.role == User.ROLE_ADMIN


def test_role_constants_have_expected_values():
    assert User.ROLE_ADMIN == "admin"
    assert User.ROLE_SUPERADMIN == "superadmin"


def test_is_superadmin_returns_false_for_admin_role(db_session):
    user = User(
        username="adminrole",
        password_hash=generate_password_hash("pass"),
        role=User.ROLE_ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    assert user.is_superadmin is False


def test_is_superadmin_returns_true_for_superadmin_role(db_session):
    user = User(
        username="superadminrole",
        password_hash=generate_password_hash("pass"),
        role=User.ROLE_SUPERADMIN,
    )
    db_session.add(user)
    db_session.commit()

    assert user.is_superadmin is True
