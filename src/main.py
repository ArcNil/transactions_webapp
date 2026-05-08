import click
from app import create_app, db

app = create_app()


@app.cli.command("seed")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True,
              help="Password for the default superuser account.")
def seed(password):
    """Create the default superuser if not present."""
    from app.models.user import User
    from werkzeug.security import generate_password_hash

    if len(password) < 6:
        raise click.UsageError("Password must be at least 6 characters.")

    existing = User.query.filter_by(username="admin").first()
    if existing:
        click.echo("Superuser already exists — skipping.")
        return

    user = User(
        username="admin",
        password_hash=generate_password_hash(password),
        role=User.ROLE_SUPERADMIN,
    )
    db.session.add(user)
    db.session.commit()
    click.echo("Superuser created: username=admin")
