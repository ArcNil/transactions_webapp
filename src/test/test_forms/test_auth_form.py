from app.forms.auth import LoginForm


def test_login_form_validates_with_both_fields(app):
    with app.test_request_context("/"):
        form = LoginForm(data={"username": "testuser", "password": "secret"})
        assert form.validate()


def test_login_form_fails_when_username_missing(app):
    with app.test_request_context("/"):
        form = LoginForm(data={"username": "", "password": "secret"})
        assert not form.validate()
        assert "username" in form.errors


def test_login_form_fails_when_password_missing(app):
    with app.test_request_context("/"):
        form = LoginForm(data={"username": "testuser", "password": ""})
        assert not form.validate()
        assert "password" in form.errors


def test_login_form_fails_with_whitespace_only_username(app):
    with app.test_request_context("/"):
        form = LoginForm(data={"username": "   ", "password": "secret"})
        assert not form.validate()
        assert "username" in form.errors


def test_login_form_fails_with_whitespace_only_password(app):
    with app.test_request_context("/"):
        form = LoginForm(data={"username": "testuser", "password": "   "})
        assert not form.validate()
        assert "password" in form.errors
