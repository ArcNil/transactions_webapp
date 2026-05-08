import pytest
from unittest.mock import patch
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models.user import User
from app.services.user_service import (
    UserError,
    change_credentials,
    create_user,
    delete_user,
    edit_user,
)


class TestCreateUser:
    def test_creates_and_returns_user_with_hashed_password(self, app, db_session):
        user = create_user("newuser", "securepass")

        assert user.id is not None
        assert user.username == "newuser"
        assert check_password_hash(user.password_hash, "securepass")

    def test_raises_if_username_already_taken(self, app, sample_user, db_session):
        with pytest.raises(UserError):
            create_user(sample_user.username, "anypassword")

    def test_creates_user_with_default_admin_role(self, app, db_session):
        user = create_user("roledefaultuser", "pass123")

        assert user.role == User.ROLE_ADMIN

    def test_creates_user_with_explicit_admin_role(self, app, db_session):
        user = create_user("explicitadmin", "pass123", role=User.ROLE_ADMIN)

        assert user.role == User.ROLE_ADMIN

    def test_creates_user_with_superadmin_role(self, app, db_session):
        user = create_user("newsuperadmin", "pass123", role=User.ROLE_SUPERADMIN)

        assert user.role == User.ROLE_SUPERADMIN

    def test_raises_for_invalid_role(self, app, db_session):
        with pytest.raises(UserError):
            create_user("badroluser", "pass123", role="manager")

    def test_create_user_raises_for_short_password(self, app, db_session):
        with pytest.raises(UserError):
            create_user("newuser", "abc")

    def test_commit_failure_rolls_back_and_propagates(self, app, db_session):
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                create_user("newuser", "securepass")
        mock_rollback.assert_called_once()


class TestChangeCredentials:
    def test_updates_username_and_password_hash(self, app, sample_user, db_session):
        change_credentials(sample_user, "password123", "updateduser", "newpassword")
        db_session.refresh(sample_user)

        assert sample_user.username == "updateduser"
        assert check_password_hash(sample_user.password_hash, "newpassword")

    def test_raises_if_current_password_is_wrong(self, app, sample_user, db_session):
        with pytest.raises(UserError):
            change_credentials(sample_user, "wrongpassword", "updateduser", "newpassword")

    def test_change_credentials_raises_for_short_new_password(self, app, sample_user, db_session):
        with pytest.raises(UserError):
            change_credentials(sample_user, "password123", "updateduser", "ab")

    def test_commit_failure_rolls_back_and_propagates(self, app, sample_user, db_session):
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                change_credentials(sample_user, "password123", "updateduser", "newpass456")
        mock_rollback.assert_called_once()


class TestDeleteUser:
    def test_deletes_user_from_db(self, app, sample_user, db_session):
        other_user = User(
            username="otheruser",
            password_hash=generate_password_hash("pass"),
        )
        db_session.add(other_user)
        db_session.commit()
        other_id = other_user.id

        delete_user(other_user, current_user_id=sample_user.id)

        assert db_session.get(User, other_id) is None

    def test_raises_if_deleting_own_account(self, app, sample_user, db_session):
        with pytest.raises(UserError):
            delete_user(sample_user, current_user_id=sample_user.id)

    def test_commit_failure_rolls_back_and_propagates(self, app, sample_user, db_session):
        other_user = User(
            username="otheruser",
            password_hash=generate_password_hash("pass"),
        )
        db_session.add(other_user)
        db_session.commit()
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                delete_user(other_user, current_user_id=sample_user.id)
        mock_rollback.assert_called_once()


class TestEditUser:
    def test_updates_username(self, app, sample_user, db_session):
        edit_user(sample_user, new_username="renameduser")
        db_session.refresh(sample_user)

        assert sample_user.username == "renameduser"

    def test_updates_password_when_new_password_given(self, app, sample_user, db_session):
        edit_user(sample_user, new_username=sample_user.username, new_password="newpass456")
        db_session.refresh(sample_user)

        assert check_password_hash(sample_user.password_hash, "newpass456")

    def test_does_not_change_password_when_new_password_is_none(self, app, sample_user, db_session):
        original_hash = sample_user.password_hash
        edit_user(sample_user, new_username=sample_user.username, new_password=None)
        db_session.refresh(sample_user)

        assert sample_user.password_hash == original_hash

    def test_raises_if_new_username_is_empty(self, app, sample_user, db_session):
        with pytest.raises(UserError):
            edit_user(sample_user, new_username="")

    def test_raises_if_new_username_is_taken_by_another_user(self, app, sample_user, db_session):
        other_user = User(
            username="takenuser",
            password_hash=generate_password_hash("pass"),
        )
        db_session.add(other_user)
        db_session.commit()

        with pytest.raises(UserError):
            edit_user(sample_user, new_username="takenuser")

    def test_edit_user_raises_for_short_password(self, app, sample_user, db_session):
        with pytest.raises(UserError):
            edit_user(sample_user, new_username="newname", new_password="abc")

    def test_commit_failure_rolls_back_and_propagates(self, app, sample_user, db_session):
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                edit_user(sample_user, new_username="newname")
        mock_rollback.assert_called_once()
