import click
import os
import sys
from app import create_app, db

app = create_app()


@app.cli.command("seed")
def seed():
    """Create the default superuser if not present."""
    password = os.environ.get("SEED_ADMIN_PASSWORD")
    if not password:
        click.echo("Error: SEED_ADMIN_PASSWORD environment variable is not set.", err=True)
        sys.exit(1)
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
