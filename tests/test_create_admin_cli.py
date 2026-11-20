import pytest
from ml_backend import create_app
from ml_backend.extensions import db
from ml_backend.models import User


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_create_admin_cli_creates_hashed_admin_user(app):
    runner = app.test_cli_runner()

    result = runner.invoke(
        args=["create-admin", "--username", "admin_cli", "--password", "Secret123!"]
    )

    assert result.exit_code == 0
    assert "Created admin user" in result.output

    admin = db.session.execute(
        db.select(User).where(User.username == "admin_cli")
    ).scalar_one_or_none()

    assert admin is not None
    assert admin.username == "admin_cli"
    assert admin.role == "admin"
    assert admin.password_hash != "Secret123!"
    assert admin.check_password("Secret123!") is True
    assert admin.check_password("wrong") is False


def test_create_admin_cli_refuses_duplicate_username(app):
    runner = app.test_cli_runner()

    first = runner.invoke(
        args=["create-admin", "--username", "admin_cli", "--password", "Secret123!"]
    )
    assert first.exit_code == 0

    second = runner.invoke(
        args=["create-admin", "--username", "ADMIN_CLI", "--password", "OtherPass123!"]
    )
    assert second.exit_code != 0
    assert "already exists" in second.output

    user_count = db.session.execute(db.select(db.func.count(User.id))).scalar_one()
    assert user_count == 1
