import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError
from ml_backend.extensions import db
from ml_backend.models import User


def register_cli(app: Flask) -> None:
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True, help="Admin username.")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Admin password (minimum 8 characters).",
    )
    @with_appcontext
    def create_admin(username: str, password: str) -> None:
        """Create a new administrator account via trusted local CLI access."""
        normalized_username = username.strip()
        if not normalized_username or len(normalized_username) > 80:
            raise click.ClickException("Username must be between 1 and 80 characters.")
        if not password or not password.strip() or len(password) < 8:
            raise click.ClickException("Password must be at least 8 characters.")

        existing = db.session.execute(
            db.select(User).where(db.func.lower(User.username) == normalized_username.lower())
        ).scalar_one_or_none()
        if existing is not None:
            raise click.ClickException(
                f"User '{existing.username}' already exists (id={existing.id}, role={existing.role}); aborting."
            )

        admin = User(username=normalized_username, role="admin")
        admin.set_password(password)
        db.session.add(admin)
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise click.ClickException(f"Database integrity error creating admin: {exc}") from exc

        click.echo(f"Created admin user {admin.id} {admin.username} (role={admin.role})")
