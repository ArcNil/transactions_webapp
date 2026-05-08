from werkzeug.security import check_password_hash, generate_password_hash

from app import db as _db
from app.models.user import User


def test_settings_index_returns_200_when_authenticated(logged_in_client):
    response = logged_in_client.get("/settings/")
    assert response.status_code == 200


def test_change_credentials_with_correct_password_updates_username_and_password(
    logged_in_client, sample_user, db_session
):
    user_id = sample_user.id
    response = logged_in_client.post(
        "/settings/change-credentials",
        data={
            "new_username": "updateduser",
            "current_password": "password123",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Credentials updated successfully." in response.data

    user = db_session.get(User, user_id)
    assert user.username == "updateduser"


def test_change_credentials_with_wrong_current_password_flashes_error(logged_in_client):
    response = logged_in_client.post(
        "/settings/change-credentials",
        data={
            "new_username": "updateduser",
            "current_password": "wrongpassword",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Current password is incorrect." in response.data


def test_add_user_creates_new_user(logged_in_superadmin_client, db_session):
    response = logged_in_superadmin_client.post(
        "/settings/users/add",
        data={
            "username": "brandnewuser",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"created" in response.data

    user = User.query.filter_by(username="brandnewuser").first()
    assert user is not None


def test_add_user_with_duplicate_username_flashes_error(
    logged_in_superadmin_client, sample_user, db_session
):
    response = logged_in_superadmin_client.post(
        "/settings/users/add",
        data={
            "username": "testuser",  # same as sample_user
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"already taken" in response.data

    assert User.query.filter_by(username="testuser").count() == 1


def test_delete_user_removes_other_user(logged_in_superadmin_client, db_session):
    other = User(
        username="otheruser", password_hash=generate_password_hash("pass")
    )
    db_session.add(other)
    db_session.commit()
    other_id = other.id

    response = logged_in_superadmin_client.post(
        f"/settings/users/{other_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"deleted" in response.data

    assert db_session.get(User, other_id) is None


def test_delete_self_flashes_cannot_delete_own_account(
    logged_in_superadmin_client, superadmin_user
):
    response = logged_in_superadmin_client.post(
        f"/settings/users/{superadmin_user.id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"You cannot delete your own account." in response.data


def test_edit_user_updates_username(logged_in_superadmin_client, db_session):
    other = User(
        username="editme", password_hash=generate_password_hash("pass")
    )
    db_session.add(other)
    db_session.commit()
    user_id = other.id

    response = logged_in_superadmin_client.post(
        f"/settings/users/{user_id}/edit",
        data={"username": "editeduser", "password": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"updated" in response.data

    user = db_session.get(User, user_id)
    assert user.username == "editeduser"


def test_edit_user_with_empty_username_flashes_error(logged_in_superadmin_client, db_session):
    other = User(username="editme2", password_hash=generate_password_hash("pass"))
    db_session.add(other)
    db_session.commit()

    response = logged_in_superadmin_client.post(
        f"/settings/users/{other.id}/edit",
        data={"username": "", "password": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Username cannot be empty." in response.data

    unchanged = db_session.get(User, other.id)
    assert unchanged.username == "editme2"


def test_edit_user_with_duplicate_username_flashes_error(
    logged_in_superadmin_client, sample_user, db_session
):
    other = User(username="otherone", password_hash=generate_password_hash("pass"))
    db_session.add(other)
    db_session.commit()

    response = logged_in_superadmin_client.post(
        f"/settings/users/{other.id}/edit",
        data={"username": "testuser", "password": ""},  # testuser = sample_user
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"already taken" in response.data


def test_add_user_with_short_username_flashes_validation_error(logged_in_superadmin_client):
    response = logged_in_superadmin_client.post(
        "/settings/users/add",
        data={"username": "ab", "password": "password123", "confirm_password": "password123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert User.query.filter_by(username="ab").first() is None


def test_delete_nonexistent_user_returns_404(logged_in_superadmin_client):
    response = logged_in_superadmin_client.post("/settings/users/99999/delete")
    assert response.status_code == 404


def test_edit_user_updates_password(logged_in_superadmin_client, db_session):
    other = User(username="pwduser", password_hash=generate_password_hash("oldpass"))
    db_session.add(other)
    db_session.commit()
    other_id = other.id

    response = logged_in_superadmin_client.post(
        f"/settings/users/{other_id}/edit",
        data={"username": "pwduser", "password": "brandnewpass"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"updated" in response.data

    db_session.refresh(other)
    assert check_password_hash(other.password_hash, "brandnewpass")


def test_edit_user_nonexistent_user_returns_404(logged_in_superadmin_client):
    response = logged_in_superadmin_client.post(
        "/settings/users/99999/edit",
        data={"username": "ghost", "password": ""},
    )
    assert response.status_code == 404


def test_change_credentials_with_non_matching_confirm_password_flashes_error(
    logged_in_client,
):
    response = logged_in_client.post(
        "/settings/change-credentials",
        data={
            "new_username": "validuser",
            "current_password": "password123",
            "new_password": "newpass123",
            "confirm_password": "different",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"match" in response.data


# ---------------------------------------------------------------------------
# Superadmin-only route access tests
# ---------------------------------------------------------------------------


def test_add_user_returns_403_for_admin(logged_in_client):
    response = logged_in_client.post(
        "/settings/users/add",
        data={
            "username": "shouldnotexist",
            "password": "password123",
            "confirm_password": "password123",
        },
    )
    assert response.status_code == 403
    assert User.query.filter_by(username="shouldnotexist").first() is None


def test_delete_user_returns_403_for_admin(logged_in_client, sample_user, db_session):
    other = User(username="nodelete", password_hash=generate_password_hash("pass"))
    db_session.add(other)
    db_session.commit()
    other_id = other.id

    response = logged_in_client.post(f"/settings/users/{other_id}/delete")
    assert response.status_code == 403
    assert db_session.get(User, other_id) is not None


def test_edit_user_returns_403_for_admin(logged_in_client, sample_user, db_session):
    other = User(username="noedit", password_hash=generate_password_hash("pass"))
    db_session.add(other)
    db_session.commit()
    other_id = other.id

    response = logged_in_client.post(
        f"/settings/users/{other_id}/edit",
        data={"username": "noedit_renamed", "password": ""},
    )
    assert response.status_code == 403
    assert db_session.get(User, other_id).username == "noedit"


def test_add_user_with_password_too_short_flashes_error(logged_in_superadmin_client):
    response = logged_in_superadmin_client.post(
        "/settings/users/add",
        data={"username": "validuser", "password": "abc", "confirm_password": "abc"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert User.query.filter_by(username="validuser").first() is None


def test_add_user_with_non_matching_passwords_flashes_error(logged_in_superadmin_client):
    response = logged_in_superadmin_client.post(
        "/settings/users/add",
        data={
            "username": "validuser",
            "password": "password123",
            "confirm_password": "different123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"match" in response.data
    assert User.query.filter_by(username="validuser").first() is None
