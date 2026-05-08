from app.models.user import User
from werkzeug.security import generate_password_hash


def test_login_page_returns_200_for_anonymous_user(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Login" in response.data


def test_login_page_redirects_to_pos_for_authenticated_user(logged_in_client):
    response = logged_in_client.get("/login")
    assert response.status_code == 302
    assert "/pos/" in response.headers["Location"]


def test_login_with_wrong_password_shows_error(client, sample_user):
    response = client.post(
        "/login",
        data={"username": "testuser", "password": "wrongpassword"},
    )
    assert response.status_code == 200
    assert b"Invalid username or password." in response.data


def test_login_with_nonexistent_user_shows_error(client):
    response = client.post(
        "/login",
        data={"username": "nobody", "password": "password123"},
    )
    assert response.status_code == 200
    assert b"Invalid username or password." in response.data


def test_login_with_correct_credentials_redirects_to_pos(client, sample_user):
    response = client.post(
        "/login",
        data={"username": "testuser", "password": "password123"},
    )
    assert response.status_code == 302
    assert "/pos/" in response.headers["Location"]


def test_logout_redirects_to_login_and_clears_session(logged_in_client):
    response = logged_in_client.get("/logout")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    # Subsequent request to a protected route should redirect to login again.
    follow = logged_in_client.get("/dashboard")
    assert follow.status_code == 302
    assert "/login" in follow.headers["Location"]


def test_logout_anonymous_user_redirects_to_login(client):
    # @login_required on logout redirects unauthenticated users to login.
    response = client.get("/logout")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
