from app.forms.settings import AddUserForm, ChangeCredentialsForm


def test_change_credentials_form_validates_with_matching_passwords(app):
    with app.test_request_context("/"):
        form = ChangeCredentialsForm(
            data={
                "new_username": "newuser",
                "current_password": "oldpass",
                "new_password": "newpass123",
                "confirm_password": "newpass123",
            }
        )
        assert form.validate()


def test_change_credentials_form_fails_when_passwords_dont_match(app):
    with app.test_request_context("/"):
        form = ChangeCredentialsForm(
            data={
                "new_username": "newuser",
                "current_password": "oldpass",
                "new_password": "newpass123",
                "confirm_password": "different",
            }
        )
        assert not form.validate()
        assert "new_password" in form.errors


def test_change_credentials_form_fails_when_username_too_short(app):
    with app.test_request_context("/"):
        form = ChangeCredentialsForm(
            data={
                "new_username": "ab",  # less than 3 chars
                "current_password": "oldpass",
                "new_password": "newpass123",
                "confirm_password": "newpass123",
            }
        )
        assert not form.validate()
        assert "new_username" in form.errors


def test_add_user_form_validates_correctly(app):
    with app.test_request_context("/"):
        form = AddUserForm(
            data={
                "username": "brandnewuser",
                "password": "secret123",
                "confirm_password": "secret123",
            }
        )
        assert form.validate()


def test_add_user_form_fails_when_passwords_dont_match(app):
    with app.test_request_context("/"):
        form = AddUserForm(
            data={
                "username": "brandnewuser",
                "password": "secret123",
                "confirm_password": "different",
            }
        )
        assert not form.validate()
        assert "password" in form.errors


def test_change_credentials_form_fails_when_new_password_too_short(app):
    with app.test_request_context("/"):
        form = ChangeCredentialsForm(
            data={
                "new_username": "newuser",
                "current_password": "oldpass",
                "new_password": "short",
                "confirm_password": "short",
            }
        )
        assert not form.validate()
        assert "new_password" in form.errors


def test_add_user_form_fails_when_password_too_short(app):
    with app.test_request_context("/"):
        form = AddUserForm(
            data={
                "username": "brandnewuser",
                "password": "short",
                "confirm_password": "short",
            }
        )
        assert not form.validate()
        assert "password" in form.errors


def test_add_user_form_fails_when_username_too_short(app):
    with app.test_request_context("/"):
        form = AddUserForm(
            data={
                "username": "ab",
                "password": "secret123",
                "confirm_password": "secret123",
            }
        )
        assert not form.validate()
        assert "username" in form.errors
