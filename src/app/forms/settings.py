from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, EqualTo, Length


class ChangeCredentialsForm(FlaskForm):
    new_username = StringField("New Username", validators=[DataRequired(), Length(min=3, max=64)])
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password",
        validators=[DataRequired(), Length(min=6), EqualTo("confirm_password", message="Passwords must match.")],
    )
    confirm_password = PasswordField("Confirm New Password", validators=[DataRequired()])
    submit = SubmitField("Update Credentials")


class AddUserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6), EqualTo("confirm_password", message="Passwords must match.")],
    )
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired()])
    role = SelectField(
        "Role",
        choices=[("admin", "Admin"), ("superadmin", "Superadmin")],
        default="admin",
    )
    submit = SubmitField("Add User")
